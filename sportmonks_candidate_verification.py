"""Targeted verification of unmatched Highlightly results against Sportmonks.

The verifier reports exact season, competition, home/away team IDs, kickoff,
completion and score. A separate opt-in helper may append only a single exact,
completed Sportmonks result whose full-time score agrees with Highlightly.
Unverified candidates remain diagnostic-only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _as_int(value: Any) -> int | None:
    """Accept integer IDs/scores only; reject booleans and fractional values."""
    import math
    import re

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def fixtures_for_utc_date(fixtures: list[dict[str, Any]], date_value: str) -> list[dict[str, Any]]:
    """Return fixture rows whose kickoff falls on the supplied UTC calendar date."""
    target_date = str(date_value or "").strip()
    if not target_date:
        return []
    selected = []
    for fixture in fixtures:
        kickoff = _utc_datetime(fixture.get("starting_at"))
        if kickoff and kickoff.date().isoformat() == target_date:
            selected.append(fixture)
    return selected


def _participant_pair(fixture: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = away = None
    for row in _rows(fixture.get("participants")):
        meta = row.get("meta") or {}
        location = str(meta.get("location") or "").casefold()
        if location == "home":
            home = row
        elif location == "away":
            away = row
    return home, away


def _finished(fixture: Mapping[str, Any]) -> bool:
    state_id = _as_int(fixture.get("state_id"))
    if state_id in {5, 7, 8}:
        return True
    state = fixture.get("state") or {}
    label = str(state.get("short_name") or state.get("name") or "").strip().casefold()
    # Only recognized complete labels count as finished. Avoid substring
    # matches such as "unfinished" or "not finished".
    return label in {
        "finished", "ft", "aet", "after extra time", "after penalties",
        "full time", "full-time", "finished after extra time",
        "finished after penalties",
    }


def _scores(fixture: Mapping[str, Any], home_id: int, away_id: int) -> tuple[int | None, int | None]:
    rows = _rows(fixture.get("scores"))
    current = [row for row in rows if str(row.get("description") or "").casefold() == "current"]
    values: dict[int, int] = {}
    # Period-specific scores cannot stand in for a missing full-time score.
    for row in current:
        participant_id = _as_int(row.get("participant_id"))
        score = row.get("score") or {}
        goals = score.get("goals") if isinstance(score, Mapping) else None
        parsed_goals = _as_int(goals)
        if participant_id is not None and parsed_goals is not None and parsed_goals >= 0:
            values[participant_id] = parsed_goals
    return values.get(home_id), values.get(away_id)




def _date_fixture_participant_catalog(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize every exact participant name/ID seen in the date response.

    This is diagnostic evidence only. It does not resolve aliases or verify a
    candidate; it lets reviewers distinguish a naming mismatch from missing
    fixture coverage without exposing the full provider payload.
    """
    observations: dict[int, dict[str, Any]] = {}
    for fixture in fixtures:
        fixture_id = _as_int(fixture.get("id"))
        for participant in _rows(fixture.get("participants")):
            team_id = _as_int(participant.get("id"))
            name = str(participant.get("name") or "").strip()
            if team_id is None or not name:
                continue
            item = observations.setdefault(team_id, {"team_id": team_id, "provider_names": set(), "fixture_ids": set()})
            item["provider_names"].add(name)
            if fixture_id is not None:
                item["fixture_ids"].add(fixture_id)
    return [
        {
            "team_id": team_id,
            "provider_names": sorted(item["provider_names"]),
            "fixture_ids": sorted(item["fixture_ids"]),
        }
        for team_id, item in sorted(observations.items())
    ]


def resolve_candidate_team_id(
    team_name: str,
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve a candidate team only from exact names in Sportmonks date results.

    This deliberately avoids fuzzy matching. A unique exact normalized name
    maps to one provider ID; absent or ambiguous names remain unresolved.
    """
    from provider_core import normalize_team_name

    target = normalize_team_name(team_name or "")
    # Explicit, reviewed provider-name variants only. These are not fuzzy
    # matches: the candidate alias must resolve to one exact Sportmonks name
    # and one unique participant ID in the date response.
    explicit_aliases = {
        # Reviewed Highlightly -> Sportmonks display-name variants. Each alias
        # still has to resolve to one unique participant ID in the exact-date
        # Sportmonks response; season, league, orientation, kickoff and score
        # are checked separately before a candidate can be verified.
        "coventry": {"coventry city"},
        "ipswich": {"ipswich town"},
        "brighton": {"brighton hove albion"},
        "bournemouth": {"afc bournemouth"},
        "leeds": {"leeds united"},
        "tottenham": {"tottenham hotspur"},
    }
    accepted_names = {target} | explicit_aliases.get(target, set()) if target else set()
    observations: dict[int, set[str]] = {}
    if accepted_names:
        for fixture in fixtures:
            for participant in _rows(fixture.get("participants")):
                name = str(participant.get("name") or "").strip()
                participant_id = _as_int(participant.get("id"))
                if not name or participant_id is None:
                    continue
                if normalize_team_name(name) in accepted_names:
                    observations.setdefault(participant_id, set()).add(name)

    matches = [
        {"team_id": team_id, "provider_names": sorted(names)}
        for team_id, names in sorted(observations.items())
    ]
    if len(matches) == 1:
        used_alias = any(
            normalize_team_name(name) != target
            for name in matches[0]["provider_names"]
        )
        return {
            "team_id": matches[0]["team_id"],
            "status": (
                "explicit_alias_resolved_from_date_fixtures"
                if used_alias else "exact_name_resolved_from_date_fixtures"
            ),
            "matched_provider_names": matches[0]["provider_names"],
            "candidate_matches": matches,
        }
    return {
        "team_id": None,
        "status": "team_name_not_found_in_date_fixtures" if not matches else "ambiguous_exact_team_name",
        "matched_provider_names": [],
        "candidate_matches": matches,
    }

def verify_highlightly_candidate(
    candidate: Mapping[str, Any],
    fixtures: list[dict[str, Any]],
    *,
    season_id: int,
    league_id: int,
    home_team_id: int | None,
    away_team_id: int | None,
) -> dict[str, Any]:
    """Compare one Highlightly candidate with all Sportmonks fixtures returned for its UTC date."""
    kickoff = _utc_datetime(candidate.get("kickoff_utc"))
    result: dict[str, Any] = {
        "highlightly_candidate": {
            "kickoff_utc": candidate.get("kickoff_utc"),
            "home": candidate.get("home"),
            "away": candidate.get("away"),
            "score": candidate.get("score"),
            "highlightly_match_id": candidate.get("highlightly_match_id"),
        },
        "sportmonks_date_query": kickoff.date().isoformat() if kickoff else None,
        "sportmonks_fixtures_returned_for_date": len(fixtures),
        "date_fixture_participant_catalog": _date_fixture_participant_catalog(fixtures),
        "expected_identity": {
            "season_id": int(season_id),
            "league_id": int(league_id),
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
        },
        "team_mapping_status": (
            "exact_team_ids_resolved"
            if home_team_id is not None and away_team_id is not None
            else "unresolved_exact_team_mapping"
        ),
        "same_season_and_competition_fixtures": 0,
        "exact_home_away_team_fixtures": 0,
        "exact_kickoff_fixtures": 0,
        "exact_completed_score_valid_fixtures": 0,
        "candidate_score_agreement": None,
        "sportmonks_candidates": [],
        "verification_status": "not_verified",
    }
    if kickoff is None:
        result["verification_status"] = "invalid_highlightly_kickoff"
        return result
    if home_team_id is None or away_team_id is None:
        result["verification_status"] = "unresolved_exact_team_mapping"
        return result

    same_competition: list[dict[str, Any]] = []
    exact_teams: list[dict[str, Any]] = []
    exact_kickoff: list[dict[str, Any]] = []
    for fixture in fixtures:
        if _as_int(fixture.get("season_id")) != int(season_id):
            continue
        fixture_league_id = fixture.get("league_id")
        if fixture_league_id is None:
            league = fixture.get("league") or {}
            fixture_league_id = league.get("id") if isinstance(league, Mapping) else None
        if _as_int(fixture_league_id) != int(league_id):
            continue
        same_competition.append(fixture)
        home, away = _participant_pair(fixture)
        if not home or not away:
            continue
        if _as_int(home.get("id")) != int(home_team_id) or _as_int(away.get("id")) != int(away_team_id):
            continue
        exact_teams.append(fixture)
        fixture_kickoff = _utc_datetime(fixture.get("starting_at"))
        if fixture_kickoff == kickoff:
            exact_kickoff.append(fixture)

    result["same_season_and_competition_fixtures"] = len(same_competition)
    result["exact_home_away_team_fixtures"] = len(exact_teams)
    result["exact_kickoff_fixtures"] = len(exact_kickoff)

    for fixture in exact_teams[:10]:
        home, away = _participant_pair(fixture)
        home_id, away_id = int(home_team_id), int(away_team_id)
        home_score, away_score = _scores(fixture, home_id, away_id)
        score_valid = home_score is not None and away_score is not None
        finished = _finished(fixture)
        fixture_kickoff = _utc_datetime(fixture.get("starting_at"))
        result["sportmonks_candidates"].append({
            "fixture_id": fixture.get("id"),
            "season_id": fixture.get("season_id"),
            "league_id": fixture.get("league_id"),
            "kickoff_utc": fixture.get("starting_at"),
            "kickoff_exact_match": fixture_kickoff == kickoff,
            "home": home.get("name"),
            "away": away.get("name"),
            "home_team_id": home.get("id"),
            "away_team_id": away.get("id"),
            "state_id": fixture.get("state_id"),
            "state": (fixture.get("state") or {}).get("short_name") or (fixture.get("state") or {}).get("name"),
            "completed": finished,
            "score": [home_score, away_score],
            "score_valid": score_valid,
        })

    exact_valid = [
        fixture for fixture in exact_kickoff
        if _finished(fixture)
        and all(value is not None for value in _scores(fixture, int(home_team_id), int(away_team_id)))
    ]
    result["exact_completed_score_valid_fixtures"] = len(exact_valid)
    if exact_valid:
        candidate_score = candidate.get("score") or []
        sm_home, sm_away = _scores(exact_valid[0], int(home_team_id), int(away_team_id))
        if len(candidate_score) == 2:
            result["candidate_score_agreement"] = (
                _as_int(candidate_score[0]) == sm_home
                and _as_int(candidate_score[1]) == sm_away
            )
        result["verification_status"] = (
            "exact_fixture_and_score_agree"
            if result["candidate_score_agreement"] is True
            else "exact_fixture_found_score_disagrees"
            if result["candidate_score_agreement"] is False
            else "exact_fixture_found_score_comparison_unavailable"
        )
    elif exact_kickoff:
        result["verification_status"] = "exact_fixture_found_but_not_completed_with_valid_scores"
    elif exact_teams:
        result["verification_status"] = "same_teams_found_but_kickoff_differs"
    elif same_competition:
        result["verification_status"] = "same_season_competition_found_but_exact_team_pair_not_found"
    else:
        result["verification_status"] = "no_same_season_competition_fixture_returned_for_date"
    return result


def apply_verified_result_candidates_to_profiles(
    profiles: list[dict[str, Any]],
    candidate_reports: list[Mapping[str, Any]],
    *,
    expected_season_id: int,
    history_limit: int = 10,
) -> dict[str, Any]:
    """Append only exact, completed Sportmonks results corroborated by Highlightly.

    The candidate is admitted only when the independent Highlightly score agrees
    with a completed Sportmonks fixture having exact competition, season,
    home/away team IDs and kickoff. The result contributes to form/goals only;
    no match statistics or TVD evidence are fabricated.
    """
    from copy import deepcopy
    from form_analyzer import analyze_form, venue_rating
    from provider_core import normalize_team_name
    from tactical_indicators import analyze_tactics
    from sportmonks_layer2 import _CORE_STATISTICS

    original_profiles = profiles
    profiles = deepcopy(profiles)
    safe_limit = max(1, min(int(history_limit), 10))
    summary = {
        "status": "completed",
        "profiles_updated": 0,
        "matches_added": 0,
        "candidates_rejected": 0,
        "duplicates_skipped": 0,
        "ambiguous_candidates_skipped": 0,
        "tactical_evidence_updated": False,
    }

    for report in candidate_reports:
        if not isinstance(report, Mapping):
            summary["candidates_rejected"] += 1
            continue
        if (
            report.get("verification_status") != "exact_fixture_and_score_agree"
            or report.get("candidate_score_agreement") is not True
        ):
            summary["candidates_rejected"] += 1
            continue
        identity = report.get("expected_identity") or {}
        if (
            _as_int(identity.get("season_id")) != _as_int(expected_season_id)
            or _as_int(identity.get("league_id")) is None
            or _as_int(identity.get("home_team_id")) is None
            or _as_int(identity.get("away_team_id")) is None
        ):
            summary["candidates_rejected"] += 1
            continue
        raw_verified_at = report.get("verification_completed_at")
        try:
            verified_at = datetime.fromisoformat(
                str(raw_verified_at).strip().replace("Z", "+00:00")
            )
            if verified_at.tzinfo is None:
                raise ValueError("Verification timestamp has no timezone.")
            verified_at = verified_at.astimezone(timezone.utc)
        except (TypeError, ValueError):
            summary["candidates_rejected"] += 1
            continue

        exact_candidates = [
            item for item in report.get("sportmonks_candidates") or []
            if isinstance(item, Mapping)
            and item.get("kickoff_exact_match") is True
            and item.get("completed") is True
            and item.get("score_valid") is True
            and _as_int(item.get("season_id")) == _as_int(expected_season_id)
            and _as_int(item.get("league_id")) == _as_int(identity.get("league_id"))
            and _as_int(item.get("home_team_id")) == _as_int(identity.get("home_team_id"))
            and _as_int(item.get("away_team_id")) == _as_int(identity.get("away_team_id"))
            and _as_int(item.get("fixture_id")) is not None
            and _utc_datetime(item.get("kickoff_utc")) is not None
            and isinstance(item.get("score"), list)
            and len(item.get("score")) == 2
            and all(_as_int(value) is not None and _as_int(value) >= 0 for value in item["score"])
        ]
        if len(exact_candidates) != 1:
            summary["ambiguous_candidates_skipped"] += 1
            continue
        verified_fixture = exact_candidates[0]
        fixture_id = _as_int(verified_fixture.get("fixture_id"))
        home_id = _as_int(verified_fixture.get("home_team_id"))
        away_id = _as_int(verified_fixture.get("away_team_id"))
        home_name = str(verified_fixture.get("home") or "")
        away_name = str(verified_fixture.get("away") or "")
        kickoff = _utc_datetime(verified_fixture.get("kickoff_utc"))
        score = [_as_int(value) for value in verified_fixture["score"]]
        if (
            fixture_id is None or fixture_id <= 0
            or home_id is None or home_id <= 0
            or away_id is None or away_id <= 0
            or not home_name or not away_name or kickoff is None
        ):
            summary["candidates_rejected"] += 1
            continue

        highlightly_candidate = report.get("highlightly_candidate") or {}
        fixture_added_for_candidate = False
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = _as_int(profile.get("id"))
            profile_name = normalize_team_name(profile.get("name") or "")
            if profile_id == home_id and profile_name == normalize_team_name(home_name):
                venue, opponent_id, opponent_name = "home", away_id, away_name
                goals_for, goals_against = score[0], score[1]
            elif profile_id == away_id and profile_name == normalize_team_name(away_name):
                venue, opponent_id, opponent_name = "away", home_id, home_name
                goals_for, goals_against = score[1], score[0]
            else:
                continue

            matches = profile.get("matches")
            if not isinstance(matches, list):
                matches = []
            if any(str(match.get("fixture_id")) == str(fixture_id) for match in matches if isinstance(match, Mapping)):
                summary["duplicates_skipped"] += 1
                continue

            new_match = {
                "fixture_id": fixture_id,
                "date": kickoff.isoformat(),
                "venue": venue,
                "opponent_id": opponent_id,
                "opponent_name": opponent_name,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "opponent_strength": None,
                "statistics": {},
                "opponent_statistics": {},
                "statistics_provenance": [],
                "statistics_raw_diagnostics": [],
                "collection_fetched_at": None,
                "repository_collected_at": None,
                "provider_updated_at": None,
                "history_source": "sportmonks_verified_result_candidate",
                "result_verification": {
                    "source_provider": "sportmonks",
                    "corroborated_by": "highlightly",
                    "verification_status": "exact_fixture_and_score_agree",
                    "candidate_score_agreement": True,
                    "highlightly_match_id": str(highlightly_candidate.get("highlightly_match_id") or ""),
                    "verification_source": report.get("verification_source"),
                    "verified_at": verified_at.isoformat(),
                },
            }
            matches.append(new_match)
            matches.sort(
                key=lambda match: (
                    _utc_datetime(match.get("date")).timestamp()
                    if isinstance(match, Mapping) and _utc_datetime(match.get("date"))
                    else -1
                ),
                reverse=True,
            )
            recent = matches[:safe_limit]
            profile["matches"] = recent
            profile["form_summary"] = analyze_form(recent)
            profile["home_rating"] = venue_rating(recent, "home")
            profile["away_rating"] = venue_rating(recent, "away")
            tactics = analyze_tactics(recent)
            profile["tactical_summary"] = tactics
            for field in ("playing_style", "defensive_structure", "attacking_approach"):
                if field in tactics:
                    profile[field] = tactics[field]
            data_quality = profile.setdefault("data_quality", {})
            data_quality["verified_result_history_fallback_added"] = (
                int(data_quality.get("verified_result_history_fallback_added") or 0) + 1
            )
            diagnostics = profile.setdefault("history_collection_diagnostics", {})
            diagnostics["verified_result_candidates_added"] = (
                int(diagnostics.get("verified_result_candidates_added") or 0) + 1
            )
            diagnostics["history_shortfall"] = max(0, safe_limit - len(recent))
            valid_dates = [
                _utc_datetime(match.get("date"))
                for match in recent
                if isinstance(match, Mapping) and _utc_datetime(match.get("date")) is not None
            ]
            if valid_dates:
                diagnostics["history_latest_match_at"] = max(valid_dates).isoformat()
                diagnostics["history_oldest_match_at"] = min(valid_dates).isoformat()
            diagnostics["history_order"] = "newest_first_by_parsed_utc_kickoff"
            statistics_coverage = {
                label: sum(
                    any(name in (match.get("statistics") or {}) for name in aliases)
                    for match in recent
                )
                for label, _group, aliases in _CORE_STATISTICS
            }
            matches_with_any_statistics = sum(
                bool(match.get("statistics")) for match in recent
            )
            matches_with_complete_core_statistics = sum(
                all(
                    any(name in (match.get("statistics") or {}) for name in aliases)
                    for _label, _group, aliases in _CORE_STATISTICS
                )
                for match in recent
            )
            core_observations = sum(statistics_coverage.values())
            core_target = len(recent) * len(_CORE_STATISTICS)
            diagnostics["statistics_coverage_by_metric"] = statistics_coverage
            diagnostics["matches_with_any_statistics"] = matches_with_any_statistics
            diagnostics["matches_with_complete_core_statistics"] = matches_with_complete_core_statistics
            diagnostics["core_statistics_completeness_pct"] = (
                round(core_observations / core_target * 100, 1) if core_target else 0.0
            )
            data_quality["history_source"] = (
                "cockroachdb_central_repository_plus_verified_sportmonks_candidates"
            )
            profile["verified_result_history_fallback"] = {
                "status": "applied",
                "fixture_id": fixture_id,
                "highlightly_match_id": str(highlightly_candidate.get("highlightly_match_id") or ""),
                "verified_at": verified_at.isoformat(),
                "tactical_evidence_updated": False,
            }
            summary["profiles_updated"] += 1
            summary["matches_added"] += 1
            fixture_added_for_candidate = True

        if not fixture_added_for_candidate:
            summary["candidates_rejected"] += 1

    for original, updated in zip(original_profiles, profiles):
        if isinstance(original, dict) and isinstance(updated, dict):
            original.clear()
            original.update(updated)
    return summary
