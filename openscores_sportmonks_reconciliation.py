"""Safely import matching Sportmonks history and reconcile OpenScores observations.

Only exact competition/country, season-year, and unique team-name matches are
used to create explicit provider_entity_links. Sportmonks remains the canonical
fixture source. OpenScores never writes canonical fixtures or prediction data.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from football_repository import (
    ensure_football_repository,
    import_sportmonks_season,
)
from openscores import OpenScoresClient
from openscores_observation_store import (
    ensure_provider_entity_link_verifications,
    reconcile_openscores_observations,
)
from provider_data_storage import _connect
from sportmonks import SportmonksClient


TEAM_NAME_ALIASES = {
    "alaves": ("deportivo alaves",),
    "ath bilbao": ("athletic club", "athletic bilbao"),
    "atl madrid": ("atletico madrid", "atletico de madrid"),
    "barcelona": ("fc barcelona",),
    "betis": ("real betis",),
    "celta vigo": ("celta de vigo", "rc celta de vigo"),
    "oviedo": ("real oviedo",),
    "bournemouth": ("afc bournemouth",),
    "brighton": ("brighton and hove albion",),
    "leeds": ("leeds united",),
    "manchester utd": ("manchester united", "man utd"),
    "newcastle": ("newcastle united",),
    "nottingham": ("nottingham forest",),
    "tottenham": ("tottenham hotspur",),
    "west ham": ("west ham united",),
    "wolves": ("wolverhampton wanderers",),
    "as roma": ("roma",),
    "verona": ("hellas verona",),
}

COUNTRY_CODES = {
    "DEU": "Germany",
    "ESP": "Spain",
    "FRA": "France",
    "ENG": "England",
    "ITA": "Italy",
}


def _norm(value: Any) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _records(value: Any, preferred: tuple[str, ...], depth: int = 0) -> list[dict[str, Any]]:
    if depth > 6:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in preferred:
            if key in value:
                found = _records(value[key], preferred, depth + 1)
                if found:
                    return found
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                found = _records(child, preferred, depth + 1)
                if found:
                    return found
    return []


def _country_name(league: Mapping[str, Any]) -> str:
    value = league.get("country") or league.get("country_name") or ""
    if isinstance(value, Mapping):
        value = value.get("name") or value.get("official_name") or ""
    return str(value or "").strip()


def _season_years(value: Any) -> tuple[int, int] | None:
    text = str(value or "")
    match = re.search(r"(20\d{2})\s*[/\-]\s*(20\d{2})", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"20\d{2}", text)
    if match:
        year = int(match.group(0))
        return year, year + 1
    return None


def find_unique_sportmonks_league(
    openscores_league: Mapping[str, Any],
    sportmonks_leagues: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Match exact competition name plus country; never fuzzy-match a league."""
    source_name = _norm(openscores_league.get("name") or openscores_league.get("league_name"))
    source_code = str(openscores_league.get("country_code") or "").upper()
    expected_country = COUNTRY_CODES.get(source_code)
    matches = []
    for league in sportmonks_leagues:
        if _norm(league.get("name")) != source_name:
            continue
        if expected_country:
            country_value = _country_name(league)
            country_code = ""
            country_payload = league.get("country")
            if isinstance(country_payload, Mapping):
                country_code = str(
                    country_payload.get("iso3")
                    or country_payload.get("iso_3")
                    or country_payload.get("code")
                    or ""
                ).upper()
            aliases = {
                "ENG": {"england", "united kingdom", "great britain"},
            }.get(source_code, {_norm(expected_country)})
            accepted_codes = {source_code, "GBR"} if source_code == "ENG" else {source_code}
            if _norm(country_value) not in aliases and country_code not in accepted_codes:
                continue
        elif _country_name(league):
            continue
        # With no country code, only a unique exact-name international entry
        # without a country may be considered.
        matches.append(league)
    if len(matches) == 1:
        return {"status": "unique_exact_name_country_match", "league": matches[0]}
    return {
        "status": "ambiguous_exact_name_country_match" if matches else "no_exact_name_country_match",
        "league": None,
        "candidate_count": len(matches),
    }


def find_unique_sportmonks_season(
    openscores_season: Mapping[str, Any],
    sportmonks_seasons: list[Mapping[str, Any]],
    sportmonks_league_id: Any,
) -> dict[str, Any]:
    """Match the same league and season-year pair; do not cross-map seasons."""
    source_years = (
        _season_years(openscores_season.get("name"))
        or _season_years(openscores_season.get("season_name"))
        or _season_years(openscores_season.get("start_date"))
    )
    if source_years is None:
        return {"status": "insufficient_season_identity", "season": None, "candidate_count": 0}
    matches = []
    for season in sportmonks_seasons:
        if str(season.get("league_id")) != str(sportmonks_league_id):
            continue
        target_years = (
            _season_years(season.get("name"))
            or _season_years(season.get("starting_at"))
            or _season_years(season.get("start_date"))
        )
        if target_years == source_years:
            matches.append(season)
    if len(matches) == 1:
        return {"status": "unique_exact_league_year_match", "season": matches[0]}
    return {
        "status": "ambiguous_league_year_match" if matches else "no_matching_league_year",
        "season": None,
        "candidate_count": len(matches),
    }


def unique_team_crosswalks(
    observed_teams: list[Mapping[str, Any]],
    sportmonks_teams: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Return exact-name mappings only when the Sportmonks season roster is unique."""
    by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for team in sportmonks_teams:
        key = _norm(team.get("name"))
        if key and team.get("id") is not None:
            by_name[key].append(team)
    mappings = []
    for team in observed_teams:
        source_name = str(team.get("name") or "")
        key = _norm(source_name)
        exact_candidates = by_name.get(key, [])
        match_method = "exact_unique_name_within_matched_season_roster"
        candidates = exact_candidates
        if not candidates:
            alias_names = TEAM_NAME_ALIASES.get(key, ())
            alias_candidates = [
                candidate
                for alias in alias_names
                for candidate in by_name.get(_norm(alias), [])
            ]
            # Deduplicate by provider team ID; aliases are accepted only when
            # they resolve to exactly one team in this specific season roster.
            candidates_by_id = {
                str(candidate["id"]): candidate for candidate in alias_candidates
            }
            candidates = list(candidates_by_id.values())
            match_method = "curated_name_alias_unique_within_matched_season_roster"
        if key and len(candidates) == 1:
            target = candidates[0]
            mappings.append({
                "entity_type": "team",
                "provider_entity_id": str(team.get("provider_team_id")),
                "canonical_entity_id": f"sportmonks:{target['id']}",
                "name": source_name,
                "basis": match_method,
                "verification_method": match_method,
                "evidence": {
                    "openscores_team_name": source_name,
                    "sportmonks_team_name": str(target.get("name") or ""),
                    "sportmonks_team_id": str(target["id"]),
                    "season_roster_unique": True,
                },
            })
    return mappings


def _observed_teams(database_url: str, league_id: str, season_id: str) -> list[dict[str, str]]:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider_team_id, team_name
                FROM (
                    SELECT provider_home_team_id AS provider_team_id,
                           home_team_name AS team_name
                    FROM provider_fixture_observations
                    WHERE provider = 'openscores'
                      AND provider_league_id = %s AND provider_season_id = %s
                    UNION
                    SELECT provider_away_team_id AS provider_team_id,
                           away_team_name AS team_name
                    FROM provider_fixture_observations
                    WHERE provider = 'openscores'
                      AND provider_league_id = %s AND provider_season_id = %s
                ) observed
                ORDER BY team_name, provider_team_id
                """,
                (league_id, season_id, league_id, season_id),
            )
            return [
                {"provider_team_id": str(row[0]), "name": str(row[1])}
                for row in cursor.fetchall()
            ]


def _canonical_fixture_count(database_url: str, season_id: str) -> int:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM football_fixtures WHERE season_id = %s",
                (season_id,),
            )
            return int(cursor.fetchone()[0])


def write_explicit_openscores_links(
    database_url: str,
    mappings: list[Mapping[str, Any]],
    *,
    explicit_approval: bool = False,
) -> dict[str, Any]:
    """Persist links only when a reviewer explicitly approves every mapping.

    Candidate generation and automated reconciliation must never promote
    name-based matches into verified links. Each mapping must carry a reviewer
    and a substantive approval reason from a separately reviewed decision.
    """
    if not explicit_approval or not mappings or any(
        not str(item.get("approved_by") or "").strip()
        or len(str(item.get("approval_reason") or "").strip()) < 12
        for item in mappings
    ):
        return {
            "inserted": 0, "existing": 0, "verified": 0,
            "conflicts": [], "status": "approval_required_no_writes",
        }
    ensure_provider_entity_link_verifications(database_url)
    conflicts = []
    inserted = 0
    existing = 0
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            for mapping in mappings:
                entity_type = str(mapping["entity_type"])
                provider_id = str(mapping["provider_entity_id"])
                canonical_id = str(mapping["canonical_entity_id"])
                cursor.execute(
                    """
                    SELECT l.link_id, l.canonical_entity_id,
                           v.verification_status, v.canonical_entity_id
                    FROM provider_entity_links AS l
                    LEFT JOIN provider_entity_link_verifications AS v
                      ON v.link_id = l.link_id
                    WHERE l.provider = 'openscores'
                      AND l.entity_type = %s AND l.provider_entity_id = %s
                    """,
                    (entity_type, provider_id),
                )
                row = cursor.fetchone()
                if row and str(row[1]) != canonical_id:
                    conflicts.append({
                        "entity_type": entity_type,
                        "provider_entity_id": provider_id,
                        "reason": "canonical_entity_conflict",
                    })
                elif row and row[2] == "rejected":
                    conflicts.append({
                        "entity_type": entity_type,
                        "provider_entity_id": provider_id,
                        "reason": "mapping_previously_rejected",
                    })
                elif row and row[3] is not None and str(row[3]) != canonical_id:
                    conflicts.append({
                        "entity_type": entity_type,
                        "provider_entity_id": provider_id,
                        "reason": "verification_record_conflict",
                    })
            if conflicts:
                return {
                    "inserted": 0, "existing": 0, "verified": 0,
                    "conflicts": conflicts, "status": "conflict_no_writes",
                }

            verified = 0
            for mapping in mappings:
                provider_id = str(mapping["provider_entity_id"])
                entity_type = str(mapping["entity_type"])
                canonical_id = str(mapping["canonical_entity_id"])
                cursor.execute(
                    """
                    SELECT link_id
                    FROM provider_entity_links
                    WHERE provider = 'openscores'
                      AND entity_type = %s AND provider_entity_id = %s
                    """,
                    (entity_type, provider_id),
                )
                row = cursor.fetchone()
                if row:
                    link_id = str(row[0])
                    existing += 1
                    cursor.execute(
                        """
                        UPDATE provider_entity_links
                        SET last_seen_at = NOW()
                        WHERE link_id = %s
                        """,
                        (link_id,),
                    )
                else:
                    link_id = str(uuid.uuid5(
                        uuid.NAMESPACE_URL, f"openscores:{entity_type}:{provider_id}"
                    ))
                    cursor.execute(
                        """
                        INSERT INTO provider_entity_links (
                            link_id, provider, entity_type, provider_entity_id,
                            canonical_entity_id
                        ) VALUES (%s, 'openscores', %s, %s, %s)
                        """,
                        (link_id, entity_type, provider_id, canonical_id),
                    )
                    inserted += 1

                evidence = json.dumps(mapping.get("evidence") or {}, sort_keys=True)
                method = str(
                    mapping.get("verification_method")
                    or mapping.get("basis")
                    or "deterministic_exact_identity_match"
                )
                cursor.execute(
                    """
                    INSERT INTO provider_entity_link_verifications (
                        link_id, provider, entity_type, provider_entity_id,
                        canonical_entity_id, verification_status,
                        verification_method, evidence, verified_at
                    ) VALUES (
                        %s, 'openscores', %s, %s, %s, 'verified',
                        %s, %s::JSONB, NOW()
                    )
                    ON CONFLICT (provider, entity_type, provider_entity_id)
                    DO UPDATE SET
                        verification_status = 'verified',
                        verification_method = EXCLUDED.verification_method,
                        evidence = EXCLUDED.evidence,
                        verified_at = NOW(),
                        updated_at = NOW()
                    """,
                    (link_id, entity_type, provider_id, canonical_id, method, evidence),
                )
                verified += 1
    return {
        "inserted": inserted, "existing": existing, "verified": verified,
        "conflicts": [], "status": "pass",
    }


def _pending_mapping_diagnostics(database_url: str) -> dict[str, Any]:
    """Expose safe names/IDs needed to resolve pending cross-provider mappings."""
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider_league_id, provider_season_id,
                       COUNT(*) AS observations,
                       COUNT(DISTINCT provider_home_team_id) AS home_ids,
                       COUNT(DISTINCT provider_away_team_id) AS away_ids,
                       ARRAY_AGG(DISTINCT home_team_name) AS home_names,
                       ARRAY_AGG(DISTINCT away_team_name) AS away_names
                FROM provider_fixture_observations
                WHERE provider = 'openscores'
                  AND canonical_fixture_id IS NULL
                  AND reconciliation_status IN (
                      'pending_entity_mapping', 'outside_upcoming_window'
                  )
                GROUP BY provider_league_id, provider_season_id
                ORDER BY provider_league_id, provider_season_id
                """
            )
            rows = cursor.fetchall()
    return {
        "pending_groups": [
            {
                "openscores_league_id": str(row[0]),
                "openscores_season_id": str(row[1]),
                "observations": int(row[2]),
                "distinct_home_team_ids": int(row[3]),
                "distinct_away_team_ids": int(row[4]),
                "home_team_names": list(row[5] or []),
                "away_team_names": list(row[6] or []),
            }
            for row in rows
        ]
    }


def run_reconciliation(
    *,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Reconcile staged observations using only pre-existing verified links.

    This operation is deliberately database-only and fail-closed. It does not
    discover or approve mappings, import canonical Sportmonks fixtures, fetch
    future fixtures, or create provider links. A separate reviewed operation
    must populate verified mappings before observations can match.
    """
    db_url = (database_url or os.getenv("PROVIDER_DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("PROVIDER_DATABASE_URL is required")
    report: dict[str, Any] = {
        "operation": "openscores_sportmonks_reconciliation",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "mapping_policy": "pre_existing_verified_links_only",
        "competitions_considered": 0,
        "competitions_imported": 0,
        "canonical_fixtures_imported": 0,
        "explicit_entity_links_inserted": 0,
        "explicit_entity_links_existing": 0,
        "explicit_entity_links_verified": 0,
        "entity_link_conflicts": [],
        "competition_results": [],
        "reconciliation": None,
        "canonical_fixtures_modified_by_openscores": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
    }

    # The reconciler reads only provider_entity_links joined to verification
    # rows whose status is already 'verified'. It updates observation
    # reconciliation status/fingerprint only; it never writes canonical
    # fixtures or creates entity mappings.
    report["reconciliation"] = reconcile_openscores_observations(
        db_url,
        include_outside_upcoming_window=True,
        preserve_outside_window_status=True,
    )
    report["mapping_diagnostics"] = _pending_mapping_diagnostics(db_url)
    matched = int(report["reconciliation"].get("matched", 0))
    pending = int(report["reconciliation"].get("pending_entity_mapping", 0))
    report["status"] = (
        "pass" if matched > 0 and pending == 0
        else "partial" if matched > 0
        else "blocked_pending_verified_mappings" if pending > 0
        else "no_eligible_observations"
    )
    return report

def main() -> int:
    report = run_reconciliation()
    serialized = json.dumps(report, indent=2, default=str)
    Path("openscores-sportmonks-reconciliation-report.json").write_text(
        serialized + "\n", encoding="utf-8"
    )
    print(serialized)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## OpenScores ↔ Sportmonks reconciliation\n\n")
            summary.write(f"- Status: {report['status']}\n")
            summary.write(f"- Competitions imported: {report['competitions_imported']}\n")
            summary.write(f"- Canonical Sportmonks fixtures imported: {report['canonical_fixtures_imported']}\n")
            summary.write(f"- Explicit OpenScores entity links inserted: {report['explicit_entity_links_inserted']}\n")
            summary.write(f"- Prediction model modified: no\n- Prediction ledger touched: no\n")
            summary.write(f"\n### Reconciliation\n\n`{json.dumps(report['reconciliation'], sort_keys=True)}`\n")
    return 0 if report["status"] in {"pass", "partial", "blocked_pending_verified_mappings", "no_eligible_observations"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
