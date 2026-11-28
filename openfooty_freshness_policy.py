"""Explicit operator-supplied freshness limits for OpenFooty readiness.

No thresholds are defaulted. Missing settings are omitted so the readiness
assessment can fail closed for the corresponding evidence class.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SETTING_NAMES = {
    "fixture": "OPENFOOTY_FIXTURE_MAX_AGE_HOURS",
    "availability": "OPENFOOTY_AVAILABILITY_MAX_AGE_HOURS",
    "history": "OPENFOOTY_HISTORY_MAX_AGE_HOURS",
}


def load_openfooty_freshness_limits(
    *settings_sources: Mapping[str, Any] | None,
) -> dict[str, float]:
    """Load positive finite hour limits; earlier sources take precedence.

    Sources are checked in order (the app passes environment, then secrets).
    Blank and absent settings are treated as unspecified, never as defaults.
    """
    limits: dict[str, float] = {}
    for evidence_class, setting_name in SETTING_NAMES.items():
        raw: Any = None
        for source in settings_sources:
            if source is None:
                continue
            try:
                candidate = source.get(setting_name)
            except Exception:
                # Streamlit may raise when no secrets file is configured.
                continue
            if candidate is not None and str(candidate).strip():
                raw = candidate
                break
        if raw is None:
            continue
        if isinstance(raw, bool):
            raise ValueError(f"{setting_name} must be a finite positive number of hours")
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{setting_name} must be a finite positive number of hours"
            ) from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{setting_name} must be a finite positive number of hours")
        limits[evidence_class] = value
    return limits
