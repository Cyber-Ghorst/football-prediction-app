"""Highlightly match statistics and lineup corroboration for Sportmonks fixtures.

This module is diagnostic only. It never writes Highlightly values into Layer 2
profiles or prediction inputs. Fixture identity must match competition, country,
season, home/away orientation and kickoff within five minutes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from canonical_data import canonicalize_highlightly_match, match_identity
from competition_crosswalk import normalize_competition_name, normalize_country
from provider_core import normalize_team_name
from provider_corroboration import canonicalize_sportmonks_fixture
from sportmonks_layer2 import _team_statistics

_STAT_NAMES = {
    "ball possession": "Ball Possession",
    "possession": "Ball Possession",
    "pass accuracy": "Passes %",
    "passes accuracy": "Passes %",
    "accurate passes percentage": "Passes %",
    "shots on target": "Shots on Target",
    "shots off target": "Shots off Target",
    "total shots": "Total Shots",
    "shots": "Total Shots",
    "shots accuracy": "Shots Accuracy",
    "corner kicks": "Corner Kicks",
    "corners": "Corner Kicks",
    "tackles": "Tackles",
    "interceptions": "Interceptions",
    "blocked shots": "Blocked Shots",
    "fouls": "Fouls",
    "yellow cards": "Yellow Cards",
    "red cards": "Red Cards",
    "offsides": "Offsides",
    "saves": "Saves",
    "goalkeeper saves": "Saves",
}
_PERCENTAGE_KEYS = {"Ball Possession", "Passes %", "Shots Accuracy"}


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


def _season_value(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("year") or value.get("start")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _highlightly_rows(
    client: Any, competition: str, country: str | None, season: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset, limit, max_pages = 0, 100, 10
    for page_number in range(max_pages):
        page = client.matches(
            leagueName=competition,
            season=int(season),
            countryName=country,
            limit=limit,
            offset=offset,
        )
        rows.extend(page)
        if len(page) < limit:
            break
        offset += limit
    else:
        raise RuntimeError("Highlightly match pagination exceeded the safe 10-page limit.")

    valid: list[dict[str, Any]] = []
    for row in rows:
        league = row.get("league") or {}
        league_name = league.get("name") or row.get("leagueName")
        if not league_name or normalize_competition_name(league_name) != normalize_competition_name(competition):
            continue
        league_country = league.get("country") or {}
        row_country = (
            league_country.get("name") if isinstance(league_country, Mapping)
            else league_country if isinstance(league_country, str)
            else league.get("countryName") or row.get("countryName")
        )
        if country and (not row_country or normalize_country(row_country) != normalize_country(country)):
            continue
        supplied_season = _season_value(league.get("season") or row.get("season"))
        if supplied_season is not None and supplied_season != int(season):
            continue
        try:
            canonical = canonicalize_highlightly_match(
                row,
                competition_key="|".join((
                    normalize_competition_name(competition),
                    normalize_country(country or ""),
                )),
                season=int(season),
            )
        except (ValueError, TypeError, KeyError):
            continue
        valid.append({"raw": row, "canonical": canonical})
    return valid


def _highlightly_stat_value(name: str, value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).strip().replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None
    if name in _PERCENTAGE_KEYS and 0 <= number <= 1:
        number *= 100
    return round(number, 3)


def _normalize_highlightly_statistics(payload: Any, match_id: Any) -> dict[str, list[dict[str, Any]]]:
    """Normalize documented [{team, statistics:[{value,displayName}]}] response."""
    by_team: dict[str, list[dict[str, Any]]] = {}
    for team_row in _rows(payload):
        team = team_row.get("team") or {}
        team_name = team.get("name")
        if not team_name:
            continue
        normalized_team = normalize_team_name(team_name)
        observations = []
        for statistic in _rows(team_row.get("statistics")):
            display_name = str(statistic.get("displayName") or "").strip()
            canonical_name = _STAT_NAMES.get(display_name.casefold())
            raw_value = statistic.get("value")
            normalized_value = (
                _highlightly_stat_value(canonical_name, raw_value)
                if canonical_name else None
            )
            observations.append({
                "provider": "highlightly",
                "match_id": str(match_id),
                "team_id": team.get("id"),
                "team_name": str(team_name),
                "display_name": display_name,
                "canonical_name": canonical_name,
                "raw_value": raw_value,
                "normalized_value": normalized_value,
            })
        by_team[normalized_team] = observations
    return by_team


def _compare_statistics(
    sportmonks_values: Mapping[str, float],
    highlightly_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    hl_values = {
        row["canonical_name"]: row["normalized_value"]
        for row in highlightly_observations
        if row.get("canonical_name") and row.get("normalized_value") is not None
    }
    comparisons = {}
    for key in sorted(set(sportmonks_values) & set(hl_values)):
        sm_value = float(sportmonks_values[key])
        hl_value = float(hl_values[key])
        tolerance = 1.0 if key in _PERCENTAGE_KEYS else 0.5
        comparisons[key] = {
            "status": "agreement" if abs(sm_value - hl_value) <= tolerance else "conflict",
            "sportmonks": sm_value,
            "highlightly": hl_value,
            "absolute_difference": round(abs(sm_value - hl_value), 3),
            "tolerance": tolerance,
        }
    return comparisons


def _flatten_lineup_players(value: Any) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return players
    for item in value:
        if isinstance(item, list):
            players.extend(player for player in item if isinstance(player, dict))
        elif isinstance(item, dict):
            players.append(item)
    return [
        {
            "player_id": player.get("id"),
            "name": player.get("name"),
            "shirt_number": player.get("number"),
            "position": player.get("position"),
        }
        for player in players
    ]


def normalize_highlightly_lineups(
    payload: Mapping[str, Any], *, expected_home: str, expected_away: str,
    match_id: Any,
) -> dict[str, Any]:
    """Normalize documented homeTeam/awayTeam lineup payload after identity checks."""
    result = {}
    for side, expected in (("home", expected_home), ("away", expected_away)):
        team = payload.get(f"{side}Team") or {}
        actual_name = team.get("name")
        if not actual_name or normalize_team_name(actual_name) != normalize_team_name(expected):
            raise ValueError(f"Highlightly {side} lineup team does not match the selected fixture.")
        starters = _flatten_lineup_players(team.get("initialLineup"))
        substitutes = _flatten_lineup_players(team.get("substitutes"))
        result[side] = {
            "team_id": team.get("id"),
            "team_name": actual_name,
            "formation": team.get("formation"),
            "starting_players": starters,
            "substitutes": substitutes,
            "lineups_available": bool(starters),
            "confirmation_status": "provider_reported",
            "source": "highlightly",
            "match_id": str(match_id),
        }
    return result


def collect_highlightly_match_enrichment(
    *,
    client: Any,
    sportmonks_fixtures: list[dict[str, Any]],
    competition: str,
    country: str | None,
    season: int,
    home_team_name: str,
    away_team_name: str,
    selected_upcoming_fixture: dict[str, Any] | None = None,
    now: datetime | None = None,
    history_per_team: int = 10,
) -> dict[str, Any]:
    """Compare Highlightly stats for exact recent matches and fetch exact-match lineups."""
    fetched = now or datetime.now(timezone.utc)
    fetched = fetched.replace(tzinfo=timezone.utc) if fetched.tzinfo is None else fetched.astimezone(timezone.utc)
    rows = _highlightly_rows(client, competition, country, int(season))
    competition_key = "|".join((
        normalize_competition_name(competition), normalize_country(country or "")
    ))
    selected_names = {normalize_team_name(home_team_name), normalize_team_name(away_team_name)}

    sportmonks_records = []
    team_match_counts = {name: 0 for name in selected_names}
    for fixture in sportmonks_fixtures:
        canonical = canonicalize_sportmonks_fixture(
            fixture, competition=competition, country=country, season=int(season)
        )
        if not canonical:
            continue
        sides = {
            normalize_team_name(canonical["home"]["name"]),
            normalize_team_name(canonical["away"]["name"]),
        }
        if not (sides & selected_names):
            continue
        if canonical["status"] == "finished" and canonical["home_score"] is not None and canonical["away_score"] is not None:
            sportmonks_records.append((fixture, canonical))
    sportmonks_records.sort(key=lambda pair: pair[1]["kickoff_utc"], reverse=True)

    # Keep at most the latest N completed matches for each selected team.
    selected_fixture_ids: set[str] = set()
    for team_name in selected_names:
        count = 0
        for fixture, canonical in sportmonks_records:
            home_norm = normalize_team_name(canonical["home"]["name"])
            away_norm = normalize_team_name(canonical["away"]["name"])
            if team_name in {home_norm, away_norm} and count < max(1, int(history_per_team)):
                selected_fixture_ids.add(str(fixture.get("id")))
                count += 1

    stats_reports = []
    errors: dict[str, str] = {}
    stats_requests = 0
    for fixture, sportmonks_match in sportmonks_records:
        fixture_id = str(fixture.get("id"))
        if fixture_id not in selected_fixture_ids:
            continue
        match_row = next((item for item in rows if match_identity(sportmonks_match, item["canonical"])), None)
        if match_row is None:
            continue
        highlightly_id = match_row["raw"].get("id")
        if highlightly_id is None:
            continue
        try:
            stats_payload = client.statistics(highlightly_id)
            stats_requests += 1
            by_team = _normalize_highlightly_statistics(stats_payload, highlightly_id)
            team_reports = {}
            for side in ("home", "away"):
                team_name = sportmonks_match[side]["name"]
                team_norm = normalize_team_name(team_name)
                hl_observations = by_team.get(team_norm, [])
                team_id = int(next(
                    participant["id"] for participant in (fixture.get("participants") or [])
                    if str((participant.get("meta") or {}).get("location", "")).casefold() == side
                ))
                sm_values = _team_statistics(fixture, team_id)
                team_reports[side] = {
                    "team_name": team_name,
                    "sportmonks_statistics": sm_values,
                    "highlightly_observations": hl_observations,
                    "comparisons": _compare_statistics(sm_values, hl_observations),
                }
            stats_reports.append({
                "sportmonks_fixture_id": fixture_id,
                "highlightly_match_id": str(highlightly_id),
                "kickoff_utc": sportmonks_match["kickoff_utc"],
                "teams": team_reports,
            })
        except Exception as exc:
            errors[f"statistics:{highlightly_id}"] = str(exc)

    lineup_report = None
    lineup_requests = 0
    lineup_not_requested_reason = None
    if selected_upcoming_fixture is not None:
        selected_canonical = canonicalize_sportmonks_fixture(
            selected_upcoming_fixture,
            competition=competition, country=country, season=int(season),
        )
        if selected_canonical and selected_canonical["status"] == "scheduled":
            kickoff = datetime.fromisoformat(
                str(selected_canonical["kickoff_utc"]).replace("Z", "+00:00")
            )
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            in_lineup_window = kickoff - timedelta(minutes=40) <= fetched <= kickoff + timedelta(minutes=120)
            if not in_lineup_window:
                lineup_not_requested_reason = "Highlightly lineups are queried only from 40 minutes before kickoff until 120 minutes after kickoff."
            else:
                matched = next(
                    (item for item in rows if match_identity(selected_canonical, item["canonical"])),
                    None,
                )
                if matched is not None and matched["raw"].get("id") is not None:
                    highlightly_id = matched["raw"]["id"]
                    try:
                        payload = client.lineups(highlightly_id)
                        lineup_requests += 1
                        if payload:
                            lineup_report = normalize_highlightly_lineups(
                                payload,
                                expected_home=home_team_name,
                                expected_away=away_team_name,
                                match_id=highlightly_id,
                            )
                            lineup_report["sportmonks_fixture_id"] = str(selected_upcoming_fixture.get("id"))
                            lineup_report["highlightly_match_id"] = str(highlightly_id)
                            lineup_report["kickoff_utc"] = selected_canonical["kickoff_utc"]
                    except Exception as exc:
                        errors[f"lineups:{highlightly_id}"] = str(exc)
                else:
                    lineup_not_requested_reason = "No exact Highlightly fixture identity match was found."

    all_comparisons = [
        comparison
        for report in stats_reports
        for team in report["teams"].values()
        for comparison in team["comparisons"].values()
    ]
    return {
        "competition": competition,
        "country": country,
        "season": int(season),
        "highlightly_matches_scanned": len(rows),
        "statistics_matches_compared": len(stats_reports),
        "statistics_requests": stats_requests,
        "statistics_metric_agreements": sum(x["status"] == "agreement" for x in all_comparisons),
        "statistics_metric_conflicts": sum(x["status"] == "conflict" for x in all_comparisons),
        "upcoming_lineup_match_found": lineup_report is not None,
        "lineup_requests": lineup_requests,
        "lineup_not_requested_reason": lineup_not_requested_reason,
        "fetched_at": fetched.isoformat(),
        "statistics": stats_reports,
        "lineups": lineup_report,
        "errors": errors,
        "note": "Highlightly statistics and lineups are diagnostic corroboration only; Sportmonks prediction inputs are unchanged.",
    }
