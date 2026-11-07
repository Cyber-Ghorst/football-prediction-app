"""Safe provider configuration diagnostics; never returns or logs secret values."""
from __future__ import annotations

import os
from typing import Any


def _secret_present(name: str, aliases: tuple[str, ...] = ()) -> bool:
    if any(os.getenv(key) for key in (name, *aliases)):
        return True
    try:
        import streamlit as st
        return any(bool(st.secrets.get(key)) for key in (name, *aliases))
    except Exception:
        return False


def provider_readiness() -> list[dict[str, Any]]:
    return [
        {
            "provider": "API-Football v3",
            "adapter": "implemented",
            "credential_configured": _secret_present("APISPORTS_API_KEY"),
            "app_integration": "active; account status and quota diagnostics available",
            "credential_name": "APISPORTS_API_KEY",
        },
        {
            "provider": "API Ninjas",
            "adapter": "implemented",
            "credential_configured": _secret_present("API_NINJAS_API_KEY", ("API_NINJAS_KEY",)),
            "app_integration": "connection diagnostic available; match fallback not yet enabled",
            "credential_name": "API_NINJAS_API_KEY",
        },
        {
            "provider": "Highlightly",
            "adapter": "implemented",
            "credential_configured": _secret_present("HIGHLIGHTLY_API_KEY", ("API_FOOTBALL_KEY",)),
            "app_integration": "connection diagnostic available; match fallback not yet enabled",
            "credential_name": "HIGHLIGHTLY_API_KEY",
        },
        {
            "provider": "Sportmonks Football API v3",
            "adapter": "implemented",
            "credential_configured": _secret_present("SPORTMONKS_API_TOKEN", ("SPORTMONKS_API_KEY",)),
            "app_integration": "authenticated connection diagnostic and current-season Layer 2 collection available; exact competition/season coverage and data-quality gates enforced",
            "credential_name": "SPORTMONKS_API_TOKEN",
        },
        {
            "provider": "LiveScoreFootball",
            "adapter": "implemented",
            "credential_configured": False,
            "credential_required": False,
            "app_integration": "read-only adapter; metadata freshness and live competition crosswalk checks implemented; fallback remains disabled",
            "credential_name": "none required for documented public endpoints",
        },
    ]
