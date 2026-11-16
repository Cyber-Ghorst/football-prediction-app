"""Record approved cross-provider team-scope corroboration without creating identity links.

Only unique exact-name matches within mapped current domestic competitions are
accepted. API Ninjas country/type/gender values are preserved in a separate
corroboration table; target provider source rows and canonical repositories are
not modified.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from provider_data_storage import _connect
from provider_team_scope_corroboration_audit import audit_team_scope_corroboration

REPORT = Path("provider-team-scope-corroboration-approval-report.json")
APPROVAL_REASON = (
    "Layer 12 reviewed scope corroboration: unique exact normalized team name "
    "within the same current domestic competition; API Ninjas explicitly reports "
    "active club, ISO country code and men's gender. This is scope evidence only, "
    "not a canonical team identity or provider link."
)
MANUAL_ALIAS_APPROVALS = (
    ("highlightly", "52695", "92692", "Auxerre", "soccer-aj-auxerre", "AJ Auxerre", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("highlightly", "52695", "94394", "Estac Troyes", "soccer-troyes", "Troyes", "FR", "France", "ligue1", ("https://www.estac.fr/", "https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released")),
    ("highlightly", "52695", "78225", "Monaco", "soccer-as-monaco", "AS Monaco", "FR", "France", "ligue1", ("https://www.asmonaco.com/en/club/statuts", "https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released")),
    ("highlightly", "67162", "142901", "1899 Hoffenheim", "soccer-tsg-hoffenheim", "TSG Hoffenheim", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("highlightly", "67162", "164176", "FC Koln", "soccer-fc-cologne", "FC Cologne", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs", "https://fc.de/en/teams/international-talent-program")),
    ("highlightly", "67162", "148858", "FC Schalke 04", "soccer-schalke-04", "Schalke 04", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("highlightly", "67162", "149709", "Hamburger SV", "soccer-hamburg-sv", "Hamburg SV", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("highlightly", "67162", "155666", "Union Berlin", "soccer-1-fc-union-berlin", "1. FC Union Berlin", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("highlightly", "52695", "80778", "Rennes FC", "soccer-stade-rennais", "Stade Rennais", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("highlightly", "52695", "90990", "Stade Brestois 29", "soccer-brest", "Brest", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("highlightly", "67162", "140348", "FSV Mainz 05", "soccer-mainz", "Mainz", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    # API-Football 2026 league-roster variants, verified against the official 2026/27 league club lists.
    ("api_football", "39", "35", "Bournemouth", "soccer-afc-bournemouth", "AFC Bournemouth", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("api_football", "39", "51", "Brighton", "soccer-brighton-hove-albion", "Brighton & Hove Albion", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("api_football", "39", "57", "Ipswich", "soccer-ipswich-town", "Ipswich Town", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("api_football", "39", "34", "Newcastle", "soccer-newcastle-united", "Newcastle United", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("api_football", "39", "47", "Tottenham", "soccer-tottenham-hotspur", "Tottenham Hotspur", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("api_football", "78", "167", "1899 Hoffenheim", "soccer-tsg-hoffenheim", "TSG Hoffenheim", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("api_football", "78", "157", "Bayern München", "soccer-bayern-munich", "Bayern Munich", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("api_football", "78", "164", "FSV Mainz 05", "soccer-mainz", "Mainz", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("api_football", "78", "182", "Union Berlin", "soccer-1-fc-union-berlin", "1. FC Union Berlin", "DE", "Germany", "bundesliga", ("https://www.bundesliga.com/en/bundesliga/clubs",)),
    ("api_football", "135", "505", "Inter", "soccer-internazionale", "Internazionale", "IT", "Italy", "seriea", ("https://www.figc.it/en/figc/news/season-2026-2027-uefa-licences-granted-to-18-serie-a-clubs-erpug9sv",)),
    ("api_football", "61", "108", "Auxerre", "soccer-aj-auxerre", "AJ Auxerre", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("api_football", "61", "111", "Le Havre", "soccer-le-havre-ac", "Le Havre AC", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("api_football", "61", "91", "Monaco", "soccer-as-monaco", "AS Monaco", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("api_football", "61", "94", "Rennes", "soccer-stade-rennais", "Stade Rennais", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    ("api_football", "61", "106", "Stade Brestois 29", "soccer-brest", "Brest", "FR", "France", "ligue1", ("https://ligue1.com/fr/articles/l1_article_5292-the-2026-27-ligue-1-mc-donald-s-calendar-is-released",)),
    # Highlightly 2026/27 Premier League variants, checked against the official club list.
    ("highlightly", "33973", "30569", "Bournemouth", "soccer-afc-bournemouth", "AFC Bournemouth", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("highlightly", "33973", "44185", "Brighton", "soccer-brighton-hove-albion", "Brighton & Hove Albion", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("highlightly", "33973", "1146230", "Coventry", "soccer-coventry-city", "Coventry City", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("highlightly", "33973", "49291", "Ipswich", "soccer-ipswich-town", "Ipswich Town", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("highlightly", "33973", "54397", "Leeds", "soccer-leeds-united", "Leeds United", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    ("highlightly", "33973", "40781", "Tottenham", "soccer-tottenham-hotspur", "Tottenham Hotspur", "GB", "United Kingdom", "epl", ("https://www.premierleague.com/en/news/4365156",)),
    # Highlightly 2026/27 LaLiga variants, checked against official LALIGA club pages.
    ("highlightly", "119924", "458622", "Celta de Vigo", "soccer-celta-vigo", "Celta Vigo", "ES", "Spain", "laliga", ("https://www.laliga.com/en-ES/clubs/rc-celta", "https://www.laliga.com/en-US/laliga-easports/clubs")),
    ("highlightly", "119924", "463728", "Deportivo La Coruña", "soccer-deportivo", "Deportivo", "ES", "Spain", "laliga", ("https://www.laliga.com/en-US/clubs/rc-deportivo/next-matches", "https://www.laliga.com/en-US/laliga-easports/clubs")),
    ("highlightly", "119924", "456920", "Sevilla FC", "soccer-sevilla", "Sevilla", "ES", "Spain", "laliga", ("https://www.laliga.com/en-US/clubs/sevilla-fc", "https://www.laliga.com/en-US/laliga-easports/clubs")),
    # Highlightly 2026/27 Serie A variant, checked against the official league and club pages.
    ("highlightly", "115669", "430539", "Inter", "soccer-internazionale", "Internazionale", "IT", "Italy", "seriea", ("https://www.legaseriea.it/serie-a/statistiche/clubs", "https://www.inter.it/en")),
)
TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_team_scope_corroborations (
    corroboration_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    corroborating_provider TEXT NOT NULL,
    corroborating_entity_id TEXT NOT NULL,
    competition_provider_id TEXT NOT NULL,
    corroborating_competition_code TEXT NOT NULL,
    country_code TEXT NOT NULL,
    country_name TEXT NOT NULL,
    team_type TEXT NOT NULL,
    gender_scope TEXT NOT NULL,
    match_method TEXT NOT NULL,
    approval_reason TEXT NOT NULL,
    evidence_snapshot JSONB NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (
        provider, provider_entity_id, corroborating_provider,
        corroborating_entity_id, competition_provider_id
    )
);
CREATE INDEX IF NOT EXISTS provider_team_scope_corroborations_target_idx
    ON provider_team_scope_corroborations (provider, provider_entity_id);
"""


def build_approved_records(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    for competition in report.get("competitions") or []:
        for candidate in competition.get("candidates") or []:
            if candidate.get("status") != "scope_corroboration_candidate":
                continue
            country_code = str(candidate.get("country_code_iso3166_alpha2") or "").strip().upper()
            country_name = str(candidate.get("country_name_from_iso_code") or "").strip()
            team_type = str(candidate.get("team_type_from_api_ninjas") or "").strip().casefold()
            gender_raw = str(candidate.get("gender_from_api_ninjas") or "").strip().casefold()
            gender_scope = candidate.get("gender_scope_normalized_candidate")
            if (
                not country_code or not country_name or team_type != "club"
                or gender_raw != "men" or gender_scope != "male"
            ):
                continue
            provider = str(candidate.get("target_provider") or "").strip().casefold()
            provider_id = str(candidate.get("target_provider_team_id") or "").strip()
            api_id = str(candidate.get("api_ninjas_team_id") or "").strip()
            competition_id = str(candidate.get("competition_scope") or "").strip()
            competition_code = str(candidate.get("api_ninjas_domestic_competition") or "").strip()
            if not all((provider, provider_id, api_id, competition_id, competition_code)):
                continue
            snapshot = {
                "target_provider": provider,
                "target_provider_team_id": provider_id,
                "target_provider_team_name": candidate.get("target_provider_team_name"),
                "api_ninjas_team_id": api_id,
                "api_ninjas_team_name": candidate.get("api_ninjas_team_name"),
                "api_ninjas_competition_code": competition_code,
                "identity_basis": candidate.get("identity_basis"),
                "country_code_iso3166_alpha2": country_code,
                "country_name_from_iso_code": country_name,
                "team_type_from_api_ninjas": team_type,
                "gender_from_api_ninjas": gender_raw,
                "gender_scope_normalized_candidate": gender_scope,
            }
            records.append({
                "provider": provider,
                "provider_entity_id": provider_id,
                "corroborating_provider": "api_ninjas",
                "corroborating_entity_id": api_id,
                "competition_provider_id": competition_id,
                "corroborating_competition_code": competition_code,
                "country_code": country_code,
                "country_name": country_name,
                "team_type": team_type,
                "gender_scope": gender_scope,
                "match_method": "unique_exact_normalized_team_name_within_same_current_domestic_competition",
                "approval_reason": APPROVAL_REASON,
                "evidence_snapshot": snapshot,
            })
    for (
        provider, competition_id, target_id, target_name,
        api_id, api_name, country_code, country_name, competition_code,
        official_urls,
    ) in MANUAL_ALIAS_APPROVALS:
        competition = next((
            item for item in report.get("competitions") or []
            if item.get("target_provider") == provider
            and str(item.get("target_competition_provider_id")) == competition_id
        ), None)
        if not competition:
            continue
        unmatched = next((
            item for item in competition.get("unmatched_target_teams") or []
            if str(item.get("provider_entity_id")) == target_id
            and str(item.get("name")) == target_name
        ), None)
        if not unmatched:
            continue
        candidate = next((
            item for item in unmatched.get("near_name_candidates") or []
            if str(item.get("api_ninjas_team_id")) == api_id
            and str(item.get("api_ninjas_team_name")) == api_name
        ), None)
        if not candidate:
            candidate = next((
                item for item in competition.get("api_ninjas_team_catalogue") or []
                if str(item.get("provider_entity_id")) == api_id
                and str(item.get("name")) == api_name
            ), None)
            if candidate:
                candidate = {
                    **candidate,
                    "country_code_iso3166_alpha2": candidate.get("country_code"),
                    "country_name_from_iso_code": {
                        "DE": "Germany",
                        "FR": "France",
                        "GB": "United Kingdom",
                        "IT": "Italy",
                        "ES": "Spain",
                    }.get(str(candidate.get("country_code") or "").strip().upper()),
                    "team_type_from_api_ninjas": candidate.get("team_type"),
                    "gender_from_api_ninjas": candidate.get("gender_scope"),
                    "api_ninjas_domestic_competition": competition.get("api_ninjas_competition_code"),
                }
        if not candidate or (
            candidate.get("country_code_iso3166_alpha2") != country_code
            or candidate.get("country_name_from_iso_code") != country_name
            or candidate.get("team_type_from_api_ninjas") != "club"
            or candidate.get("gender_from_api_ninjas") != "men"
            or candidate.get("api_ninjas_domestic_competition") != competition_code
        ):
            continue
        reason = (
            "Layer 12 manual official-name alias review: exact provider IDs and names "
            "were revalidated in the same current domestic competition; official "
            "competition/club references confirm the club-name variant. API Ninjas "
            "explicitly reports active club, ISO country and men's gender. Scope "
            "evidence only; not a canonical team identity or provider link."
        )
        snapshot = {
            "target_provider": provider, "target_provider_team_id": target_id,
            "target_provider_team_name": target_name,
            "api_ninjas_team_id": api_id, "api_ninjas_team_name": api_name,
            "api_ninjas_competition_code": competition_code,
            "competition_provider_id": competition_id,
            "identity_basis": "explicit_manual_alias_review_with_official_2026_27_competition_reference",
            "country_code_iso3166_alpha2": country_code,
            "country_name_from_iso_code": country_name,
            "team_type_from_api_ninjas": "club", "gender_from_api_ninjas": "men",
            "official_reference_urls": list(official_urls),
        }
        records.append({
            "provider": provider, "provider_entity_id": target_id,
            "corroborating_provider": "api_ninjas", "corroborating_entity_id": api_id,
            "competition_provider_id": competition_id,
            "corroborating_competition_code": competition_code,
            "country_code": country_code, "country_name": country_name,
            "team_type": "club", "gender_scope": "male",
            "match_method": "manual_official_competition_alias_review",
            "approval_reason": reason, "evidence_snapshot": snapshot,
        })
    return records


def approve_team_scope_corroborations(database_url: str) -> dict[str, Any]:
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    audit = audit_team_scope_corroboration(database_url)
    records = build_approved_records(audit)
    inserted = 0
    already_present = 0
    held_conflicts = []
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(TABLE_SQL)
            for row in records:
                cursor.execute(
                    """SELECT country_code, country_name, team_type, gender_scope,
                              corroborating_entity_id
                       FROM provider_team_scope_corroborations
                       WHERE provider = %s AND provider_entity_id = %s
                       ORDER BY approved_at DESC""",
                    (row["provider"], row["provider_entity_id"]),
                )
                existing = cursor.fetchall()
                conflicting = [
                    value for value in existing
                    if (
                        str(value[0]) != row["country_code"]
                        or str(value[1]) != row["country_name"]
                        or str(value[2]) != row["team_type"]
                        or str(value[3]) != row["gender_scope"]
                    )
                ]
                if conflicting:
                    held_conflicts.append({
                        "provider": row["provider"],
                        "provider_entity_id": row["provider_entity_id"],
                        "reason": "existing_scope_corroboration_conflict",
                    })
                    continue
                if any(str(value[4]) == row["corroborating_entity_id"] for value in existing):
                    already_present += 1
                    continue
                corroboration_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    ":".join((
                        row["provider"], row["provider_entity_id"],
                        row["corroborating_provider"], row["corroborating_entity_id"],
                        row["competition_provider_id"],
                    )),
                ))
                cursor.execute(
                    """INSERT INTO provider_team_scope_corroborations (
                           corroboration_id, provider, provider_entity_id,
                           corroborating_provider, corroborating_entity_id,
                           competition_provider_id, corroborating_competition_code,
                           country_code, country_name, team_type, gender_scope,
                           match_method, approval_reason, evidence_snapshot
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (
                           provider, provider_entity_id, corroborating_provider,
                           corroborating_entity_id, competition_provider_id
                       ) DO NOTHING""",
                    (
                        corroboration_id, row["provider"], row["provider_entity_id"],
                        row["corroborating_provider"], row["corroborating_entity_id"],
                        row["competition_provider_id"], row["corroborating_competition_code"],
                        row["country_code"], row["country_name"], row["team_type"],
                        row["gender_scope"], row["match_method"], row["approval_reason"],
                        Jsonb(row["evidence_snapshot"]),
                    ),
                )
                inserted += cursor.rowcount
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "operation": "provider_team_scope_corroboration_approval",
        "write_scope": "provider_team_scope_corroborations_table_only",
        "candidate_records": len(records),
        "exact_name_corroborations": sum(row["match_method"] == "unique_exact_normalized_team_name_within_same_current_domestic_competition" for row in records),
        "manual_official_alias_corroborations": sum(row["match_method"] == "manual_official_competition_alias_review" for row in records),
        "new_corroborations_written": inserted,
        "already_present": already_present,
        "held_conflicts": held_conflicts,
        "highlightly_corroborations": sum(row["provider"] == "highlightly" for row in records) - len([
            row for row in held_conflicts if row["provider"] == "highlightly"
        ]),
        "livescore_corroborations": sum(row["provider"] == "livescore_football" for row in records) - len([
            row for row in held_conflicts if row["provider"] == "livescore_football"
        ]),
        "provider_source_rows_updated": 0,
        "canonical_entities_written": 0,
        "provider_links_written": 0,
        "fixtures_written": 0,
        "predictions_written": 0,
        "prediction_ledger_touched": False,
        "approval_reason": APPROVAL_REASON,
        "age_group_scope_resolved": False,
        "squad_scope_resolved": False,
        "interpretation": (
            "Approved records are cross-provider scope corroboration evidence only. "
            "The source provider rows are unchanged and team canonical identity remains "
            "held until age-group and squad scope are independently evidenced."
        ),
    }


def main() -> int:
    report = approve_team_scope_corroborations(
        os.getenv("PROVIDER_DATABASE_URL", "").strip()
    )
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
