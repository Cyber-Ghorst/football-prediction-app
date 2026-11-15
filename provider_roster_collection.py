"""Season-scoped provider roster collection without cross-provider inference.

Highlightly rosters come from league-season standings. LiveScoreFootball
rosters are observed from fixtures within an explicitly supplied season date
window; those are participant observations, not a claim of complete squads.
"""
from __future__ import annotations

from typing import Any, Mapping


def _team_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    raw_id = value.get("id") or value.get("teamId") or value.get("team_id")
    name = value.get("name") or value.get("displayName") or value.get("teamName")
    if raw_id is None or not str(name or "").strip():
        return None
    return {
        "id": raw_id,
        "name": str(name).strip(),
        "shortName": value.get("shortName") or value.get("short_name"),
        "country": value.get("country") or value.get("countryName"),
        "logo": value.get("logo") or value.get("logoUrl"),
        "type": value.get("type"),
        "raw": dict(value),
    }


def _highlightly_standing_teams(payload: Any) -> list[dict[str, Any]]:
    """Extract only explicit team objects nested in standings rows/groups."""
    found: dict[str, dict[str, Any]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, Mapping):
            return
        team = node.get("team")
        if isinstance(team, Mapping):
            normalized = _team_record(team)
            if normalized:
                found.setdefault(str(normalized["id"]), normalized)
        for key in ("groups", "standings", "data", "rows", "items"):
            child = node.get(key)
            if isinstance(child, (list, Mapping)):
                visit(child)

    visit(payload)
    return [found[key] for key in sorted(found)]


def collect_highlightly_season_roster(
    client: Any,
    *,
    league: Mapping[str, Any],
    season: Mapping[str, Any],
) -> dict[str, Any]:
    """Fetch a league-season standings roster from Highlightly."""
    league_id = league.get("id")
    season_value = season.get("season", season.get("year", season.get("id")))
    if league_id is None or season_value is None:
        raise ValueError("Highlightly league ID and explicit season are required.")
    country = league.get("country")
    if not isinstance(country, Mapping):
        raise ValueError("Highlightly league country object is required.")
    country_name = country.get("name")
    if not str(country_name or "").strip():
        raise ValueError("Highlightly league country name is required.")
    payload = client._get("standings", {
        "leagueId": league_id,
        "season": season_value,
    })
    teams = _highlightly_standing_teams(payload)
    normalized_season = {
        "id": season_value,
        "league_id": league_id,
        "name": str(season_value),
        "start_date": season.get("startDate") or season.get("start_date"),
        "end_date": season.get("endDate") or season.get("end_date"),
    }
    normalized_league = {
        "id": league_id,
        "name": league.get("name"),
        "country": country,
        "type": league.get("type"),
        "logo": league.get("logo"),
    }
    return {
        "provider": "highlightly",
        "league": normalized_league,
        "season": normalized_season,
        "teams": teams,
        "team_evidence_method": "league_season_standings",
        "team_evidence_complete": bool(teams),
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
    }


def _livescore_competitors(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    competitions = event.get("competitions")
    if not isinstance(competitions, list):
        return []
    output = []
    for competition in competitions:
        if not isinstance(competition, Mapping):
            continue
        competitors = competition.get("competitors")
        if not isinstance(competitors, list):
            continue
        for competitor in competitors:
            if not isinstance(competitor, Mapping):
                continue
            team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else competitor
            normalized = _team_record(team)
            if normalized:
                normalized["home_away"] = competitor.get("homeAway") or competitor.get("home_away")
                output.append(normalized)
    return output


def collect_livescore_season_participants(
    client: Any,
    *,
    league: Mapping[str, Any],
    season: Mapping[str, Any],
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    """Collect observed fixture participants in a bounded, explicit season window."""
    league_id = league.get("slug") or league.get("id")
    season_value = season.get("year") or season.get("season") or season.get("id")
    league_name = league.get("name")
    country = league.get("country")
    if not league_id or not str(league_name or "").strip():
        raise ValueError("LiveScoreFootball league slug/ID and name are required.")
    if not str(country or "").strip():
        raise ValueError("LiveScoreFootball competition country is required.")
    if not season_value:
        raise ValueError("An explicit LiveScoreFootball season is required.")
    if not date_from or not date_to or date_from > date_to:
        raise ValueError("A valid inclusive season date window is required.")
    # The upstream fixtures endpoint currently rejects the documented-looking
    # date bounds with HTTP 400. Fetch its bounded paginated catalogue, then
    # apply the explicit season window locally; events without a parseable date
    # are excluded rather than assigned to a season.
    events = client.fixtures(str(league_id), status="all")
    selected_events = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_date = str(event.get("date") or event.get("startDate") or event.get("dateTime") or "")
        event_day = event_date[:10]
        if event_day and date_from <= event_day <= date_to:
            selected_events.append(event)
    found: dict[str, dict[str, Any]] = {}
    for event in selected_events:
        for team in _livescore_competitors(event):
            found.setdefault(str(team["id"]), team)
    return {
        "provider": "livescore_football",
        "league": {
            "id": str(league_id),
            "name": str(league_name).strip(),
            "country": country,
            "type": league.get("type"),
        },
        "season": {
            "id": str(season_value),
            "league_id": str(league_id),
            "name": str(season_value),
            "start_date": date_from,
            "end_date": date_to,
        },
        "teams": [found[key] for key in sorted(found)],
        "team_evidence_method": "season_window_fixture_participants",
        "team_evidence_complete": False,
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
        "fixtures_examined": len(events),
        "season_window_fixtures": len(selected_events),
    }
