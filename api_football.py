"""API-Football v3 client. API key is read from environment or Streamlit secrets."""
from __future__ import annotations
import os
import requests
from typing import Any

BASE_URL = "https://v3.football.api-sports.io"

class APIFootballError(RuntimeError):
    pass

class APIFootballClient:
    def __init__(self, api_key: str | None = None, timeout: int = 25):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.secrets.get("API_FOOTBALL_KEY")
            except Exception:
                self.api_key = None
        if not self.api_key:
            raise APIFootballError("API_FOOTBALL_KEY is not configured. Add it to Streamlit Secrets.")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-apisports-key": self.api_key})

    def get(self, endpoint: str, **params: Any) -> list[dict]:
        try:
            response = self.session.get(f"{BASE_URL}/{endpoint.lstrip('/')}", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise APIFootballError(f"API-Football request failed: {exc}") from exc
        errors = payload.get("errors") or {}
        if errors:
            raise APIFootballError(f"API-Football returned an error: {errors}")
        return payload.get("response") or []

    def leagues(self, season: int, country: str | None = None) -> list[dict]:
        params = {"season": season}
        if country:
            params["country"] = country
        return self.get("leagues", **params)

    def teams(self, league_id: int, season: int) -> list[dict]:
        return self.get("teams", league=league_id, season=season)

    def standings(self, league_id: int, season: int) -> dict[int, float]:
        rows = self.get("standings", league=league_id, season=season)
        result: dict[int, float] = {}
        try:
            table = rows[0]["league"]["standings"][0]
        except (IndexError, KeyError, TypeError):
            return result
        points = [int(x.get("points", 0)) for x in table if x.get("points") is not None]
        maximum = max(points) if points else 0
        if maximum <= 0:
            return result
        for item in table:
            tid = item.get("team", {}).get("id")
            pts = item.get("points")
            if tid is not None and pts is not None:
                result[int(tid)] = round(float(pts) / maximum * 100, 1)
        return result

    def last_fixtures(self, team_id: int, season: int, last: int = 10) -> list[dict]:
        return self.get("fixtures", team=team_id, season=season, last=last)

    def next_fixture(self, team_id: int, season: int) -> list[dict]:
        return self.get("fixtures", team=team_id, season=season, next=1)

    def fixture_statistics(self, fixture_id: int) -> list[dict]:
        return self.get("fixtures/statistics", fixture=fixture_id)

    def injuries(self, team_id: int, season: int, fixture_id: int | None = None) -> list[dict]:
        params = {"team": team_id, "season": season}
        if fixture_id is not None:
            params["fixture"] = fixture_id
        return self.get("injuries", **params)

    def fixture_lineups(self, fixture_id: int) -> list[dict]:
        return self.get("fixtures/lineups", fixture=fixture_id)
