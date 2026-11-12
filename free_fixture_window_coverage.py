"""Seven-day coverage audit across archived future-fixture providers.

This report measures potential fixture supply only. It does not approve
crosswalks, write canonical fixtures, stage fixtures for prediction, or touch
the prediction ledger.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Mapping

from provider_data_storage import load_provider_observation_snapshots
from provider_entity_crosswalk import normalize_entity_name

PROVIDERS = (
    "openligadb",
    "openfootball",
    "open_matchday",
    "livescore_football",
    "bzzoiro",
    "highlightly",
    "api_ninjas",
)
SCHEDULED_STATUSES = {"scheduled", "upcoming", "not started", "notstarted", "ns", "fixture"}


def _utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _display_country(observation: Mapping[str, Any]) -> str:
    raw = observation.get("raw_payload")
    if not isinstance(raw, Mapping):
        raw = {}
    league = raw.get("league") if isinstance(raw.get("league"), Mapping) else {}
    value = (
        raw.get("country") or raw.get("leagueCountry") or raw.get("country_name")
        or league.get("country") or observation.get("country")
    )
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("display_name") or value.get("country")
    return str(value or "").strip()


def _observation_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = snapshot.get("payload")
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("observations")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _exact_cross_provider_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    country = normalize_entity_name(row.get("country") or "")
    competition = normalize_entity_name(row.get("competition") or "")
    season = normalize_entity_name(row.get("season") or "")
    home = normalize_entity_name(row.get("home_team") or "")
    away = normalize_entity_name(row.get("away_team") or "")
    kickoff = str(row.get("kickoff_utc") or "")
    if country and competition and season and home and away and kickoff:
        return ("exact", country, competition, season, home, away, kickoff)
    # Without a country, do not deduplicate across providers. Keep provider IDs
    # as the only safe identity boundary for this report.
    return ("provider", row.get("provider"), row.get("provider_fixture_id"))


def build_window_coverage_report(
    snapshots_by_provider: Mapping[str, list[Mapping[str, Any]]],
    *,
    now: datetime | None = None,
    window_days: int = 7,
    daily_target: int = 20,
    minimum_daily_target: int = 10,
    stretch_daily_target: int = 30,
    max_highlights: int = 15,
    max_age_hours: int = 24,
    highlightly_use_allowed: bool = False,
    api_ninjas_noncommercial_confirmed: bool = False,
    open_matchday_noncommercial_confirmed: bool = False,
) -> dict[str, Any]:
    current = _utc_datetime(now or datetime.now(timezone.utc))
    if current is None:
        raise ValueError("now must be timezone-aware.")
    if isinstance(window_days, bool) or not isinstance(window_days, int) or not 1 <= window_days <= 14:
        raise ValueError("window_days must be an integer from 1 through 14.")
    if isinstance(daily_target, bool) or not isinstance(daily_target, int) or daily_target < 1:
        raise ValueError("daily_target must be a positive integer.")
    for label, value in (("minimum_daily_target", minimum_daily_target), ("stretch_daily_target", stretch_daily_target)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer.")
    # Measure the next N complete UTC calendar days. The current UTC date is
    # a partial day at report time and must not be held to a full-day target.
    window_end = current + timedelta(days=window_days + 1)
    calendar_days = [
        (current.date() + timedelta(days=offset)).isoformat()
        for offset in range((window_end.date() - current.date()).days + 1)
    ]

    latest_by_provider_id: dict[tuple[str, str], dict[str, Any]] = {}
    provider_snapshot_counts: dict[str, int] = {}
    source_observation_count = 0
    stale_snapshot_count = 0
    rejected_observation_counts: Counter[str] = Counter()
    rejected_by_provider: dict[str, Counter[str]] = {provider: Counter() for provider in PROVIDERS}
    excluded_provider_snapshot_counts: dict[str, int] = {}

    def reject(provider: str, reason: str) -> None:
        rejected_observation_counts[reason] += 1
        rejected_by_provider[provider][reason] += 1

    for provider in PROVIDERS:
        snapshots = list(snapshots_by_provider.get(provider) or [])
        if provider == "highlightly" and not highlightly_use_allowed:
            provider_snapshot_counts[provider] = 0
            excluded_provider_snapshot_counts[provider] = len(snapshots)
            continue
        if provider == "api_ninjas" and not api_ninjas_noncommercial_confirmed:
            provider_snapshot_counts[provider] = 0
            excluded_provider_snapshot_counts[provider] = len(snapshots)
            continue
        if provider == "open_matchday" and not open_matchday_noncommercial_confirmed:
            provider_snapshot_counts[provider] = 0
            excluded_provider_snapshot_counts[provider] = len(snapshots)
            continue
        provider_snapshot_counts[provider] = len(snapshots)
        for snapshot in snapshots:
            retrieved = _utc_datetime(snapshot.get("retrieved_at"))
            payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), Mapping) else {}
            if retrieved is None:
                retrieved = _utc_datetime(payload.get("retrieved_at"))
            if (
                retrieved is None
                or retrieved > current + timedelta(minutes=5)
                or current - retrieved > timedelta(hours=max_age_hours)
            ):
                stale_snapshot_count += 1
                continue
            for observation in _observation_rows(snapshot):
                source_observation_count += 1
                if observation.get("eligible_for_review") is not True:
                    reject(provider, str(
                        observation.get("exclusion_reason") or "not_eligible_for_review"
                    ))
                    continue
                fixture_id = str(observation.get("provider_fixture_id") or "").strip()
                if not fixture_id:
                    reject(provider, "missing_provider_fixture_id")
                    continue
                status = str(observation.get("status") or "").strip().casefold().replace("_", " ")
                if status not in SCHEDULED_STATUSES:
                    reject(provider, "not_scheduled")
                    continue
                kickoff = _utc_datetime(observation.get("kickoff_utc"))
                fetched = _utc_datetime(observation.get("fetched_at"))
                if kickoff is None or fetched is None:
                    reject(provider, "missing_timezone_aware_timestamp")
                    continue
                if fetched > current + timedelta(minutes=5):
                    reject(provider, "future_provider_timestamp")
                    continue
                if kickoff <= current or kickoff > window_end:
                    reject(provider, "kickoff_outside_window")
                    continue
                home = str(observation.get("home_team_name") or "").strip()
                away = str(observation.get("away_team_name") or "").strip()
                competition = str(observation.get("competition_name") or "").strip()
                season = str(observation.get("season_name") or observation.get("season_key") or "").strip()
                if not all((home, away, competition, season)):
                    reject(provider, "missing_fixture_identity")
                    continue
                record = {
                    "provider": provider,
                    "provider_fixture_id": fixture_id,
                    "kickoff_utc": kickoff.isoformat(timespec="seconds"),
                    "date_utc": kickoff.date().isoformat(),
                    "country": _display_country(observation),
                    "competition": competition,
                    "season": season,
                    "home_team": home,
                    "away_team": away,
                    "fetched_at": fetched,
                }
                key = (provider, fixture_id)
                previous = latest_by_provider_id.get(key)
                if previous is None or record["fetched_at"] >= previous["fetched_at"]:
                    latest_by_provider_id[key] = record

    provider_rows = list(latest_by_provider_id.values())
    provider_rows.sort(key=lambda row: (row["kickoff_utc"], row["provider"], row["provider_fixture_id"]))

    unique_by_exact_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in provider_rows:
        key = _exact_cross_provider_key(row)
        previous = unique_by_exact_key.get(key)
        if previous is None or row["fetched_at"] > previous["fetched_at"]:
            unique_by_exact_key[key] = row
    unique_rows = list(unique_by_exact_key.values())

    daily_counts = {day: 0 for day in calendar_days}
    daily_by_provider: dict[str, dict[str, int]] = {
        provider: {day: 0 for day in calendar_days} for provider in PROVIDERS
    }
    competition_counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in provider_rows:
        daily_by_provider[row["provider"]][row["date_utc"]] += 1
        competition_counts[(
            row["provider"], row["country"], row["competition"], row["season"]
        )] += 1
    for row in unique_rows:
        daily_counts[row["date_utc"]] += 1

    # The reporting window includes the current partial UTC date, the next N
    # complete UTC dates, and a final partial boundary date. Keep both partial
    # dates visible, but apply daily targets only to the N complete dates.
    target_days = calendar_days[1:window_days + 1]
    partial_boundary_days = [calendar_days[0], *calendar_days[window_days + 1:]]
    shortfalls = {
        day: max(0, daily_target - daily_counts[day])
        for day in target_days
    }
    minimum_shortfalls = {
        day: max(0, minimum_daily_target - daily_counts[day])
        for day in target_days
    }
    stretch_shortfalls = {
        day: max(0, stretch_daily_target - daily_counts[day])
        for day in target_days
    }
    competition_summary = [
        {
            "provider": provider,
            "country": country or None,
            "competition": competition,
            "season": season,
            "fixtures_in_window": count,
        }
        for (provider, country, competition, season), count in competition_counts.most_common(100)
    ]
    total_target = daily_target * len(target_days)
    total_unique = len(unique_rows)
    cross_provider_duplicates = max(0, len(provider_rows) - total_unique)

    return {
        "report_name": "free_fixture_window_coverage",
        "generated_at_utc": current.isoformat(),
        "window_start_utc": current.isoformat(),
        "window_end_utc": window_end.isoformat(),
        "window_days": window_days,
        "calendar_days_in_window": len(calendar_days),
        "target_days_in_window": len(target_days),
        "target_dates_utc": target_days,
        "partial_boundary_days_utc": {
            day: daily_counts[day] for day in partial_boundary_days
        },
        "daily_target": daily_target,
        "minimum_daily_target": minimum_daily_target,
        "stretch_daily_target": stretch_daily_target,
        "minimum_target_fixtures_in_window": minimum_daily_target * len(target_days),
        "stretch_target_fixtures_in_window": stretch_daily_target * len(target_days),
        "target_fixtures_in_window": total_target,
        "max_highlights": max_highlights,
        "provider_snapshot_counts": provider_snapshot_counts,
        "excluded_provider_snapshot_counts_by_terms": excluded_provider_snapshot_counts,
        "providers_excluded_by_terms": [
            provider for provider, allowed in (
                ("highlightly", highlightly_use_allowed),
                ("api_ninjas", api_ninjas_noncommercial_confirmed),
                ("open_matchday", open_matchday_noncommercial_confirmed),
            ) if not allowed
        ],
        "source_observations_loaded": source_observation_count,
        "fresh_provider_fixture_records_in_window": len(provider_rows),
        "unique_fixtures_in_window": total_unique,
        "exact_identity_duplicates_removed": cross_provider_duplicates,
        "stale_snapshots_skipped": stale_snapshot_count,
        "rejected_observation_counts": dict(rejected_observation_counts),
        "rejected_observation_counts_by_provider": {
            provider: dict(counts) for provider, counts in rejected_by_provider.items()
            if counts
        },
        "daily_unique_fixture_counts_utc": daily_counts,
        "daily_counts_by_provider_utc": daily_by_provider,
        "daily_target_shortfalls_utc": shortfalls,
        "minimum_target_shortfalls_utc": minimum_shortfalls,
        "stretch_target_shortfalls_utc": stretch_shortfalls,
        "target_met_by_day": {
            day: daily_counts[day] >= daily_target for day in target_days
        },
        "minimum_target_met_by_day": {
            day: daily_counts[day] >= minimum_daily_target for day in target_days
        },
        "stretch_target_met_by_day": {
            day: daily_counts[day] >= stretch_daily_target for day in target_days
        },
        "target_shortfall_total": sum(shortfalls.values()),
        "minimum_target_shortfall_total": sum(minimum_shortfalls.values()),
        "stretch_target_shortfall_total": sum(stretch_shortfalls.values()),
        "minimum_target_met": all(daily_counts[day] >= minimum_daily_target for day in target_days),
        "stretch_target_met": all(daily_counts[day] >= stretch_daily_target for day in target_days),
        "target_met": all(daily_counts[day] >= daily_target for day in target_days),
        "competition_summary": competition_summary,
        "identity_policy": (
            "Cross-provider deduplication requires exact normalized country, competition, "
            "season, home team, away team and UTC kickoff. Without country, records remain "
            "provider-scoped. No fuzzy name matching is used."
        ),
        "canonical_fixture_writes": 0,
        "temporary_fixture_staging_writes": 0,
        "prediction_ledger_writes": 0,
    }


def build_free_fixture_window_coverage(
    database_url: str,
    *,
    now: datetime | None = None,
    window_days: int = 7,
    daily_target: int = 20,
    minimum_daily_target: int = 10,
    stretch_daily_target: int = 30,
    max_highlights: int = 15,
    max_age_hours: int = 24,
    snapshot_limit: int = 5,
    highlightly_use_allowed: bool = False,
    api_ninjas_noncommercial_confirmed: bool = False,
    open_matchday_noncommercial_confirmed: bool = False,
) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    snapshots_by_provider = {}
    for provider in PROVIDERS:
        if provider == "highlightly" and not highlightly_use_allowed:
            snapshots_by_provider[provider] = []
        elif provider == "api_ninjas" and not api_ninjas_noncommercial_confirmed:
            snapshots_by_provider[provider] = []
        elif provider == "open_matchday" and not open_matchday_noncommercial_confirmed:
            snapshots_by_provider[provider] = []
        else:
            snapshots_by_provider[provider] = load_provider_observation_snapshots(
                database_url, provider=provider, limit=snapshot_limit,
            )
    return build_window_coverage_report(
        snapshots_by_provider, now=now, window_days=window_days,
        daily_target=daily_target, minimum_daily_target=minimum_daily_target,
        stretch_daily_target=stretch_daily_target, max_highlights=max_highlights,
        max_age_hours=max_age_hours,
        highlightly_use_allowed=highlightly_use_allowed,
        api_ninjas_noncommercial_confirmed=api_ninjas_noncommercial_confirmed,
        open_matchday_noncommercial_confirmed=open_matchday_noncommercial_confirmed,
    )


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL") or os.getenv("COCKROACHDB_URL")
    report = build_free_fixture_window_coverage(
        database_url or "",
        window_days=int(os.getenv("FREE_FIXTURE_WINDOW_DAYS", "7")),
        daily_target=int(os.getenv("FREE_FIXTURE_DAILY_TARGET", "20")),
        minimum_daily_target=int(os.getenv("FREE_FIXTURE_MIN_DAILY_TARGET", "10")),
        stretch_daily_target=int(os.getenv("FREE_FIXTURE_STRETCH_DAILY_TARGET", "30")),
        max_highlights=int(os.getenv("FREE_FIXTURE_MAX_HIGHLIGHTS", "15")),
        max_age_hours=int(os.getenv("FREE_FIXTURE_WINDOW_MAX_AGE_HOURS", "24")),
        snapshot_limit=int(os.getenv("FREE_FIXTURE_WINDOW_SNAPSHOT_LIMIT", "5")),
        highlightly_use_allowed=(
            os.getenv("FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY", "").casefold() in {"1", "true", "yes", "on"}
            and os.getenv("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED", "").casefold() in {"1", "true", "yes", "on"}
        ),
        api_ninjas_noncommercial_confirmed=(
            os.getenv("FREE_FIXTURE_TERMS_ACK_API_NINJAS", "").casefold() in {"1", "true", "yes", "on"}
            and os.getenv("FREE_FIXTURE_NONCOMMERCIAL_ACK_API_NINJAS", "").casefold() in {"1", "true", "yes", "on"}
        ),
        open_matchday_noncommercial_confirmed=(
            os.getenv("FREE_FIXTURE_TERMS_ACK_OPEN_MATCHDAY", "").casefold() in {"1", "true", "yes", "on"}
            and os.getenv("FREE_FIXTURE_NONCOMMERCIAL_ACK_OPEN_MATCHDAY", "").casefold() in {"1", "true", "yes", "on"}
        ),
    )
    print(json.dumps(report, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
