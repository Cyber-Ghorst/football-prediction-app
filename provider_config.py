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
        "domains": ("fixtures", "results", "standings", "statistics", "injuries", "lineups", "players", "squads"),
        "limitation": "Coverage is limited to competitions/seasons enabled by the account; each selected competition must pass data-quality gates.",
    },
    "highlightly": {
        "display_name": "Highlightly",
        "rank": 2,
        "role": "Independent current-season corroboration and secondary source",
        "domains": ("fixtures", "results", "standings", "statistics", "injuries", "lineups", "players", "squads"),
        "limitation": "Coverage, fields, quotas and refresh intervals are plan-dependent; match data is not yet active in Layer 2 reconciliation.",
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
        "limitation": "The current adapter does not supply detailed fixture statistics, injuries or lineups; not yet active in Layer 2 reconciliation.",
    },
    "livescore_football": {
        "display_name": "LiveScoreFootball",
        "rank": 5,
        "role": "Conditional competition-specific corroboration for fixtures/results/standings",
        "domains": ("fixtures", "results", "standings"),
        "limitation": "Database-backed snapshots can be delayed; require exact competition/season crosswalk and fresh sync metadata for every use.",
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
    }
    integration = {
        "api_football": "historical Layer 2 path active for supported seasons; account status/quota diagnostic available",
        "api_ninjas": "adapter and authenticated smoke test available; canonical normalizer exists; not yet active in Layer 2 reconciliation",
        "highlightly": "adapter and authenticated smoke test available; canonical normalizer exists; not yet active in Layer 2 reconciliation",
        "sportmonks": "current-season Layer 2 path active; exact competition/season coverage and data-quality gates enforced",
        "livescore_football": "read-only adapter, metadata freshness and exact competition crosswalk checks available; automatic fallback remains disabled",
    }
    credential_names = {
        "api_football": "APISPORTS_API_KEY",
        "api_ninjas": "API_NINJAS_API_KEY",
        "highlightly": "HIGHLIGHTLY_API_KEY",
        "sportmonks": "SPORTMONKS_API_TOKEN",
        "livescore_football": "none required for documented public endpoints",
    }
    rows = []
    for key in ("sportmonks", "highlightly", "api_football", "api_ninjas", "livescore_football"):
        role = PROVIDER_ROLES[key]
        rows.append({
            "provider_id": key,
            "provider": role["display_name"],
            "rank": role["rank"],
            "role": role["role"],
            "domains": list(role["domains"]),
            "limitation": role["limitation"],
            "adapter": "implemented",
            "credential_configured": configured[key],
            "credential_required": key != "livescore_football",
            "app_integration": integration[key],
            "credential_name": credential_names[key],
        })
    return rows
