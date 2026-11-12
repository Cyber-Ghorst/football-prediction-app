"""Append-only archive for normalized provider observations.

Future-discovery providers use the future_fixture_observations resource; football-data.org uses a separate independent_data_observations resource. This store never writes canonical fixtures or prediction
ledger rows and never changes the active provider routing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from provider_data_storage import (
    build_provider_cache_key,
    save_provider_snapshot_and_record_run,
)

ALLOWED_PROVIDERS = {
    "openligadb", "openfootball", "open_matchday",
    "livescore_football", "bzzoiro", "highlightly", "api_ninjas",
    "football_data_org",
}
RESOURCE_TYPE = "future_fixture_observations"
SENSITIVE_PARAM_NAMES = {
    "authorization", "api_key", "apikey", "token", "secret", "password",
}


def _validate_request_params(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("request_params must be an object.")

    def reject_secrets(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if str(key).strip().casefold() in SENSITIVE_PARAM_NAMES:
                    raise ValueError("Credentials must never be included in snapshot request parameters.")
                reject_secrets(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                reject_secrets(nested)

    params = dict(value)
    reject_secrets(params)
    return params


def archive_future_fixture_observations(
    database_url: str,
    *,
    provider: str,
    request_params: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    """Persist one immutable provider observation batch without canonical writes."""
    provider_name = str(provider or "").strip().casefold()
    if provider_name not in ALLOWED_PROVIDERS:
        raise ValueError("provider is not an approved observation source.")
    if not database_url:
        raise ValueError("PROVIDER_DATABASE_URL is required.")
    if not isinstance(observations, list):
        raise ValueError("observations must be a list.")

    params = _validate_request_params(request_params)
    safe_rows = []
    source_ids = []
    eligible_count = 0
    for row in observations:
        if not isinstance(row, Mapping):
            raise ValueError("Every observation must be an object.")
        if str(row.get("provider") or "").strip().casefold() != provider_name:
            raise ValueError("Observation provider does not match the archive batch.")
        fixture_id = str(row.get("provider_fixture_id") or "").strip()
        if not fixture_id:
            raise ValueError("Every observation requires a provider-scoped fixture ID.")
        safe = dict(row)
        safe_rows.append(safe)
        source_ids.append(fixture_id)
        eligible_count += row.get("eligible_for_review") is True

    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    captured = captured.astimezone(timezone.utc)
    payload = {
        "schema_version": 1,
        "provider": provider_name,
        "retrieved_at": captured.isoformat().replace("+00:00", "Z"),
        "observation_count": len(safe_rows),
        "eligible_for_review_count": eligible_count,
        "observations": safe_rows,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }
    resource_type = (
        "independent_data_observations"
        if provider_name == "football_data_org"
        else RESOURCE_TYPE
    )
    cache_key = build_provider_cache_key(provider_name, resource_type, params)
    result = save_provider_snapshot_and_record_run(
        database_url,
        provider=provider_name,
        resource_type=resource_type,
        cache_key=cache_key,
        request_params=params,
        payload=payload,
        source_ids=source_ids,
        ttl_seconds=0,
        retrieved_at=captured,
        http_status=200,
    )
    return {
        **result,
        "provider": provider_name,
        "resource_type": resource_type,
        "cache_key": cache_key,
        "observation_count": len(safe_rows),
        "eligible_for_review_count": eligible_count,
        "canonical_fixture_writes": 0,
        "prediction_ledger_writes": 0,
    }
