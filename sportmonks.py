"""Sportmonks Football API v3 adapter.

Credential: SPORTMONKS_API_TOKEN (Streamlit Secrets or environment).
Uses the documented v3 REST API and Authorization header. Current-season
collection is wired to Layer 2 with strict season/team identity and completeness gates.
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
            raise SportmonksError(f"Sportmonks request to '{path}' failed{suffix}.") from exc
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

    @staticmethod
    def _flatten_schedule_fixtures(payload: Any) -> list[dict[str, Any]]:
        """Flatten Sportmonks' stages -> rounds -> fixtures schedule response."""
        fixtures: list[dict[str, Any]] = []
        seen: set[int] = set()
        for stage in SportmonksClient._rows(payload):
            for round_row in SportmonksClient._rows(stage.get("rounds")):
                for fixture_row in SportmonksClient._rows(round_row.get("fixtures")):
                    fixture = dict(fixture_row)
                    fixture.setdefault("stage_id", stage.get("id"))
                    fixture.setdefault("round_id", round_row.get("id"))
                    fixture_id = fixture.get("id")
                    if fixture_id is None:
                        continue
                    try:
                        key = int(fixture_id)
                    except (TypeError, ValueError):
                        continue
                    if key not in seen:
                        seen.add(key)
                        fixtures.append(fixture)
        return fixtures

    @staticmethod
    def _fixture_team_ids(fixture: dict[str, Any]) -> set[int]:
        participants = SportmonksClient._rows(fixture.get("participants"))
        ids: set[int] = set()
        for participant in participants:
            try:
                if participant.get("id") is not None:
                    ids.add(int(participant["id"]))
            except (TypeError, ValueError):
                continue
        return ids

    def fixtures_by_season(
        self,
        season_id: int | str,
        *,
        include_statistics: bool = True,
        team_ids: list[int] | tuple[int, ...] | None = None,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Fetch a season schedule and optionally enrich selected teams' recent matches.

        Sportmonks schedules are returned as one nested stages/rounds/fixtures
        response and do not support pagination or includes. Detailed statistics
        are therefore fetched in one multi-fixture request for up to ten recent
        completed matches per selected team, rather than requesting every match.
        """
        if params:
            unsupported = ", ".join(sorted(params))
            raise SportmonksError(
                f"Unsupported schedule parameters ({unsupported}); the schedule endpoint does not accept query filters or includes."
            )
        payload = self._get(f"schedules/seasons/{season_id}")
        fixtures = self._flatten_schedule_fixtures(payload)

        selected_ids: set[int] = set()
        for value in team_ids or ():
            try:
                selected_ids.add(int(value))
            except (TypeError, ValueError):
                continue

        if include_statistics and selected_ids:
            recent_by_team: dict[int, list[dict[str, Any]]] = {
                team_id: [] for team_id in selected_ids
            }
            for fixture in fixtures:
                if int(fixture.get("state_id") or 0) not in {5, 7, 8}:
                    continue
                for team_id in self._fixture_team_ids(fixture) & selected_ids:
                    recent_by_team[team_id].append(fixture)

            chosen: dict[int, dict[str, Any]] = {}
            for team_fixtures in recent_by_team.values():
                ordered = sorted(
                    team_fixtures,
                    key=lambda row: str(row.get("starting_at") or ""),
                    reverse=True,
                )
                for fixture in ordered[:10]:
                    chosen[int(fixture["id"])] = fixture

            fixture_ids = sorted(chosen)
            if fixture_ids:
                include = "participants;scores;state;statistics.type"
                details_payload = self._get(
                    f"fixtures/multi/{','.join(str(value) for value in fixture_ids)}",
                    {"include": include},
                )
                details = self._rows(details_payload)
                details_by_id = {
                    int(row["id"]): row for row in details
                    if row.get("id") is not None
                }
                for fixture_id, detail in details_by_id.items():
                    base = chosen.get(fixture_id)
                    if base is not None:
                        base.update(detail)
        return fixtures

    def seasons(self, **params: Any) -> list[dict[str, Any]]:
        return self._rows(self._get("seasons", params))

    def available_seasons(self, **params: Any) -> list[dict[str, Any]]:
        return self._all_pages("seasons", **params)

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
            "note": "Connection verified; Layer 2 integration is present. Selected competition and season coverage must still be validated before use.",
        }

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "SportmonksClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
