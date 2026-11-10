"""Evidence-based provider reliability diagnostics for Layer 3.

Reliability is measured only on exact-identity, freshness-eligible comparisons
against the configured primary provider. Small samples are explicitly
insufficient; this module never changes provider priority or prediction inputs.
"""
from __future__ import annotations

from math import sqrt
from typing import Any, Mapping


_RESULT_FIELDS = ("home_score", "away_score")
_DIAGNOSTIC_FIELDS = ("status", "kickoff_utc")


def _strict_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt(
        (proportion * (1 - proportion) / total)
        + (z * z / (4 * total * total))
    ) / denominator
    return (
        round(max(0.0, center - margin) * 100, 1),
        round(min(1.0, center + margin) * 100, 1),
    )


def _observations(match: Mapping[str, Any], field: str) -> dict[str, Any]:
    detail = (match.get("reconciliation") or {}).get(field) or {}
    rows = detail.get("observations") or []
    result: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        provider = str(row.get("provider") or "").strip()
        if not provider or provider in result:
            # A duplicate observation from one provider is ambiguous and is
            # deliberately excluded instead of being counted as extra votes.
            if provider:
                result.pop(provider, None)
            continue
        result[provider] = row.get("value")
    return result


def _kickoff_agrees(left: Any, right: Any, tolerance_seconds: int = 300) -> bool | None:
    from datetime import datetime, timezone

    def parse(value: Any):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    first, second = parse(left), parse(right)
    if first is None or second is None:
        return None
    return abs((first - second).total_seconds()) <= tolerance_seconds


def _new_counter() -> dict[str, int]:
    return {"compared": 0, "agreed": 0, "disagreed": 0}


def build_source_reliability_report(
    corroboration: Mapping[str, Any] | None,
    *,
    primary_provider: str = "sportmonks",
    minimum_score_samples: int = 30,
) -> dict[str, Any]:
    """Summarize provider agreement without allowing small samples to rank sources.

    Score reliability uses one paired home/away full-time score per exact
    fixture, not two independent observations. Status and kickoff agreement
    are reported separately and never blended into the score metric.
    """
    if isinstance(minimum_score_samples, bool) or not isinstance(minimum_score_samples, int) or minimum_score_samples < 1:
        raise ValueError("minimum_score_samples must be a positive integer.")

    matches = (corroboration or {}).get("matches") or []
    providers: set[str] = set()
    per_provider: dict[str, dict[str, Any]] = {}

    for match in matches:
        if not isinstance(match, Mapping):
            continue
        score_rows = {
            field: _observations(match, field)
            for field in _RESULT_FIELDS
        }
        status_rows = _observations(match, "status")
        kickoff_rows = _observations(match, "kickoff_utc")
        observed = set().union(
            *(set(rows) for rows in score_rows.values()),
            set(status_rows), set(kickoff_rows),
        )
        providers.update(observed - {primary_provider})

    for provider in sorted(providers):
        per_provider[provider] = {
            "score_pairs": _new_counter(),
            "status": _new_counter(),
            "kickoff_within_5_minutes": _new_counter(),
            "matched_fixture_observations": 0,
        }

    for match in matches:
        if not isinstance(match, Mapping):
            continue
        home_rows = _observations(match, "home_score")
        away_rows = _observations(match, "away_score")
        status_rows = _observations(match, "status")
        kickoff_rows = _observations(match, "kickoff_utc")
        for provider, report in per_provider.items():
            if provider in (
                set(home_rows) | set(away_rows) | set(status_rows) | set(kickoff_rows)
            ):
                report["matched_fixture_observations"] += 1

            primary_home = _strict_score(home_rows.get(primary_provider))
            primary_away = _strict_score(away_rows.get(primary_provider))
            candidate_home = _strict_score(home_rows.get(provider))
            candidate_away = _strict_score(away_rows.get(provider))
            if None not in (primary_home, primary_away, candidate_home, candidate_away):
                counter = report["score_pairs"]
                counter["compared"] += 1
                if (primary_home, primary_away) == (candidate_home, candidate_away):
                    counter["agreed"] += 1
                else:
                    counter["disagreed"] += 1

            primary_status = status_rows.get(primary_provider)
            candidate_status = status_rows.get(provider)
            if primary_status is not None and candidate_status is not None:
                counter = report["status"]
                counter["compared"] += 1
                if str(primary_status).strip().casefold() == str(candidate_status).strip().casefold():
                    counter["agreed"] += 1
                else:
                    counter["disagreed"] += 1

            primary_kickoff = kickoff_rows.get(primary_provider)
            candidate_kickoff = kickoff_rows.get(provider)
            agreement = _kickoff_agrees(primary_kickoff, candidate_kickoff)
            if agreement is not None:
                counter = report["kickoff_within_5_minutes"]
                counter["compared"] += 1
                counter["agreed" if agreement else "disagreed"] += 1

    output = {}
    for provider, report in per_provider.items():
        score = report["score_pairs"]
        compared = score["compared"]
        sufficient = compared >= minimum_score_samples
        interval = _wilson_interval(score["agreed"], compared)
        output[provider] = {
            **report,
            "score_pair_agreement_pct": (
                round(score["agreed"] / compared * 100, 1) if compared else None
            ),
            "score_pair_agreement_95pct_wilson_interval": (
                {"lower": interval[0], "upper": interval[1]} if interval else None
            ),
            "score_reliability_status": (
                "sample_sufficient_descriptive_only" if sufficient
                else "insufficient_sample"
            ),
            "minimum_score_samples": minimum_score_samples,
            "eligible_for_provider_priority_changes": False,
        }

    return {
        "primary_provider": primary_provider,
        "minimum_score_samples": minimum_score_samples,
        "providers": output,
        "matches_received": len(matches),
        "method": (
            "Exact-identity, freshness-eligible corroboration records only. "
            "Score agreement is measured as an exact home-away full-time score pair "
            "against the primary provider. Status and kickoff are separate diagnostics. "
            "A 95% Wilson interval is descriptive; insufficient samples are not ranked."
        ),
        "prediction_inputs_modified": False,
        "provider_priority_modified": False,
        "note": (
            "This is a quality-control report, not an automatic source switch. "
            "The configured provider hierarchy remains authoritative."
        ),
    }
