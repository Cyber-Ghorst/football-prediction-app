"""Optional independent corroboration of Sportmonks recent results.

This module is deliberately diagnostic: it never mutates Layer 2 profiles or
prediction inputs. Only exact competition/season/team/kickoff matches join.
Provider observations retain namespaced IDs and field-level conflicts.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import time
from typing import Any, Mapping

from canonical_data import (
    canonicalize_api_ninjas_match,
    canonicalize_highlightly_match,
    match_identity,
)
from competition_crosswalk import normalize_competition_name, normalize_country
from multi_source_reconciliation import reconcile_match_records
from provider_core import normalize_team_name


# Provider-specific identity aliases are keyed by both exact display name and
# reviewed provider team ID. Display names and namespaced IDs remain unchanged.
_HIGHLIGHTLY_TEAM_IDENTITY_ALIASES = {
    ("brighton", "44185"): "brighton & hove albion",
}


def _team_identity_key(team: Mapping[str, Any] | None) -> str:
    team = team or {}
    return str(team.get("normalized_name") or normalize_team_name(team.get("name", "")))


def _apply_highlightly_team_identity_aliases(record: dict[str, Any]) -> None:
    for side in ("home", "away"):
        team = record.get(side) or {}
        name_key = normalize_team_name(team.get("name", ""))
        source_id = str((team.get("source_ids") or {}).get("highlightly") or "")
        alias = _HIGHLIGHTLY_TEAM_IDENTITY_ALIASES.get((name_key, source_id))
        if alias:
            team["normalized_name"] = normalize_team_name(alias)
        record[side] = team


def competition_key(name: str, country: str | None = None) -> str:
    """Build the same conservative key for the selected competition in each feed."""
    return "|".join((normalize_competition_name(name), normalize_country(country or "")))


def _participants(fixture: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    home = away = None
    rows = fixture.get("participants") or []
    for row in rows:
        location = str((row.get("meta") or {}).get("location") or "").casefold()
        if location == "home":
            home = row
        elif location == "away":
            away = row
    return home, away


def _current_scores(fixture: Mapping[str, Any], home_id: Any, away_id: Any) -> tuple[int | None, int | None]:
    rows = fixture.get("scores") or []
    current = [row for row in rows if str(row.get("description") or "").casefold() == "current"]
    values: dict[str, int] = {}
    for row in current or rows:
        score = row.get("score") or {}
        goals = score.get("goals") if isinstance(score, Mapping) else None
        participant_id = row.get("participant_id")
        if participant_id is None or goals is None:
            continue
        try:
            values[str(participant_id)] = int(goals)
        except (TypeError, ValueError):
            continue
    return values.get(str(home_id)), values.get(str(away_id))


def canonicalize_sportmonks_fixture(
    fixture: Mapping[str, Any], *, competition: str, country: str | None, season: int
) -> dict[str, Any] | None:
    """Normalize a Sportmonks fixture for comparison; unknown fields stay unknown."""
    home, away = _participants(fixture)
    if not home or not away or not home.get("name") or not away.get("name"):
        return None
    kickoff = fixture.get("starting_at")
    if not kickoff:
        return None
    home_score, away_score = _current_scores(fixture, home.get("id"), away.get("id"))
    state = fixture.get("state") or {}
    label = str(state.get("short_name") or state.get("name") or "").casefold()
    state_id = fixture.get("state_id")
    if str(state_id) in {"5", "7", "8"} or any(x in label for x in ("finished", "full time", "after extra", "after penalties")):
        status = "finished"
    elif any(x in label for x in ("live", "in play", "half time", "1st half", "2nd half", "extra time", "penalty")):
        status = "live"
    elif label in {"ns", "tbd", "not started", "scheduled"} or any(x in label for x in ("not started", "scheduled", "to be played")):
        status = "scheduled"
    else:
        status = "unknown"
    return {
        "competition_key": competition_key(competition, country),
        "season": int(season),
        "kickoff_utc": str(kickoff),
        "home": {"name": str(home["name"]), "source_ids": {"sportmonks": str(home.get("id") or "")}},
        "away": {"name": str(away["name"]), "source_ids": {"sportmonks": str(away.get("id") or "")}},
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "source_ids": {"sportmonks": str(fixture.get("id") or "")},
        "source": "sportmonks",
        "raw_source_updated_at": fixture.get("updated_at") or fixture.get("updatedAt"),
    }


def _api_ninjas_league_slug(client: Any, competition: str) -> str | None:
    target = normalize_competition_name(competition)
    matches = [
        row for row in client.LEAGUES
        if normalize_competition_name(row.get("name")) == target
    ]
    return str(matches[0]["id"]) if len(matches) == 1 else None


def _collect_api_ninjas_records(
    *,
    client: Any,
    competition: str,
    season: int,
    home_team_name: str,
    away_team_name: str,
    competition_key_value: str,
) -> dict[str, Any]:
    """Fetch and normalize API Ninjas team histories independently."""
    started = time.perf_counter()
    result: dict[str, Any] = {
        "records": [],
        "provider_count": 0,
        "team_requests": 0,
        "raw_rows_received": 0,
        "error": None,
        "metadata": {},
    }
    try:
        league_slug = _api_ninjas_league_slug(client, competition)
        if league_slug is None:
            result["error"] = (
                "No unique exact competition-name mapping exists in the API Ninjas league catalogue."
            )
        else:
            rows = []
            for team_name in (home_team_name, away_team_name):
                result["team_requests"] += 1
                rows.extend(client.team_matches(
                    team=team_name, league=league_slug, season=int(season)
                ))
            result["raw_rows_received"] = len(rows)
            seen: set[str] = set()
            normalized = []
            for row in rows:
                match_id = str(row.get("game_id") or row.get("fixture_id") or "")
                if match_id and match_id in seen:
                    continue
                if match_id:
                    seen.add(match_id)
                if str(row.get("league") or league_slug) != league_slug:
                    continue
                row_season = row.get("season")
                if row_season is not None and str(row_season) != str(int(season)):
                    continue
                try:
                    normalized.append(canonicalize_api_ninjas_match(
                        row, competition_key=competition_key_value, season=int(season)
                    ))
                except (ValueError, TypeError, KeyError):
                    continue
            result["records"] = normalized
            result["provider_count"] = len(normalized)
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        result["metadata"] = dict(getattr(client, "last_metadata", {}) or {})
    return result


def collect_recent_result_corroboration(
    *,
    sportmonks_fixtures: list[dict[str, Any]],
    competition: str,
    country: str | None,
    season: int,
    sportmonks_season_id: int | None = None,
    home_team_name: str,
    away_team_name: str,
    highlightly_client: Any | None = None,
    highlightly_client_factory: Any | None = None,
    api_ninjas_client: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch independent match records and reconcile against Sportmonks fixtures.

    Highlightly uses documented leagueName/season/countryName filters and
    paginates its /matches endpoint. API Ninjas uses its documented team,
    league and season filters. A provider is skipped if an exact competition
    mapping is not available. No fuzzy team aliases are inferred.
    """
    fetched = now or datetime.now(timezone.utc)
    fetched = fetched.replace(tzinfo=timezone.utc) if fetched.tzinfo is None else fetched.astimezone(timezone.utc)
    key = competition_key(competition, country)
    home_records: list[dict[str, Any]] = []
    away_records: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    provider_counts: dict[str, int] = {}
    highlightly_records: list[dict[str, Any]] = []

    highlightly_diagnostics: dict[str, Any] = {
        "requested_filters": {
            "leagueName": competition,
            "countryName": country,
            "season": int(season),
            "limit": 100,
            "max_pages": 10,
        },
        "pages_requested": 0,
        "raw_rows_received": 0,
        "rejected_competition_mismatch": 0,
        "competition_missing_in_response": 0,
        "rejected_country_missing": 0,
        "rejected_country_mismatch": 0,
        "country_missing_but_retained": 0,
        "season_missing_in_response": 0,
        "rejected_season_mismatch": 0,
        "rejected_invalid_season": 0,
        "normalization_failures": 0,
        "records_normalized": 0,
        "completed_score_valid_records": 0,
        "selected_team_records": 0,
        "page_metadata": [],
    }

    # Overlap the independent API Ninjas fetch with Highlightly pagination.
    # Each provider client is confined to one thread; results are merged below.
    api_ninjas_executor = None
    api_ninjas_future = None
    if api_ninjas_client is not None:
        api_ninjas_executor = ThreadPoolExecutor(max_workers=1)
        api_ninjas_future = api_ninjas_executor.submit(
            _collect_api_ninjas_records,
            client=api_ninjas_client,
            competition=competition,
            season=int(season),
            home_team_name=home_team_name,
            away_team_name=away_team_name,
            competition_key_value=key,
        )

    highlightly_started = time.perf_counter()
    if highlightly_client is not None:
        try:
            rows: list[dict[str, Any]] = []
            limit, max_pages = 100, 10

            def fetch_highlightly_page(client: Any, offset: int) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
                page = client.matches(
                    leagueName=competition, season=int(season),
                    countryName=country, limit=limit, offset=offset,
                )
                metadata = dict(getattr(client, "last_metadata", {}) or {})
                return offset, page, metadata

            first_offset, first_page, first_metadata = fetch_highlightly_page(
                highlightly_client, 0
            )
            page_results = [(first_offset, first_page, first_metadata)]
            pagination = first_metadata.get("pagination")
            total_count = pagination.get("total_count") if isinstance(pagination, Mapping) else None
            reported_limit = pagination.get("limit") if isinstance(pagination, Mapping) else None
            try:
                total_count = int(total_count)
                reported_limit = int(reported_limit)
                if total_count < 0 or reported_limit <= 0:
                    raise ValueError
                page_count = (total_count + reported_limit - 1) // reported_limit
            except (TypeError, ValueError):
                total_count = None
                reported_limit = limit
                page_count = 0

            if total_count is not None:
                if page_count > max_pages:
                    raise RuntimeError("Highlightly pagination exceeded the safe page limit.")
                offsets = [
                    page_number * reported_limit
                    for page_number in range(1, page_count)
                ]
                if offsets and highlightly_client_factory is not None:
                    # Construct clients on the Streamlit script thread so
                    # credential/secrets access never occurs in worker threads.
                    page_clients = [
                        (offset, highlightly_client_factory())
                        for offset in offsets
                    ]

                    def fetch_with_independent_client(item):
                        offset, client = item
                        try:
                            return fetch_highlightly_page(client, offset)
                        finally:
                            close = getattr(client, "close", None)
                            if callable(close):
                                close()

                    with ThreadPoolExecutor(max_workers=min(2, len(offsets))) as executor:
                        page_results.extend(executor.map(fetch_with_independent_client, page_clients))
                else:
                    for offset in offsets:
                        page_results.append(fetch_highlightly_page(highlightly_client, offset))
            else:
                # Compatibility fallback for clients/providers that omit the
                # documented pagination envelope: retain safe sequential paging.
                offset = limit
                while len(first_page) == limit and len(page_results) < max_pages:
                    page_results.append(fetch_highlightly_page(highlightly_client, offset))
                    if len(page_results[-1][1]) < limit:
                        break
                    offset += limit
                if len(page_results) == max_pages and len(page_results[-1][1]) == limit:
                    raise RuntimeError("Highlightly pagination exceeded the safe page limit.")

            for offset, page, metadata in sorted(page_results, key=lambda item: item[0]):
                highlightly_diagnostics["pages_requested"] += 1
                highlightly_diagnostics["page_metadata"].append({
                    "offset": offset,
                    "rows_returned": len(page),
                    "response": metadata,
                })
                rows.extend(page)

            highlightly_diagnostics["raw_rows_received"] = len(rows)
            normalized = []
            for row in rows:
                league_value = row.get("league")
                league = league_value if isinstance(league_value, Mapping) else {}
                league_name = league.get("name") or row.get("leagueName")
                if not league_name:
                    highlightly_diagnostics["competition_missing_in_response"] += 1
                elif normalize_competition_name(league_name) != normalize_competition_name(competition):
                    highlightly_diagnostics["rejected_competition_mismatch"] += 1
                    continue

                # Highlightly's documented match schema places country at
                # the match's top level (row.country). Retain compatibility
                # with older/nested payloads that expose it under league.
                country_value = league.get("country")
                if country_value is None:
                    country_value = row.get("country")
                row_country = (
                    country_value.get("name") if isinstance(country_value, Mapping)
                    else country_value if isinstance(country_value, str)
                    else league.get("countryName") or row.get("countryName")
                )
                if country:
                    if not row_country:
                        highlightly_diagnostics["rejected_country_missing"] += 1
                        continue
                    if normalize_country(row_country) != normalize_country(country):
                        highlightly_diagnostics["rejected_country_mismatch"] += 1
                        continue
                elif not row_country:
                    highlightly_diagnostics["country_missing_but_retained"] += 1

                reported_season = league.get("season") or row.get("season")
                if isinstance(reported_season, Mapping):
                    reported_season = reported_season.get("year") or reported_season.get("start")
                if reported_season is None:
                    highlightly_diagnostics["season_missing_in_response"] += 1
                else:
                    try:
                        if int(reported_season) != int(season):
                            highlightly_diagnostics["rejected_season_mismatch"] += 1
                            continue
                    except (TypeError, ValueError):
                        highlightly_diagnostics["rejected_invalid_season"] += 1
                        continue
                try:
                    canonical = canonicalize_highlightly_match(
                        row, competition_key=key, season=int(season)
                    )
                    _apply_highlightly_team_identity_aliases(canonical)
                    normalized.append(canonical)
                except (ValueError, TypeError, KeyError):
                    highlightly_diagnostics["normalization_failures"] += 1
                    continue

            highlightly_records = normalized
            home_records.extend(normalized)
            away_records.extend(normalized)
            provider_counts["highlightly"] = len(normalized)
            selected_team_keys = {
                normalize_team_name(home_team_name),
                normalize_team_name(away_team_name),
            }
            # Preserve a compact catalogue of every normalized provider team
            # name and source ID. This reveals abbreviated/alternate names
            # without weakening exact selected-team matching.
            team_name_catalog: dict[str, dict[str, Any]] = {}
            for record in normalized:
                for side in ("home", "away"):
                    team = record.get(side) or {}
                    display_name = str(team.get("name") or "")
                    if not display_name:
                        continue
                    entry = team_name_catalog.setdefault(display_name, {
                        "normalized_name": normalize_team_name(display_name),
                        "appearances": 0,
                        "source_team_ids": [],
                    })
                    entry["appearances"] += 1
                    source_id = str((team.get("source_ids") or {}).get("highlightly") or "")
                    if source_id and source_id not in entry["source_team_ids"]:
                        entry["source_team_ids"].append(source_id)
            highlightly_diagnostics["team_name_catalog"] = team_name_catalog

            highlightly_diagnostics["records_normalized"] = len(normalized)
            highlightly_diagnostics["completed_score_valid_records"] = sum(
                1 for row in normalized
                if row.get("status") == "finished"
                and row.get("home_score") is not None
                and row.get("away_score") is not None
            )
            highlightly_diagnostics["selected_team_records"] = sum(
                1 for row in normalized
                if selected_team_keys.intersection({
                    _team_identity_key(row.get("home")),
                    _team_identity_key(row.get("away")),
                })
            )

            # Explain per-team gaps instead of reporting only a zero valid-match
            # count. Keep this diagnostic compact and retain raw provider state
            # fields so status/score schema differences can be identified.
            raw_by_id = {
                str(row.get("id")): row
                for row in rows
                if row.get("id") is not None
            }
            team_breakdown: dict[str, Any] = {}
            for team_name in (home_team_name, away_team_name):
                team_key = normalize_team_name(team_name)
                team_rows = [
                    row for row in normalized
                    if team_key in {
                        _team_identity_key(row.get("home")),
                        _team_identity_key(row.get("away")),
                    }
                ]
                status_counts: dict[str, int] = {}
                state_descriptions: dict[str, int] = {}
                sample_records = []
                for record in team_rows:
                    status = str(record.get("status") or "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                    source_id = str((record.get("source_ids") or {}).get("highlightly") or "")
                    raw = raw_by_id.get(source_id, {})
                    raw_state = raw.get("state") if isinstance(raw.get("state"), Mapping) else {}
                    description = str(raw_state.get("description") or "<missing>")
                    state_descriptions[description] = state_descriptions.get(description, 0) + 1
                    if len(sample_records) < 6:
                        home_raw = raw.get("homeTeam") if isinstance(raw.get("homeTeam"), Mapping) else {}
                        away_raw = raw.get("awayTeam") if isinstance(raw.get("awayTeam"), Mapping) else {}
                        league_raw = raw.get("league") if isinstance(raw.get("league"), Mapping) else {}
                        country_raw = raw.get("country")
                        if isinstance(country_raw, Mapping):
                            country_raw = country_raw.get("name")
                        sample_records.append({
                            "highlightly_match_id": source_id or None,
                            "date": raw.get("date"),
                            "home": record.get("home", {}).get("name"),
                            "away": record.get("away", {}).get("name"),
                            "home_team_id": home_raw.get("id"),
                            "away_team_id": away_raw.get("id"),
                            "raw_state": {
                                key: raw_state.get(key)
                                for key in ("id", "description", "name", "shortName", "status", "score")
                                if key in raw_state
                            },
                            "normalized_status": status,
                            "normalized_score": [record.get("home_score"), record.get("away_score")],
                            "league": {
                                "id": league_raw.get("id"),
                                "name": league_raw.get("name") or raw.get("leagueName"),
                                "season": league_raw.get("season") or raw.get("season"),
                            },
                            "country": country_raw or (
                                league_raw.get("countryName") or raw.get("countryName")
                            ),
                        })
                valid_count = sum(
                    1 for row in team_rows
                    if row.get("status") == "finished"
                    and row.get("home_score") is not None
                    and row.get("away_score") is not None
                )
                finished_missing_score = sum(
                    1 for row in team_rows
                    if row.get("status") == "finished"
                    and (row.get("home_score") is None or row.get("away_score") is None)
                )
                team_breakdown[team_name] = {
                    "normalized_team_records": len(team_rows),
                    "status_counts": status_counts,
                    "raw_state_descriptions": state_descriptions,
                    "completed_score_valid": valid_count,
                    "finished_missing_score": finished_missing_score,
                    "sample_records": sample_records,
                }
            highlightly_diagnostics["selected_team_breakdown"] = team_breakdown
        except Exception as exc:
            errors["highlightly"] = str(exc)
            highlightly_diagnostics["retrieval_error"] = str(exc)
            highlightly_diagnostics["client_metadata_at_error"] = dict(
                getattr(highlightly_client, "last_metadata", {}) or {}
            )

    highlightly_elapsed = round(time.perf_counter() - highlightly_started, 3)
    api_ninjas_diagnostics: dict[str, Any] = {
        "team_requests": 0,
        "raw_rows_received": 0,
        "records_normalized": 0,
        "elapsed_seconds": 0.0,
        "metadata": {},
    }
    if api_ninjas_future is not None:
        try:
            api_result = api_ninjas_future.result()
            normalized_api_ninjas = api_result.get("records") or []
            home_records.extend(normalized_api_ninjas)
            away_records.extend(normalized_api_ninjas)
            provider_counts["api_ninjas"] = int(api_result.get("provider_count") or 0)
            api_ninjas_diagnostics.update({
                "team_requests": api_result.get("team_requests", 0),
                "raw_rows_received": api_result.get("raw_rows_received", 0),
                "records_normalized": len(normalized_api_ninjas),
                "elapsed_seconds": api_result.get("elapsed_seconds", 0.0),
                "metadata": api_result.get("metadata") or {},
            })
            if api_result.get("error"):
                errors["api_ninjas"] = str(api_result["error"])
        finally:
            if api_ninjas_executor is not None:
                api_ninjas_executor.shutdown(wait=True)

    # Restrict the diagnostic to fixtures involving either selected team.
    selected = {normalize_team_name(home_team_name), normalize_team_name(away_team_name)}
    target_fixtures = []
    # Sportmonks season_id is an internal identifier, not the calendar year
    # used by Highlightly's season filter. Keep the two values separate.
    expected_sportmonks_season_id = int(
        sportmonks_season_id if sportmonks_season_id is not None else season
    )
    for fixture in sportmonks_fixtures:
        try:
            if int(fixture.get("season_id")) != expected_sportmonks_season_id:
                continue
        except (TypeError, ValueError):
            continue
        canonical = canonicalize_sportmonks_fixture(
            fixture, competition=competition, country=country, season=season
        )
        if canonical is None:
            continue
        if canonical["status"] != "finished" or canonical["home_score"] is None or canonical["away_score"] is None:
            continue
        if (normalize_team_name(canonical["home"]["name"]) in selected
                or normalize_team_name(canonical["away"]["name"]) in selected):
            target_fixtures.append(canonical)
    target_fixtures.sort(key=lambda row: row["kickoff_utc"], reverse=True)
    target_fixtures = target_fixtures[:20]

    # Compare each selected team's completed Highlightly results with the
    # primary provider's completed, score-valid fixtures. Unmatched records are
    # review candidates only; they are never appended to prediction history.
    team_history_coverage: dict[str, dict[str, Any]] = {}
    for team_name in (home_team_name, away_team_name):
        team_key = normalize_team_name(team_name)
        primary_team = [
            row for row in target_fixtures
            if team_key in {
                normalize_team_name(row["home"]["name"]),
                normalize_team_name(row["away"]["name"]),
            }
        ]
        secondary_team = []
        seen_secondary: set[str] = set()
        for row in highlightly_records:
            if row.get("season") != int(season) or row.get("competition_key") != key:
                continue
            if team_key not in {
                _team_identity_key(row.get("home")),
                _team_identity_key(row.get("away")),
            }:
                continue
            if row.get("status") != "finished" or row.get("home_score") is None or row.get("away_score") is None:
                continue
            source_id = str((row.get("source_ids") or {}).get("highlightly") or "")
            identity_key = source_id or "|".join((
                str(row.get("kickoff_utc") or ""),
                normalize_team_name(row.get("home", {}).get("name", "")),
                normalize_team_name(row.get("away", {}).get("name", "")),
            ))
            if identity_key in seen_secondary:
                continue
            seen_secondary.add(identity_key)
            secondary_team.append(row)
        secondary_team.sort(key=lambda row: str(row.get("kickoff_utc") or ""), reverse=True)
        unmatched = [
            row for row in secondary_team
            if not any(match_identity(row, primary) for primary in primary_team)
        ]
        ninjas_team = []
        seen_ninjas: set[str] = set()
        for row in home_records:
            if row.get("source") != "api_ninjas":
                continue
            if row.get("season") != int(season) or row.get("competition_key") != key:
                continue
            if team_key not in {
                normalize_team_name(row.get("home", {}).get("name", "")),
                normalize_team_name(row.get("away", {}).get("name", "")),
            }:
                continue
            if row.get("status") != "finished" or row.get("home_score") is None or row.get("away_score") is None:
                continue
            source_id = str((row.get("source_ids") or {}).get("api_ninjas") or "")
            identity_key = source_id or "|".join((
                str(row.get("kickoff_utc") or ""),
                normalize_team_name(row.get("home", {}).get("name", "")),
                normalize_team_name(row.get("away", {}).get("name", "")),
            ))
            if identity_key in seen_ninjas:
                continue
            seen_ninjas.add(identity_key)
            ninjas_team.append(row)
        ninjas_team.sort(key=lambda row: str(row.get("kickoff_utc") or ""), reverse=True)
        ninjas_unmatched = [
            row for row in ninjas_team
            if not any(match_identity(row, primary) for primary in primary_team)
        ]
        team_history_coverage[team_name] = {
            "highlightly_completed_score_valid": len(secondary_team),
            "highlightly_exact_matches": len(secondary_team) - len(unmatched),
            "highlightly_unmatched_count": len(unmatched),
            "sportmonks_completed_score_valid": len(primary_team),
            "api_ninjas_completed_score_valid": len(ninjas_team),
            "api_ninjas_exact_matches": len(ninjas_team) - len(ninjas_unmatched),
            "api_ninjas_unmatched_count": len(ninjas_unmatched),
            "api_ninjas_unmatched_candidates": [{
                "kickoff_utc": row.get("kickoff_utc"),
                "home": row.get("home", {}).get("name"),
                "away": row.get("away", {}).get("name"),
                "score": [row.get("home_score"), row.get("away_score")],
                "api_ninjas_match_id": (row.get("source_ids") or {}).get("api_ninjas"),
                "review_status": "candidate_only_not_added_to_prediction_history",
            } for row in ninjas_unmatched[:5]],
            "exact_matches_across_sources": len(secondary_team) - len(unmatched),
            "highlightly_results_not_found_in_sportmonks": len(unmatched),
            "latest_highlightly_completed_match": ({
                "kickoff_utc": secondary_team[0].get("kickoff_utc"),
                "home": secondary_team[0].get("home", {}).get("name"),
                "away": secondary_team[0].get("away", {}).get("name"),
                "score": [secondary_team[0].get("home_score"), secondary_team[0].get("away_score")],
                "highlightly_match_id": (secondary_team[0].get("source_ids") or {}).get("highlightly"),
            } if secondary_team else None),
            "unmatched_completed_candidates": [{
                "kickoff_utc": row.get("kickoff_utc"),
                "home": row.get("home", {}).get("name"),
                "away": row.get("away", {}).get("name"),
                "score": [row.get("home_score"), row.get("away_score")],
                "highlightly_match_id": (row.get("source_ids") or {}).get("highlightly"),
                "review_status": "candidate_only_not_added_to_prediction_history",
            } for row in unmatched[:5]],
            "interpretation": (
                "Provider-specific unmatched results are review candidates, not accepted extra matches. "
                "Exact competition, season, home/away teams and kickoff must match before joining."
            ),
        }

    all_alternates = home_records
    reconciled: list[dict[str, Any]] = []
    matched_providers: set[str] = set()
    for primary in target_fixtures:
        group = [primary]
        for alternate in all_alternates:
            if match_identity(primary, alternate):
                group.append(alternate)
        if len(group) < 2:
            continue
        result = reconcile_match_records(
            group,
            fetched_at={row["source"]: fetched for row in group},
            now=fetched,
            max_age_seconds=24 * 60 * 60,
        )
        if result is not None:
            reconciled.append(result)
            matched_providers.update(result.get("providers_seen", []))

    # Keep fixture-level agreement and conflict as independent flags: a match
    # can agree on one field (for example, score) and conflict on another
    # (for example, status or kickoff). Expose the exact field-level evidence.
    field_names = ("status", "home_score", "away_score", "kickoff_utc")
    field_level_summary: dict[str, dict[str, int]] = {
        field: {
            "fixtures_compared": 0,
            "fixtures_with_agreement": 0,
            "fixtures_with_conflict": 0,
            "fixtures_with_multiple_observations": 0,
        }
        for field in field_names
    }
    for row in reconciled:
        agreement_fields: list[str] = []
        conflict_fields: list[str] = []
        field_observations: list[dict[str, Any]] = []
        for field in field_names:
            detail = (row.get("reconciliation") or {}).get(field) or {}
            observations = detail.get("observations") or []
            if not observations:
                continue
            summary = field_level_summary[field]
            summary["fixtures_compared"] += 1
            if len(observations) > 1:
                summary["fixtures_with_multiple_observations"] += 1
            if detail.get("status") == "corroborated":
                agreement_fields.append(field)
                summary["fixtures_with_agreement"] += 1
            elif detail.get("status") == "conflict":
                conflict_fields.append(field)
                summary["fixtures_with_conflict"] += 1
            for observation in observations:
                field_observations.append({
                    "field": field,
                    "provider": observation.get("provider"),
                    "value": observation.get("value"),
                    "selected_provider": detail.get("provider"),
                    "field_status": detail.get("status"),
                    "source_id": observation.get("source_id"),
                    "fetched_at": observation.get("fetched_at"),
                    "source_updated_at": observation.get("source_updated_at"),
                })
        row["agreement_fields"] = agreement_fields
        row["conflict_fields"] = conflict_fields
        row["field_observations"] = field_observations
        row["diagnostic_status"] = (
            "agreement_and_conflict" if agreement_fields and conflict_fields
            else "conflict" if conflict_fields
            else "agreement" if agreement_fields
            else "matched_identity_only"
        )

    conflicts = sum(1 for row in reconciled if row.get("conflict_fields"))
    corroborated = sum(1 for row in reconciled if row.get("agreement_fields"))
    mixed = sum(
        1 for row in reconciled
        if row.get("agreement_fields") and row.get("conflict_fields")
    )
    return {
        "competition": competition,
        "country": country,
        "season": int(season),
        "sportmonks_fixtures_checked": len(target_fixtures),
        "provider_records_returned": provider_counts,
        "highlightly_diagnostics": highlightly_diagnostics,
        "team_history_coverage": team_history_coverage,
        "fixtures_matched_across_sources": len(reconciled),
        "fixtures_with_agreement": corroborated,
        "fixtures_with_conflicts": conflicts,
        "fixtures_with_both_agreement_and_conflict": mixed,
        "field_level_summary": field_level_summary,
        "providers_matched": sorted(matched_providers),
        "provider_timings_seconds": {
            "highlightly": highlightly_elapsed,
            "api_ninjas": api_ninjas_diagnostics["elapsed_seconds"],
        },
        "api_ninjas_diagnostics": api_ninjas_diagnostics,
        "errors": errors,
        "matches": reconciled,
        "interpretation": (
            "Agreement and conflict are counted independently at fixture level. "
            "A fixture may appear in both counts when providers agree on some fields "
            "and disagree on others. Inspect field_level_summary and each match's "
            "field_observations for the exact provider values and timestamps."
        ),
        "note": "Corroboration is diagnostic only; Sportmonks Layer 2 profiles and prediction inputs are not modified.",
    }
