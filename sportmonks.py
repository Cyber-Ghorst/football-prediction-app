"""Sportmonks Football API v3 adapter.

Credential: SPORTMONKS_API_TOKEN (Streamlit Secrets or environment).
Uses the documented v3 REST API and Authorization header. This adapter is
initially diagnostic/read-only; it does not silently replace Layer 2 data.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

import requests


class SportmonksError(RuntimeError):
    """Safe provider error; never includes token values or response bodies."""


class SportmonksClient:
    BASE_URL = "https://api.sportmonks.com/v3/football"

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: int = 20,
    ):
        self.api_token = (
            api_token
            or os.getenv("SPORTMONKS_API_TOKEN")
            or os.getenv("SPORTMONKS_API_KEY")
        )
        if not self.api_token:
            try:
                import streamlit as st
                self.api_token = (
                    st.secrets.get("SPORTMONKS_API_TOKEN")
                    or st.secrets.get("SPORTMONKS_API_KEY")
                )
            except Exception:
                self.api_token = None
        if not self.api_token:
            raise SportmonksError(
                "Sportmonks token missing. Configure SPORTMONKS_API_TOKEN in Streamlit Secrets."
            )

        self.base_url = (base_url or os.getenv("SPORTMONKS_BASE_URL") or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.api_token,
            "Accept": "application/json",
        })
        self.last_metadata: dict[str, Any] = {}

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=dict(params or {}),
                timeout=self.timeout,
            )
            self.last_metadata = {
                "http_status": response.status_code,
                "rate_limit": response.headers.get("X-RateLimit-Limit"),
                "rate_remaining": response.headers.get("X-RateLimit-Remaining"),
            }
            if response.status_code in (401, 403):
                raise SportmonksError(
                    f"Sportmonks authentication or subscription access failed (HTTP {response.status_code})."
                )
            if response.status_code == 429:
                raise SportmonksError("Sportmonks rate limit reached (HTTP 429).")
            response.raise_for_status()
            payload = response.json()
        except SportmonksError:
            raise
        except requests.Timeout as exc:
            raise SportmonksError("Sportmonks request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise SportmonksError(f"Sportmonks network request failed{suffix}.") from exc
        except ValueError as exc:
            raise SportmonksError("Sportmonks returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise SportmonksError("Sportmonks returned an unexpected response schema.")
        if payload.get("message") and not isinstance(payload.get("data"), (list, dict)):
            raise SportmonksError("Sportmonks rejected the request; verify endpoint access and parameters.")
        return payload

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("data")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
            if isinstance(rows, dict):
                return [rows]
        return []

    def _all_pages(self, path: str, **params: Any) -> list[dict[str, Any]]:
        """Read a complete paginated collection or fail rather than use a partial season."""
        rows: list[dict[str, Any]] = []
        page = 1
        max_pages = 20
        while page <= max_pages:
            query = {**params, "per_page": min(int(params.get("per_page", 50)), 50), "page": page}
            payload = self._get(path, query)
            rows.extend(self._rows(payload))
            pagination = payload.get("pagination") or {}
            has_more = pagination.get("has_more")
            if has_more is None:
                # Some responses omit pagination when the collection fits one page.
                if len(self._rows(payload)) < query["per_page"]:
                    return rows
                raise SportmonksError("Sportmonks pagination metadata is missing; refusing a potentially incomplete dataset.")
            if not has_more:
                return rows
            page += 1
        raise SportmonksError("Sportmonks season collection exceeded the safe pagination limit; no partial dataset was accepted.")

    def leagues(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("leagues", params))

    def available_leagues(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("leagues", **params)

    def teams_by_season(self, season_id: int | str, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages(f"teams/seasons/{season_id}", **params)

    def standings_by_season(self, season_id: int | str, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages(f"standings/seasons/{season_id}", **params)

    def fixtures_by_season(self, season_id: int | str, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages(
            f"fixtures/seasons/{season_id}",
            include="participants;scores;state;statistics.type;lineups",
            **params,
        )

    def seasons(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("seasons", params))

    def teams(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("teams", params))

    def standings(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("standings", params))

    def fixtures(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("fixtures", params))

    def fixtures_between(self, start_date: str, end_date: str, **params: Any) -> list[dict[str, Any]]:
        """Fetch a date range; Sportmonks documents a maximum 100-day range."""
        return self._rows(self._get(f"fixtures/between/{start_date}/{end_date}", params))

    def fixture(self, fixture_id: int | str, **params: Any) -> dict[str, Any] | None:
        rows = self._rows(self._get(f"fixtures/{fixture_id}", params))
        return rows[0] if rows else None

    def livescores(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("livescores", params))

    def test_connection(self) -> dict[str, Any]:
        """Verify token access through the documented leagues endpoint."""
        rows = self.leagues(per_page=1)
        return {
            "transport_status": "responding",
            "records_returned": len(rows),
            "metadata": dict(self.last_metadata),
            "fallback_enabled": False,
            "note": "Connection verified; Sportmonks is not yet wired into Layer 2 prediction collection.",
        }

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "SportmonksClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
