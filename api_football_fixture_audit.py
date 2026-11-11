"""Read-only API-Football v3 audit for upcoming fixtures.

This audit checks the configured APISPORTS_API_KEY without writing to either
football database or the prediction ledger.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

from api_football import APIFootballClient, APIFootballError


SCHEDULED_STATUSES = {"NS", "PST"}


def _utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_api_football_fixture_audit(
    *,
    client_factory: Callable[[], Any] = APIFootballClient,
    now: datetime | None = None,
    window_days: int = 7,
    daily_target: int = 90,
    max_pages: int = 20,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    if not 1 <= int(window_days) <= 14:
        raise ValueError("window_days must be between 1 and 14.")
    if int(daily_target) < 1:
        raise ValueError("daily_target must be positive.")

    current = current.astimezone(timezone.utc)
    window_end = current + timedelta(days=window_days)
    first_date = current.date()
    last_date = window_end.date()
    calendar_dates = [
        (first_date + timedelta(days=offset)).isoformat()
        for offset in range((last_date - first_date).days + 1)
    ]
    target_dates = calendar_dates[:window_days]
    partial_boundary_dates = calendar_dates[window_days:]
    daily_counts = {day: 0 for day in calendar_dates}
    rejected = Counter()
    competition_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    seen_fixture_ids: set[str] = set()

    report: dict[str, Any] = {
        "provider": "api_football_v3",
        "generated_at_utc": current.isoformat(),
        "window_start_utc": current.isoformat(),
        "window_end_utc": window_end.isoformat(),
        "window_days": window_days,
        "target_dates_utc": target_dates,
        "partial_boundary_days_utc": partial_boundary_dates,
        "daily_target": daily_target,
        "daily_fixture_counts_utc": daily_counts,
        "daily_target_shortfalls_utc": {},
        "target_shortfall_total": daily_target * len(target_dates),
        "target_met": False,
        "future_fixture_count": 0,
        "prediction_ready_fixture_count": 0,
        "duplicate_fixture_ids": 0,
        "rejected_fixture_counts": {},
        "competition_counts": {},
        "sample_fixtures": [],
        "requests_made": 0,
        "requests_limit_daily": None,
        "requests_used_before": None,
        "requests_remaining_before": None,
        "subscription_plan": None,
        "status": "not_run",
        "errors": [],
        "writes": {
            "canonical_fixture_writes": 0,
            "temporary_fixture_inserts": 0,
            "prediction_ledger_writes": 0,
        },
    }

    try:
        with client_factory() as client:
            account = client.status()
            requests_info = account.get("requests") or {}
            limit = _safe_int(requests_info.get("limit_day") or requests_info.get("limit"))
            used = _safe_int(requests_info.get("current"))
            remaining = (
                max(0, limit - used)
                if limit is not None and used is not None else
                _safe_int(requests_info.get("remaining"))
            )
            subscription = account.get("subscription") or {}
            report["requests_limit_daily"] = limit
            report["requests_used_before"] = used
            report["requests_remaining_before"] = remaining
            report["subscription_plan"] = subscription.get("plan")

            if remaining is not None and remaining < 1:
                report["status"] = "quota_exhausted"
                report["errors"].append("API-Football daily request quota is exhausted.")
                return report

            rows = client.fixtures_between(
                first_date.isoformat(),
                last_date.isoformat(),
                timezone="UTC",
                max_pages=max_pages,
            )
            report["requests_made"] = int(
                getattr(client, "last_fixture_request_count", 0) or 0
            )

            for row in rows:
                fixture = row.get("fixture") or {}
                league = row.get("league") or {}
                teams = row.get("teams") or {}
                home = teams.get("home") or {}
                away = teams.get("away") or {}
                kickoff = _utc_datetime(fixture.get("date"))
                status = (fixture.get("status") or {}).get("short")
                fixture_id = fixture.get("id")

                if kickoff is None:
                    rejected["missing_timezone_aware_kickoff"] += 1
                    continue
                if kickoff < current or kickoff > window_end:
                    rejected["outside_rolling_window"] += 1
                    continue
                if status == "TBD":
                    rejected["kickoff_time_not_confirmed"] += 1
                    continue
                if status not in SCHEDULED_STATUSES:
                    rejected["not_scheduled"] += 1
                    continue

                report["future_fixture_count"] += 1
                fixture_key = str(fixture_id or "").strip()
                if not fixture_key:
                    rejected["missing_fixture_id"] += 1
                    continue
                if fixture_key in seen_fixture_ids:
                    report["duplicate_fixture_ids"] += 1
                    rejected["duplicate_fixture_id"] += 1
                    continue
                seen_fixture_ids.add(fixture_key)

                league_id = league.get("id")
                season = league.get("season")
                home_id = home.get("id")
                away_id = away.get("id")
                if not all((league_id, season, home_id, away_id, league.get("name"), home.get("name"), away.get("name"))):
                    rejected["missing_competition_season_or_team_identity"] += 1
                    continue

                day = kickoff.date().isoformat()
                daily_counts[day] = daily_counts.get(day, 0) + 1
                report["prediction_ready_fixture_count"] += 1
                competition_key = f"{league_id}:{league.get('name')}"
                competition_counts[competition_key] += 1
                if len(samples) < 20:
                    samples.append({
                        "fixture_id": fixture_key,
                        "kickoff_utc": kickoff.isoformat(),
                        "status": status,
                        "league_id": league_id,
                        "league_name": league.get("name"),
                        "league_country": league.get("country"),
                        "season": season,
                        "home_team_id": home_id,
                        "home_team": home.get("name"),
                        "away_team_id": away_id,
                        "away_team": away.get("name"),
                    })

    except (APIFootballError, OSError, ValueError, TypeError) as exc:
        report["errors"].append(str(exc))
        report["status"] = "error"
    else:
        report["daily_target_shortfalls_utc"] = {
            day: max(0, daily_target - daily_counts[day])
            for day in target_dates
        }
        report["target_shortfall_total"] = sum(
            report["daily_target_shortfalls_utc"].values()
        )
        report["target_met"] = all(
            daily_counts[day] >= daily_target for day in target_dates
        )
        report["rejected_fixture_counts"] = dict(rejected)
        report["competition_counts"] = dict(competition_counts)
        report["sample_fixtures"] = samples
        report["status"] = (
            "ok" if report["prediction_ready_fixture_count"] else "no_future_fixtures"
        )
    return report


def main() -> int:
    report = build_api_football_fixture_audit()
    output = Path(os.getenv(
        "API_FOOTBALL_FIXTURE_AUDIT_PATH",
        "reports/api_football_fixture_audit/latest.json",
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, indent=2, sort_keys=True, default=str)
    output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
