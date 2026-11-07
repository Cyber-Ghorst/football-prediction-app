"""Provider health and source-data freshness checks.

Transport health and data freshness are separate: a responding API can still
serve stale competition snapshots. Missing timestamps remain unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


# Conservative, domain-specific freshness windows; callers may override them.
FRESHNESS_LIMITS_SECONDS = {
    "live_scores": 120,
    "fixtures": 24 * 60 * 60,
    "results": 24 * 60 * 60,
    "standings": 24 * 60 * 60,
    "statistics": 24 * 60 * 60,
    "injuries": 6 * 60 * 60,
    "lineups": 6 * 60 * 60,
    "players": 7 * 24 * 60 * 60,
    "squads": 7 * 24 * 60 * 60,
}


def parse_timestamp(value: Any) -> datetime | None:
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


def assess_freshness(
    source_updated_at: Any,
    domain: str,
    *,
    now: datetime | None = None,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    if domain not in FRESHNESS_LIMITS_SECONDS and max_age_seconds is None:
        raise ValueError(f"No freshness policy configured for domain: {domain}")
    limit = max_age_seconds if max_age_seconds is not None else FRESHNESS_LIMITS_SECONDS[domain]
    timestamp = parse_timestamp(source_updated_at)
    if timestamp is None:
        return {
            "status": "unknown", "fresh": False, "source_updated_at": None,
            "age_seconds": None, "max_age_seconds": limit,
            "reason": "Source data timestamp is missing or invalid; freshness cannot be verified.",
        }
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = (current.astimezone(timezone.utc) - timestamp).total_seconds()
    if age < 0:
        return {
            "status": "invalid", "fresh": False,
            "source_updated_at": timestamp.isoformat(), "age_seconds": age,
            "max_age_seconds": limit,
            "reason": "Source timestamp is in the future.",
        }
    fresh = age <= limit
    return {
        "status": "fresh" if fresh else "stale", "fresh": fresh,
        "source_updated_at": timestamp.isoformat(), "age_seconds": round(age, 1),
        "max_age_seconds": limit,
        "reason": "Within domain freshness limit." if fresh else "Older than domain freshness limit.",
    }


def assess_livescore_competition_coverage(
    competition: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
) -> dict[str, Any]:
    """Require a fresh per-competition coverage.lastSyncedAt timestamp."""
    coverage = competition.get("coverage") if isinstance(competition.get("coverage"), Mapping) else {}
    freshness = assess_freshness(
        coverage.get("lastSyncedAt"), "fixtures", now=now,
        max_age_seconds=max_age_seconds,
    )
    return {
        "competition": competition.get("name") or competition.get("slug"),
        "slug": competition.get("slug"),
        "freshness": freshness,
        "fallback_eligible": competition.get("active") is True
            and coverage.get("hasData") is True and freshness["fresh"],
    }


def assess_livescore_fixture_freshness(
    fixture: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
) -> dict[str, Any]:
    """Require a provider-reported fixture update timestamp before use."""
    timestamp = next((
        fixture.get(key) for key in (
            "updatedAt", "lastUpdatedAt", "sourceUpdatedAt", "updated_at",
            "last_updated_at",
        ) if fixture.get(key) is not None
    ), None)
    freshness = assess_freshness(
        timestamp, "fixtures", now=now, max_age_seconds=max_age_seconds,
    )
    return {
        "fixture_id": fixture.get("id") or fixture.get("eventId"),
        "freshness": freshness,
        "eligible": freshness["fresh"],
        "reason": freshness["reason"],
    }


def assess_livescore_metadata(
    metadata: Mapping[str, Any],
    *,
    now: datetime | None = None,
    domain: str = "fixtures",
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    """Assess the documented global lastSuccessfulSyncAt without inventing it."""
    timestamp = metadata.get("lastSuccessfulSyncAt")
    freshness = assess_freshness(
        timestamp, domain, now=now, max_age_seconds=max_age_seconds
    )
    service = metadata.get("service") if isinstance(metadata.get("service"), Mapping) else {}
    coverage = metadata.get("coverage") if isinstance(metadata.get("coverage"), Mapping) else {}
    healthy = bool(service) and service.get("dataSource") == "MongoDB"
    return {
        "provider": "livescore_football",
        "transport_status": "responding" if metadata else "unknown",
        "service_contract_valid": healthy,
        "freshness": freshness,
        "coverage": dict(coverage),
        "fallback_eligible": healthy and freshness["fresh"],
        "reason": (
            "Metadata contract valid and source sync is fresh."
            if healthy and freshness["fresh"]
            else "Do not use as fallback until service contract and source freshness are verified."
        ),
    }


def assess_api_football_status(status: Mapping[str, Any]) -> dict[str, Any]:
    """Read API-Football account/server status without exposing account identity."""
    subscription = status.get("subscription") if isinstance(status.get("subscription"), Mapping) else {}
    requests = status.get("requests") if isinstance(status.get("requests"), Mapping) else {}
    active = subscription.get("active") is True
    limit = requests.get("limit_day")
    current = requests.get("current")
    remaining = None
    try:
        if limit is not None and current is not None:
            remaining = max(0, int(limit) - int(current))
    except (TypeError, ValueError):
        remaining = None
    valid = bool(subscription) and active
    return {
        "provider": "api_football",
        "transport_status": "responding" if status else "unknown",
        "account_active": active,
        "plan": subscription.get("plan"),
        "daily_request_limit": limit,
        "daily_requests_used": current,
        "daily_requests_remaining": remaining,
        "fallback_eligible": valid,
        "reason": "Account subscription is active." if valid else "Account status is missing or subscription is inactive.",
    }
