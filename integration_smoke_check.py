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


def run_check(name: str, configured: bool, callback) -> dict[str, Any]:
    if not configured:
        return {"check": name, "status": "skipped", "reason": "credential_not_configured"}
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
        if name in {"api_football", "highlightly"}:
            variable = "APISPORTS_API_KEY" if name == "api_football" else "HIGHLIGHTLY_API_KEY"
            credential = os.getenv(variable, "")
            result["credential_format"] = {
                "length": len(credential),
                "contains_control_characters": any(ord(char) < 32 or ord(char) == 127 for char in credential),
                "has_outer_whitespace": credential != credential.strip(),
            }
        if cause is not None and name in {"api_football", "highlightly"}:
            result["cause_type"] = type(cause).__name__
            errno = getattr(cause, "errno", None)
            if isinstance(errno, int):
                result["cause_errno"] = errno
        return result


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
            lambda: _provider_probe(APIFootballClient(), "leagues"),
        ),
        run_check(
            "highlightly",
            bool(os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY")),
            lambda: _provider_probe(HighlightlyClient(), "test_connection"),
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
        "status": "fail" if failed else ("pass" if passed else "skipped"),
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
        return {
            "authenticated": True,
            "records_returned": result.get("records_returned"),
            "metadata": result.get("metadata", {}),
        }
    finally:
        close = getattr(client, "close", None)
        if close:
            close()


if __name__ == "__main__":
    sys.exit(main())
