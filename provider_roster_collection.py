"""Season-scoped provider roster collection without cross-provider inference.

Highlightly and LiveScoreFootball standings can provide season-roster evidence
when their returned season metadata validates. LiveScore fixture participants
remain a separate, incomplete observation method.
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
        "gender": value.get("gender") or value.get("genderScope") or value.get("gender_scope"),
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


def collect_highlightly_season_match_participants(
    client: Any,
    *,
    league: Mapping[str, Any],
    season: Mapping[str, Any],
    page_size: int = 100,
    max_pages: int = 20,
) -> dict[str, Any]:
    """Collect teams explicitly participating in every retrieved season match.

    This is a fallback when a tournament has no standings table (for example,
    a completed group-stage tournament). It remains participant evidence, not
    a club/national-team identity approval.
    """
    league_id = league.get("id")
    season_value = season.get("season", season.get("year", season.get("id")))
    if league_id is None or season_value is None:
        raise ValueError("Highlightly league ID and explicit season are required.")
    page_size = min(max(int(page_size), 1), 100)
    max_pages = max(1, min(int(max_pages), 20))
    found: dict[str, dict[str, Any]] = {}
    matches_examined = 0
    offset = 0
    total_count = None
    pagination_complete = False
    for _ in range(max_pages):
        matches = client.matches(
            leagueId=league_id, season=season_value,
            limit=page_size, offset=offset,
        )
        metadata = getattr(client, "last_metadata", {}) or {}
        pagination = metadata.get("pagination") if isinstance(metadata, Mapping) else None
        if isinstance(pagination, Mapping) and pagination.get("total_count") is not None:
            try:
                total_count = int(pagination["total_count"])
            except (TypeError, ValueError):
                total_count = None
        if not matches:
            pagination_complete = total_count is None or offset >= total_count
            break
        matches_examined += len(matches)
        for match in matches:
            if not isinstance(match, Mapping):
                continue
            for key in ("homeTeam", "awayTeam"):
                team = match.get(key)
                normalized = _team_record(team)
                if normalized:
                    found.setdefault(str(normalized["id"]), normalized)
        offset += len(matches)
        if total_count is not None and offset >= total_count:
            pagination_complete = True
            break
        if len(matches) < page_size:
            pagination_complete = True
            break
    teams = [found[key] for key in sorted(found)]
    return {
        "provider": "highlightly",
        "league": {
            "id": league_id,
            "name": league.get("name"),
            "country": league.get("country"),
            "type": league.get("type"),
        },
        "season": {
            "id": season_value,
            "league_id": league_id,
            "name": str(season_value),
        },
        "teams": teams,
        "team_evidence_method": "season_match_participants",
        "team_evidence_complete": pagination_complete and bool(teams),
        "matches_examined": matches_examined,
        "pagination_complete": pagination_complete,
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
    }


def _livescore_standing_teams(payload: Any) -> list[dict[str, Any]]:
    """Extract explicit team objects from nested LiveScore standings entries."""
    found: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, Mapping):
            return
        team = node.get("team")
        if isinstance(team, Mapping):
            record = _team_record(team)
            if record:
                found.append(record)
        for key in ("standings", "groups", "rows", "table", "data", "items", "entries", "children"):
            child = node.get(key)
            if isinstance(child, (list, Mapping)):
                visit(child)

    visit(payload)
    return found


def collect_livescore_season_standings(
    client: Any,
    *,
    league: Mapping[str, Any],
    season_year: int,
    retrieved_at: str,
) -> dict[str, Any]:
    """Capture a standings roster only when nested returned metadata proves the season."""
    slug = str(league.get("slug") or league.get("id") or "").strip()
    name = str(league.get("name") or "").strip()
    country = str(league.get("country") or "").strip()
    if not slug or not name or not country:
        raise ValueError("Exact LiveScore competition slug, name and country are required.")
    payload = client.standings(slug, season=season_year)
    base = {
        "provider": "livescore_football",
        "league": {"id": slug, "name": name, "country": country},
        "season": str(season_year),
        "team_evidence_method": "season_standings",
        "source_endpoint": f"/get/soccer/{slug}/standings",
        "requested_season_parameter": season_year,
        "source_retrieved_at": retrieved_at,
        "provider_payload": payload,
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
    }
    if not isinstance(payload, Mapping):
        return {
            **base, "teams": [], "team_evidence_complete": False,
            "status": "held_invalid_response_schema",
        }

    returned_year = payload.get("season")
    top_level_year_matches = (
        not isinstance(returned_year, bool)
        and str(returned_year) == str(season_year)
    )
    expected_labels = (
        f"{season_year}/{str(season_year + 1)[-2:]}",
        f"{season_year}-{str(season_year + 1)[-2:]}",
    )
    children = payload.get("children")
    matching_children = []
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, Mapping):
                continue
            standings = child.get("standings")
            if not isinstance(standings, Mapping):
                continue
            standings_year = standings.get("season")
            label_text = " ".join(
                str(child.get(key) or "") for key in ("name", "abbreviation")
            )
            label_matches = any(label in label_text for label in expected_labels)
            if (
                not isinstance(standings_year, bool)
                and str(standings_year) == str(season_year)
                and label_matches
            ):
                matching_children.append((child, standings, label_text.strip()))

    if not top_level_year_matches or len(matching_children) != 1:
        return {
            **base,
            "teams": [],
            "team_evidence_complete": False,
            "status": (
                "held_returned_season_mismatch"
                if not top_level_year_matches or not matching_children
                else "held_ambiguous_returned_season"
            ),
            "provider_returned_season": {
                "competition_season": returned_year,
                "matching_child_count": len(matching_children),
            },
        }

    child, standings, returned_label = matching_children[0]
    teams = _livescore_standing_teams({"entries": standings.get("entries", [])})
    ids = [str(team["id"]) for team in teams]
    names = [team["name"].casefold() for team in teams]
    duplicate_ids = len(ids) != len(set(ids))
    duplicate_names = len(names) != len(set(names))
    complete = bool(teams and not duplicate_ids and not duplicate_names)
    return {
        **base,
        "teams": teams if complete else [],
        "team_evidence_complete": complete,
        "status": "collected" if complete else "held_invalid_roster",
        "provider_returned_season": {
            "competition_season": returned_year,
            "standings_season": standings.get("season"),
            "child_id": child.get("id"),
            "child_label": returned_label,
        },
        "duplicate_team_ids": duplicate_ids,
        "duplicate_team_names": duplicate_names,
    }
