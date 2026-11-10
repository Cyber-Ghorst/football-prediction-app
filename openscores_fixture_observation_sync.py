"""Disabled legacy OpenScores scheduled-fixture sync.

OpenScores is not an upcoming-fixture provider. Existing provider observations
remain available for read-only entity-mapping and result-reconciliation audits,
but this legacy operation must never fetch or stage new future fixtures.
"""
from __future__ import annotations

from typing import Any


def run_sync(
    *, client_factory: Any = None, database_url: str | None = None,
    max_leagues: int | None = None, now: Any = None,
) -> dict[str, Any]:
    """Fail closed before network or database access."""
    raise RuntimeError(
        "OpenScores is not a future-fixture provider. Its scheduled-fixture "
        "observation sync is disabled; use the read-only entity-mapping audit."
    )


def main() -> int:
    run_sync()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
