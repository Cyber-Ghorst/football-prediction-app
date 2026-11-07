"""Highlightly football API adapter.

Uses Highlightly's direct Football API host by default. The key is read only
from HIGHLIGHTLY_API_KEY (legacy API_FOOTBALL_KEY fallback retained).
"""
from __future__ import annotations

import os
from typing import Any
import requests


class HighlightlyError(RuntimeError):
    """Provider error that never includes credentials or raw response bodies."""


class HighlightlyClient:
    BASE_URL = "https://soccer.highlightly.net"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 15):
        self.api_key = api_key or os.getenv("HIGHLIGHTLY_API_KEY") or os.getenv("API_FOOTBALL_KEY")
        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.secrets.get("HIGHLIGHTLY_API_KEY") or st.secrets.get("API_FOOTBALL_KEY")
            except Exception:
                self.api_key = None
        if not self.api_key:
            raise HighlightlyError("Highlightly key missing. Configure HIGHLIGHTLY_API_KEY in Streamlit Secrets.")
        self.base_url = (base_url or os.getenv("HIGHLIGHTLY_BASE_URL") or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-rapidapi-key": self.api_key, "Accept": "application/json"})
        self.last_metadata: dict[str, Any] = {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(f"{self.base_url}/{path.lstrip('/')}", params=params or {}, timeout=self.timeout)
            self.last_metadata = {
                "http_status": response.status_code,
                "requests_limit": response.headers.get("x-ratelimit-requests-limit"),
                "requests_remaining": response.headers.get("x-ratelimit-requests-remaining"),
            }
            if response.status_code in (401, 403):
                raise HighlightlyError(f"Highlightly authentication/plan access failed (HTTP {response.status_code}).")
            if response.status_code == 429:
                raise HighlightlyError("Highlightly rate limit or daily quota reached (HTTP 429).")
            response.raise_for_status()
            return response.json()
        except HighlightlyError:
            raise
        except requests.Timeout as exc:
            raise HighlightlyError("Highlightly request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise HighlightlyError(f"Highlightly network request failed{suffix}.") from exc
        except ValueError as exc:
            raise HighlightlyError("Highlightly returned invalid JSON.") from exc

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        return []

    def leagues(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("leagues", params))

    def teams(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("teams", params))

    def matches(self, **params: Any) -> list[dict[str, Any]]:
        payload = self._get("matches", params)
        rows = self._rows(payload)
        if isinstance(payload, list):
            envelope = "top_level_list"
            data_type = None
            top_level_keys: list[str] = []
        elif isinstance(payload, dict):
            data = payload.get("data")
            envelope = "data_list" if isinstance(data, list) else "unrecognized"
            data_type = type(data).__name__ if "data" in payload else None
            top_level_keys = sorted(str(key) for key in payload.keys())
        else:
            envelope = "unrecognized"
            data_type = None
            top_level_keys = []
        self.last_metadata.update({
            "response_payload_type": type(payload).__name__,
            "response_top_level_keys": top_level_keys,
            "response_data_type": data_type,
            "rows_envelope": envelope,
            "extracted_rows_count": len(rows),
        })
        return rows

    def match(self, match_id: int | str) -> dict[str, Any] | None:
        payload = self._get(f"matches/{match_id}")
        return payload if isinstance(payload, dict) else None

    def standings(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("standings", params))

    def statistics(self, match_id: int | str) -> list[dict[str, Any]]:
        return self._rows(self._get(f"statistics/{match_id}"))

    def lineups(self, match_id: int | str) -> dict[str, Any] | None:
        payload = self._get(f"lineups/{match_id}")
        return payload if isinstance(payload, dict) else None

    def players(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("players", params))

    def player_statistics(self, player_id: int | str) -> list[dict[str, Any]]:
        """Return competition- and club-level career statistics for one player."""
        return self._rows(self._get(f"players/{player_id}/statistics"))

    def team_statistics(self, team_id: int | str, **params: Any) -> list[dict[str, Any]]:
        """Return team aggregates from the required fromDate onward."""
        return self._rows(self._get(f"teams/statistics/{team_id}", params))

    def test_connection(self) -> dict[str, Any]:
        """Verify authenticated access using the documented leagues endpoint."""
        rows = self.leagues(limit=1, offset=0)
        return {
            "transport_status": "responding",
            "records_returned": len(rows),
            "metadata": dict(self.last_metadata),
        }

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HighlightlyClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
