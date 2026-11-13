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


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    normalized_name = _normalize(name)
    normalized_country = _normalize(country)
    normalized_type = _normalize(competition_type)
    if not normalized_name:
        raise ValueError("A competition name is required.")
    if not normalized_country:
        raise ValueError("A country is required for a canonical competition key.")
    if not normalized_type:
        raise ValueError("A verified competition type is required.")
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
    normalized_label = _normalize(season_label)
    if not competition_id:
        raise ValueError("An existing canonical competition ID is required.")
    if not normalized_label:
        raise ValueError("A season label is required.")
    return _digest("season", (competition_id, normalized_label))
