"""Read-only catalogue audit for Highlightly and WorldCup26 historical scope."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


REPORT = Path("provider-league-catalogue-audit.json")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict)]
    return []


def audit_highlightly() -> dict[str, Any]:
    key = (os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY") or "").strip()
    if not key:
        return {"status": "not_configured", "catalogue_count": None,
                "reason": "HIGHLIGHTLY_API_KEY is not configured."}
    base = os.getenv("HIGHLIGHTLY_BASE_URL", "https://soccer.highlightly.net").rstrip("/")
    session = requests.Session()
    session.headers.update({"x-rapidapi-key": key, "Accept": "application/json"})
    all_rows: list[dict[str, Any]] = []
    offset, limit, total = 0, 100, None
    plan: dict[str, Any] = {}
    rate_limit: dict[str, Any] = {}
    try:
        for _ in range(100):
            response = session.get(f"{base}/leagues",
                                   params={"limit": limit, "offset": offset},
                                   timeout=20)
            rate_limit = {
                "limit": response.headers.get("x-ratelimit-requests-limit"),
                "remaining": response.headers.get("x-ratelimit-requests-remaining"),
            }
            response.raise_for_status()
            payload = response.json()
            rows = _rows(payload)
            pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
            if not isinstance(pagination, dict) or "totalCount" not in pagination:
                raise ValueError("Highlightly league response omitted pagination.totalCount.")
            if not plan and isinstance(payload.get("plan"), dict):
                plan = payload["plan"]
            if total is None:
                total = int(pagination["totalCount"])
            all_rows.extend(rows)
            if not rows or len(all_rows) >= total:
                break
            offset += limit
        else:
            raise RuntimeError("Highlightly catalogue exceeded the 100-page safety limit.")
        countries = Counter(str(row.get("countryName") or row.get("country") or "Unknown")
                            for row in all_rows)
        seasons = sum(len(row.get("seasons", [])) for row in all_rows
                      if isinstance(row.get("seasons"), list))
        return {
            "status": "responding", "catalogue_count": len(all_rows),
            "reported_total_count": total, "country_count": len(countries),
            "season_records": seasons, "plan": plan, "rate_limit": rate_limit,
            "base_url": base,
            "competitions": [{
                "id": row.get("id"), "name": row.get("name") or row.get("leagueName"),
                "country": row.get("countryName") or row.get("country"),
                "seasons": row.get("seasons", []),
            } for row in all_rows],
            "pagination_complete": len(all_rows) >= int(total or 0),
        }
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        headers = getattr(response, "headers", {}) or {}
        return {"status": "error", "catalogue_count": None,
                "http_status": status, "reason": str(exc)[:300],
                "retry_after": headers.get("Retry-After"),
                "rate_limit": rate_limit}
    finally:
        session.close()


def audit_livescore() -> dict[str, Any]:
    """Report the documented WorldCup26 historical scope without probing generic fixtures."""
    reason = (
        "The current worldcup26.ir fork covers FIFA World Cup 2026 only (48 teams, "
        "104 matches; tournament completed 2026-07-19). Its generic /get/soccer/{league}/fixtures "
        "route returned HTTP 400 in the live audit. The documented /get/games endpoint is "
        "historical-only and requires JWT authentication."
    )
    return {
        "status": "historical_only",
        "catalogue_count": 0,
        "available_count": 0,
        "country_count": 0,
        "fresh_competition_count": 0,
        "documented_matches": 104,
        "documented_teams": 48,
        "tournament_completed_on": "2026-07-19",
        "future_fixture_eligible": False,
        "documented_historical_endpoint": "/get/games",
        "authentication_required": "JWT",
        "reason": reason,
    }


def main() -> int:
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "database_touched": False,
        "prediction_model_modified": False, "prediction_ledger_touched": False,
        "highlightly": audit_highlightly(),
        "livescore_football": audit_livescore(),
        "coverage_policy": (
            "Raw catalogue counts are not prediction-ready counts. LiveScoreFootball "
            "is historical World Cup 2026 only and is excluded from future fixtures. "
            "Highlightly account coverage is measured from its paginated authenticated catalogue."
        ),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at": report["checked_at"],
        "highlightly": {k: report["highlightly"].get(k) for k in
                        ("status", "catalogue_count", "country_count", "plan", "reason")},
        "livescore_football": {k: report["livescore_football"].get(k) for k in
                               ("status", "catalogue_count", "available_count",
                                "country_count", "fresh_competition_count", "reason")},
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
