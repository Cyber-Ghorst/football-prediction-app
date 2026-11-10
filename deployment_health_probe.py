"""Classify the unauthenticated Streamlit deployment health probe."""

from __future__ import annotations

from typing import Any


def classify_probe_response(
    http_status: int,
    *,
    body: str = "",
    redirect_location: str = "",
) -> dict[str, Any]:
    """Distinguish a healthy endpoint from a protected but reachable app."""
    status = int(http_status)
    location = str(redirect_location or "")
    if status == 200 and str(body or "").strip().lower() == "ok":
        return {
            "deployment_reachable": True,
            "application_status": "healthy",
            "deployment_health": "healthy",
            "health_endpoint_confirmed": True,
            "healthy": True,
            "result": "healthy",
        }

    auth_redirect = (
        status in (301, 302, 303, 307, 308)
        and "share.streamlit.io/-/auth/app" in location
    )
    if auth_redirect or status in (401, 403):
        return {
            "deployment_reachable": True,
            "application_status": "authentication_required",
            "deployment_health": "protected_reachable",
            "authentication": "required",
            "health_endpoint_confirmed": False,
            "healthy": None,
            "result": "protected_endpoint_reachable",
            "note": (
                "The deployment host and app route are reachable and enforce "
                "authentication. This unauthenticated probe cannot verify the "
                "authenticated Streamlit session; app smoke and provider checks "
                "are reported separately."
            ),
        }

    if 500 <= status <= 599:
        return {
            "deployment_reachable": True,
            "application_status": "unhealthy",
            "deployment_health": "degraded",
            "health_endpoint_confirmed": False,
            "healthy": False,
            "result": "application_error",
            "error": f"HTTP {status}",
        }

    return {
        "deployment_reachable": 100 <= status <= 599,
        "application_status": "unverified",
        "deployment_health": "reachable_unverified",
        "health_endpoint_confirmed": False,
        "healthy": None,
        "result": "reachable_but_health_unconfirmed",
        "note": f"HTTP {status} did not return the expected HTTP 200 and body 'ok'.",
    }
