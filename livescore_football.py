"""Read-only adapter for the rezarahiminia/livescoreFootball public API.

Public service: https://worldcup26.ir
No API key is documented or required for the public read endpoints.
The service reads stored MongoDB snapshots; it is not an upstream live-data
vendor and freshness depends on its separately operated listener.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests


class LiveScoreFootballError(RuntimeError):
    """Safe service error; never includes request headers or credentials."""


class LiveScoreFootballClient:
    DEFAULT_BASE_URL = "https://worldcup26.ir"

    def __init__(self, base_url: str | None = None, timeout: int = 15,
                 session: requests.Session | None = None):
        self.base_url = (base_url or os.getenv(
            "LIVESCORE_FOOTBALL_BASE_URL", self.DEFAULT_BASE_URL
        )).rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "football-prediction-app/1.0",
        })
        self.last_metadata: dict[str, Any] = {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params or {},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise LiveScoreFootballError("LiveScoreFootball request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise LiveScoreFootballError(
                f"LiveScoreFootball request failed{suffix}."
            ) from exc
        except ValueError as exc:
            raise LiveScoreFootballError(
                "LiveScoreFootball returned invalid JSON."
            ) from exc
        if not isinstance(payload, (dict, list)):
            raise LiveScoreFootballError(
                "LiveScoreFootball returned an unexpected response schema."
            )
        return payload

    def health(self) -> dict[str, Any]:
        payload = self._get("health")
        if not isinstance(payload, dict):
            raise LiveScoreFootballError("Health endpoint returned an unexpected schema.")
        return payload

    def meta(self) -> dict[str, Any]:
        payload = self._get("get/soccer/meta")
        if not isinstance(payload, dict):
            raise LiveScoreFootballError("Metadata endpoint returned an unexpected schema.")
        self.last_metadata = payload
        return payload

    def leagues(self, kind: str = "club", available: bool = True) -> list[dict[str, Any]]:
        if kind not in {"club", "international", "all"}:
            raise ValueError("kind must be club, international, or all")
        payload = self._get("get/soccer/leagues", {
            "kind": kind, "available": str(bool(available)).lower()
        })
        rows = payload.get("leagues") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise LiveScoreFootballError("League catalog response has no leagues array.")
        return [row for row in rows if isinstance(row, dict)]

    def fixtures(self, league: str, *, status: str = "all",
                 date_from: str | None = None, date_to: str | None = None,
                 max_pages: int = 20, page_size: int = 200) -> list[dict[str, Any]]:
        if status not in {"all", "scheduled", "live", "finished"}:
            raise ValueError("status must be all, scheduled, live, or finished")
        page_size = min(max(int(page_size), 1), 200)
        all_rows: list[dict[str, Any]] = []
        for page in range(1, max(1, int(max_pages)) + 1):
            params: dict[str, Any] = {
                "status": status, "page": page, "limit": page_size
            }
            if date_from:
                params["from"] = date_from
            if date_to:
                params["to"] = date_to
            payload = self._get(
                f"get/soccer/{quote(str(league), safe='')}/fixtures", params
            )
            rows = payload.get("events") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise LiveScoreFootballError("Fixtures response has no events array.")
            all_rows.extend(row for row in rows if isinstance(row, dict))
            page_count = payload.get("pageCount", page)
            if page >= int(page_count or page) or not rows:
                break
        return all_rows

    def team_fixtures(self, league: str, team_id: str | int, **kwargs: Any) -> list[dict[str, Any]]:
        target = str(team_id)
        matches = self.fixtures(league, **kwargs)
        selected = []
        for match in matches:
            competitors = (
                (match.get("competitions") or [{}])[0].get("competitors") or []
            )
            if any(str(item.get("id")) == target for item in competitors):
                selected.append(match)
        return selected

    def scoreboard(self, league: str, dates: str) -> list[dict[str, Any]]:
        payload = self._get(
            f"get/soccer/{quote(str(league), safe='')}/scoreboard",
            {"dates": dates},
        )
        rows = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise LiveScoreFootballError("Scoreboard response has no events array.")
        return [row for row in rows if isinstance(row, dict)]

    def standings(self, league: str, season: int | None = None) -> dict[str, Any]:
        params = {"season": int(season)} if season is not None else {}
        payload = self._get(
            f"get/soccer/{quote(str(league), safe='')}/standings", params
        )
        if not isinstance(payload, dict):
            raise LiveScoreFootballError("Standings response has an unexpected schema.")
        return payload

    def summary(self, league: str, event_id: str | int) -> dict[str, Any]:
        payload = self._get(
            f"get/soccer/{quote(str(league), safe='')}/summary",
            {"event": str(event_id)},
        )
        if not isinstance(payload, dict):
            raise LiveScoreFootballError("Match summary has an unexpected schema.")
        return payload

    def plays(self, league: str, event_id: str | int, *,
              important: bool = True, max_pages: int = 10,
              page_size: int = 300) -> list[dict[str, Any]]:
        page_size = min(max(int(page_size), 1), 300)
        rows: list[dict[str, Any]] = []
        for page in range(1, max(1, int(max_pages)) + 1):
            payload = self._get(
                f"get/soccer/{quote(str(league), safe='')}/events/"
                f"{quote(str(event_id), safe='')}/plays",
                {"page": page, "limit": page_size,
                 "important": str(bool(important)).lower()},
            )
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                raise LiveScoreFootballError("Play-by-play response has no items array.")
            rows.extend(item for item in items if isinstance(item, dict))
            page_count = payload.get("pageCount", page)
            if page >= int(page_count or page) or not items:
                break
        return rows

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "LiveScoreFootballClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
