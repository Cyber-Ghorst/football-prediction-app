"""Promote explicitly crosswalked free-source fixtures into the canonical catalogue.

The module never creates or changes canonical leagues, seasons or teams. It only
inserts future scheduled fixtures whose four source entity IDs already have
human-approved links to existing Sportmonks canonical entities. It preserves
source provenance and refuses conflicting kickoff/identity observations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from football_repository import ensure_football_repository
from provider_data_storage import _connect, load_provider_observation_snapshots
from provider_entity_crosswalk import load_provider_entity_links

SUPPORTED_PROVIDERS = {
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro",
}
PROMOTION_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS football_fixture_sources (
    source_link_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_fixture_id TEXT NOT NULL,
    fixture_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    source_url TEXT,
    licence TEXT,
    observed_at TIMESTAMPTZ,
    raw_payload JSONB,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_fixture_id)
);
CREATE INDEX IF NOT EXISTS football_fixture_sources_fixture_idx
    ON football_fixture_sources (fixture_id, provider);
CREATE TABLE IF NOT EXISTS free_fixture_promotion_audit (
    audit_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_fixture_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    canonical_fixture_id TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_fixture_id, snapshot_id)
);
"""


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _provider_fixture_id(provider: str, value: Any) -> str:
    return f"{provider}:{str(value).strip()}"


def assess_free_fixture_observation(
    provider: str,
    observation: Mapping[str, Any],
    *,
    snapshot_id: str,
    snapshot_retrieved_at: Any,
    league_links: Mapping[str, str],
    season_links: Mapping[str, str],
    team_links: Mapping[str, str],
    canonical_entities: Mapping[str, Mapping[str, Mapping[str, Any]]],
    now: datetime,
    max_age_hours: int = 24,
    window_days: int = 7,
) -> dict[str, Any]:
    """Validate freshness, schedule precision and four explicit canonical links."""
    source_id = str(observation.get("provider_fixture_id") or "").strip()
    fixture_id = _provider_fixture_id(provider, source_id) if source_id else ""
    result = {
        "provider": provider,
        "provider_fixture_id": source_id,
        "fixture_id": fixture_id,
        "snapshot_id": snapshot_id,
        "decision": "blocked",
        "reason": "",
        "canonical": None,
    }
    if not source_id:
        result["reason"] = "missing_provider_fixture_id"
        return result
    if observation.get("eligible_for_review") is not True:
        result["reason"] = str(observation.get("exclusion_reason") or "observation_not_eligible_for_review")
        return result

    retrieved = _datetime(snapshot_retrieved_at)
    fetched = _datetime(observation.get("fetched_at"))
    kickoff = _datetime(observation.get("kickoff_utc"))
    if retrieved is None or fetched is None:
        result["reason"] = "missing_timezone_aware_retrieval_timestamp"
        return result
    if retrieved > now + timedelta(minutes=5) or fetched > now + timedelta(minutes=5):
        result["reason"] = "provider_timestamp_is_in_the_future"
        return result
    if now - retrieved > timedelta(hours=max_age_hours):
        result["reason"] = "stale_observation_snapshot"
        return result
    if kickoff is None:
        result["reason"] = "kickoff_missing_timezone_or_precision"
        return result
    if kickoff <= now or kickoff > now + timedelta(days=window_days):
        result["reason"] = "kickoff_outside_active_future_window"
        return result
    status = str(observation.get("status") or "").strip().casefold().replace("_", " ")
    if status not in {"scheduled", "upcoming", "not started", "ns", "fixture"}:
        result["reason"] = "fixture_status_is_not_scheduled"
        return result

    source_keys = {
        "league": str(observation.get("competition_key") or "").strip(),
        "season": str(observation.get("season_key") or "").strip(),
        "home_team": str(observation.get("home_team_key") or "").strip(),
        "away_team": str(observation.get("away_team_key") or "").strip(),
    }
    if not all(source_keys.values()):
        result["reason"] = "missing_source_competition_season_or_team_identity"
        return result
    canonical = {
        "league_id": league_links.get(source_keys["league"]),
        "season_id": season_links.get(source_keys["season"]),
        "home_team_id": team_links.get(source_keys["home_team"]),
        "away_team_id": team_links.get(source_keys["away_team"]),
    }
    if not all(canonical.values()):
        missing = [key for key, value in canonical.items() if not value]
        result["reason"] = "missing_explicit_crosswalk:" + ",".join(missing)
        return result
    if canonical["home_team_id"] == canonical["away_team_id"]:
        result["reason"] = "home_and_away_map_to_same_canonical_team"
        return result

    # The current prediction workflow resolves season/team profiles and match
    # enrichment through Sportmonks IDs. Do not promote mappings to another ID
    # namespace until the prediction flow supports provider-neutral profiles.
    if any(not str(value).startswith("sportmonks:") for value in canonical.values()):
        result["reason"] = "canonical_target_is_not_a_sportmonks_entity"
        return result
    league = canonical_entities["leagues"].get(canonical["league_id"])
    season = canonical_entities["seasons"].get(canonical["season_id"])
    home = canonical_entities["teams"].get(canonical["home_team_id"])
    away = canonical_entities["teams"].get(canonical["away_team_id"])
    if not all((league, season, home, away)):
        result["reason"] = "canonical_entity_target_does_not_exist"
        return result
    if str(season.get("league_id") or "") != canonical["league_id"]:
        result["reason"] = "canonical_season_belongs_to_a_different_competition"
        return result

    result.update({
        "decision": "ready_for_promotion",
        "reason": "Fresh scheduled fixture with explicit links to existing canonical Sportmonks entities.",
        "canonical": {
            **canonical,
            "starting_at": kickoff,
            "home_team": str(home.get("name") or ""),
            "away_team": str(away.get("name") or ""),
            "competition": str(league.get("name") or ""),
            "country": league.get("country"),
            "venue": None,
        },
    })
    return result


def _ensure_promotion_tables(database_url: str) -> None:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in PROMOTION_TABLES_SQL.split(";"):
                if statement.strip():
                    cursor.execute(statement.strip())


def review_and_promote_free_fixture_observations(
    database_url: str,
    *,
    provider: str,
    promote: bool = False,
    now: datetime | None = None,
    snapshot_limit: int = 100,
    max_age_hours: int = 24,
    window_days: int = 7,
) -> dict[str, Any]:
    """Preview eligible observations or explicitly promote safe, mapped fixtures."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported free-fixture provider.")
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if isinstance(snapshot_limit, bool) or not 1 <= int(snapshot_limit) <= 1000:
        raise ValueError("snapshot_limit must be from 1 through 1000.")
    if not 1 <= int(max_age_hours) <= 168:
        raise ValueError("max_age_hours must be from 1 through 168.")
    if not 1 <= int(window_days) <= 7:
        raise ValueError("window_days must be from 1 through 7.")

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    current = current.astimezone(timezone.utc)

    ensure_football_repository(database_url)
    _ensure_promotion_tables(database_url)
    snapshots = load_provider_observation_snapshots(
        database_url, provider=provider_name, limit=int(snapshot_limit)
    )
    league_links = load_provider_entity_links(
        database_url, provider=provider_name, entity_type="league"
    )
    season_links = load_provider_entity_links(
        database_url, provider=provider_name, entity_type="season"
    )
    team_links = load_provider_entity_links(
        database_url, provider=provider_name, entity_type="team"
    )

    from football_repository import get_repository_leagues, get_repository_seasons, get_repository_teams
    canonical_entities = {
        "leagues": {str(row["league_id"]): row for row in get_repository_leagues(database_url)},
        "seasons": {str(row["season_id"]): row for row in get_repository_seasons(database_url)},
        "teams": {str(row["team_id"]): row for row in get_repository_teams(database_url)},
    }

    observation_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    assessments: list[dict[str, Any]] = []
    for snapshot in snapshots:
        payload = snapshot.get("payload")
        if not isinstance(payload, Mapping) or payload.get("provider") != provider_name:
            continue
        rows = payload.get("observations")
        if not isinstance(rows, list):
            continue
        for observation in rows:
            if not isinstance(observation, Mapping):
                continue
            source_id = str(observation.get("provider_fixture_id") or "").strip()
            observation_by_key[(str(snapshot.get("snapshot_id") or ""), source_id)] = observation
            assessments.append(assess_free_fixture_observation(
                provider_name, observation,
                snapshot_id=str(snapshot.get("snapshot_id") or ""),
                snapshot_retrieved_at=snapshot.get("retrieved_at") or payload.get("retrieved_at"),
                league_links=league_links,
                season_links=season_links,
                team_links=team_links,
                canonical_entities=canonical_entities,
                now=current,
                max_age_hours=int(max_age_hours),
                window_days=int(window_days),
            ))

    counts: dict[str, int] = {}
    for row in assessments:
        counts[row["decision"]] = counts.get(row["decision"], 0) + 1

    if not promote:
        return {
            "provider": provider_name,
            "mode": "preview",
            "snapshot_count": len(snapshots),
            "observation_count": len(assessments),
            "decisions": counts,
            "rows": assessments,
            "canonical_fixture_writes": 0,
            "prediction_ledger_writes": 0,
        }

    promoted = duplicate = conflicts = blocked = 0
    staging_fixtures: list[dict[str, Any]] = []
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for row in assessments:
                source_id = row["provider_fixture_id"]
                if row["decision"] != "ready_for_promotion":
                    blocked += 1
                    continue
                canonical = row["canonical"]
                fixture_id = row["fixture_id"]
                kickoff = canonical["starting_at"]
                observation = observation_by_key.get((row["snapshot_id"], source_id), {})
                cursor.execute(
                    """SELECT fixture_id, season_id, league_id, home_team_id, away_team_id, starting_at, source_provider
                       FROM football_fixtures WHERE fixture_id = %s""",
                    (fixture_id,),
                )
                same_source = cursor.fetchone()
                if same_source:
                    same_identity = (
                        str(same_source[1]) == canonical["season_id"]
                        and str(same_source[2]) == canonical["league_id"]
                        and str(same_source[3]) == canonical["home_team_id"]
                        and str(same_source[4]) == canonical["away_team_id"]
                        and _datetime(same_source[5]) == kickoff
                    )
                    if not same_identity:
                        row.update(decision="conflict_source_fixture_id_reused",
                                   reason="The provider fixture ID already exists with a different canonical identity.")
                        conflicts += 1
                        continue
                    canonical_fixture_id = fixture_id
                    duplicate += 1
                    fixture_source_provider = str(same_source[6] or provider_name)
                else:
                    cursor.execute(
                        """SELECT fixture_id, starting_at, source_provider FROM football_fixtures
                           WHERE season_id = %s AND league_id = %s
                             AND home_team_id = %s AND away_team_id = %s
                             AND starting_at BETWEEN %s AND %s
                           ORDER BY starting_at""",
                        (canonical["season_id"], canonical["league_id"],
                         canonical["home_team_id"], canonical["away_team_id"],
                         kickoff - timedelta(hours=12), kickoff + timedelta(hours=12)),
                    )
                    nearby = cursor.fetchall()
                    exact = next((item for item in nearby if _datetime(item[1]) == kickoff), None)
                    if exact:
                        canonical_fixture_id = str(exact[0])
                        fixture_source_provider = str(exact[2] or provider_name)
                        duplicate += 1
                    elif nearby:
                        row.update(decision="conflict_kickoff_disagreement",
                                   reason="A canonical fixture with the same competition, season and teams has a different kickoff within 12 hours.")
                        conflicts += 1
                        continue
                    else:
                        canonical_fixture_id = fixture_id
                        fixture_source_provider = provider_name
                        raw_payload = {
                            "source_provider": provider_name,
                            "provider_fixture_id": source_id,
                            "snapshot_id": row["snapshot_id"],
                            "source_url": next((
                                observation.get("source_url") for snapshot in snapshots
                                if str(snapshot.get("snapshot_id") or "") == row["snapshot_id"]
                                for observation in (snapshot.get("payload") or {}).get("observations", [])
                                if str(observation.get("provider_fixture_id") or "") == source_id
                            ), None),
                            "licence": next((
                                observation.get("licence") for snapshot in snapshots
                                if str(snapshot.get("snapshot_id") or "") == row["snapshot_id"]
                                for observation in (snapshot.get("payload") or {}).get("observations", [])
                                if str(observation.get("provider_fixture_id") or "") == source_id
                            ), None),
                            "kickoff_utc": kickoff.isoformat(),
                            "source_fixture_id": source_id,
                        }
                        cursor.execute(
                            """INSERT INTO football_fixtures (
                                   fixture_id, season_id, league_id, home_team_id, away_team_id,
                                   starting_at, status, home_goals, away_goals, venue,
                                   source_provider, provider_updated_at, raw_payload
                               ) VALUES (%s, %s, %s, %s, %s, %s, 'scheduled', NULL, NULL, %s, %s, %s, %s)""",
                            (fixture_id, canonical["season_id"], canonical["league_id"],
                             canonical["home_team_id"], canonical["away_team_id"],
                             kickoff, canonical.get("venue"), provider_name,
                             _datetime(next((
                                 observation.get("fetched_at") for snapshot in snapshots
                                 if str(snapshot.get("snapshot_id") or "") == row["snapshot_id"]
                                 for observation in (snapshot.get("payload") or {}).get("observations", [])
                                 if str(observation.get("provider_fixture_id") or "") == source_id
                             ), None)), Jsonb(raw_payload)),
                        )
                        promoted += 1

                cursor.execute(
                    """SELECT fixture_id FROM football_fixture_sources
                       WHERE provider = %s AND provider_fixture_id = %s""",
                    (provider_name, source_id),
                )
                existing_source_link = cursor.fetchone()
                if existing_source_link and str(existing_source_link[0]) != canonical_fixture_id:
                    row.update(decision="conflict_provider_provenance_reassigned",
                               reason="This provider fixture ID is already linked to a different canonical fixture.")
                    conflicts += 1
                    continue
                cursor.execute(
                    """INSERT INTO football_fixture_sources (
                           source_link_id, provider, provider_fixture_id, fixture_id,
                           snapshot_id, source_url, licence, observed_at, raw_payload
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (provider, provider_fixture_id) DO NOTHING""",
                    (str(uuid.uuid4()), provider_name, source_id, canonical_fixture_id,
                     row["snapshot_id"], observation.get("source_url"), observation.get("licence"),
                     _datetime(observation.get("fetched_at")), Jsonb(dict(observation))),
                )
                cursor.execute(
                    """INSERT INTO free_fixture_promotion_audit (
                           audit_id, provider, provider_fixture_id, snapshot_id,
                           decision, reason, canonical_fixture_id
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (provider, provider_fixture_id, snapshot_id) DO NOTHING""",
                    (str(uuid.uuid4()), provider_name, source_id, row["snapshot_id"],
                     "duplicate_exact" if canonical_fixture_id != fixture_id else "promoted",
                     "Linked to exact canonical fixture identity." if canonical_fixture_id != fixture_id
                     else "Inserted canonical fixture with explicit source crosswalks.",
                     canonical_fixture_id),
                )
                row.update(
                    decision="duplicate_exact" if canonical_fixture_id != fixture_id or fixture_source_provider != provider_name else "promoted",
                    reason="Linked to exact canonical fixture identity." if canonical_fixture_id != fixture_id or fixture_source_provider != provider_name
                    else "Inserted canonical fixture with explicit source crosswalks.",
                    canonical_fixture_id=canonical_fixture_id,
                )
                staging_fixtures.append({
                    "fixture_id": canonical_fixture_id,
                    "league_id": canonical["league_id"],
                    "season_id": canonical["season_id"],
                    "starting_at": kickoff,
                    "status": "scheduled",
                    "home_team_id": canonical["home_team_id"],
                    "away_team_id": canonical["away_team_id"],
                    "home_team": canonical["home_team"],
                    "away_team": canonical["away_team"],
                    "competition": canonical["competition"],
                    "country": canonical.get("country"),
                    "venue": canonical.get("venue"),
                    "source_provider": fixture_source_provider,
                    "provider_updated_at": _datetime(observation.get("fetched_at")),
                    "provider_fixture_id": source_id,
                })

    return {
        "provider": provider_name,
        "mode": "promote",
        "snapshot_count": len(snapshots),
        "observation_count": len(assessments),
        "decisions": {
            "promoted": promoted, "duplicate_exact": duplicate,
            "conflicts": conflicts, "blocked": blocked,
        },
        "rows": assessments,
        "staging_fixtures": staging_fixtures,
        "canonical_fixture_writes": promoted,
        "prediction_ledger_writes": 0,
    }
