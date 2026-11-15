"""Read-only OpenLigaDB fixture probe for 27 country-unscoped source records.

The public API is queried gently (at most one request per second). The report
stores metadata, aggregate team/fixture evidence, a bounded sample and hashes;
it does not persist raw match payloads or write to any database.
"""
from __future__ import annotations

import hashlib
import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_BASE = "https://api.openligadb.de"
INPUT_PATH = Path("reports/provider_independent_catalogue/openligadb_country_scope_candidates.json")
OUTPUT_PATH = Path("reports/provider_independent_catalogue/openligadb_country_scope_probe_latest.json")
USER_AGENT = "football-prediction-app-read-only-identity-audit/1.0"
REQUEST_TIMEOUT_SECONDS = 25
REQUEST_INTERVAL_SECONDS = 1.0
MAX_SAMPLE_FIXTURES = 8


class OpenLigaDBProbeError(RuntimeError):
    """Sanitized public API retrieval error."""


def _get_json(url: str) -> tuple[Any, str]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise OpenLigaDBProbeError(f"OpenLigaDB returned HTTP {status}.")
            raw = response.read()
    except HTTPError as exc:
        raise OpenLigaDBProbeError(f"OpenLigaDB returned HTTP {exc.code}.") from None
    except URLError as exc:
        raise OpenLigaDBProbeError(f"OpenLigaDB network request failed ({type(exc.reason).__name__}).") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OpenLigaDBProbeError("OpenLigaDB returned a non-JSON response.") from None
    return data, hashlib.sha256(raw).hexdigest()


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def select_league_metadata(
    available: Sequence[Mapping[str, Any]], league_id: int, season: int
) -> tuple[dict[str, Any] | None, str]:
    matches = [
        row for row in available
        if _int(row.get("leagueId")) == league_id and _int(row.get("leagueSeason")) == season
    ]
    if not matches:
        return None, "not_found_in_available_leagues_for_season"
    if len(matches) > 1:
        return None, "ambiguous_available_league_metadata"
    row = matches[0]
    shortcut = str(row.get("leagueShortcut") or "").strip()
    if not shortcut:
        return None, "available_league_missing_shortcut"
    sport_value = row.get("sport")
    if isinstance(sport_value, Mapping):
        sport_name = str(sport_value.get("sportName") or "").strip() or None
    else:
        sport_name = str(sport_value or "").strip() or None
    return {
        "league_id": _int(row.get("leagueId")),
        "league_name": str(row.get("leagueName") or "").strip() or None,
        "league_shortcut": shortcut,
        "league_season": _int(row.get("leagueSeason")),
        "sport": sport_name,
    }, "metadata_found"


def summarize_matches(matches: Any) -> dict[str, Any]:
    if not isinstance(matches, list):
        return {"response_shape": type(matches).__name__, "match_count": 0, "status": "unexpected_response_shape"}
    teams: set[str] = set()
    team_ids: set[int] = set()
    pairings: set[tuple[str, str]] = set()
    timezone_ids: set[str] = set()
    utc_kickoffs = 0
    local_kickoffs = 0
    id_mismatches = 0
    normalized: list[dict[str, Any]] = []
    fixture_identity_hashes: list[str] = []
    first_valid = next((row for row in matches if isinstance(row, Mapping)), {})
    expected_league_id = _int(first_valid.get("leagueId")) if isinstance(first_valid, Mapping) else None
    expected_season = _int(first_valid.get("leagueSeason")) if isinstance(first_valid, Mapping) else None

    for match in matches:
        if not isinstance(match, Mapping):
            continue
        home_obj = match.get("team1") if isinstance(match.get("team1"), Mapping) else {}
        away_obj = match.get("team2") if isinstance(match.get("team2"), Mapping) else {}
        home = str(home_obj.get("teamName") or "").strip()
        away = str(away_obj.get("teamName") or "").strip()
        if home:
            teams.add(home)
        if away:
            teams.add(away)
        for team_obj in (home_obj, away_obj):
            team_id = _int(team_obj.get("teamId"))
            if team_id is not None:
                team_ids.add(team_id)
        if home and away:
            pairings.add((home, away))
        tzid = str(match.get("timeZoneID") or "").strip()
        if tzid:
            timezone_ids.add(tzid)
        utc_value = str(match.get("matchDateTimeUTC") or "").strip()
        local_value = str(match.get("matchDateTime") or "").strip()
        if utc_value:
            utc_kickoffs += 1
            if home and away:
                home_key = " ".join(unicodedata.normalize("NFKC", home).casefold().split())
                away_key = " ".join(unicodedata.normalize("NFKC", away).casefold().split())
                identity_key = "\x1f".join((home_key, away_key, utc_value))
                fixture_identity_hashes.append(hashlib.sha256(identity_key.encode("utf-8")).hexdigest())
        elif local_value:
            local_kickoffs += 1
        match_league_id = _int(match.get("leagueId"))
        match_season = _int(match.get("leagueSeason"))
        if (
            (expected_league_id is not None and match_league_id is not None and match_league_id != expected_league_id)
            or (expected_season is not None and match_season is not None and match_season != expected_season)
        ):
            id_mismatches += 1
        normalized.append({
            "match_id": _int(match.get("matchID")),
            "kickoff_utc": utc_value or None,
            "kickoff_local": local_value or None,
            "timezone_id": tzid or None,
            "home_team": home or None,
            "away_team": away or None,
            "finished": match.get("matchIsFinished") if isinstance(match.get("matchIsFinished"), bool) else None,
            "group_name": (
                str(match.get("group", {}).get("groupName") or "").strip() or None
                if isinstance(match.get("group"), Mapping) else None
            ),
            "group_order_id": (
                _int(match.get("group", {}).get("groupOrderID"))
                if isinstance(match.get("group"), Mapping) else None
            ),
        })

    normalized.sort(key=lambda row: (row.get("kickoff_utc") or row.get("kickoff_local") or "", row.get("match_id") or 0))
    return {
        "response_shape": "array",
        "status": "matches_found" if normalized else "empty_match_list",
        "match_count": len(normalized),
        "unique_team_count": len(teams),
        "unique_team_id_count": len(team_ids),
        "team_names": sorted(teams),
        "team_ids": sorted(team_ids),
        "unique_home_away_pairings": len(pairings),
        "utc_kickoff_count": utc_kickoffs,
        "local_kickoff_only_count": local_kickoffs,
        "timezone_ids": sorted(timezone_ids),
        "league_id_or_season_mismatch_rows": id_mismatches,
        "fixture_identity_hashes": sorted(set(fixture_identity_hashes)),
        "fixture_identity_duplicate_rows": len(fixture_identity_hashes) - len(set(fixture_identity_hashes)),
        "sample_fixtures": normalized[:MAX_SAMPLE_FIXTURES],
    }


def build_probe_report(
    candidates: Mapping[str, Any],
    *,
    get_json: Callable[[str], tuple[Any, str]] = _get_json,
    sleep: Callable[[float], None] = time.sleep,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    records = candidates.get("records")
    if not isinstance(records, list):
        raise ValueError("Candidate inventory must contain a records array.")
    available, available_hash = get_json(f"{API_BASE}/getavailableleagues/2026")
    if not isinstance(available, list):
        raise OpenLigaDBProbeError("OpenLigaDB available-leagues response was not an array.")

    results: list[dict[str, Any]] = []
    fixture_identity_sets: dict[int, set[str]] = {}
    for index, source in enumerate(records):
        if not isinstance(source, Mapping):
            continue
        league_id = _int(source.get("league_id"))
        season = _int(source.get("season"))
        base = {
            "league_id": league_id,
            "source_name": source.get("source_name"),
            "source_scope_class": source.get("scope_class"),
            "candidate_country": source.get("candidate_country"),
            "prior_observation_count": source.get("prior_observation_count"),
        }
        if league_id is None or season is None:
            results.append({**base, "status": "invalid_candidate_record"})
            continue
        metadata, metadata_status = select_league_metadata(available, league_id, season)
        if metadata is None:
            results.append({**base, "status": metadata_status})
            continue
        if index:
            sleep(REQUEST_INTERVAL_SECONDS)
        shortcut = quote(metadata["league_shortcut"], safe="")
        url = f"{API_BASE}/getmatchdata/{shortcut}/{season}"
        try:
            matches, payload_hash = get_json(url)
            summary = summarize_matches(matches)
            identity_hashes = summary.pop("fixture_identity_hashes", [])
            fixture_identity_sets[league_id] = set(identity_hashes)
            summary["fixture_identity_count"] = len(identity_hashes)
            summary["fixture_identity_set_sha256"] = hashlib.sha256(
                "\n".join(identity_hashes).encode("utf-8")
            ).hexdigest()
            results.append({
                **base,
                "status": summary["status"],
                "api_metadata": metadata,
                "matchdata_url": url,
                "matchdata_sha256": payload_hash,
                "match_summary": summary,
            })
        except OpenLigaDBProbeError as exc:
            results.append({
                **base,
                "status": "request_error",
                "api_metadata": metadata,
                "error": str(exc),
            })

    exact_overlap_pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(results):
        left_id = left.get("league_id")
        if left_id not in fixture_identity_sets:
            continue
        for right in results[left_index + 1:]:
            right_id = right.get("league_id")
            if right_id not in fixture_identity_sets:
                continue
            shared = sorted(fixture_identity_sets[left_id] & fixture_identity_sets[right_id])
            if shared:
                exact_overlap_pairs.append({
                    "left_league_id": left_id,
                    "left_source_name": left.get("source_name"),
                    "right_league_id": right_id,
                    "right_source_name": right.get("source_name"),
                    "exact_fixture_overlap_count": len(shared),
                    "left_only_fixture_count": len(fixture_identity_sets[left_id] - fixture_identity_sets[right_id]),
                    "right_only_fixture_count": len(fixture_identity_sets[right_id] - fixture_identity_sets[left_id]),
                    "overlap_sample_hashes": shared[:5],
                })

    current = generated_at or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware.")
    return {
        "report_name": "openligadb_unscoped_country_scope_probe",
        "schema_version": 1,
        "generated_at_utc": current.astimezone(timezone.utc).isoformat(),
        "source_candidate_inventory": str(INPUT_PATH),
        "source_record_count": len(records),
        "available_leagues_season": 2026,
        "available_leagues_sha256": available_hash,
        "api_rate_limit_note": "OpenLigaDB documentation states a limit of 60 requests per minute; requests are spaced by at least one second.",
        "results": results,
        "fixture_identity_comparison": {
            "identity_basis": "exact normalized home team, away team and UTC kickoff; Unicode NFKC and casefold applied to team names",
            "pairs_with_exact_fixture_overlap": len(exact_overlap_pairs),
            "overlap_pairs": exact_overlap_pairs,
            "interpretation": "Exact overlaps are evidence of shared fixture observations, not automatic competition or season identity approval.",
        },
        "summary": {
            "records_probed": len(results),
            "matches_found": sum(row.get("status") == "matches_found" for row in results),
            "empty_match_lists": sum(row.get("status") == "empty_match_list" for row in results),
            "not_found_or_ambiguous": sum(
                row.get("status") in {
                    "not_found_in_available_leagues_for_season",
                    "ambiguous_available_league_metadata",
                    "available_league_missing_shortcut",
                } for row in results
            ),
            "request_errors": sum(row.get("status") == "request_error" for row in results),
        },
        "safeguards": {
            "public_api_read_only": True,
            "database_connections": 0,
            "database_writes": 0,
            "canonical_identity_writes": 0,
            "provider_link_writes": 0,
            "fixture_writes": 0,
            "prediction_writes": 0,
        },
    }


def main() -> int:
    candidates = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    report = build_probe_report(candidates)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "report_name": report["report_name"],
        "output": str(OUTPUT_PATH),
        "summary": report["summary"],
        "database_writes": report["safeguards"]["database_writes"],
        "provider_link_writes": report["safeguards"]["provider_link_writes"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
