"""Independent, read-only football-data.org v4 fixture observations.

This adapter never writes canonical fixtures. It preserves football-data.org
IDs and payload provenance and emits the same observation contract as the
other future-fixture adapters.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any, Mapping

import requests

from free_fixture_adapters import (
    FreeFixtureProviderError,
    _observation,
    _utc_now,
)


class FootballDataOrgAdapter:
    provider = "football_data_org"
    BASE_URL = "https://api.football-data.org/v4"
    LICENCE = (
        "football-data.org API terms; account plan, attribution and reuse "
        "conditions must be checked before production display or commercial use"
    )

    def __init__(
        self,
        token: str | None = None,
        *,
        session: requests.Session | None = None,
        timeout: int = 20,
        base_url: str | None = None,
    ):
        self.token = token or os.getenv("FOOTBALL_DATA_ORG_API_TOKEN") or os.getenv(
            "FOOTBALL_DATA_ORG_TOKEN"
        )
        if not self.token:
            try:
                import streamlit as st
                self.token = (
                    st.secrets.get("FOOTBALL_DATA_ORG_API_TOKEN")
                    or st.secrets.get("FOOTBALL_DATA_ORG_TOKEN")
                )
            except Exception:
                self.token = None
        if not self.token:
            raise FreeFixtureProviderError(
                "FOOTBALL_DATA_ORG_API_TOKEN is required for football-data.org."
            )
        self.session = session or requests.Session()
        self.timeout = timeout
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.session.headers.setdefault("User-Agent", "football-prediction-app/1.0")
        self.session.headers.setdefault("Accept", "application/json")
        self.session.headers["X-Auth-Token"] = self.token

    def _get_json(self, endpoint: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=dict(params or {}), timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise FreeFixtureProviderError("football-data.org request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise FreeFixtureProviderError(
                f"football-data.org request failed{suffix}."
            ) from exc
        except ValueError as exc:
            raise FreeFixtureProviderError(
                "football-data.org returned invalid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise FreeFixtureProviderError(
                "football-data.org returned an unexpected response shape."
            )
        if payload.get("error"):
            message = str(payload.get("message") or "provider API error")[:240]
            raise FreeFixtureProviderError(
                f"football-data.org rejected the request: {message}"
            )
        return payload

    def competitions(self) -> list[dict[str, Any]]:
        """Return the provider's own competition catalogue, without mapping IDs."""
        payload = self._get_json("competitions")
        rows = payload.get("competitions")
        if not isinstance(rows, list):
            raise FreeFixtureProviderError(
                "football-data.org competition catalogue has no competitions array."
            )
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _date(value: str, field: str) -> str:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be a valid YYYY-MM-DD date.") from exc

    def matches(
        self,
        date_from: str,
        date_to: str,
        *,
        competitions: list[str] | tuple[str, ...] | None = None,
        max_pages: int = 5,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch scheduled fixtures over a bounded date range with pagination."""
        start = self._date(date_from, "date_from")
        end = self._date(date_to, "date_to")
        if end < start:
            raise ValueError("date_to must not be earlier than date_from.")
        if (date.fromisoformat(end) - date.fromisoformat(start)).days > 30:
            raise ValueError("football-data.org date range cannot exceed 31 calendar days.")
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 20:
            raise ValueError("max_pages must be an integer from 1 through 20.")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
            raise ValueError("page_size must be an integer from 1 through 100.")

        selected = [str(code).strip().upper() for code in (competitions or []) if str(code).strip()]
        params: dict[str, Any] = {
            "dateFrom": start,
            "dateTo": end,
            "limit": page_size,
        }
        if selected:
            params["competitions"] = ",".join(selected)

        fetched = _utc_now()
        output: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            query = {**params, "page": page}
            payload = self._get_json("matches", query)
            rows = payload.get("matches")
            if not isinstance(rows, list):
                raise FreeFixtureProviderError(
                    "football-data.org matches response has no matches array."
                )
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                competition = row.get("competition") if isinstance(row.get("competition"), Mapping) else {}
                season = row.get("season") if isinstance(row.get("season"), Mapping) else {}
                home = row.get("homeTeam") if isinstance(row.get("homeTeam"), Mapping) else {}
                away = row.get("awayTeam") if isinstance(row.get("awayTeam"), Mapping) else {}
                status = str(row.get("status") or "unknown").upper()
                # football-data.org uses TIMED as a scheduled fixture with a
                # confirmed kickoff; preserve the original value in raw_payload.
                normalized_status = "scheduled" if status in {"SCHEDULED", "TIMED"} else status.lower()
                season_key = season.get("id") or season.get("startDate")
                output.append(_observation(
                    self.provider,
                    dict(row),
                    fetched_at=fetched,
                    source_url=f"{self.base_url}/matches",
                    licence=self.LICENCE,
                    fixture_id=row.get("id"),
                    competition=competition.get("id") or competition.get("code"),
                    competition_name=competition.get("name") or competition.get("code"),
                    season=season_key,
                    season_name=season.get("startDate") or season.get("endDate") or season_key,
                    home=home.get("name") or home.get("shortName") or home.get("tla"),
                    away=away.get("name") or away.get("shortName") or away.get("tla"),
                    home_id=home.get("id"),
                    away_id=away.get("id"),
                    kickoff=row.get("utcDate"),
                    status=normalized_status,
                ).to_dict())
            result_set = payload.get("resultSet") if isinstance(payload.get("resultSet"), Mapping) else {}
            total = result_set.get("count")
            if not rows or len(rows) < page_size or (
                isinstance(total, int) and page * page_size >= total
            ):
                break
        # Match payloads do not consistently include competition.area. When
        # scheduled observations need country context, enrich them from the
        # provider's own /competitions catalogue. The original match fields are
        # retained and the added area is explicitly marked as adapter metadata.
        needs_area = [
            item for item in output
            if item.get("eligible_for_review") is True
            and isinstance(item.get("raw_payload"), dict)
            and not (
                isinstance(item["raw_payload"].get("competition"), Mapping)
                and isinstance(item["raw_payload"]["competition"].get("area"), Mapping)
            )
        ]
        if needs_area:
            try:
                catalogue = self.competitions()
            except FreeFixtureProviderError:
                catalogue = []
            by_id_or_code: dict[str, Mapping[str, Any]] = {}
            for item in catalogue:
                if not isinstance(item, Mapping):
                    continue
                for key in (item.get("id"), item.get("code")):
                    if key is not None:
                        by_id_or_code[str(key)] = item
            for observation in needs_area:
                raw = observation["raw_payload"]
                competition = raw.get("competition")
                if not isinstance(competition, Mapping):
                    continue
                metadata = (
                    by_id_or_code.get(str(competition.get("id") or ""))
                    or by_id_or_code.get(str(competition.get("code") or ""))
                )
                area = metadata.get("area") if isinstance(metadata, Mapping) else None
                if not isinstance(area, Mapping) or not area.get("name"):
                    continue
                enriched_competition = dict(competition)
                enriched_competition["area"] = dict(area)
                raw["competition"] = enriched_competition
                raw["_adapter_enrichment"] = {
                    "competition_area": {
                        "source_endpoint": f"{self.base_url}/competitions",
                        "provider_competition_id": metadata.get("id"),
                        "area_id": area.get("id"),
                        "area_name": area.get("name"),
                    }
                }
        return output

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "FootballDataOrgAdapter":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
