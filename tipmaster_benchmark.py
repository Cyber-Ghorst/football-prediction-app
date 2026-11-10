"""Independent TipMaster crowd-consensus benchmark adapter.

The returned outcome shares describe player agreement, not calibrated model
probabilities. This module is diagnostic-only and must never feed prediction
inputs, model weights, or TVD.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

import requests


TIPMASTER_BASE_URL = "https://tipmaster.de"
TIPMASTER_CONSENSUS_URL = f"{TIPMASTER_BASE_URL}/api/agent/v1/consensus"
TIPMASTER_SOURCE_URL = "https://tipmaster.de/agents/"
MIN_GROUP_SAMPLE = 20
OUTCOMES = ("home", "draw", "away")


class TipMasterError(RuntimeError):
    """Raised when the public TipMaster feed cannot be read safely."""


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_epoch(value: Any) -> datetime | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric):
        return None
    try:
        return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _valid_outcome_shares(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        shares = {key: float(value[key]) for key in OUTCOMES}
    except (KeyError, TypeError, ValueError):
        return None
    if any(not isfinite(item) or item < 0 or item > 1 for item in shares.values()):
        return None
    total = sum(shares.values())
    # TipMaster documents these as fractions summing to one within rounding.
    if not 0.98 <= total <= 1.02:
        return None
    return {key: shares[key] / total for key in OUTCOMES}


def _normalise_band(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    group_id = str(item.get("id") or "").strip().casefold()
    if group_id not in {"top20", "top25", "all"}:
        return None
    sample = item.get("sample")
    if isinstance(sample, bool):
        return None
    try:
        sample = int(sample)
    except (TypeError, ValueError):
        return None
    if sample < MIN_GROUP_SAMPLE:
        return None
    shares = _valid_outcome_shares(item.get("outcome"))
    if shares is None:
        return None
    return {
        "id": group_id,
        "label": str(item.get("label") or group_id),
        "sample": sample,
        "shares": shares,
        "majority": item.get("majority"),
    }


def normalize_tipmaster_match(
    row: Mapping[str, Any],
    *,
    fetched_at: str | None = None,
) -> dict[str, Any] | None:
    """Validate and normalize one frozen National-mode consensus record.

    Only locked/played records are eligible. The deadline is the timestamp at
    which TipMaster says the crowd's picks became immutable; it must precede
    kickoff. Results and score fields are deliberately not copied.
    """
    if not isinstance(row, Mapping):
        return None
    if str(row.get("mode") or "").casefold() != "national":
        return None
    status = str(row.get("status") or "").casefold()
    if status not in {"locked", "played"}:
        return None

    match_id = str(row.get("id") or "").strip()
    competition = str(row.get("competition") or "").strip()
    home = str(row.get("home") or "").strip()
    away = str(row.get("away") or "").strip()
    kickoff = _parse_epoch(row.get("kickoffUtc"))
    deadline = _parse_epoch(row.get("deadlineUtc"))
    if not all((match_id, competition, home, away, kickoff, deadline)):
        return None
    if deadline >= kickoff:
        return None

    bands = row.get("bands")
    items = bands.get("items") if isinstance(bands, Mapping) else None
    groups: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            normalized = _normalise_band(item)
            if normalized:
                groups[normalized["id"]] = normalized
    if not groups:
        return None

    source_url = row.get("source")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        source_url = TIPMASTER_SOURCE_URL

    return {
        "source": "tipmaster",
        "source_url": source_url,
        "source_match_id": match_id,
        "mode": "national",
        "status": status,
        "competition": competition,
        "home_team": home,
        "away_team": away,
        "kickoff_at": _iso(kickoff),
        "prediction_locked_at": _iso(deadline),
        "source_updated_at": _iso(_parse_iso_datetime(row.get("updatedAt"))),
        "fetched_at": fetched_at,
        "groups": groups,
        "interpretation": (
            "Outcome shares measure the selected group's agreement, not calibrated "
            "probabilities or a guaranteed forecast."
        ),
        "prediction_inputs_eligible": False,
    }


def normalize_tipmaster_payload(
    payload: Mapping[str, Any],
    *,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Normalize a full TipMaster consensus response with audit counters."""
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        raise TipMasterError("TipMaster returned an invalid response envelope.")
    rows = payload.get("matches")
    if not isinstance(rows, list):
        raise TipMasterError("TipMaster response did not contain a matches list.")

    captured_at = fetched_at or datetime.now(timezone.utc).isoformat()
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicates = 0
    rejected = 0
    for row in rows:
        item = normalize_tipmaster_match(row, fetched_at=captured_at)
        if item is None:
            rejected += 1
            continue
        match_id = item["source_match_id"]
        if match_id in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(match_id)
        normalized.append(item)

    normalized.sort(key=lambda item: (item["kickoff_at"], item["source_match_id"]))
    return {
        "source": "tipmaster",
        "source_url": TIPMASTER_SOURCE_URL,
        "source_generated_at": _iso(_parse_iso_datetime(payload.get("generatedAt"))),
        "fetched_at": captured_at,
        "matches": normalized,
        "counts": {
            "received": len(rows),
            "accepted": len(normalized),
            "rejected": rejected,
            "duplicates": duplicates,
        },
        "prediction_inputs_eligible": False,
    }


def fetch_tipmaster_consensus(
    *,
    session: Any = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Fetch the public National-mode feed; no API key is required."""
    client = session or requests
    try:
        response = client.get(
            TIPMASTER_CONSENSUS_URL,
            params={"mode": "national"},
            headers={"User-Agent": "FootballPredictionLab/1.0 (+https://tipmaster.de/agents/)"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise TipMasterError(f"TipMaster request failed: {type(exc).__name__}.") from exc
    return normalize_tipmaster_payload(payload)
