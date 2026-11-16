"""Read-only official 2026/27 senior first-team scope evidence audit.

This module compares season-scoped provider roster observations with official
league club lists. It emits review candidates only: it never writes scope
metadata, canonical identities, or cross-provider links.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from provider_data_storage import _connect
from provider_entity_crosswalk import normalize_entity_name
from provider_season_provenance import explicit_season_label, payload_mapping

REPORT = Path("provider-official-team-scope-audit.json")

OFFICIAL_COMPETITIONS: dict[str, dict[str, Any]] = {
    "premier_league": {
        "name": "Premier League",
        "country": "England",
        "provider_ids": {("highlightly", "33973")},
        "official_reference_url": "https://www.premierleague.com/en/news/4365156",
        "official_scope_basis": "2026/27 highest level of men's professional football; official 20-club competition list",
        "teams": (
            "AFC Bournemouth", "Arsenal", "Aston Villa", "Brentford",
            "Brighton & Hove Albion", "Chelsea", "Coventry City",
            "Crystal Palace", "Everton", "Fulham", "Hull City",
            "Ipswich Town", "Leeds United", "Liverpool", "Manchester City",
            "Manchester United", "Newcastle United", "Nottingham Forest",
            "Sunderland", "Tottenham Hotspur",
        ),
    },
    "laliga": {
        "name": "LALIGA EA SPORTS",
        "country": "Spain",
        "provider_ids": {("highlightly", "119924")},
        "official_reference_url": "https://www.laliga.com/en-US/laliga-easports/clubs",
        "official_scope_basis": "2026/27 LALIGA EA SPORTS senior top-flight club list, distinct from Liga F and LALIGA HYPERMOTION",
        "teams": (
            "Athletic Club", "Atlético de Madrid", "CA Osasuna", "Celta",
            "Deportivo Alavés", "Elche CF", "FC Barcelona", "Getafe CF",
            "Levante UD", "Málaga CF", "R. Racing Club", "Rayo Vallecano",
            "RC Deportivo", "RCD Espanyol de Barcelona", "Real Betis",
            "Real Madrid", "Real Sociedad", "Sevilla FC", "Valencia CF",
            "Villarreal CF",
        ),
    },
    "serie_a": {
        "name": "Serie A",
        "country": "Italy",
        "provider_ids": {("highlightly", "115669")},
        "official_reference_url": "https://en.legaseriea.it/serie-a/standings?app_v1=true",
        "official_scope_basis": "Lega Serie A official 2026/2027 senior league standings and club list",
        "teams": (
            "Lazio", "Inter", "Roma", "Milan", "Como", "Frosinone",
            "Juventus", "Bologna", "Cagliari", "Napoli", "Torino",
            "Atalanta", "Genoa", "Lecce", "Fiorentina", "Parma",
            "Sassuolo", "Monza", "Venezia", "Udinese",
        ),
    },
    "bundesliga": {
        "name": "Bundesliga",
        "country": "Germany",
        "provider_ids": {
            ("highlightly", "67162"), ("livescore_football", "ger.1"),
        },
        "official_reference_url": "https://www.bundesliga.com/en/bundesliga/clubs",
        "official_scope_basis": "Official Bundesliga 2026/27 season club list and standings",
        "teams": (
            "FC Bayern München", "Borussia Dortmund", "RB Leipzig",
            "VfB Stuttgart", "TSG Hoffenheim", "Bayer 04 Leverkusen",
            "Sport-Club Freiburg", "Eintracht Frankfurt", "FC Augsburg",
            "1. FSV Mainz 05", "1. FC Union Berlin",
            "Borussia Mönchengladbach", "Hamburger SV", "1. FC Köln",
            "SV Werder Bremen", "FC Schalke 04", "SV Elversberg",
            "SC Paderborn 07",
        ),
    },
    "ligue1": {
        "name": "Ligue 1 McDonald's",
        "country": "France",
        "provider_ids": {
            ("highlightly", "52695"), ("livescore_football", "fra.1"),
        },
        "official_reference_url": "https://ligue1.com/en?type_classement=EXT",
        "official_scope_basis": "Official 2026/27 Ligue 1 McDonald's senior league standings and 18-club competition list",
        "teams": (
            "Olympique Lyonnais", "Paris Saint-Germain", "Paris FC",
            "LOSC Lille", "AS Monaco", "Rennes", "FC Lorient", "RC Lens",
            "Olympique de Marseille", "Brest", "Toulouse FC", "AJ Auxerre",
            "OGC Nice", "RC Strasbourg", "Angers SCO", "Le Mans FC",
            "Troyes", "Havre AC",
        ),
    },
}

# Reviewed provider-name variants mapped to the exact official competition-list
# spelling. These are candidate aliases only; no provider IDs are merged.
TEAM_NAME_ALIASES = {
    ("premier_league", "bournemouth"): "AFC Bournemouth",
    ("premier_league", "brighton"): "Brighton & Hove Albion",
    ("premier_league", "coventry"): "Coventry City",
    ("premier_league", "ipswich"): "Ipswich Town",
    ("premier_league", "leeds"): "Leeds United",
    ("premier_league", "tottenham"): "Tottenham Hotspur",
    ("laliga", "atletico madrid"): "Atlético de Madrid",
    ("laliga", "barcelona"): "FC Barcelona",
    ("laliga", "celta de vigo"): "Celta",
    ("laliga", "malaga"): "Málaga CF",
    ("laliga", "racing santander"): "R. Racing Club",
    ("laliga", "deportivo la coruna"): "RC Deportivo",
    ("laliga", "espanyol"): "RCD Espanyol de Barcelona",
    ("laliga", "levante"): "Levante UD",
    ("laliga", "alaves"): "Deportivo Alavés",
    ("laliga", "osasuna"): "CA Osasuna",
    ("laliga", "valencia"): "Valencia CF",
    ("serie_a", "ac milan"): "Milan",
    ("serie_a", "as roma"): "Roma",
    ("bundesliga", "bayern munich"): "FC Bayern München",
    ("bundesliga", "werder bremen"): "SV Werder Bremen",
    ("bundesliga", "fsv mainz 05"): "1. FSV Mainz 05",
    ("bundesliga", "mainz"): "1. FSV Mainz 05",
    ("bundesliga", "union berlin"): "1. FC Union Berlin",
    ("bundesliga", "1899 hoffenheim"): "TSG Hoffenheim",
    ("bundesliga", "fc koln"): "1. FC Köln",
    ("bundesliga", "fc cologne"): "1. FC Köln",
    ("bundesliga", "hamburg sv"): "Hamburger SV",
    ("bundesliga", "schalke 04"): "FC Schalke 04",
    ("bundesliga", "bayer leverkusen"): "Bayer 04 Leverkusen",
    ("bundesliga", "sc freiburg"): "Sport-Club Freiburg",
    ("ligue1", "angers"): "Angers SCO",
    ("ligue1", "le mans"): "Le Mans FC",
    ("ligue1", "le havre ac"): "Havre AC",
    ("ligue1", "lille"): "LOSC Lille",
    ("ligue1", "lyon"): "Olympique Lyonnais",
    ("ligue1", "marseille"): "Olympique de Marseille",
    ("ligue1", "nice"): "OGC Nice",
    ("ligue1", "paris saint germain"): "Paris Saint-Germain",
    ("ligue1", "monaco"): "AS Monaco",
    ("ligue1", "rennes fc"): "Rennes",
    ("ligue1", "stade rennais"): "Rennes",
    ("ligue1", "strasbourg"): "RC Strasbourg",
    ("ligue1", "toulouse"): "Toulouse FC",
    ("ligue1", "stade brestois 29"): "Brest",
    ("ligue1", "brest"): "Brest",
    ("ligue1", "auxerre"): "AJ Auxerre",
    ("ligue1", "estac troyes"): "Troyes",
    ("ligue1", "troyes"): "Troyes",
    ("ligue1", "lens"): "RC Lens",
    ("ligue1", "lorient"): "FC Lorient",
}


def _official_team_lookup(competition: Mapping[str, Any]) -> dict[str, str]:
    return {
        normalize_entity_name(team): team
        for team in competition.get("teams", ())
    }


def _resolve_official_team(
    competition_key: str, provider_team_name: str, official_lookup: Mapping[str, str]
) -> tuple[str | None, str]:
    normalized = normalize_entity_name(provider_team_name)
    if normalized in official_lookup:
        return official_lookup[normalized], "exact_normalized_official_name"
    alias = TEAM_NAME_ALIASES.get((competition_key, normalized))
    if alias and normalize_entity_name(alias) in official_lookup:
        return official_lookup[normalize_entity_name(alias)], "reviewed_official_name_alias"
    return None, "held_official_team_name_unmatched"


def build_official_team_scope_audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    provider_competition_index = {
        provider_id: (competition_key, competition)
        for competition_key, competition in OFFICIAL_COMPETITIONS.items()
        for provider_id in competition["provider_ids"]
    }
    candidates = []
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        provider = str(row.get("provider") or "").strip().casefold()
        if provider not in {"highlightly", "livescore_football"}:
            continue
        raw = payload_mapping(row.get("raw_payload"))
        provider_ids = raw.get("competition_provider_ids")
        if not isinstance(provider_ids, list):
            provider_ids = [provider_ids] if provider_ids else []
        if not provider_ids:
            counts[provider]["held_missing_competition_id"] += 1
            continue
        for provider_competition_id in provider_ids:
            key = (provider, str(provider_competition_id))
            selected = provider_competition_index.get(key)
            if not selected:
                continue
            competition_key, competition = selected
            season_label = explicit_season_label(raw)
            team_name = str(row.get("name") or "").strip()
            official_name, name_method = _resolve_official_team(
                competition_key, team_name, _official_team_lookup(competition)
            )
            if season_label != "2026/27":
                status = (
                    "held_missing_explicit_2026_27_season"
                    if not season_label else "held_wrong_season"
                )
            elif not official_name:
                status = "held_official_team_name_unmatched"
            else:
                method = str(raw.get("team_evidence_method") or "")
                complete = bool(raw.get("roster_observation_complete") or raw.get("team_evidence_complete"))
                if provider == "highlightly" and method == "league_season_standings" and complete:
                    status = "candidate_review_complete_standings"
                else:
                    status = "candidate_review_incomplete_or_participant_evidence"
            candidate = {
                "provider": provider,
                "provider_entity_id": str(row.get("provider_entity_id") or ""),
                "provider_team_name": team_name,
                "competition_key": competition_key,
                "competition_name": competition["name"],
                "competition_provider_id": str(provider_competition_id),
                "country": competition["country"],
                "season_label": season_label,
                "source_endpoint": raw.get("source_endpoint"),
                "source_retrieved_at": raw.get("source_retrieved_at"),
                "team_evidence_method": raw.get("team_evidence_method"),
                "provider_roster_observation_complete": bool(raw.get("roster_observation_complete")),
                "official_team_name": official_name,
                "name_match_method": name_method,
                "official_reference_url": competition["official_reference_url"],
                "official_scope_basis": competition["official_scope_basis"],
                "scope_candidate": (
                    {
                        "team_type": "club",
                        "gender_scope": "male",
                        "age_group": "senior",
                        "squad_scope": "first_team",
                    } if status.startswith("candidate_review_") else None
                ),
                "status": status,
                "promotion_allowed": False,
            }
            candidates.append(candidate)
            counts[provider][status] += 1
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_writes": False,
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "provider_scope_fields_updated": 0,
        "source_rows_examined": len(rows),
        "official_competitions": {
            key: {
                "name": value["name"],
                "country": value["country"],
                "official_team_count": len(value["teams"]),
                "official_reference_url": value["official_reference_url"],
            }
            for key, value in OFFICIAL_COMPETITIONS.items()
        },
        "provider_candidate_counts": {
            provider: dict(statuses) for provider, statuses in sorted(counts.items())
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "interpretation": (
            "Official competition membership supports senior men's first-team scope candidates "
            "only for explicit 2026/27 provider records whose team name matches the official "
            "competition list. These are review candidates, not approvals; no source rows, "
            "canonical identities or provider links are changed."
        ),
    }


def audit_official_team_scope(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """SELECT provider, provider_entity_id, name, raw_payload
                   FROM provider_source_entities
                   WHERE entity_type = 'team'
                     AND provider IN ('highlightly', 'livescore_football')
                   ORDER BY provider, provider_entity_id"""
            )
            columns = ("provider", "provider_entity_id", "name", "raw_payload")
            rows = [dict(zip(columns, values)) for values in cursor.fetchall()]
    report = build_official_team_scope_audit(rows)
    report["database_read_only"] = True
    return report


def main() -> int:
    database_url = os.getenv("PROVIDER_DATABASE_URL", "").strip()
    report = audit_official_team_scope(database_url)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at": report["checked_at"],
        "read_only": report["read_only"],
        "candidate_count": report["candidate_count"],
        "provider_candidate_counts": report["provider_candidate_counts"],
        "canonical_ids_assigned": 0,
        "provider_links_created": 0,
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
