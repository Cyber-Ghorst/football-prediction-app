"""Conservative provider-to-canonical entity crosswalk review.

Name matches are suggestions only. A persisted link requires an explicit
approval reason and an existing canonical entity.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any, Iterable, Mapping


# Define the grouped loader before importing repository/storage modules.
# This keeps the symbol available if an older report module imports this
# module during an import cycle.
def load_provider_entity_links_by_type(
    database_url: str,
    *,
    provider: str,
) -> dict[str, dict[str, str]]:
    """Load all entity-type links for one provider with a single read query."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    ensure_football_repository(database_url)
    grouped: dict[str, dict[str, str]] = {
        entity_type: {} for entity_type in ENTITY_TABLES
    }
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT entity_type, provider_entity_id, canonical_entity_id
                   FROM provider_entity_links
                   WHERE provider = %s
                   ORDER BY entity_type, provider_entity_id""",
                (provider_name,),
            )
            for entity_type, provider_id, canonical_id in cursor.fetchall():
                if entity_type in grouped:
                    grouped[entity_type][str(provider_id)] = str(canonical_id)
    return grouped


from football_repository import ensure_football_repository
from provider_data_storage import _connect

SUPPORTED_PROVIDERS = {
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro", "highlightly", "api_ninjas",
    "football_data_org",
}
ENTITY_TABLES = {
    "league": ("football_leagues", "league_id"),
    "season": ("football_seasons", "season_id"),
    "team": ("football_teams", "team_id"),
    "fixture": ("football_fixtures", "fixture_id"),
}


def provider_season_entity_id(competition_id: Any, season_id: Any) -> str:
    """Build a parent-scoped provider season key because season IDs are often reused per league."""
    competition = "" if competition_id is None else str(competition_id).strip()
    season = "" if season_id is None else str(season_id).strip()
    if not competition or not season:
        return ""
    return f"{competition}::{season}"


def normalize_entity_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\\s+", " ", text).strip()


def _season_start_year(value: Any) -> int | None:
    """Extract a season's first four-digit year for parent-scoped season review."""
    match = re.search(r"(?<!\\d)(20\\d{2})(?!\\d)", str(value or ""))
    return int(match.group(1)) if match else None


def _country_key(value: Any) -> str:
    key = normalize_entity_name(value)
    aliases = {
        "de": "germany", "deutschland": "germany",
        "england": "england", "es": "spain", "espana": "spain",
        "españa": "spain", "it": "italy", "italia": "italy",
        "fr": "france", "nl": "netherlands", "nederland": "netherlands",
        "pt": "portugal", "us": "united states", "usa": "united states",
        "united states of america": "united states",
    }
    return aliases.get(key, key)


def _candidate_name_key(provider: str, entity_type: str, value: Any) -> str:
    key = normalize_entity_name(value)
    if provider == "openligadb" and entity_type == "league":
        key = re.sub(r"\\s+herren$", "", key).strip()
        key = re.sub(r"\\s+20\\d{2}\\s+(?:20)?\\d{2}$", "", key).strip()
        aliases = {
            "1 fussball bundesliga": "bundesliga",
            "2 fussball bundesliga": "2 bundesliga",
        }
        key = aliases.get(key, key)
    return key


def _value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return None

def _display_value(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("displayName") or value.get("display_name")
    return str(value or "").strip()


def _is_numeric_identifier_name(value: Any) -> bool:
    """Reject provider IDs accidentally presented as human-readable league names."""
    return bool(re.fullmatch(r"\\d+", _display_value(value)))


# Stable provider-ID aliases are explicit review hints, never automatic links.
CURATED_PROVIDER_LEAGUE_NAME_ALIASES = {
    ("openligadb", "4936"): "La Liga",  # OpenLigaDB "LaLiga EA Sports"
    ("livescore_football", "3921"): "La Liga 2",  # LiveScoreFootball "Spanish LALIGA 2"
}


def build_entity_crosswalk_candidates(
    provider: str,
    entity_type: str,
    source_entities: Iterable[Mapping[str, Any]],
    canonical_entities: Iterable[Mapping[str, Any]],
    *,
    canonical_parent_ids: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Suggest exact name/country or parent-scoped season matches; never auto-link."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    if entity_type not in {"league", "season", "team"}:
        raise ValueError("entity_type must be league, season or team.")

    parent_map = {str(k): str(v) for k, v in (canonical_parent_ids or {}).items()}
    canonical = [row for row in canonical_entities if isinstance(row, Mapping)]
    output: list[dict[str, Any]] = []

    for source in source_entities:
        if not isinstance(source, Mapping):
            continue
        if entity_type == "league":
            source_id = _value(source, "provider_competition_id", "competition_id", "id", "slug")
            source_name = _value(source, "competition_name", "name", "league_name")
            source_country = _value(source, "country", "country_name")
            source_parent = None
        elif entity_type == "team":
            source_id = _value(source, "provider_team_id", "team_id", "id")
            source_name = _value(source, "team_name", "name", "display_name")
            source_country = _value(source, "country", "country_name")
            source_parent = None
        else:
            source_id = _value(source, "provider_season_id", "season_id", "id")
            source_name = _value(source, "season_name", "name", "season")
            source_country = None
            provider_parent = _value(source, "provider_competition_id", "competition_id", "league_id")
            source_parent = parent_map.get(str(provider_parent)) if provider_parent is not None else None
            source_parent_name = _value(source, "provider_competition_name", "competition_name", "league_name")

        base = {
            "provider": provider_name,
            "entity_type": entity_type,
            "provider_entity_id": str(source_id) if source_id is not None else None,
            "provider_name": str(source_name or ""),
            "provider_country": str(source_country or "") if entity_type != "season" else None,
            "provider_parent_id": str(provider_parent) if entity_type == "season" and provider_parent is not None else None,
            "provider_parent_name": str(source_parent_name or "") if entity_type == "season" else None,
            "canonical_parent_id": None,
            "canonical_entity_id": None,
            "canonical_name": None,
            "status": "unmatched",
            "reason": "",
            "match_method": None,
        }
        if source_id is None or not source_name:
            output.append({**base, "status": "invalid_source_identity",
                           "reason": "Provider entity ID and name are both required."})
            continue
        if entity_type == "league" and _is_numeric_identifier_name(source_name):
            output.append({**base, "status": "invalid_source_identity",
                           "reason": "Numeric provider league ID is not a verified display name; retrieve the provider's actual league name before crosswalk review."})
            continue
        if entity_type == "season" and source_parent is None:
            output.append({**base, "status": "parent_competition_unmapped",
                           "reason": "A verified provider-competition to canonical-competition link is required first."})
            continue

        curated_alias = (
            CURATED_PROVIDER_LEAGUE_NAME_ALIASES.get((provider_name, str(source_id)))
            if entity_type == "league" else None
        )
        source_key = _candidate_name_key(
            provider_name, entity_type, curated_alias or source_name
        )
        matches: list[tuple[str, str, str, str | None]] = []
        source_season_year = _season_start_year(source_name) if entity_type == "season" else None
        for target in canonical:
            if entity_type == "league":
                target_id = _value(target, "league_id", "canonical_entity_id")
                target_name = _value(target, "name", "competition_name")
                target_country = _value(target, "country", "country_name")
                exact_context = (
                    bool(source_country) and bool(target_country)
                    and _country_key(_display_value(source_country)) == _country_key(_display_value(target_country))
                )
            elif entity_type == "team":
                target_id = _value(target, "team_id", "canonical_entity_id")
                target_name = _value(target, "name", "team_name")
                target_country = _value(target, "country", "country_name")
                exact_context = (
                    bool(source_country) and bool(target_country)
                    and _country_key(source_country) == _country_key(target_country)
                )
            else:
                target_id = _value(target, "season_id", "canonical_entity_id")
                target_name = _value(target, "name", "season_name")
                target_parent = _value(target, "league_id", "canonical_league_id")
                exact_context = str(target_parent or "") == source_parent

            if target_id is None or not target_name or not exact_context:
                continue
            exact_name = (
                _candidate_name_key(provider_name, entity_type, target_name) == source_key
            )
            exact_start_year = (
                entity_type == "season"
                and source_season_year is not None
                and _season_start_year(target_name) == source_season_year
            )
            if exact_name or exact_start_year:
                match_method = (
                    "exact_start_year_and_parent"
                    if entity_type == "season" and exact_start_year and not exact_name
                    else "exact_name_and_country_or_parent"
                )
                matches.append((str(target_id), str(target_name), match_method, str(target_parent) if entity_type == "season" and target_parent is not None else None))

        if len(matches) == 1:
            match_method = (
                "curated_provider_id_alias" if curated_alias else matches[0][2]
            )
            output.append({
                **base, "canonical_entity_id": matches[0][0],
                "canonical_name": matches[0][1],
                "canonical_parent_id": matches[0][3],
                "status": "candidate_requires_manual_approval",
                "match_method": match_method,
                "reason": (
                    "Curated stable provider-ID alias and exact country context match; "
                    "explicit review is still mandatory."
                    if curated_alias else
                    "Exact season start year and verified parent competition match; "
                    "explicit review is still mandatory."
                    if match_method == "exact_start_year_and_parent" else
                    "Exact normalized name and required country/parent context match; "
                    "explicit review is still mandatory."
                ),
            })
        elif len(matches) > 1:
            output.append({
                **base, "status": "ambiguous_multiple_canonical_matches",
                "reason": f"{len(matches)} canonical entities match the exact identity criteria.",
            })
        else:
            output.append({
                **base, "status": "no_exact_contextual_match",
                "reason": "No exact name plus country/parent-context match; no link is proposed.",
            })
    return output


def load_provider_entity_links(
    database_url: str,
    *,
    provider: str,
    entity_type: str | None = None,
) -> dict[str, str]:
    """Load existing provider-scoped links without modifying them."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    if entity_type is not None and entity_type not in ENTITY_TABLES:
        raise ValueError("Unsupported canonical entity type.")
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    ensure_football_repository(database_url)
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            if entity_type:
                cursor.execute(
                    """SELECT provider_entity_id, canonical_entity_id
                       FROM provider_entity_links
                       WHERE provider = %s AND entity_type = %s
                       ORDER BY provider_entity_id""",
                    (provider_name, entity_type),
                )
            else:
                cursor.execute(
                    """SELECT provider_entity_id, canonical_entity_id
                       FROM provider_entity_links
                       WHERE provider = %s
                       ORDER BY entity_type, provider_entity_id""",
                    (provider_name,),
                )
            return {str(row[0]): str(row[1]) for row in cursor.fetchall()}


def save_explicit_provider_entity_links(
    database_url: str,
    *,
    links: list[Mapping[str, Any]],
    approval_reason: str,
) -> int:
    """Persist only explicitly reviewed links to existing canonical entities."""
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    reason = str(approval_reason or "").strip()
    if len(reason) < 12:
        raise ValueError("An explicit approval_reason of at least 12 characters is required.")
    if not isinstance(links, list) or not links:
        raise ValueError("At least one explicit provider entity link is required.")

    prepared = []
    for link in links:
        if not isinstance(link, Mapping):
            raise ValueError("Every link must be an object.")
        provider = str(link.get("provider") or "").strip().casefold()
        entity_type = str(link.get("entity_type") or "").strip().casefold()
        provider_id = str(link.get("provider_entity_id") or "").strip()
        canonical_id = str(link.get("canonical_entity_id") or "").strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("Unsupported provider in explicit link.")
        if entity_type not in ENTITY_TABLES:
            raise ValueError("Unsupported canonical entity type.")
        if not provider_id or not canonical_id:
            raise ValueError("Provider and canonical entity IDs are required.")
        table, primary_key = ENTITY_TABLES[entity_type]
        link_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{provider}:{entity_type}:{provider_id}",
        ))
        prepared.append((provider, entity_type, provider_id, canonical_id,
                         table, primary_key, link_id))

    ensure_football_repository(database_url)
    saved = 0
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for provider, entity_type, provider_id, canonical_id, table, primary_key, link_id in prepared:
                cursor.execute(
                    f"SELECT {primary_key} FROM {table} WHERE {primary_key} = %s",
                    (canonical_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError(
                        f"Canonical {entity_type} {canonical_id} does not exist."
                    )
                cursor.execute(
                    """SELECT canonical_entity_id FROM provider_entity_links
                       WHERE provider = %s AND entity_type = %s AND provider_entity_id = %s""",
                    (provider, entity_type, provider_id),
                )
                existing = cursor.fetchone()
                if existing and str(existing[0]) != canonical_id:
                    raise ValueError(
                        f"Conflicting existing link for {provider} {entity_type} {provider_id}."
                    )
                if existing:
                    continue
                cursor.execute(
                    """INSERT INTO provider_entity_links (
                           link_id, provider, entity_type, provider_entity_id, canonical_entity_id
                       ) VALUES (%s, %s, %s, %s, %s)""",
                    (link_id, provider, entity_type, provider_id, canonical_id),
                )
                cursor.execute(
                    """INSERT INTO provider_entity_link_approval_audit (
                           audit_id, link_id, provider, entity_type, provider_entity_id,
                           canonical_entity_id, approval_reason
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (str(uuid.uuid4()), link_id, provider, entity_type, provider_id,
                     canonical_id, reason),
                )
                saved += 1
    return saved


def _competition_type_from_payload(raw: Mapping[str, Any]) -> str | None:
    """Read an explicit provider competition-type field; never infer league/cup."""
    for parent_name in ("competition", "league", "tournament"):
        parent = raw.get(parent_name)
        if isinstance(parent, Mapping):
            value = _display_value(_value(
                parent, "type", "competitionType", "competition_type",
                "typeName", "type_name", "format",
            ))
            if value:
                return value
    return _display_value(_value(
        raw, "competition_type", "competitionType", "tournament_type"
    )) or None


def _country_from_payload(raw: Mapping[str, Any], team_key: str | None = None) -> str | None:
    country = _display_value(_value(raw, "country", "leagueCountry", "league_country"))
    if country:
        return country
    # football-data.org nests country context under competition.area and
    # homeTeam/awayTeam.area rather than a top-level country field.
    competition = raw.get("competition") if isinstance(raw.get("competition"), Mapping) else {}
    area = competition.get("area") if isinstance(competition.get("area"), Mapping) else {}
    country = _display_value(_value(area, "name", "country", "country_name"))
    if country:
        return country
    league = raw.get("league") if isinstance(raw.get("league"), Mapping) else {}
    country = _display_value(_value(league, "country", "country_name"))
    if country:
        return country
    if team_key:
        side = "team1" if team_key == "home" else "team2"
        modern_side = "homeTeam" if team_key == "home" else "awayTeam"
        team = (
            raw.get(modern_side) or raw.get(side) or raw.get(side.title())
            or raw.get(f"{team_key}_team") or {}
        )
        if isinstance(team, Mapping):
            country = _display_value(_value(team, "country", "teamCountry", "country_name"))
            if country:
                return country
            team_area = team.get("area") if isinstance(team.get("area"), Mapping) else {}
            return _display_value(_value(team_area, "name", "country", "country_name")) or None
        competitions = raw.get("competitions") or []
        if competitions and isinstance(competitions[0], Mapping):
            for competitor in competitions[0].get("competitors") or []:
                if not isinstance(competitor, Mapping):
                    continue
                if str(competitor.get("homeAway") or "").casefold() == team_key:
                    nested = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else competitor
                    return _display_value(_value(nested, "country", "country_name")) or None
    return None


def extract_provider_entities_from_observations(
    provider: str,
    observations: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Extract unique source leagues, seasons and teams from archived observations."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported provider.")
    entities: dict[str, dict[str, dict[str, Any]]] = {
        "leagues": {}, "seasons": {}, "teams": {},
    }

    def add(collection: str, source_id: Any, name: Any, **metadata: Any) -> None:
        if source_id is None or not str(source_id).strip() or not _display_value(name):
            return
        key = str(source_id)
        current = entities[collection].get(key)
        if current is None:
            entities[collection][key] = {
                "id": key, "name": _display_value(name), "provider": provider_name,
                "observation_count": 1, **metadata,
            }
            return
        current["observation_count"] += 1
        for field, value in metadata.items():
            if value and not current.get(field):
                current[field] = value
        if _display_value(name) != current["name"]:
            variants = set(current.get("name_variants", []))
            variants.add(_display_value(name))
            current["name_variants"] = sorted(variants)

    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        raw = observation.get("raw_payload")
        raw = raw if isinstance(raw, Mapping) else {}
        competition_id = observation.get("competition_key")
        # Never turn a numeric provider ID into a display name. Missing league
        # names stay absent and cannot enter crosswalk review as false candidates.
        competition_name = observation.get("competition_name")
        country = _display_value(observation.get("country")) or _country_from_payload(raw)
        add(
            "leagues", competition_id, competition_name, country=country,
            competition_type=_competition_type_from_payload(raw),
        )
        season_id = observation.get("season_key")
        season_name = observation.get("season_name") or season_id
        season_link_id = provider_season_entity_id(competition_id, season_id)
        add(
            "seasons", season_link_id, season_name,
            provider_competition_id=str(competition_id) if competition_id is not None else None,
            provider_competition_name=competition_name,
        )
        add(
            "teams", observation.get("home_team_key"), observation.get("home_team_name"),
            country=_display_value(observation.get("home_team_country")) or _country_from_payload(raw, "home") or country,
        )
        add(
            "teams", observation.get("away_team_key"), observation.get("away_team_name"),
            country=_display_value(observation.get("away_team_country")) or _country_from_payload(raw, "away") or country,
        )

    return {
        name: sorted(rows.values(), key=lambda row: (row["name"].casefold(), row["id"]))
        for name, rows in entities.items()
    }
