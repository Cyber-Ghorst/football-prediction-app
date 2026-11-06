
import requests
import streamlit as st
from datetime import date, timedelta

BASE_URL = "https://v3.football.api-sports.io"


class APIFootball:
    def __init__(self):
        try:
            self.api_key = st.secrets["API_FOOTBALL_KEY"]
        except Exception:
            self.api_key = None

        if not self.api_key:
            raise ValueError(
                "API_FOOTBALL_KEY is missing from Streamlit Secrets."
            )

        self.headers = {
            "x-apisports-key": self.api_key
        }

    def request(self, endpoint, params=None):
        """Make a validated request to API-Football."""
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}",
                headers=self.headers,
                params=params or {},
                timeout=20
            )
            response.raise_for_status()
            data = response.json()

            if data.get("errors"):
                raise RuntimeError(
                    f"API error: {data['errors']}"
                )

            return data.get("response", [])

        except requests.RequestException as error:
            raise RuntimeError(
                f"Football data connection failed: {error}"
            ) from error

    def search_team(self, team_name):
        """Find a team and its API ID."""
        results = self.request(
            "teams",
            {"search": team_name}
        )

        return [
            {
                "id": item["team"]["id"],
                "name": item["team"]["name"],
                "country": item["team"].get("country")
            }
            for item in results
        ]

    def recent_matches(self, team_id, limit=10):
        """Retrieve a team's latest completed matches."""
        matches = self.request(
            "fixtures",
            {
                "team": team_id,
                "last": limit,
                "status": "FT-AET-PEN"
            }
        )

        return [
            self.normalize_match(match, team_id)
            for match in matches
        ]

    def upcoming_matches(self, team_id, limit=10):
        """Retrieve upcoming fixtures."""
        return self.request(
            "fixtures",
            {
                "team": team_id,
                "next": limit
            }
        )

    def fixture_details(self, fixture_id):
        """Retrieve one fixture."""
        results = self.request(
            "fixtures",
            {"id": fixture_id}
        )

        return results[0] if results else None

    def injuries(self, fixture_id):
        """Retrieve injury and suspension information."""
        return self.request(
            "injuries",
            {"fixture": fixture_id}
        )

    def team_statistics(self, team_id, league_id, season):
        """Retrieve competition-specific team statistics."""
        return self.request(
            "teams/statistics",
            {
                "team": team_id,
                "league": league_id,
                "season": season
            }
        )

    @staticmethod
    def normalize_match(match, team_id):
        fixture = match.get("fixture", {})
        teams = match.get("teams", {})
        goals = match.get("goals", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        is_home = home.get("id") == team_id

        return {
            "fixture_id": fixture.get("id"),
            "date": fixture.get("date"),
            "opponent": (
                away.get("name") if is_home
                else home.get("name")
            ),
            "home": is_home,
            "goals_for": (
                goals.get("home") if is_home
                else goals.get("away")
            ),
            "goals_against": (
                goals.get("away") if is_home
                else goals.get("home")
            ),
            "result": (
                "W" if (
                    goals.get("home") > goals.get("away")
                    if is_home else
                    goals.get("away") > goals.get("home")
                )
                else "D" if goals.get("home") == goals.get("away")
                else "L"
            )
        }
    def fixture_statistics(self, fixture_id):
        return self.request(
            "fixtures/statistics",
            {"fixture": fixture_id}
        )