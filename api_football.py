"""API-FOOTBALL v3 client (API-SPORTS).

Credential: APISPORTS_API_KEY (Streamlit Secrets or environment).
The legacy API_FOOTBALL_KEY name is intentionally not read here because it
was previously used for Highlightly/API Ninjas in this repository.
"""
from __future__ import annotations

import os
from typing import Any
import requests


class APIFootballError(RuntimeError):
    """Safe provider error; API keys and request headers are never included."""


class APIFootballClient:
    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None, timeout: int = 20):
        self.api_key = api_key or os.getenv("APISPORTS_API_KEY")
        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.secrets.get("APISPORTS_API_KEY")
            except Exception:
                self.api_key = None
        if isinstance(self.api_key, str):
            self.api_key = self.api_key.strip()
        if not self.api_key:
            raise APIFootballError("API-Football v3 key missing. Configure APISPORTS_API_KEY in Streamlit Secrets.")
        self.timeout = timeout
        self.session = requests.Session()
        self.last_paging: dict[str, Any] = {}
        self.last_fixture_request_count = 0
        self.session.headers.update({"x-apisports-key": self.api_key, "Accept": "application/json"})

    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            response = self.session.get(f"{self.BASE_URL}/{endpoint.lstrip('/')}", params=params or {}, timeout=self.timeout)
            if response.status_code in (401, 403):
                raise APIFootballError(f"API-Football authentication/authorization failed (HTTP {response.status_code}); verify APISPORTS_API_KEY and plan access.")
            if response.status_code == 429:
                raise APIFootballError("API-Football rate limit reached (HTTP 429).")
            response.raise_for_status()
            payload = response.json()
        except APIFootballError:
            raise
        except requests.Timeout as exc:
            raise APIFootballError("API-Football request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise APIFootballError(f"API-Football network request failed{suffix}.") from exc
        except ValueError as exc:
            raise APIFootballError("API-Football returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise APIFootballError("API-Football returned an unexpected response.")
        if payload.get("errors"):
            errors = payload.get("errors")
            sensitive_keys = {"key", "api_key", "apikey", "authorization", "token", "secret"}
            if isinstance(errors, dict):
                safe_errors = {
                    str(key): str(value).replace(self.api_key, "[redacted]")[:240]
                    for key, value in errors.items()
                    if str(key).lower() not in sensitive_keys
                }
            elif isinstance(errors, list):
                safe_errors = [
                    str(value).replace(self.api_key, "[redacted]")[:240]
                    for value in errors[:8]
                ]
            else:
                safe_errors = str(errors).replace(self.api_key, "[redacted]")[:500]
            raise APIFootballError(
                f"API-Football rejected endpoint '{endpoint}': {safe_errors}"
            )
        self.last_paging = payload.get("paging") or {}
        rows = payload.get("response", [])
        if not isinstance(rows, list):
            raise APIFootballError("API-Football response had an unexpected schema.")
        return rows

    def status(self) -> dict[str, Any]:
        """Read account status/remaining quota; documented as quota-exempt."""
        try:
            response = self.session.get(f"{self.BASE_URL}/status", timeout=self.timeout)
            if response.status_code in (401, 403):
                raise APIFootballError(f"API-Football status authorization failed (HTTP {response.status_code}).")
            response.raise_for_status()
            payload = response.json()
        except APIFootballError:
            raise
        except requests.RequestException as exc:
            raise APIFootballError("API-Football status request failed.") from exc
        except ValueError as exc:
            raise APIFootballError("API-Football status returned invalid JSON.") from exc
        if not isinstance(payload, dict) or payload.get("errors"):
            raise APIFootballError("API-Football status endpoint rejected the request.")
        data = payload.get("response")
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return {}

    def leagues(self, season: int | None = None) -> list[dict[str, Any]]:
        return self._request("leagues", {"season": season} if season is not None else {})

    def fixtures_by_date(
        self,
        fixture_date: str,
        timezone: str = "UTC",
    ) -> list[dict[str, Any]]:
        """Return all fixtures for one date; API-Football v3 does not accept a page parameter."""
        from datetime import date

        try:
            normalized_date = date.fromisoformat(str(fixture_date)).isoformat()
        except ValueError as exc:
            raise ValueError("fixture_date must be YYYY-MM-DD.") from exc

        self.last_fixture_request_count = 1
        return self._request(
            "fixtures",
            {"date": normalized_date, "timezone": timezone},
        )

    def teams(self, league_id: int, season: int) -> list[dict[str, Any]]:
        return self._request("teams", {"league": league_id, "season": season})

    def standings(self, league_id: int, season: int) -> list[dict[str, Any]]:
        return self._request("standings", {"league": league_id, "season": season})

    def last_fixtures(self, team_id: int, season: int, last: int = 10, league_id: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"team": team_id, "season": season, "last": min(max(int(last), 1), 20)}
        if league_id is not None:
            params["league"] = league_id
        return self._request("fixtures", params)

    def next_fixture(self, team_id: int, season: int, league_id: int | None = None) -> dict[str, Any] | None:
        params: dict[str, Any] = {"team": team_id, "season": season, "next": 1}
        if league_id is not None:
            params["league"] = league_id
        rows = self._request("fixtures", params)
        return rows[0] if rows else None

    def fixture_statistics(self, fixture_id: int) -> list[dict[str, Any]]:
        return self._request("fixtures/statistics", {"fixture": fixture_id})

    def injuries(self, team_id: int, season: int) -> list[dict[str, Any]]:
        return self._request("injuries", {"team": team_id, "season": season})

    def fixture_lineups(self, fixture_id: int) -> list[dict[str, Any]]:
        return self._request("fixtures/lineups", {"fixture": fixture_id})

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "APIFootballClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
