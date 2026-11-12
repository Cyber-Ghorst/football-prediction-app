"""Independent football-data.org observation collection; no canonical writes."""
from __future__ import annotations

from typing import Any

from football_data_org_adapter import FootballDataOrgAdapter
from free_fixture_observation_pipeline import _archive, _close_owned


def collect_football_data_org_observations(
    database_url: str,
    *,
    date_from: str,
    date_to: str,
    competitions: list[str] | None = None,
    client: FootballDataOrgAdapter | None = None,
    max_pages: int = 5,
    page_size: int = 100,
) -> dict[str, Any]:
    """Fetch and archive football-data.org observations independently."""
    owned = client is None
    api = client or FootballDataOrgAdapter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful = 0
    try:
        rows = api.matches(
            date_from, date_to, competitions=competitions,
            max_pages=max_pages, page_size=page_size,
        )
        successful = 1
    except Exception as exc:
        errors.append({"scope": "scheduled_matches", "error": str(exc)[:300]})
    finally:
        _close_owned(api, owned)
    return _archive(
        database_url,
        "football_data_org",
        {
            "date_from": date_from,
            "date_to": date_to,
            "competitions": list(competitions or []),
            "max_pages": max_pages,
            "page_size": page_size,
            "status": "SCHEDULED,TIMED",
        },
        rows,
        errors,
        successful,
    )
