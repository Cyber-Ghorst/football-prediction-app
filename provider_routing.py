"""Competition- and data-category-aware provider routing.

This is a policy layer, not a data importer. It identifies eligible sources while
keeping source activation explicit; an adapter is not operational merely because
its client class or credentials exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProviderAssignment:
    provider: str
    category: str
    role: str
    priority: int = 100
    competitions: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.category.strip():
            raise ValueError("provider and category are required")
        if self.role not in {"primary", "co_primary", "fallback", "validation"}:
            raise ValueError("unsupported provider role")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int) or self.priority < 0:
            raise ValueError("priority must be a non-negative integer")
        if any(not item.strip() for item in self.competitions):
            raise ValueError("competition keys cannot be blank")


class ProviderRegistry:
    """Resolve source roles without imposing one global provider hierarchy."""

    def __init__(self, assignments: Iterable[ProviderAssignment]):
        self._assignments = tuple(assignments)
        seen: set[tuple[str, str, tuple[str, ...]]] = set()
        for item in self._assignments:
            key = (item.provider.casefold(), item.category.casefold(),
                   tuple(sorted(x.casefold() for x in item.competitions)))
            if key in seen:
                raise ValueError(f"duplicate provider assignment: {item.provider}/{item.category}")
            seen.add(key)

    @staticmethod
    def _matches(item: ProviderAssignment, category: str, competition: str | None) -> bool:
        if item.category.casefold() != category.casefold() or not item.enabled:
            return False
        if not item.competitions:
            return True
        return bool(competition) and competition.casefold() in {
            value.casefold() for value in item.competitions
        }

    def resolve(self, category: str, competition: str | None = None) -> dict[str, list[str]]:
        """Return eligible sources by role, ordered by ascending priority."""
        matched = [item for item in self._assignments
                   if self._matches(item, category, competition)]
        result = {role: [] for role in ("primary", "co_primary", "fallback", "validation")}
        for role in result:
            rows = sorted((item for item in matched if item.role == role),
                          key=lambda item: (item.priority, item.provider.casefold()))
            result[role] = list(dict.fromkeys(item.provider for item in rows))
        return result

    def primary_sources(self, category: str, competition: str | None = None) -> list[str]:
        """Return every primary and co-primary; never collapse to one source."""
        resolved = self.resolve(category, competition)
        return resolved["primary"] + resolved["co_primary"]


# OpenScores is retained only as a disabled result-validation observation
# source. Its staged fixture observations are not future-fixture candidates.
OPENSCORES_COMPETITIONS = (
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "2026 fifa world cup",
)

# Future-fixture discovery is deliberately distinct from match-data enrichment.
# Only Sportmonks is currently implemented in the rolling-window collector.
# The five free sources remain disabled candidates until live coverage,
# timestamp, identity, licence and database round-trip gates pass.
FREE_FIXTURE_CANDIDATES = (
    "openligadb",
    "openfootball",
    "open_matchday",
    "thesportsdb",
    "bzzoiro",
)

DEFAULT_PROVIDER_ASSIGNMENTS = (
    ProviderAssignment("sportmonks", "fixtures", "primary", 10),
    ProviderAssignment("sportmonks", "future_fixtures", "primary", 10),
    ProviderAssignment("sportmonks", "results", "primary", 10),
    ProviderAssignment("sportmonks", "match_statistics", "primary", 10),
    ProviderAssignment("sportmonks", "lineups", "primary", 10),
    ProviderAssignment("sportmonks", "player_data", "primary", 10),
    ProviderAssignment("api_football", "historical_fixtures", "primary", 10),
    ProviderAssignment("api_football", "historical_statistics", "primary", 10),
    # OpenScores is retained for read-only result observation/review only.
    # It is deliberately not assigned to either fixtures or future_fixtures.
    ProviderAssignment("openscores", "results", "validation", 20,
                       competitions=OPENSCORES_COMPETITIONS, enabled=False),
    ProviderAssignment("openligadb", "future_fixtures", "co_primary", 30, enabled=False),
    ProviderAssignment("openfootball", "future_fixtures", "co_primary", 31, enabled=False),
    ProviderAssignment("open_matchday", "future_fixtures", "co_primary", 32, enabled=False),
    # TheSportsDB free tier returns one next event per league; keep disabled
    # pending terms, coverage and timestamp validation.
    ProviderAssignment("thesportsdb", "future_fixtures", "co_primary", 33, enabled=False),
    ProviderAssignment("bzzoiro", "future_fixtures", "co_primary", 34, enabled=False),
)


def default_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(DEFAULT_PROVIDER_ASSIGNMENTS)
