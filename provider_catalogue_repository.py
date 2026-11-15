"""Provider-neutral ingestion of competition, season and team-roster catalogues.

Each provider's records remain in their own namespaced identity space until a
separately reviewed crosswalk is approved. This importer does not import
fixtures, create cross-provider links, or touch prediction data.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from provider_data_storage import _connect

SUPPORTED_PROVIDERS = {
    "sportmonks", "highlightly", "api_ninjas", "api_football",
    "livescore_football", "openscores", "openligadb", "openfootball",
    "football_data_org", "bzzoiro", "open_matchday",
}


def provider_entity_id(provider: str, raw_id: Any) -> str:
    """Create a collision-safe source identity for a repository entity."""
    name = str(provider or "").strip().casefold()
    value = "" if raw_id is None else str(raw_id).strip()
    if name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    if not value:
        raise ValueError("Provider entity ID is required.")
    return f"{name}:{value}"


def _display(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("displayName") or value.get("label")
    result = str(value or "").strip()
    return result or None


def _date_value(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def prepare_provider_catalogue(
    provider: str,
    *,
    league: Mapping[str, Any],
    season: Mapping[str, Any],
    teams: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate and namespace one provider's league-season roster.

    Accepted rows are source records, not canonical cross-provider matches.
    Missing/ambiguous provider IDs are rejected rather than synthesized.
    """
    name = str(provider or "").strip().casefold()
    league_raw_id = league.get("id", league.get("league_id", league.get("competitionId")))
    season_raw_id = season.get("id", season.get("season_id", season.get("seasonId")))
    if league_raw_id is None or season_raw_id is None:
        raise ValueError("Provider league and season IDs are both required.")
    season_parent = season.get("league_id", season.get("leagueId", season.get("competitionId")))
    if season_parent is None or str(season_parent) != str(league_raw_id):
        raise ValueError("Provider season must explicitly belong to the supplied league.")
    league_name = _display(league.get("name") or league.get("leagueName"))
    country = _display(league.get("country") or league.get("countryName") or league.get("country_name"))
    if not league_name:
        raise ValueError("Provider league display name is required.")
    if not country:
        raise ValueError("Provider league country is required; international scopes must be explicit.")
    season_name = _display(season.get("name") or season.get("seasonName") or season.get("year"))
    if not season_name:
        raise ValueError("Provider season label is required.")

    normalized_teams = []
    seen_ids: set[str] = set()
    for row in teams:
        if not isinstance(row, Mapping):
            continue
        raw_id = row.get("id", row.get("team_id", row.get("teamId")))
        team_name = _display(row.get("name") or row.get("teamName"))
        if raw_id is None or not team_name:
            continue
        raw_key = str(raw_id).strip()
        if not raw_key or raw_key in seen_ids:
            continue
        seen_ids.add(raw_key)
        normalized_teams.append({
            "team_id": provider_entity_id(name, raw_id),
            "name": team_name,
            "short_name": _display(row.get("short_name") or row.get("shortName") or row.get("short_code")),
            "country": _display(row.get("country") or row.get("countryName")) or country,
            "logo_url": row.get("logo") or row.get("logo_url") or row.get("image_path"),
            "raw_payload": dict(row),
        })
    return {
        "provider": name,
        "league": {
            "league_id": provider_entity_id(name, league_raw_id),
            "name": league_name,
            "country": country,
            "competition_type": _display(league.get("type") or league.get("competitionType")),
            "logo_url": league.get("logo") or league.get("logo_url") or league.get("image_path"),
            "raw_payload": dict(league),
        },
        "season": {
            "season_id": provider_entity_id(name, season_raw_id),
            "league_id": provider_entity_id(name, league_raw_id),
            "name": season_name,
            "start_date": _date_value(season.get("start_date") or season.get("startDate")),
            "end_date": _date_value(season.get("end_date") or season.get("endDate")),
            "is_current": season.get("is_current") if isinstance(season.get("is_current"), bool) else None,
            "raw_payload": dict(season),
        },
        "teams": normalized_teams,
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
    }


def import_provider_catalogue(
    database_url: str,
    *,
    provider: str,
    league: Mapping[str, Any],
    season: Mapping[str, Any],
    teams: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Persist source-namespaced catalogue entities only; no fixture/link writes."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    prepared = prepare_provider_catalogue(
        provider, league=league, season=season, teams=teams,
    )
    source = prepared["provider"]
    league_row = prepared["league"]
    season_row = prepared["season"]
    team_rows = prepared["teams"]
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO football_leagues
                     (league_id, name, country, competition_type, logo_url,
                      source_provider, raw_payload)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (league_id) DO UPDATE SET
                     name = excluded.name, country = excluded.country,
                     competition_type = excluded.competition_type,
                     logo_url = excluded.logo_url,
                     source_provider = excluded.source_provider,
                     collected_at = NOW(),
                     raw_payload = excluded.raw_payload""",
                (league_row["league_id"], league_row["name"], league_row["country"],
                 league_row["competition_type"], league_row["logo_url"], source,
                 Jsonb(league_row["raw_payload"])),
            )
            cursor.execute(
                """INSERT INTO football_seasons
                     (season_id, league_id, name, start_date, end_date, is_current,
                      source_provider, raw_payload)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (season_id) DO UPDATE SET
                     league_id = excluded.league_id, name = excluded.name,
                     start_date = excluded.start_date, end_date = excluded.end_date,
                     is_current = excluded.is_current,
                     source_provider = excluded.source_provider,
                     collected_at = NOW(),
                     raw_payload = excluded.raw_payload""",
                (season_row["season_id"], season_row["league_id"], season_row["name"],
                 season_row["start_date"], season_row["end_date"], season_row["is_current"],
                 source, Jsonb(season_row["raw_payload"])),
            )
            for row in team_rows:
                cursor.execute(
                    """INSERT INTO football_teams
                         (team_id, name, short_name, country, logo_url,
                          source_provider, raw_payload)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (team_id) DO UPDATE SET
                         name = excluded.name, short_name = excluded.short_name,
                         country = excluded.country, logo_url = excluded.logo_url,
                         source_provider = excluded.source_provider,
                         collected_at = NOW(),
                         raw_payload = excluded.raw_payload""",
                    (row["team_id"], row["name"], row["short_name"], row["country"],
                     row["logo_url"], source, Jsonb(row["raw_payload"])),
                )
    return {
        "success": True,
        "provider": source,
        "league_id": league_row["league_id"],
        "season_id": season_row["season_id"],
        "teams_upserted": len(team_rows),
        "fixtures_imported": 0,
        "cross_provider_links_created": 0,
        "note": "Provider-native catalogue rows stored separately; no cross-provider identity was inferred.",
    }
