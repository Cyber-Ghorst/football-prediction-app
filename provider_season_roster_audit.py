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
    collect_livescore_season_participants,
)

REPORT = Path("provider-season-roster-audit.json")
TARGET_HIGHLIGHTLY = (
    {"name": "Bundesliga", "country": "Germany"},
    {"name": "Ligue 1", "country": "France"},
    {"name": "World Cup", "country": None},
)
TARGET_LIVESCORE = (
    {"name": "Bundesliga", "country": "Germany", "slug": "ger.1"},
    {"name": "Ligue 1", "country": "France", "slug": "fra.1"},
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
                results.append({
                    "target": target, "status": "collected" if roster["teams"] else "empty_standings",
                    "selection": selection, "league_id": league.get("id"),
                    "season": SEASON_YEAR, "team_count": len(roster["teams"]),
                    "team_evidence_method": roster["team_evidence_method"],
                    "team_evidence_complete": roster["team_evidence_complete"],
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
        catalogue = client.leagues(kind="club", available=True)
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


def main() -> int:
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "database_touched": False,
        "canonical_rows_written": 0,
        "provider_links_written": 0,
        "fixtures_imported": 0,
        "prediction_model_modified": False,
        "prediction_ledger_touched": False,
        "highlightly": audit_highlightly_rosters(),
        "livescore_football": audit_livescore_rosters(),
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
