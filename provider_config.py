"""Safe provider roles and configuration diagnostics; never returns secret values."""
from __future__ import annotations

import os
from typing import Any


# Roles describe intended responsibility; they do not bypass validation or
# activate an unverified fallback.
PROVIDER_ROLES: dict[str, dict[str, Any]] = {
    "sportmonks": {
        "display_name": "Sportmonks Football API v3",
        "rank": 1,
        "role": "Primary current-season provider",
        "domains": ("fixtures", "future_fixtures", "results", "standings", "statistics", "injuries", "lineups", "players", "squads"),
        "limitation": "Coverage is limited to competitions/seasons enabled by the account; each selected competition must pass data-quality gates.",
    },
    "highlightly": {
        "display_name": "Highlightly",
        "rank": 2,
        "role": "Independent current-season corroboration and secondary source",
        "domains": ("fixtures", "results", "standings", "statistics", "injuries", "lineups", "players", "squads"),
        "limitation": "Official catalogue advertises 950+ leagues, but account-specific catalogue access currently returns HTTP 429; plan coverage, fields, quotas and refresh intervals must be revalidated before broad fixture discovery. Existing opt-in missing-stat, exact-fixture lineup and exact-verified result-history paths remain available with Sportmonks precedence and no injury/availability inference.",
    },
    "api_football": {
        "display_name": "API-Football v3",
        "rank": 3,
        "role": "Historical specialist source and secondary detail provider",
        "domains": ("fixtures", "results", "standings", "statistics", "injuries", "lineups", "players", "squads"),
        "limitation": "The configured account is limited to seasons 2022–2024; do not request newer seasons from this account.",
    },
    "api_ninjas": {
        "display_name": "API Ninjas",
        "rank": 4,
        "role": "Independent fixtures/results/standings and club/squad corroboration",
        "domains": ("fixtures", "results", "standings", "players", "squads"),
        "limitation": "The adapter supplies fixtures/results/standings and club/squad data, but no detailed fixture statistics, injuries or lineups. Result candidates enter history only after exact Sportmonks fixture and score verification.",
    },
    "livescore_football": {
        "display_name": "LiveScoreFootball",
        "rank": 5,
        "role": "Scheduled-fixture candidate plus competition-specific results/standings corroboration",
        "domains": ("future_fixtures", "fixtures", "results", "standings"),
        "limitation": "The existing adapter exposes a scheduled-fixtures endpoint and the public service is hosted at worldcup26.ir. This is one provider, not a separate WorldCup26 provider. The database-backed snapshot depends on an external listener; keep the future-fixture route disabled until live scheduled records, kickoff timestamps, coverage and per-event freshness pass validation.",
    },
    "openligadb": {
        "display_name": "OpenLigaDB",
        "rank": 6,
        "role": "Free fixture discovery and validation candidate",
        "domains": ("future_fixtures", "results", "standings"),
        "limitation": "No API key; strongest in German football; public API documents a 60-requests-per-minute IP limit. Community-maintained data and applicable reuse terms must be checked before commercial use.",
    },
    "openfootball": {
        "display_name": "OpenFootball football.json",
        "rank": 7,
        "role": "Open fixture discovery and validation candidate",
        "domains": ("future_fixtures", "results"),
        "limitation": "Public CC0 JSON datasets. Current-season mirror refreshes daily, but upstream source updates are not automatically daily; timezone and event freshness must be validated.",
    },
    "open_matchday": {
        "display_name": "Open Matchday",
        "rank": 8,
        "role": "Non-commercial fixture discovery candidate",
        "domains": ("future_fixtures", "results", "match_statistics"),
        "limitation": "Advertises 75 competitions and daily CSV refresh, but terms restrict use to non-commercial purposes. Not live; fixed CET-1 kickoff convention can be inaccurate during daylight-saving time. Disabled for commercial use.",
    },
    "bzzoiro": {
        "display_name": "Bzzoiro Sports Data",
        "rank": 9,
        "role": "Free-tier future-fixture discovery candidate",
        "domains": ("future_fixtures", "results", "standings", "statistics", "lineups", "odds", "predictions"),
        "limitation": "Football free tier advertises 60+ competitions and 7,500 requests/day; requires BZZOIRO_API_TOKEN. Terms permit app display and derived prediction outputs but prohibit raw-data redistribution as a standalone feed/database/API. Future-fixture route remains disabled pending live validation.",
    },
    "football_data_org": {
        "display_name": "football-data.org v4",
        "rank": 11,
        "role": "Independent current-season data provider and competition/team catalogue source",
        "domains": ("independent_data", "fixtures", "teams", "competitions"),
        "limitation": "Requires FOOTBALL_DATA_ORG_API_TOKEN; account-plan competition coverage, rate limits, current-season access, freshness and canonical crosswalks must be verified before routing or promotion.",
    },
    "openscores": {
        "display_name": "OpenScores",
        "rank": 10,
        "role": "Read-only historical result observations and entity-mapping audit; not a future-fixture source",
        "domains": ("results", "historical_results"),
        "limitation": "Staged observations are not canonical fixtures or prediction inputs. Entity crosswalks remain unapproved; do not use OpenScores for future-fixture discovery or production prediction routing.",
    },
}


def _secret_present(name: str, aliases: tuple[str, ...] = ()) -> bool:
    if any(os.getenv(key) for key in (name, *aliases)):
        return True
    try:
        import streamlit as st
        return any(bool(st.secrets.get(key)) for key in (name, *aliases))
    except Exception:
        return False


def provider_readiness() -> list[dict[str, Any]]:
    configured = {
        "api_football": _secret_present("APISPORTS_API_KEY"),
        "api_ninjas": _secret_present("API_NINJAS_API_KEY", ("API_NINJAS_KEY",)),
        "highlightly": _secret_present("HIGHLIGHTLY_API_KEY", ("API_FOOTBALL_KEY",)),
        "sportmonks": _secret_present("SPORTMONKS_API_TOKEN", ("SPORTMONKS_API_KEY",)),
        "livescore_football": False,
        "openligadb": False,
        "openfootball": False,
        "open_matchday": False,
        "bzzoiro": _secret_present("BZZOIRO_API_TOKEN"),
        "openscores": _secret_present("OPENSCORES_API_KEY"),
        "football_data_org": _secret_present("FOOTBALL_DATA_ORG_API_TOKEN", ("FOOTBALL_DATA_ORG_TOKEN", "FOOTBALL_DATA_API_KEY")),
    }
    integration = {
        "api_football": "historical Layer 2 path active for supported seasons; account status/quota diagnostic available",
        "api_ninjas": "adapter and authenticated smoke test available; exact result candidates can trigger an opt-in Sportmonks-verified history fallback; no direct statistics, injury or lineup fields",
        "highlightly": "adapter and authenticated smoke test available; opt-in exact-match missing-stat, lineup and Sportmonks-verified result-history fallbacks are wired into Layer 2; no injury or availability inference",
        "sportmonks": "current-season Layer 2 path active; exact competition/season coverage and data-quality gates enforced",
        "livescore_football": "implemented read-only adapter exposes scheduled fixtures, results and standings; 35-competition catalogue audit and opt-in missing-score fallback are wired into Streamlit (default off). Future-fixture route remains disabled until live scheduled fixtures, kickoff precision, exact season/team crosswalks and event freshness are verified; worldcup26.ir is this same service, not a second provider",
        "openligadb": "read-only season adapter implemented; live coverage, freshness, canonical crosswalk and route activation remain pending",
        "openfootball": "read-only football.json adapter implemented; timezone-bearing future rows, upstream freshness, canonical crosswalk and route activation remain pending",
        "open_matchday": "read-only CSV adapter implemented; fixed CET-1 timestamps are rejected without a verified timezone; non-commercial rights and route activation remain pending",
        "bzzoiro": "read-only API adapter implemented; requires BZZOIRO_API_TOKEN and uses documented v2 events endpoint; live coverage, licence and canonical crosswalk remain pending",
        "openscores": "read-only historical/result observations for mapping and audit; not a future-fixture source; not enabled for production prediction inputs",
        "football_data_org": "independent football-data.org v4 adapter and separate read-only provider refresh implemented; it is not a future-fixture discovery source. Authenticated coverage, competition/country/season/team crosswalks, freshness and database round-trip remain review-gated; no canonical promotion",
    }
    credential_names = {
        "api_football": "APISPORTS_API_KEY",
        "api_ninjas": "API_NINJAS_API_KEY",
        "highlightly": "HIGHLIGHTLY_API_KEY",
        "sportmonks": "SPORTMONKS_API_TOKEN",
        "livescore_football": "none required for documented public endpoints",
        "openligadb": "none required",
        "openfootball": "none required",
        "open_matchday": "none required",
        "bzzoiro": "BZZOIRO_API_TOKEN",
        "openscores": "OPENSCORES_API_KEY",
        "football_data_org": "FOOTBALL_DATA_ORG_API_TOKEN",
    }
    rows = []
    for key in (
        "sportmonks", "highlightly", "api_football", "api_ninjas",
        "livescore_football", "openligadb", "openfootball",
        "open_matchday", "bzzoiro", "openscores", "football_data_org",
    ):
        role = PROVIDER_ROLES[key]
        rows.append({
            "provider_id": key,
            "provider": role["display_name"],
            "rank": role["rank"],
            "role": role["role"],
            "domains": list(role["domains"]),
            "limitation": role["limitation"],
            "adapter": "implemented" if key in {
                "sportmonks", "highlightly", "api_football", "api_ninjas",
                "livescore_football", "openligadb", "openfootball", "open_matchday", "bzzoiro", "openscores", "football_data_org",
            } else "candidate_only_not_implemented",
            "credential_configured": configured[key],
            "credential_required": key in {"sportmonks", "highlightly", "api_football", "api_ninjas", "bzzoiro", "openscores", "football_data_org"},
            "app_integration": integration[key],
            "credential_name": credential_names[key],
        })
    return rows
