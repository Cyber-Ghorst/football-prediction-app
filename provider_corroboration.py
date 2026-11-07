"""Optional independent corroboration of Sportmonks recent results.

This module is deliberately diagnostic: it never mutates Layer 2 profiles or
prediction inputs. Only exact competition/season/team/kickoff matches join.
Provider observations retain namespaced IDs and field-level conflicts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from canonical_data import (
    canonicalize_api_ninjas_match,
    canonicalize_highlightly_match,
    match_identity,
)
from competition_crosswalk import normalize_competition_name, normalize_country
from multi_source_reconciliation import reconcile_match_records
from provider_core import normalize_team_name


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

    if highlightly_client is not None:
        try:
            rows: list[dict[str, Any]] = []
            offset, limit, max_pages = 0, 100, 10
            for _ in range(max_pages):
                page = highlightly_client.matches(
                    leagueName=competition, season=int(season),
                    countryName=country, limit=limit, offset=offset,
                )
                rows.extend(page)
                if len(page) < limit:
                    break
                offset += limit
            else:
                raise RuntimeError("Highlightly pagination exceeded the safe page limit.")
            normalized = []
            for row in rows:
                league_value = row.get("league")
                league = league_value if isinstance(league_value, Mapping) else {}
                league_name = league.get("name") or row.get("leagueName")
                if league_name and normalize_competition_name(league_name) != normalize_competition_name(competition):
                    continue
                country_value = league.get("country")
                row_country = (
                    country_value.get("name") if isinstance(country_value, Mapping)
                    else country_value if isinstance(country_value, str)
                    else league.get("countryName") or row.get("countryName")
                )
                if country and (not row_country or normalize_country(row_country) != normalize_country(country)):
                    continue
                reported_season = league.get("season") or row.get("season")
                if isinstance(reported_season, Mapping):
                    reported_season = reported_season.get("year") or reported_season.get("start")
                if reported_season is not None:
                    try:
                        if int(reported_season) != int(season):
                            continue
                    except (TypeError, ValueError):
                        continue
                try:
                    normalized.append(canonicalize_highlightly_match(
                        row, competition_key=key, season=int(season)
                    ))
                except (ValueError, TypeError, KeyError):
                    continue
            highlightly_records = normalized
            home_records.extend(normalized)
            away_records.extend(normalized)
            provider_counts["highlightly"] = len(normalized)
        except Exception as exc:
            errors["highlightly"] = str(exc)

    if api_ninjas_client is not None:
        try:
            league_slug = _api_ninjas_league_slug(api_ninjas_client, competition)
            if league_slug is None:
                provider_counts["api_ninjas"] = 0
                errors["api_ninjas"] = "No unique exact competition-name mapping exists in the API Ninjas league catalogue."
            else:
                rows = []
                for team_name in (home_team_name, away_team_name):
                    rows.extend(api_ninjas_client.team_matches(
                        team=team_name, league=league_slug, season=int(season)
                    ))
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
                            row, competition_key=key, season=int(season)
                        ))
                    except (ValueError, TypeError, KeyError):
                        continue
                home_records.extend(normalized)
                away_records.extend(normalized)
                provider_counts["api_ninjas"] = len(normalized)
        except Exception as exc:
            errors["api_ninjas"] = str(exc)

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
                normalize_team_name(row.get("home", {}).get("name", "")),
                normalize_team_name(row.get("away", {}).get("name", "")),
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
        team_history_coverage[team_name] = {
            "highlightly_completed_score_valid": len(secondary_team),
            "sportmonks_completed_score_valid": len(primary_team),
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
                "An unmatched Highlightly result is a review candidate, not an accepted extra match. "
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
        "team_history_coverage": team_history_coverage,
        "fixtures_matched_across_sources": len(reconciled),
        "fixtures_with_agreement": corroborated,
        "fixtures_with_conflicts": conflicts,
        "fixtures_with_both_agreement_and_conflict": mixed,
        "field_level_summary": field_level_summary,
        "providers_matched": sorted(matched_providers),
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
