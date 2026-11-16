"""Read-only season roster evidence audit across independent providers.

This operation collects provider-native roster evidence only. It does not
persist canonical rows, create provider links, import fixtures, or run
predictions. Highlightly standings provide a league-season table; LiveScore
fixture participants are deliberately marked as incomplete evidence.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from highlightly import HighlightlyClient
from livescore_football import LiveScoreFootballClient
from provider_roster_collection import (
    collect_highlightly_season_roster,
    collect_highlightly_season_match_participants,
    collect_livescore_season_participants,
    collect_livescore_season_standings,
)

REPORT = Path("provider-season-roster-audit.json")
TARGET_HIGHLIGHTLY = (
    {"name": "Bundesliga", "country": "Germany"},
    {"name": "Ligue 1", "country": "France"},
    {"name": "World Cup", "country": None},
)
TARGET_LIVESCORE = (
    {"name": "German Bundesliga", "country": "Germany", "slug": "ger.1"},
    {"name": "French Ligue 1", "country": "France", "slug": "fra.1"},
)
SEASON_START = "2026-08-01"
SEASON_END = "2027-05-31"
SEASON_YEAR = 2026


def _country_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("countryName")
    return str(value or "").strip()


def _select_highlightly(rows: list[dict[str, Any]], target: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    matches = []
    for row in rows:
        name = str(row.get("name") or row.get("leagueName") or "").strip()
        country = _country_name(row.get("country") or row.get("countryName"))
        if name.casefold() != target["name"].casefold():
            continue
        if target["country"] and country.casefold() != target["country"].casefold():
            continue
        matches.append(row)
    if len(matches) != 1:
        return None, "not_found" if not matches else "ambiguous_competition"
    return matches[0], "unique_exact_name_country"


def audit_highlightly_rosters() -> dict[str, Any]:
    if not (
        os.getenv("FREE_FIXTURE_TERMS_ACK_HIGHLIGHTLY", "").strip().casefold()
        in {"1", "true", "yes", "on"}
        and os.getenv("HIGHLIGHTLY_NON_BETTING_USE_CONFIRMED", "").strip().casefold()
        in {"1", "true", "yes", "on"}
    ):
        return {"status": "held", "reason": "Highlightly terms and non-betting-use acknowledgements are required.", "competitions": []}
    try:
        client = HighlightlyClient()
    except Exception as exc:
        return {"status": "not_configured", "reason": str(exc)[:250], "competitions": []}
    results = []
    try:
        for target in TARGET_HIGHLIGHTLY:
            try:
                params = {"leagueName": target["name"], "limit": 20, "offset": 0}
                if target["country"]:
                    params["countryName"] = target["country"]
                rows = client.leagues(**params)
                league, selection = _select_highlightly(rows, target)
                if league is None:
                    results.append({"target": target, "status": selection, "teams": []})
                    continue
                seasons = league.get("seasons") if isinstance(league.get("seasons"), list) else []
                season = next((row for row in seasons
                               if isinstance(row, dict) and str(row.get("season")) == str(SEASON_YEAR)), None)
                if season is None:
                    results.append({"target": target, "status": "season_not_listed",
                                    "league_id": league.get("id"), "teams": []})
                    continue
                roster = collect_highlightly_season_roster(
                    client, league=league, season=season,
                )
                if not roster["teams"]:
                    roster = collect_highlightly_season_match_participants(
                        client, league=league, season=season,
                    )
                results.append({
                    "target": target,
                    "status": (
                        "collected" if roster["teams"] and roster["team_evidence_method"] == "league_season_standings"
                        else "collected_match_participants" if roster["teams"]
                        else "empty_standings_and_matches"
                    ),
                    "selection": selection, "league_id": league.get("id"),
                    "season": SEASON_YEAR, "team_count": len(roster["teams"]),
                    "team_evidence_method": roster["team_evidence_method"],
                    "team_evidence_complete": roster["team_evidence_complete"],
                    "matches_examined": roster.get("matches_examined"),
                    "pagination_complete": roster.get("pagination_complete"),
                    "teams": roster["teams"],
                    "rate_limit": dict(client.last_metadata),
                })
            except Exception as exc:
                results.append({"target": target, "status": "error",
                                "reason": str(exc)[:250], "teams": []})
    finally:
        client.close()
    return {"status": "completed", "competitions": results}


def audit_livescore_rosters() -> dict[str, Any]:
    try:
        client = LiveScoreFootballClient()
    except Exception as exc:
        return {"status": "not_configured", "reason": str(exc)[:250], "competitions": []}
    results = []
    try:
        catalogue = client.leagues(kind="all", available=False)
        for target in TARGET_LIVESCORE:
            matches = [
                row for row in catalogue
                if str(row.get("slug") or "") == target["slug"]
                and str(row.get("name") or "").casefold() == target["name"].casefold()
                and str(row.get("country") or "").casefold() == target["country"].casefold()
                and row.get("active") is True
                and (row.get("coverage") or {}).get("hasData") is True
            ]
            if len(matches) != 1:
                results.append({"target": target,
                                "status": "not_found" if not matches else "ambiguous_competition",
                                "teams": []})
                continue
            league = matches[0]
            try:
                standings_roster = collect_livescore_season_standings(
                    client, league=league, season_year=SEASON_YEAR,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                )
                results.append({
                    **standings_roster,
                    "target": target,
                    "league_id": standings_roster["league"]["id"],
                    "team_count": len(standings_roster["teams"]),
                })
            except Exception as exc:
                results.append({
                    "target": target, "status": "error",
                    "team_evidence_method": "season_standings",
                    "reason": str(exc)[:250], "teams": [],
                    "team_evidence_complete": False,
                })
            try:
                roster = collect_livescore_season_participants(
                    client, league=league, season={"year": SEASON_YEAR},
                    date_from=SEASON_START, date_to=SEASON_END,
                )
                results.append({
                    "target": target, "status": "collected" if roster["teams"] else "no_participants",
                    "league_id": roster["league"]["id"], "season": SEASON_YEAR,
                    "fixtures_examined": roster["fixtures_examined"],
                    "team_count": len(roster["teams"]),
                    "team_evidence_method": roster["team_evidence_method"],
                    "team_evidence_complete": False,
                    "teams": roster["teams"],
                })
            except Exception as exc:
                results.append({"target": target, "status": "error",
                                "reason": str(exc)[:250], "teams": []})
    finally:
        client.close()
    return {"status": "completed", "competitions": results}



def _normalized_team_name(value: Any) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_roster_identity_candidates(
    highlightly: dict[str, Any],
    livescore: dict[str, Any],
) -> dict[str, Any]:
    """Compare only same-competition, same-season provider roster observations.

    Exact normalized names produce review candidates, never verified links.
    Duplicate normalized names are held as ambiguous. No aliases or fuzzy
    matching are attempted.
    """
    pairs = (
        ("Bundesliga", "German Bundesliga"),
        ("Ligue 1", "French Ligue 1"),
    )
    comparisons = []
    for highlightly_name, livescore_name in pairs:
        h_rows = [
            row for row in highlightly.get("competitions", [])
            if row.get("target", {}).get("name") == highlightly_name
            and row.get("status") == "collected"
            and row.get("team_evidence_method") == "league_season_standings"
        ]
        l_rows = [
            row for row in livescore.get("competitions", [])
            if row.get("target", {}).get("name") == livescore_name
            and row.get("status") == "collected"
            and row.get("team_evidence_method") == "season_standings"
            and row.get("team_evidence_complete") is True
        ]
        if len(h_rows) != 1 or len(l_rows) != 1:
            comparisons.append({
                "competition": highlightly_name,
                "status": "held_missing_or_ambiguous_roster",
                "candidate_count": 0, "ambiguous_count": 0,
                "candidates": [], "ambiguous": [], "unmatched_highlightly": [],
                "unmatched_livescore": [],
            })
            continue
        h_row, l_row = h_rows[0], l_rows[0]
        h_groups: dict[str, list[dict[str, Any]]] = {}
        l_groups: dict[str, list[dict[str, Any]]] = {}
        for team in h_row.get("teams", []):
            key = _normalized_team_name(team.get("name"))
            if key:
                h_groups.setdefault(key, []).append(team)
        for team in l_row.get("teams", []):
            key = _normalized_team_name(team.get("name"))
            if key:
                l_groups.setdefault(key, []).append(team)
        candidates, ambiguous = [], []
        for key in sorted(set(h_groups) & set(l_groups)):
            left, right = h_groups[key], l_groups[key]
            if len(left) != 1 or len(right) != 1:
                ambiguous.append({
                    "normalized_name": key,
                    "highlightly": [{"id": str(t["id"]), "name": t["name"]} for t in left],
                    "livescore_football": [{"id": str(t["id"]), "name": t["name"]} for t in right],
                    "status": "ambiguous_duplicate_normalized_name",
                })
                continue
            candidates.append({
                "normalized_name": key,
                "highlightly": {
                    "provider": "highlightly", "competition_id": str(h_row["league_id"]),
                    "season": str(h_row["season"]), "team_id": str(left[0]["id"]),
                    "team_name": left[0]["name"],
                    "evidence_method": h_row["team_evidence_method"],
                },
                "livescore_football": {
                    "provider": "livescore_football", "competition_id": str(l_row["league_id"]),
                    "season": str(l_row["season"]), "team_id": str(right[0]["id"]),
                    "team_name": right[0]["name"],
                    "evidence_method": l_row["team_evidence_method"],
                },
                "status": "candidate_exact_normalized_name_review_required",
                "verified": False,
                "link_written": False,
            })
        comparisons.append({
            "competition": highlightly_name,
            "country": h_row.get("target", {}).get("country"),
            "season": str(h_row.get("season")),
            "status": "candidate_review",
            "highlightly_team_count": len(h_row.get("teams", [])),
            "livescore_team_count": len(l_row.get("teams", [])),
            "candidate_count": len(candidates),
            "ambiguous_count": len(ambiguous),
            "candidates": candidates,
            "ambiguous": ambiguous,
            "unmatched_highlightly": [
                {"id": str(team["id"]), "name": team["name"]}
                for key, group in h_groups.items() if key not in l_groups
                for team in group
            ],
            "unmatched_livescore": [
                {"id": str(team["id"]), "name": team["name"]}
                for key, group in l_groups.items() if key not in h_groups
                for team in group
            ],
        })
    total = sum(row.get("candidate_count", 0) for row in comparisons)
    return {
        "status": "candidate_only",
        "method": "exact_normalized_team_name_within_country_competition_and_season",
        "automatic_aliases_used": False,
        "fuzzy_matching_used": False,
        "candidates_total": total,
        "verified_links_created": 0,
        "comparisons": comparisons,
        "warning": (
            "Matching names and season-scoped roster co-membership are review evidence, "
            "not proof of identity. Provider-native IDs remain namespaced and unlinked."
        ),
    }


def main() -> int:
    highlightly_report = audit_highlightly_rosters()
    livescore_report = audit_livescore_rosters()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_touched": False,
        "canonical_rows_written": 0,
        "provider_links_written": 0,
        "fixtures_imported": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "highlightly": highlightly_report,
        "livescore_football": livescore_report,
        "cross_provider_team_identity_candidates": build_roster_identity_candidates(
            highlightly_report, livescore_report,
        ),
        "season_window": {"year": SEASON_YEAR, "from": SEASON_START, "to": SEASON_END},
        "interpretation": (
            "Highlightly standings are season-scoped roster evidence. "
            "LiveScoreFootball fixture participants are incomplete observations. "
            "No cross-provider identity is inferred by this report."
        ),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "checked_at": report["checked_at"],
        "read_only": report["read_only"],
        "cross_provider_candidate_count": report["cross_provider_team_identity_candidates"]["candidates_total"],
        "highlightly": [
            {key: row.get(key) for key in ("target", "status", "league_id", "season", "team_count")}
            for row in report["highlightly"].get("competitions", [])
        ],
        "livescore_football": [
            {key: row.get(key) for key in ("target", "status", "league_id", "season", "fixtures_examined", "team_count")}
            for row in report["livescore_football"].get("competitions", [])
        ],
        "report": str(REPORT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
