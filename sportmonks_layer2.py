"""Sportmonks v3 -> existing Layer 2 team-profile contract.

Only exact season/team IDs are used. Missing fields remain None; no synthetic
scores, opponent mappings, or availability ratings are created.
"""
from __future__ import annotations

from typing import Any

from form_analyzer import analyze_form, venue_rating
from tactical_indicators import analyze_tactics
from tactical_evidence import build_league_reference_statistics, build_tactical_evidence_profile


_COMPLETED = {"finished", "ft", "aet", "penalties", "after extra time", "after penalties"}
_STAT_ALIASES = {
    # Core tactical metrics consumed by tactical_indicators.py.
    "ball possession": "Ball Possession",
    "ball possession %": "Ball Possession",
    "pass accuracy": "Passes %",
    "passes accuracy": "Passes %",
    "accurate passes percentage": "Passes %",
    "pass success percentage": "Passes %",
    "successful passes percentage": "Passes %",
    "successful passes %": "Passes %",
    "passes %": "Passes %",
    "shots on goal": "Shots on Goal",
    "total shots": "Total Shots",
    "shots total": "Total Shots",
    "goal attempts": "Total Shots",
    "shots on target": "Shots on Target",
    "shots off target": "Shots off Target",
    "tackles": "Tackles",
    "interceptions": "Interceptions",
    "blocked shots": "Blocked Shots",
    "shots blocked": "Blocked Shots",
    "corners": "Corner Kicks",
    "corner kicks": "Corner Kicks",
    "accurate crosses": "Accurate Crosses",
    "successful dribbles": "Successful Dribbles",
    "successful headers": "Successful Headers",
    "big chances created": "Big Chances Created",
    "key passes": "Key Passes",
    "shots insidebox": "Shots Insidebox",
    "shots inside box": "Shots Insidebox",
    "counter attacks": "Counter Attacks",
    "counter-attacks": "Counter Attacks",
}
_STAT_TYPE_ID_NAMES = {1527: "counter attacks"}
_PERCENTAGE_STATS = {"Ball Possession", "Passes %"}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            return [data]
    return []


def _participants(fixture: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    home = away = None
    for participant in _rows(fixture.get("participants")):
        location = str((participant.get("meta") or {}).get("location") or "").casefold()
        if location == "home":
            home = participant
        elif location == "away":
            away = participant
    return home, away


def _state(fixture: dict[str, Any]) -> str:
    state = fixture.get("state") or {}
    # Sportmonks documents finished fixture state IDs 5, 7 and 8.
    try:
        if int(fixture.get("state_id")) in {5, 7, 8}:
            return "finished"
    except (TypeError, ValueError):
        pass
    label = str(state.get("short_name") or state.get("name") or "").strip().casefold()
    if label in _COMPLETED or any(x in label for x in ("finished", "full time", "after extra", "after penalties")):
        return "finished"
    if any(x in label for x in ("live", "in play", "half time", "1st half", "2nd half", "extra time", "penalty")):
        return "live"
    if label in {"ns", "not started", "scheduled", "tbd"} or any(x in label for x in ("not started", "scheduled", "to be played")):
        return "scheduled"
    return "unknown"


def _scores(fixture: dict[str, Any], home_id: int, away_id: int) -> tuple[int | None, int | None]:
    rows = _rows(fixture.get("scores"))
    current = [r for r in rows if str(r.get("description") or "").casefold() == "current"]
    candidates = current or rows
    if not candidates:
        return None, None
    values: dict[int, int] = {}
    for row in candidates:
        participant_id = row.get("participant_id")
        score = row.get("score")
        goals = score.get("goals") if isinstance(score, dict) else None
        if participant_id is not None and goals is not None:
            try:
                values[int(participant_id)] = int(goals)
            except (TypeError, ValueError):
                continue
    return values.get(home_id), values.get(away_id)


def _stat_name(row: dict[str, Any]) -> str:
    stat_type = row.get("type") or {}
    if isinstance(stat_type, dict):
        name = str(stat_type.get("name") or "").strip().casefold()
        if name:
            return name
        try:
            return _STAT_TYPE_ID_NAMES.get(int(stat_type.get("id")), "")
        except (TypeError, ValueError):
            return ""
    return str(stat_type).strip().casefold()


def _stat_value(row: dict[str, Any]) -> Any:
    data = row.get("data")
    if isinstance(data, dict):
        return data.get("value")
    return data if data is not None else row.get("value")


def _normalize_stat_value(key: str, value: Any) -> float | None:
    """Normalize numeric statistics; percentage fractions become 0-100 values."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    had_percent_sign = text.endswith("%")
    if had_percent_sign:
        text = text[:-1].strip()
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if key in _PERCENTAGE_STATS and not had_percent_sign and 0 < number <= 1:
        number *= 100
    return round(number, 3)


def _fixture_statistics_index(fixture: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Parse a fixture's provider statistics once, grouped by participant ID."""
    indexed: dict[int, dict[str, Any]] = {}
    fixture_id = fixture.get("id")
    season_id = fixture.get("season_id")
    updated_at = fixture.get("updated_at") or fixture.get("last_processed_at")

    for row in _rows(fixture.get("statistics")):
        try:
            team_id = int(row.get("participant_id"))
        except (TypeError, ValueError):
            continue

        team_data = indexed.setdefault(team_id, {
            "statistics": {},
            "provenance": [],
            "raw_diagnostics": [],
        })
        stat_type = row.get("type") or {}
        raw_name = (
            stat_type.get("name")
            if isinstance(stat_type, dict)
            else str(stat_type or "")
        )
        normalized_name = _stat_name(row)
        canonical_name = _STAT_ALIASES.get(normalized_name)
        raw_value = _stat_value(row)
        normalized_value = (
            _normalize_stat_value(canonical_name, raw_value)
            if canonical_name is not None
            else None
        )

        team_data["raw_diagnostics"].append({
            "provider": "sportmonks",
            "fixture_id": fixture_id,
            "participant_id": team_id,
            "statistic_type_id": stat_type.get("id") if isinstance(stat_type, dict) else None,
            "statistic_name_raw": str(raw_name or ""),
            "canonical_name": canonical_name,
            "raw_value": raw_value,
            "normalized_value": normalized_value,
            "mapping_status": "mapped" if canonical_name is not None else "unmapped",
        })

        if canonical_name is None or normalized_value is None:
            continue

        team_data["statistics"][canonical_name] = normalized_value
        team_data["provenance"].append({
            "provider": "sportmonks",
            "fixture_id": fixture_id,
            "season_id": season_id,
            "fixture_updated_at": updated_at,
            "statistic_type_id": stat_type.get("id") if isinstance(stat_type, dict) else None,
            "statistic_name": normalized_name,
            "canonical_name": canonical_name,
            "raw_value": raw_value,
            "normalized_value": normalized_value,
        })

    return indexed


def _team_statistics(fixture: dict[str, Any], team_id: int) -> dict[str, float]:
    """Compatibility wrapper; profile collection uses the shared fixture index."""
    return _fixture_statistics_index(fixture).get(team_id, {}).get("statistics", {})


def _team_statistics_provenance(fixture: dict[str, Any], team_id: int) -> list[dict[str, Any]]:
    """Compatibility wrapper for source-level normalized observations."""
    return _fixture_statistics_index(fixture).get(team_id, {}).get("provenance", [])


def _team_statistics_raw_diagnostics(fixture: dict[str, Any], team_id: int) -> list[dict[str, Any]]:
    """Compatibility wrapper for all provider statistic rows, mapped or not."""
    return _fixture_statistics_index(fixture).get(team_id, {}).get("raw_diagnostics", [])


def standings_strength(rows: list[dict[str, Any]]) -> dict[int, float]:
    ranks: dict[int, float] = {}
    for row in rows:
        participant_id = row.get("participant_id")
        rank = row.get("position") or row.get("rank")
        if participant_id is None or rank is None:
            continue
        try:
            ranks[int(participant_id)] = float(rank)
        except (TypeError, ValueError):
            continue
    if not ranks:
        return {}
    maximum = max(ranks.values())
    return {team_id: (maximum - rank + 1) / maximum * 100 for team_id, rank in ranks.items()}


def collect_sportmonks_team_profile(
    team: dict[str, Any],
    season_id: int,
    fixtures: list[dict[str, Any]],
    standings: list[dict[str, Any]],
    league_reference_statistics: dict[str, list[float]] | None = None,
    fixture_statistics_indexes: dict[int, dict[int, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Build a profile from one validated Sportmonks season collection."""
    team_id = int(team["id"])
    strength_map = standings_strength(standings)
    matches: list[dict[str, Any]] = []
    history_diagnostics = {
        "fixtures_scanned": len(fixtures),
        "same_season_fixtures": 0,
        "season_eligible_fixtures": 0,
        "fixtures_missing_season_id": 0,
        "team_fixtures": 0,
        "completed_fixtures": 0,
        "fixtures_with_valid_scores": 0,
        "excluded_wrong_season": 0,
        "excluded_missing_participants": 0,
        "excluded_other_team": 0,
        "excluded_not_completed": 0,
        "excluded_missing_scores": 0,
    }

    for fixture in fixtures:
        fixture_index = (
            fixture_statistics_indexes.get(id(fixture))
            if fixture_statistics_indexes is not None
            else _fixture_statistics_index(fixture)
        ) or {}
        fixture_season_id = fixture.get("season_id")
        if fixture_season_id is not None:
            try:
                if int(fixture_season_id) != int(season_id):
                    history_diagnostics["excluded_wrong_season"] += 1
                    continue
            except (TypeError, ValueError):
                history_diagnostics["excluded_wrong_season"] += 1
                continue
            history_diagnostics["same_season_fixtures"] += 1
        else:
            # Existing collection behavior accepts records with no season_id;
            # expose them separately rather than silently calling them same-season.
            history_diagnostics["fixtures_missing_season_id"] += 1
        history_diagnostics["season_eligible_fixtures"] += 1

        home, away = _participants(fixture)
        if not home or not away:
            history_diagnostics["excluded_missing_participants"] += 1
            continue
        try:
            home_id, away_id = int(home["id"]), int(away["id"])
        except (KeyError, TypeError, ValueError):
            history_diagnostics["excluded_missing_participants"] += 1
            continue
        if team_id not in {home_id, away_id}:
            history_diagnostics["excluded_other_team"] += 1
            continue
        history_diagnostics["team_fixtures"] += 1
        if _state(fixture) != "finished":
            history_diagnostics["excluded_not_completed"] += 1
            continue
        history_diagnostics["completed_fixtures"] += 1
        home_goals, away_goals = _scores(fixture, home_id, away_id)
        if home_goals is None or away_goals is None:
            history_diagnostics["excluded_missing_scores"] += 1
            continue
        history_diagnostics["fixtures_with_valid_scores"] += 1
        is_home = team_id == home_id
        opponent = away if is_home else home
        opponent_id = away_id if is_home else home_id
        matches.append({
            "fixture_id": fixture.get("id"),
            "date": fixture.get("starting_at"),
            "venue": "home" if is_home else "away",
            "opponent_id": opponent_id,
            "opponent_name": opponent.get("name"),
            "goals_for": home_goals if is_home else away_goals,
            "goals_against": away_goals if is_home else home_goals,
            "opponent_strength": strength_map.get(opponent_id),
            "statistics": fixture_index.get(team_id, {}).get("statistics", {}),
            "opponent_statistics": fixture_index.get(opponent_id, {}).get("statistics", {}),
            "statistics_provenance": fixture_index.get(team_id, {}).get("provenance", []),
            "statistics_raw_diagnostics": fixture_index.get(team_id, {}).get("raw_diagnostics", []),
        })

    matches.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    recent = matches[:10]
    form = analyze_form(recent)
    tactics = analyze_tactics(recent)
    if league_reference_statistics is None:
        league_team_match_statistics = []
        for reference_fixture in fixtures:
            reference_home, reference_away = _participants(reference_fixture)
            for participant in (reference_home, reference_away):
                if not participant or participant.get("id") is None:
                    continue
                try:
                    participant_id = int(participant["id"])
                except (TypeError, ValueError):
                    continue
                participant_statistics = _team_statistics(reference_fixture, participant_id)
                if participant_statistics:
                    league_team_match_statistics.append(participant_statistics)
        league_reference = build_league_reference_statistics(league_team_match_statistics)
    else:
        league_reference = league_reference_statistics
    tactical_evidence = build_tactical_evidence_profile(
        recent, league_reference, team.get("name") or f"Team {team_id}"
    )
    return {
        "id": team_id,
        "name": team.get("name") or f"Team {team_id}",
        "logo": team.get("image_path"),
        "matches": recent,
        "home_rating": venue_rating(recent, "home"),
        "away_rating": venue_rating(recent, "away"),
        # Injury data is not assumed from absence in the fixture feed.
        "player_availability": None,
        "playing_style": tactics["playing_style"],
        "defensive_structure": tactics["defensive_structure"],
        "attacking_approach": tactics["attacking_approach"],
        "tactical_compatibility": None,
        "form_summary": form,
        "tactical_summary": tactics,
        "tactical_evidence": tactical_evidence,
        "availability": {
            "injury_data_available": False,
            "reported_injuries": None,
            "injuries": [],
            "player_availability": None,
            "note": "No verified injury feed was included in this collection; player availability remains unknown.",
        },
        "lineups": {"lineups_available": False, "teams": [],
                    "note": "Lineups are not used unless a verified lineup response is available."},
        "upcoming_fixture_id": None,
        "history_collection_diagnostics": history_diagnostics,
        "data_quality": {
            "provider": "sportmonks",
            "season_id": int(season_id),
            "matches_returned": len(recent),
            "goals_complete": len(recent) >= 5,
            "opponent_strength_matches": sum(m.get("opponent_strength") is not None for m in recent),
            "statistics_matches": sum(bool(m.get("statistics")) for m in recent),
            "statistics_observations": sum(len(m.get("statistics_provenance") or []) for m in recent),
            "statistics_raw_observations": sum(len(m.get("statistics_raw_diagnostics") or []) for m in recent),
            "statistics_unmapped_observations": sum(
                sum(row.get("mapping_status") == "unmapped" for row in (m.get("statistics_raw_diagnostics") or []))
                for m in recent
            ),
            "fixtures_scanned": len(fixtures),
        },
    }


def find_exact_match_fixture(
    fixtures: list[dict[str, Any]],
    home_team_id: int,
    away_team_id: int,
    season_id: int,
    now_timestamp: int | None = None,
) -> dict[str, Any] | None:
    """Find the closest exact home-v-away fixture in the selected season, at any status."""
    import time

    current = int(now_timestamp if now_timestamp is not None else time.time())
    candidates: list[dict[str, Any]] = []
    for fixture in fixtures:
        try:
            if int(fixture.get("season_id")) != int(season_id):
                continue
            kickoff = int(fixture.get("starting_at_timestamp"))
        except (TypeError, ValueError):
            continue
        home, away = _participants(fixture)
        if not home or not away:
            continue
        try:
            if int(home.get("id")) != int(home_team_id) or int(away.get("id")) != int(away_team_id):
                continue
        except (TypeError, ValueError):
            continue
        candidates.append(fixture)
    future = [row for row in candidates if int(row["starting_at_timestamp"]) > current]
    if future:
        return min(future, key=lambda row: int(row["starting_at_timestamp"]))
    return max(candidates, key=lambda row: int(row["starting_at_timestamp"])) if candidates else None


def find_upcoming_match_fixture(
    fixtures: list[dict[str, Any]],
    home_team_id: int,
    away_team_id: int,
    season_id: int,
    now_timestamp: int | None = None,
) -> dict[str, Any] | None:
    """Find the exact scheduled home-v-away fixture; never substitute a team's other match."""
    import time

    current = int(now_timestamp if now_timestamp is not None else time.time())
    candidates: list[dict[str, Any]] = []
    for fixture in fixtures:
        try:
            if int(fixture.get("season_id")) != int(season_id):
                continue
        except (TypeError, ValueError):
            continue
        if _state(fixture) != "scheduled":
            continue
        home, away = _participants(fixture)
        if not home or not away:
            continue
        try:
            if int(home.get("id")) != int(home_team_id) or int(away.get("id")) != int(away_team_id):
                continue
            kickoff = int(fixture.get("starting_at_timestamp"))
        except (TypeError, ValueError):
            continue
        if kickoff <= current:
            continue
        candidates.append(fixture)
    return min(candidates, key=lambda row: int(row["starting_at_timestamp"])) if candidates else None


def extract_sportmonks_match_details(
    fixture: dict[str, Any],
    home_team_id: int,
    away_team_id: int,
    season_id: int,
) -> dict[str, Any]:
    """Extract fixture-specific lineups and sidelined reports without inventing availability."""
    if int(fixture.get("season_id", -1)) != int(season_id):
        raise ValueError("Sportmonks match detail season does not match the selected season.")
    home, away = _participants(fixture)
    if not home or not away:
        raise ValueError("Sportmonks match detail is missing home/away participants.")
    if int(home.get("id", -1)) != int(home_team_id) or int(away.get("id", -1)) != int(away_team_id):
        raise ValueError("Sportmonks match detail does not match the selected home/away teams.")

    team_ids = {"home": int(home_team_id), "away": int(away_team_id)}
    lineups_by_team: dict[int, list[dict[str, Any]]] = {team_ids["home"]: [], team_ids["away"]: []}
    for row in _rows(fixture.get("lineups")):
        try:
            team_id = int(row.get("team_id"))
        except (TypeError, ValueError):
            continue
        if team_id not in lineups_by_team:
            continue
        player = row.get("player") or {}
        lineup_type = row.get("type") or {}
        lineups_by_team[team_id].append({
            "player_id": row.get("player_id") or player.get("id"),
            "player_name": row.get("player_name") or player.get("name"),
            "jersey_number": row.get("jersey_number"),
            "position": (row.get("position") or {}).get("name") if isinstance(row.get("position"), dict) else row.get("position"),
            "formation_position": row.get("formation_position"),
            "formation_field": row.get("formation_field"),
            "lineup_type": lineup_type.get("name") if isinstance(lineup_type, dict) else str(lineup_type or ""),
        })

    formations: dict[int, str] = {}
    for row in _rows(fixture.get("formations")):
        try:
            participant_id = int(row.get("participant_id"))
        except (TypeError, ValueError):
            continue
        if participant_id in lineups_by_team and row.get("formation"):
            formations[participant_id] = str(row["formation"])

    sidelined_by_team: dict[int, list[dict[str, Any]]] = {team_ids["home"]: [], team_ids["away"]: []}
    for row in _rows(fixture.get("sidelined")):
        participant_value = row.get("participant_id") or row.get("team_id")
        try:
            participant_id = int(participant_value)
        except (TypeError, ValueError):
            continue
        if participant_id not in sidelined_by_team:
            continue
        player = row.get("player") or {}
        sideline = row.get("sideline") or {}
        sidelined_type = row.get("type") or {}
        sidelined_by_team[participant_id].append({
            "player_id": row.get("player_id") or player.get("id"),
            "player_name": player.get("name") or row.get("player_name"),
            "category": sideline.get("category") or row.get("category"),
            "reason": sidelined_type.get("name") if isinstance(sidelined_type, dict) else str(sidelined_type or ""),
            "start_date": sideline.get("start_date") or row.get("start_date"),
            "end_date": sideline.get("end_date") or row.get("end_date"),
            "source": "sportmonks",
            "fixture_id": fixture.get("id"),
        })

    teams: dict[str, dict[str, Any]] = {}
    availability: dict[str, dict[str, Any]] = {}
    for side, team_id in team_ids.items():
        lineup_rows = lineups_by_team[team_id]
        sidelined_rows = sidelined_by_team[team_id]
        teams[side] = {
            "team_id": team_id,
            "team_name": home.get("name") if side == "home" else away.get("name"),
            "formation": formations.get(team_id),
            "players": lineup_rows,
            "lineups_available": bool(lineup_rows),
            # Sportmonks can return predictive as well as confirmed lineups.
            # Do not mark confirmed unless the fixture metadata explicitly proves it.
            "confirmation_status": "unknown",
            "source": "sportmonks",
            "fixture_id": fixture.get("id"),
        }
        availability[side] = {
            "injury_data_available": bool(sidelined_rows),
            "reported_unavailable_count": len(sidelined_rows) if sidelined_rows else None,
            "reported_sidelined": sidelined_rows,
            "player_availability": None,
            "source": "sportmonks" if sidelined_rows else None,
            "fixture_id": fixture.get("id"),
            "note": "Provider-reported sidelined records are shown as reported; no availability score is inferred.",
        }
    return {
        "fixture_id": fixture.get("id"),
        "season_id": int(season_id),
        "kickoff": fixture.get("starting_at"),
        "teams": teams,
        "availability": availability,
        "source": "sportmonks",
    }



def load_repository_season_snapshot(
    database_url: str,
    season_id: int | str,
) -> dict[str, Any]:
    """Load one season's teams, fixtures and normalized statistics for reuse."""
    from football_repository import (
        get_repository_fixtures,
        get_repository_fixture_statistics,
        get_repository_teams,
    )

    canonical_season_id = str(season_id)
    teams = get_repository_teams(database_url, season_id=canonical_season_id)
    fixture_rows = get_repository_fixtures(
        database_url, season_id=canonical_season_id, limit=2000
    )
    fixture_ids = [str(row["fixture_id"]) for row in fixture_rows]
    normalized_statistics = get_repository_fixture_statistics(
        database_url, fixture_ids
    )
    return {
        "season_id": canonical_season_id,
        "teams": teams,
        "fixtures": fixture_rows,
        "statistics": normalized_statistics,
    }


def collect_repository_team_profiles(
    database_url: str,
    team_ids: list[int | str] | tuple[int | str, ...],
    season_id: int | str,
    standings: list[dict[str, Any]] | None = None,
    season_snapshot: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build multiple profiles from one shared season snapshot."""
    canonical_season_id = str(season_id)
    snapshot = season_snapshot or load_repository_season_snapshot(
        database_url, canonical_season_id
    )
    if str(snapshot.get("season_id")) != canonical_season_id:
        raise ValueError("Cached central repository snapshot belongs to a different season.")
    canonical_team_ids = list(dict.fromkeys(str(value) for value in team_ids))
    teams = snapshot.get("teams") or []
    fixture_rows = snapshot.get("fixtures") or []
    normalized_statistics = snapshot.get("statistics") or []
    team_rows = {
        str(row.get("team_id")): row
        for row in teams
        if str(row.get("team_id")) in canonical_team_ids
    }
    missing = [value for value in canonical_team_ids if value not in team_rows]
    if missing:
        raise ValueError(
            "Team(s) are not present in central season "
            f"{canonical_season_id}: {', '.join(missing)}."
        )

    statistics_by_fixture: dict[str, list[dict[str, Any]]] = {}
    for statistic_row in normalized_statistics:
        raw_statistic = statistic_row.get("raw_payload")
        if not isinstance(raw_statistic, dict):
            raw_statistic = {
                "participant_id": (
                    str(statistic_row.get("team_id") or "").split(":", 1)[-1] or None
                ),
                "type": {
                    "id": statistic_row.get("provider_statistic_id"),
                    "name": statistic_row.get("statistic_type"),
                },
                "data": {"value": statistic_row.get("statistic_value")},
            }
        else:
            raw_statistic = dict(raw_statistic)
        raw_statistic.setdefault(
            "participant_id",
            str(statistic_row.get("team_id") or "").split(":", 1)[-1] or None,
        )
        raw_statistic.setdefault(
            "type",
            {
                "id": statistic_row.get("provider_statistic_id"),
                "name": statistic_row.get("statistic_type"),
            },
        )
        if "data" not in raw_statistic:
            raw_statistic["data"] = {
                "value": statistic_row.get("statistic_value")
            }
        statistics_by_fixture.setdefault(
            str(statistic_row.get("fixture_id")), []
        ).append(raw_statistic)

    provider_fixtures = []
    for row in fixture_rows:
        raw_fixture = row.get("raw_payload")
        if not isinstance(raw_fixture, dict):
            continue
        fixture_payload = dict(raw_fixture)
        normalized_rows = statistics_by_fixture.get(str(row.get("fixture_id")))
        if normalized_rows:
            fixture_payload["statistics"] = normalized_rows
        provider_fixtures.append(fixture_payload)
    if not provider_fixtures:
        raise ValueError(
            f"No archived provider fixture payloads are available for season {canonical_season_id}."
        )

    try:
        numeric_season_id = int(canonical_season_id.split(":", 1)[-1])
        numeric_team_ids = {
            value: int(value.split(":", 1)[-1]) for value in canonical_team_ids
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Central repository IDs are not valid Sportmonks IDs.") from exc

    # The league-wide empirical reference is identical for both selected
    # teams. Calculate it once instead of rescanning every fixture/stat row
    # separately for each profile.
    fixture_statistics_indexes = {
        id(reference_fixture): _fixture_statistics_index(reference_fixture)
        for reference_fixture in provider_fixtures
    }
    league_team_match_statistics = []
    for reference_fixture in provider_fixtures:
        reference_index = fixture_statistics_indexes[id(reference_fixture)]
        reference_home, reference_away = _participants(reference_fixture)
        for participant in (reference_home, reference_away):
            if not participant or participant.get("id") is None:
                continue
            try:
                participant_id = int(participant["id"])
            except (TypeError, ValueError):
                continue
            participant_statistics = reference_index.get(participant_id, {}).get("statistics", {})
            if participant_statistics:
                league_team_match_statistics.append(participant_statistics)
    league_reference = build_league_reference_statistics(league_team_match_statistics)

    profiles: dict[str, dict[str, Any]] = {}
    for canonical_team_id in canonical_team_ids:
        team_row = team_rows[canonical_team_id]
        provider_team_id = canonical_team_id.split(":", 1)[-1]
        team = {
            "id": numeric_team_ids[canonical_team_id],
            "name": team_row.get("name") or f"Team {provider_team_id}",
            "image_path": None,
        }
        profile = collect_sportmonks_team_profile(
            team,
            numeric_season_id,
            provider_fixtures,
            standings or [],
            league_reference_statistics=league_reference,
            fixture_statistics_indexes=fixture_statistics_indexes,
        )
        profile["data_quality"]["history_source"] = "cockroachdb_central_repository"
        profile["data_quality"]["repository_fixture_rows"] = len(fixture_rows)
        profile["data_quality"]["repository_fixture_payloads"] = len(provider_fixtures)
        profile["data_quality"]["normalized_statistics_rows"] = len(normalized_statistics)
        profile["data_quality"]["fixtures_with_normalized_statistics"] = len(
            statistics_by_fixture
        )
        profiles[canonical_team_id] = profile
    return profiles


def collect_repository_team_profile(database_url, team_id, season_id, standings=None):
    """Backward-compatible single-team wrapper around the shared repository reader."""
    return collect_repository_team_profiles(database_url, [team_id], season_id, standings)[str(team_id)]
