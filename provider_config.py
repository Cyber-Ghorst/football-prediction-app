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
            "app_integration": "active",
            "credential_name": "APISPORTS_API_KEY",
        },
        {
            "provider": "API Ninjas",
            "adapter": "implemented",
            "credential_configured": _secret_present("API_NINJAS_API_KEY", ("API_NINJAS_KEY",)),
            "app_integration": "adapter only; fallback not enabled",
            "credential_name": "API_NINJAS_API_KEY",
        },
        {
            "provider": "Highlightly",
            "adapter": "implemented",
            "credential_configured": _secret_present("HIGHLIGHTLY_API_KEY", ("API_FOOTBALL_KEY",)),
            "app_integration": "adapter only; fallback not enabled",
            "credential_name": "HIGHLIGHTLY_API_KEY",
        },
        {
            "provider": "LiveScoreFootball",
            "adapter": "implemented",
            "credential_configured": True,
            "app_integration": "read-only adapter; not yet enabled as automatic fallback",
            "credential_name": "none required for documented public endpoints",
        },
    ]
