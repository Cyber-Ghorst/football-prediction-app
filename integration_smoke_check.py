"""Optional live integration checks for configured production-like credentials.

The checks are read-only: provider probes call a small list endpoint and the
CockroachDB probe executes SELECT 1 only. No tables are created or modified.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg


def run_check(
    name: str,
    configured: bool,
    callback,
    *,
    skip_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not configured:
        return {"check": name, "status": "skipped", "reason": "credential_not_configured"}
    if skip_details:
        result = {"check": name, "status": "skipped", **skip_details}
        if name == "highlightly":
            credential = os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY", "")
            result["credential_format"] = {
                "length": len(credential),
                "trimmed_length": len(credential.strip()),
                "contains_control_characters": any(ord(char) < 32 or ord(char) == 127 for char in credential),
                "has_outer_whitespace": credential != credential.strip(),
            }
        return result
    try:
        details = callback()
        return {"check": name, "status": "pass", "details": details}
    except Exception as exc:  # Provider adapters expose credential-safe messages.
        result = {"check": name, "status": "fail", "error_type": type(exc).__name__}
        if name == "api_football" and type(exc).__name__ == "APIFootballError":
            result["safe_detail"] = str(exc)
        elif name == "highlightly" and type(exc).__name__ == "HighlightlyError":
            result["safe_detail"] = str(exc)
        cause = exc.__cause__
        credential_variables = {
            "api_football": "APISPORTS_API_KEY",
            "api_ninjas": "API_NINJAS_API_KEY",
            "highlightly": "HIGHLIGHTLY_API_KEY",
        }
        variable = credential_variables.get(name)
        if variable:
            credential = os.getenv(variable, "")
            result["credential_format"] = {
                "length": len(credential),
                "contains_control_characters": any(ord(char) < 32 or ord(char) == 127 for char in credential),
                "has_outer_whitespace": credential != credential.strip(),
            }
        if cause is not None and variable:
            result["cause_type"] = type(cause).__name__
            status = getattr(getattr(cause, "response", None), "status_code", None)
            if isinstance(status, int):
                result["http_status"] = status
            errno = getattr(cause, "errno", None)
            if isinstance(errno, int):
                result["cause_errno"] = errno
        return result


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def highlightly_use_skip_details() -> dict[str, Any] | None:
    if not (
        _enabled("FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY")
        and _enabled("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED")
    ):
        return {
            "reason": "provider_use_not_confirmed",
            "required_acknowledgements": [
                "FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY",
                "HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED",
            ],
        }
    return highlightly_refresh_cooldown_skip_details()


def api_ninjas_use_skip_details() -> dict[str, Any] | None:
    if not (
        _enabled("FREE_FIXTURE_TERMS_ACK_API_NINJAS")
        and _enabled("FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS")
    ):
        return {
            "reason": "free_plan_noncommercial_use_not_confirmed",
            "required_acknowledgements": [
                "FREE_FIXTURE_TERMS_ACK_API_NINJAS",
                "FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS",
            ],
        }
    return None


def api_football_account_probe(
    client=None, *, data_use_allowed: bool = False,
) -> dict[str, Any]:
    """Return API-Football account/quota metadata without exposing account PII."""
    if client is None:
        from api_football import APIFootballClient
        client = APIFootballClient()
    try:
        status_payload = client.status()
        status = (
            status_payload.get("response")
            if isinstance(status_payload, dict) and isinstance(status_payload.get("response"), dict)
            else status_payload
        )
        leagues = client.leagues() if data_use_allowed else None
        subscription = status.get("subscription") if isinstance(status, dict) else {}
        requests_info = status.get("requests") if isinstance(status, dict) else {}
        subscription = subscription if isinstance(subscription, dict) else {}
        requests_info = requests_info if isinstance(requests_info, dict) else {}
        return {
            "authenticated": True,
            "leagues_returned": len(leagues) if isinstance(leagues, list) else None,
            "league_catalogue_probe_status": (
                "completed" if data_use_allowed else "skipped_data_use_not_confirmed"
            ),
            "subscription_plan": subscription.get("plan"),
            "subscription_active": subscription.get("active"),
            "requests_used_today": requests_info.get("current"),
            "requests_limit_per_day": requests_info.get("limit_day"),
            "status_endpoint_quota_exempt": True,
        }
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


def highlightly_refresh_cooldown_skip_details(
    report_path: str | Path = "reports/free_fixture_provider_refresh/latest.json",
) -> dict[str, Any] | None:
    """Avoid a second live Highlightly probe while the fixture collector is in 429 cooldown."""
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    provider = (report.get("providers") or {}).get("highlightly") or {}
    if provider.get("skipped") != "refresh_cooldown":
        return None
    return {
        "reason": "provider_refresh_cooldown_active",
        "cooldown_hours": provider.get("cooldown_hours"),
        "last_successful_snapshot_at": provider.get("last_successful_snapshot_at"),
    }


def check_cockroach() -> dict[str, Any]:
    database_url = os.environ["PROVIDER_DATABASE_URL"]
    certificate = Path(__file__).resolve().with_name("root.crt")
    if not certificate.is_file():
        raise FileNotFoundError("CockroachDB CA certificate missing")
    with psycopg.connect(
        database_url,
        connect_timeout=10,
        sslmode="verify-full",
        sslrootcert=str(certificate),
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
    if result != (1,):
        raise RuntimeError("Unexpected CockroachDB response")
    return {"query": "SELECT 1", "read_only": True}


def main() -> int:
    from api_football import APIFootballClient
    from api_ninjas import APINinjasClient
    from highlightly import HighlightlyClient
    from sportmonks import SportmonksClient

    checks = [
        run_check(
            "cockroachdb",
            bool(os.getenv("PROVIDER_DATABASE_URL")),
            check_cockroach,
        ),
        run_check(
            "api_football",
            bool(os.getenv("APISPORTS_API_KEY")),
            lambda: api_football_account_probe(
                APIFootballClient(),
                data_use_allowed=_enabled("APISPORTS_DATA_USE_ALLOWED_CONFIRMED"),
            ),
        ),
        run_check(
            "api_ninjas",
            bool(os.getenv("API_NINJAS_API_KEY")),
            lambda: _provider_probe(APINinjasClient(), "test_connection"),
            skip_details=api_ninjas_use_skip_details(),
        ),
        run_check(
            "highlightly",
            bool(os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY")),
            lambda: _provider_probe(HighlightlyClient(), "test_connection"),
            skip_details=highlightly_use_skip_details(),
        ),
        run_check(
            "sportmonks",
            bool(os.getenv("SPORTMONKS_API_TOKEN") or os.getenv("SPORTMONKS_API_KEY")),
            lambda: _provider_probe(SportmonksClient(), "test_connection"),
        ),
    ]
    passed = sum(item["status"] == "pass" for item in checks)
    failed = sum(item["status"] == "fail" for item in checks)
    skipped = sum(item["status"] == "skipped" for item in checks)
    report = {
        "operation": "read_only_live_integration_check",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if failed else ("partial" if skipped else ("pass" if passed else "skipped")),
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_skipped": skipped,
        "checks": checks,
        "scope": (
            "Read-only authenticated provider list probes and CockroachDB SELECT 1. "
            "Missing credentials are reported as skipped. No schema or application data is changed."
        ),
    }
    Path("integration-smoke-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


def _provider_probe(client, method_name: str) -> dict[str, Any]:
    try:
        if method_name == "leagues":
            rows = client.leagues()
            metadata = getattr(client, "last_metadata", {})
            return {"authenticated": True, "records_returned": len(rows), "metadata": metadata}
        result = getattr(client, method_name)()
        if isinstance(result, dict):
            return {
                "authenticated": True,
                "records_returned": result.get("records_returned"),
                "metadata": result.get("metadata", {}),
            }
        return {"authenticated": bool(result), "metadata": getattr(client, "last_metadata", {})}
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


if __name__ == "__main__":
    sys.exit(main())
