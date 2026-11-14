"""Read-only raw-observation verification for Priority A competitions.

This report inspects archived future-fixture observations. It compares source
IDs, season IDs, participating teams and exact UTC kickoff values, but never
creates canonical records, provider links, fixtures or predictions.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from provider_data_storage import _connect
from provider_entity_crosswalk import normalize_entity_name

PROVIDERS = (
    "bzzoiro", "football_data_org", "openfootball",
    "openligadb", "livescore_football",
)
RESOURCE_TYPES = ("future_fixture_observations", "independent_data_observations")
QUEUE_PATH = Path("reports/provider_independent_catalogue/identity_review_queue.json")
OUTPUT_PATH = Path("reports/provider_independent_catalogue/priority_a_provider_observation_audit/latest.json")


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("display_name") or value.get("country")
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return normalize_entity_name(_text(value))


def _country(row: Mapping[str, Any]) -> str:
    raw = row.get("raw_payload")
    raw = raw if isinstance(raw, Mapping) else {}
    league = raw.get("league") if isinstance(raw.get("league"), Mapping) else {}
    return _text(
        row.get("country") or raw.get("country") or raw.get("leagueCountry")
        or raw.get("country_name") or league.get("country")
    )


def _season_label_year_evidence(value: Any) -> dict[str, Any] | None:
    """Parse season labels without mistaking calendar dates for season ranges.

    Examples: 26/27, 2026/27, 2026-27 and a standalone 2026.
    This is descriptive evidence only; it never establishes season equivalence.
    """
    label = _text(value)
    if not label or re.fullmatch(r"20\d{2}-\d{2}-\d{2}", label):
        return None

    match = re.search(r"(?<!\d)(20\d{2})\s*[/–—-]\s*(\d{2}|20\d{2})(?!\d)", label)
    if match:
        start = int(match.group(1))
        end_token = match.group(2)
        end = int(end_token) if len(end_token) == 4 else (start // 100) * 100 + int(end_token)
        if end < start:
            end += 100
        if end - start not in (0, 1):
            return None
        return {
            "label": label,
            "start_year": start,
            "end_year": end,
            "normalized_season": f"{start}/{end}",
            "format": "four_digit_start_year_range",
        }

    short_match = re.search(r"(?<!\d)(\d{2})\s*/\s*(\d{2})(?!\d)", label)
    if short_match:
        start_short, end_short = map(int, short_match.groups())
        start = 2000 + start_short if start_short <= 79 else 1900 + start_short
        end = (start // 100) * 100 + end_short
        if end < start:
            end += 100
        if end - start not in (0, 1):
            return None
        return {
            "label": label,
            "start_year": start,
            "end_year": end,
            "normalized_season": f"{start}/{end}",
            "format": "two_digit_season_range",
        }

    if re.fullmatch(r"20\d{2}", label):
        year = int(label)
        return {
            "label": label,
            "start_year": year,
            "end_year": None,
            "normalized_season": str(year),
            "format": "calendar_year",
        }
    return None


def _kickoff(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _observations(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = snapshot.get("payload")
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("observations")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def load_recent_snapshots(database_url: str, *, per_provider_limit: int = 5) -> list[dict[str, Any]]:
    """Read recent source snapshots in a transaction explicitly marked READ ONLY."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if isinstance(per_provider_limit, bool) or not isinstance(per_provider_limit, int) or not 1 <= per_provider_limit <= 20:
        raise ValueError("per_provider_limit must be from 1 through 20.")
    sql = """
        SELECT snapshot_id, provider, resource_type, request_params, source_ids,
               payload, retrieved_at, expires_at, payload_sha256
        FROM (
            SELECT snapshot_id, provider, resource_type, request_params, source_ids,
                   payload, retrieved_at, expires_at, payload_sha256,
                   ROW_NUMBER() OVER (
                       PARTITION BY provider, resource_type
                       ORDER BY retrieved_at DESC, snapshot_id DESC
                   ) AS snapshot_rank
            FROM provider_api_snapshots
            WHERE provider = ANY(%s)
              AND resource_type = ANY(%s)
        ) recent
        WHERE snapshot_rank <= %s
        ORDER BY provider, resource_type, retrieved_at DESC
    """
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(sql, (list(PROVIDERS), list(RESOURCE_TYPES), per_provider_limit))
            rows = cursor.fetchall()
    names = (
        "snapshot_id", "provider", "resource_type", "request_params", "source_ids",
        "payload", "retrieved_at", "expires_at", "payload_sha256",
    )
    return [dict(zip(names, row)) for row in rows]


def build_priority_a_observation_audit(
    queue: Mapping[str, Any],
    snapshots: Sequence[Mapping[str, Any]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Compare provider source identities and exact fixture overlap for Priority A."""
    current = generated_at or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware.")

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    overlap: dict[tuple[str, str, str, str, str, str], set[str]] = defaultdict(set)
    source_snapshot_counts: Counter[tuple[str, str]] = Counter()
    total_observations = 0

    for snapshot in snapshots:
        provider = _text(snapshot.get("provider")).casefold()
        if provider not in PROVIDERS:
            continue
        source_snapshot_counts[(provider, _text(snapshot.get("resource_type")))] += 1
        for row in _observations(snapshot):
            total_observations += 1
            comp_id = _text(row.get("competition_key"))
            season_id = _text(row.get("season_key"))
            if not comp_id or not season_id:
                continue
            key = (provider, comp_id, season_id)
            record = grouped.setdefault(key, {
                "provider": provider,
                "provider_competition_id": comp_id,
                "provider_season_id": f"{comp_id}::{season_id}",
                "season_key": season_id,
                "competition_names": set(),
                "season_names": set(),
                "countries": set(),
                "home_teams": set(),
                "away_teams": set(),
                "eligible_observations": 0,
                "all_observations": 0,
                "valid_utc_kickoffs": 0,
                "fixture_ids": set(),
                "statuses": Counter(),
            })
            record["all_observations"] += 1
            name = _text(row.get("competition_name"))
            season_name = _text(row.get("season_name"))
            country = _country(row)
            home = _text(row.get("home_team_name"))
            away = _text(row.get("away_team_name"))
            kickoff = _kickoff(row.get("kickoff_utc"))
            if name:
                record["competition_names"].add(name)
            if season_name:
                record["season_names"].add(season_name)
            if country:
                record["countries"].add(country)
            if home:
                record["home_teams"].add(home)
            if away:
                record["away_teams"].add(away)
            if row.get("provider_fixture_id"):
                record["fixture_ids"].add(_text(row.get("provider_fixture_id")))
            record["statuses"][_text(row.get("status")).casefold() or "unknown"] += 1
            eligible = row.get("eligible_for_review") is True
            if eligible:
                record["eligible_observations"] += 1
            if kickoff:
                record["valid_utc_kickoffs"] += 1
            if eligible and kickoff and country and name and home and away:
                signature = (
                    _norm(country), _norm(name), kickoff, _norm(home), _norm(away), "exact"
                )
                overlap[signature].add(provider)

    priority_a = [
        entry for entry in queue.get("entries", [])
        if isinstance(entry, Mapping) and entry.get("priority") == "A"
    ]
    entries = []
    for entry in priority_a:
        entry_id = _text(entry.get("catalogue_entry_id"))
        expected_name = _text((entry.get("display_names") or [""])[0])
        expected_country = _text((entry.get("countries") or [""])[0])
        source_rows = []
        for source in entry.get("source_records", []):
            if not isinstance(source, Mapping):
                continue
            provider = _text(source.get("provider")).casefold()
            comp_id = _text(source.get("provider_competition_id"))
            season_rows = source.get("seasons") or []
            if not season_rows:
                source_rows.append({
                    "provider": provider,
                    "provider_competition_id": comp_id,
                    "provider_season_id": None,
                    "status": "no_season_record_in_review_queue",
                })
                continue
            for season in season_rows:
                season_link_id = _text(season.get("provider_season_id"))
                season_key = season_link_id.split("::", 1)[1] if "::" in season_link_id else ""
                record = grouped.get((provider, comp_id, season_key))
                if record is None:
                    source_rows.append({
                        "provider": provider,
                        "provider_competition_id": comp_id,
                        "provider_season_id": season_link_id or None,
                        "status": "no_matching_raw_observations_in_selected_snapshots",
                        "queue_observation_count": season.get("observation_count", 0),
                    })
                    continue
                countries = sorted(record["countries"])
                names = sorted(record["competition_names"])
                source_rows.append({
                    "provider": provider,
                    "provider_competition_id": comp_id,
                    "provider_season_id": season_link_id,
                    "status": "raw_observations_found",
                    "raw_observation_count": record["all_observations"],
                    "eligible_observation_count": record["eligible_observations"],
                    "unique_home_teams": len(record["home_teams"]),
                    "unique_away_teams": len(record["away_teams"]),
                    "unique_teams_combined": len(record["home_teams"] | record["away_teams"]),
                    "unique_provider_fixture_ids": len(record["fixture_ids"]),
                    "valid_timezone_aware_kickoffs": record["valid_utc_kickoffs"],
                    "competition_names": names,
                    "season_names": sorted(record["season_names"]),
                    "season_label_year_evidence": [
                        evidence for label in sorted(record["season_names"])
                        if (evidence := _season_label_year_evidence(label)) is not None
                    ],
                    "countries": countries,
                    "competition_name_matches_queue": _norm(expected_name) in {_norm(v) for v in names},
                    "country_matches_queue": _norm(expected_country) in {_norm(v) for v in countries},
                    "status_counts": dict(sorted(record["statuses"].items())),
                })
        entries.append({
            "catalogue_entry_id": entry_id,
            "competition": expected_name,
            "country": expected_country,
            "providers": list(entry.get("providers") or []),
            "provider_sources": source_rows,
            "exact_cross_provider_fixture_overlap_count": sum(
                1 for sig, providers in overlap.items()
                if len(providers) >= 2 and sig[0] == _norm(expected_country)
                and sig[1] == _norm(expected_name)
            ),
            "identity_decision": "not_approved",
        })

    overlap_rows = [
        {
            "country_key": sig[0],
            "competition_key": sig[1],
            "kickoff_utc": sig[2],
            "home_team_key": sig[3],
            "away_team_key": sig[4],
            "providers": sorted(providers),
            "provider_count": len(providers),
        }
        for sig, providers in sorted(overlap.items())
        if len(providers) >= 2
    ]
    return {
        "report_name": "priority_a_provider_observation_audit",
        "generated_at_utc": current.astimezone(timezone.utc).isoformat(),
        "source_queue": "reports/provider_independent_catalogue/identity_review_queue.json",
        "snapshot_limit_per_provider_resource": 5,
        "providers_checked": list(PROVIDERS),
        "snapshot_counts_by_provider_resource": {
            f"{provider}:{resource}": count
            for (provider, resource), count in sorted(source_snapshot_counts.items())
        },
        "total_raw_observations_examined": total_observations,
        "priority_a_entry_count": len(entries),
        "entries": entries,
        "exact_cross_provider_fixture_overlaps": overlap_rows,
        "exact_overlap_count": len(overlap_rows),
        "interpretation": (
            "An exact team-pair and UTC-kickoff overlap is strong fixture-level corroboration, "
            "but does not alone approve competition or season identity. Missing observations "
            "in the selected recent snapshots mean not observed in this audit window, not that "
            "the provider lacks the competition."
        ),
        "safeguards": {
            "database_transaction_read_only": True,
            "canonical_competition_writes": 0,
            "canonical_season_writes": 0,
            "provider_link_writes": 0,
            "fixture_writes": 0,
            "prediction_ledger_writes": 0,
            "automatic_identity_approvals": 0,
            "future_fixture_routes_enabled": 0,
        },
    }


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "")
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    report = build_priority_a_observation_audit(queue, load_recent_snapshots(database_url))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": report["report_name"],
        "output": str(OUTPUT_PATH),
        "priority_a_entries": report["priority_a_entry_count"],
        "observations_examined": report["total_raw_observations_examined"],
        "exact_fixture_overlaps": report["exact_overlap_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
