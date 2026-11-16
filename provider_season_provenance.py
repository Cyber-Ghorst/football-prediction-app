"""Strict season-label extraction for provider roster provenance."""
from __future__ import annotations
import json
import re
from collections.abc import Mapping
from typing import Any

def payload_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}

def explicit_season_label(value: Any) -> str | None:
    """Extract an explicit season label; never infer it from an evidence method or opaque ID."""
    raw = payload_mapping(value)
    for key in ("season_label", "season_name", "catalogue_season_label",
                "catalogue_reference_season", "season_year", "season"):
        item = raw.get(key)
        if isinstance(item, Mapping):
            item = item.get("label") or item.get("name") or item.get("year")
        if item is None or isinstance(item, (list, dict, bool)):
            continue
        label = str(item).strip()
        match = re.fullmatch(r"(20\d{2})\\s*(?:/|-|–)\\s*(\d{2}|20\d{2})", label)
        if match:
            start = int(match.group(1))
            end = match.group(2)
            if end in {str(start + 1), str(start + 1)[-2:]}:
                return f"{start}/{str(start + 1)[-2:]}"
        elif re.fullmatch(r"20\d{2}", label):
            start = int(label)
            return f"{start}/{str(start + 1)[-2:]}"
    return None

def season_match(target_payload: Any, corroborating_payload: Any) -> tuple[bool, str | None, str | None, str]:
    target = explicit_season_label(target_payload)
    corroborating = explicit_season_label(corroborating_payload)
    if not target or not corroborating:
        return False, target, corroborating, "held_missing_explicit_season"
    if target != corroborating:
        return False, target, corroborating, "held_mismatched_season"
    if target != "2026/27":
        return False, target, corroborating, "held_not_target_2026_27_season"
    return True, target, corroborating, "verified_2026_27_season_match"
