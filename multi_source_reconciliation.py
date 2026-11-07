"""Three-or-more-provider match reconciliation.

All records must match one canonical fixture identity. Provider IDs remain
namespaced, fields are resolved independently, and conflicts are preserved.
This module performs no network requests and never averages source values.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from canonical_data import match_identity
from provider_core import Observation, resolve_field


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reconcile_match_records(
    records: Iterable[Mapping[str, Any]],
    *,
    fetched_at: Mapping[str, datetime] | None = None,
    now: datetime | None = None,
    max_age_seconds: int | None = 86400,
    team_aliases: Mapping[str, str] | None = None,
    livescore_verified: bool = False,
) -> dict[str, Any] | None:
    """Reconcile a fixture from at least two independent provider records.

    Returns None unless every supplied record matches the anchor on competition,
    season, home/away identity and kickoff. Duplicate provider records are
    rejected rather than silently allowing one provider to vote more than once.
    Freshness requires a supplied fetched_at timestamp per provider (either in
    the mapping or on the record); absent timestamps remain ineligible.
    """
    rows = list(records)
    if len(rows) < 2:
        return None

    providers = [str(row.get("source") or "") for row in rows]
    if any(not provider for provider in providers) or len(set(providers)) != len(providers):
        return None

    anchor = rows[0]
    if any(
        not match_identity(
            anchor, row, team_aliases=team_aliases, kickoff_tolerance_seconds=300
        )
        for row in rows[1:]
    ):
        return None

    timestamps = dict(fetched_at or {})
    for row, provider in zip(rows, providers):
        if provider not in timestamps:
            timestamps[provider] = _timestamp(row.get("fetched_at"))

    result = dict(anchor)
    result["home"] = dict(anchor.get("home") or {})
    result["away"] = dict(anchor.get("away") or {})
    result["source_ids"] = {}
    for side in ("home", "away"):
        result[side]["source_ids"] = {}
    result["reconciliation"] = {}
    result["source_ids_by_provider"] = {}

    for row, provider in zip(rows, providers):
        match_id = (row.get("source_ids") or {}).get(provider)
        if match_id:
            result["source_ids"][provider] = str(match_id)
        result["source_ids_by_provider"][provider] = {
            "match": str(match_id) if match_id else None,
        }
        for side in ("home", "away"):
            side_id = (row.get(side) or {}).get("source_ids", {}).get(provider)
            if side_id:
                result[side]["source_ids"][provider] = str(side_id)
                result["source_ids_by_provider"][provider][side] = str(side_id)

    domains = (
        ("status", "results"),
        ("home_score", "results"),
        ("away_score", "results"),
        ("kickoff_utc", "fixtures"),
    )
    for field, domain in domains:
        observations = []
        observed_values = []
        for row, provider in zip(rows, providers):
            value = row.get(field)
            fetched = _timestamp(timestamps.get(provider))
            if value is None or fetched is None:
                continue
            source_id = (row.get("source_ids") or {}).get(provider)
            source_updated_at = _timestamp(row.get("raw_source_updated_at"))
            observations.append(Observation(
                provider=provider,
                value=value,
                fetched_at=fetched,
                source_id=source_id,
                updated_at=source_updated_at,
                valid=True,
            ))
            observed_values.append({
                "provider": provider,
                "value": value,
                "source_id": str(source_id) if source_id is not None else None,
                "fetched_at": fetched.isoformat(),
                "source_updated_at": source_updated_at.isoformat() if source_updated_at else None,
            })
        resolved = resolve_field(
            domain,
            observations,
            now=now,
            max_age_seconds=max_age_seconds,
            livescore_verified=livescore_verified,
        )
        result[field] = resolved.value
        result["reconciliation"][field] = {
            "provider": resolved.provider,
            "source_id": resolved.source_id,
            "status": resolved.status,
            "corroborating_providers": list(resolved.corroborating_providers),
            "conflicting_providers": list(resolved.conflicting_providers),
            "fetched_at": resolved.fetched_at.isoformat() if resolved.fetched_at else None,
            "observations": observed_values,
            "message": resolved.message,
        }

    result["source"] = result["reconciliation"]["status"]["provider"]
    result["providers_seen"] = providers
    return result
