"""Deterministic provider-neutral keys for reviewed football identities.

These helpers create identity candidates only. They do not persist canonical
entities, approve provider mappings, or infer equivalence between providers.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


IDENTITY_KEY_VERSION = 1
_UNKNOWN_DIMENSIONS = {
    "unknown", "not known", "unspecified", "unverified", "n a", "na",
    "none", "null", "tbd", "to be determined", "not applicable",
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _require_verified_dimension(value: str, label: str) -> str:
    """Reject placeholders that would turn missing evidence into identity."""
    if not value or value in _UNKNOWN_DIMENSIONS:
        raise ValueError(f"{label} must be verified; unknown placeholders are not accepted.")
    return value


def _digest(kind: str, parts: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"version": IDENTITY_KEY_VERSION, "kind": kind, "parts": parts},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{kind}_v{IDENTITY_KEY_VERSION}_{hashlib.sha256(payload).hexdigest()[:24]}"


def canonical_competition_key(
    name: Any,
    country: Any,
    competition_type: Any,
) -> str:
    """Return a deterministic candidate key; all identity dimensions are required.

    The key is application-generated and contains no provider IDs. Exact
    normalized name/country/type equality is intentionally conservative:
    synonyms and ambiguous names must be reviewed rather than guessed.
    """
    normalized_name = _require_verified_dimension(_normalize(name), "Competition name")
    normalized_country = _require_verified_dimension(_normalize(country), "Country")
    normalized_type = _require_verified_dimension(_normalize(competition_type), "Competition type")
    return _digest(
        "competition",
        (normalized_country, normalized_type, normalized_name),
    )


def canonical_season_key(
    canonical_competition_id: Any,
    season_label: Any,
) -> str:
    """Return a season candidate key scoped to an existing canonical competition.

    Provider season IDs are deliberately not accepted. Season labels are
    normalized as text; date-range equivalence requires separate validation.
    """
    competition_id = str(canonical_competition_id or "").strip()
    normalized_label = _require_verified_dimension(_normalize(season_label), "Season label")
    if not competition_id or _normalize(competition_id) in _UNKNOWN_DIMENSIONS:
        raise ValueError("An existing verified canonical competition ID is required.")
    return _digest("season", (competition_id, normalized_label))


def canonical_team_key(
    name: Any,
    country: Any,
    team_type: Any,
    gender: Any,
    age_group: Any,
    squad_scope: Any,
) -> str:
    """Return a deterministic team identity candidate with explicit scope.

    Required scope dimensions deliberately distinguish clubs from national
    teams, men's/women's/mixed teams, senior/youth age groups, and first-team,
    reserve or academy squads. Values are normalized text rather than guessed
    from a provider ID or name. Aliases and uncertain scope require review.
    """
    normalized = (
        _normalize(name),
        _normalize(country),
        _normalize(team_type),
        _normalize(gender),
        _normalize(age_group),
        _normalize(squad_scope),
    )
    labels = (
        "A team name",
        "A country or territory",
        "A verified team type (club or national)",
        "A verified gender scope",
        "A verified age-group scope",
        "A verified squad scope",
    )
    for value, label in zip(normalized, labels):
        _require_verified_dimension(value, label)
    if normalized[2] not in {"club", "national"}:
        raise ValueError("Team type must be 'club' or 'national'.")
    return _digest("team", normalized)
