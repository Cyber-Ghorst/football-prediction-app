
"""
Highlightly Football API Client
Football Prediction App - Layer 2

Keeps the existing APIFootballClient class name so app.py
can continue importing it without changing the import statement.
"""

import os
import requests

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional


class APIFootballError(Exception):
    """Raised when Highlightly API requests fail."""
    pass


class APIFootballClient:

    BASE_URL = "https://soccer.highlightly.net"

    FINISHED_STATES = {
        "finished",
        "finished after penalties",
        "finished after extra time",
        "awarded",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 25,
    ):
        self.api_key = (
            api_key
            or os.getenv("HIGHLIGHTLY_API_KEY")
            or os.getenv("API_FOOTBALL_KEY")
        )

        if not self.api_key:
            raise APIFootballError(
                "Missing Highlightly API key. "
                "Set HIGHLIGHTLY_API_KEY in Streamlit Secrets."
            )

        self.base_url = (
            base_url or os.getenv(
                "HIGHLIGHTLY_BASE_URL", self.BASE_URL
            )
        ).rstrip("/")

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({
            "x-rapidapi-key": self.api_key,
            "Accept": "application/json",
        })

    # --------------------------------------------------
    # GENERAL REQUEST HANDLER
    # --------------------------------------------------

    def request(self, endpoint: str, params=None):

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout,
            )

            if response.status_code == 401:
                raise APIFootballError(
                    "Authentication failed. Check your Highlightly API key."
                )

            if response.status_code == 403:
                raise APIFootballError(
                    "Access denied. Check your Highlightly subscription."
                )

            if response.status_code == 429:
                raise APIFootballError(
                    "Highlightly API rate limit exceeded."
                )

            if response.status_code >= 400:
                raise APIFootballError(
                    f"Highlightly API error "
                    f"{response.status_code}: {response.text[:500]}"
                )

            try:
                return response.json()
            except ValueError:
                raise APIFootballError(
                    "Highlightly returned an invalid JSON response."
                )

        except requests.exceptions.Timeout:
            raise APIFootballError(
                "Highlightly request timed out."
            )

        except requests.exceptions.ConnectionError:
            raise APIFootballError(
                "Could not connect to Highlightly."
            )

        except requests.exceptions.RequestException as exc:
            raise APIFootballError(str(exc))

    # --------------------------------------------------
    # RESPONSE HELPERS
    # --------------------------------------------------

    @staticmethod
    def extract_data(response):

        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            data = response.get("data")

            if isinstance(data, list):
                return data

            if isinstance(data, dict):
                return [data]

            return [response]

        return []

    @staticmethod
    def parse_score(score):

        if isinstance(score, dict):
            score = score.get("current")

        if not score or not isinstance(score, str):
            return None, None

        try:
            parts = score.replace("-", ":").split(":")

            if len(parts) != 2:
                return None, None

            return int(parts[0].strip()), int(parts[1].strip())

        except (ValueError, TypeError):
            return None, None

    # --------------------------------------------------
    # NORMALIZE MATCH DATA
    # --------------------------------------------------

    @classmethod
    def normalize_match(cls, match):

        if not isinstance(match, dict):
            return {}

        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        league = match.get("league") or {}
        state = match.get("state") or {}

        score_data = state.get("score") or {}

        home_goals, away_goals = cls.parse_score(
            score_data.get("current")
        )

        # Support alternative response formats where available.
        if home_goals is None:
            home_goals = match.get("homeGoals")

        if away_goals is None:
            away_goals = match.get("awayGoals")

        status = state.get("description")

        return {
            "fixture_id": match.get("id"),
            "date": match.get("date"),
            "timestamp": match.get("date"),

            "home_team": home.get("name"),
            "away_team": away.get("name"),

            "home_team_id": home.get("id"),
            "away_team_id": away.get("id"),

            "home_team_logo": home.get("logo"),
            "away_team_logo": away.get("logo"),

            "league": league.get("name"),
            "league_id": league.get("id"),
            "season": league.get("season"),

            "status": status,

            "home_goals": home_goals,
            "away_goals": away_goals,

            "score": score_data.get("current"),

            "round": match.get("round"),

            "is_finished": (
                str(status).lower() in cls.FINISHED_STATES
            ),
        }
    # --------------------------------------------------
    # LEAGUES
    # --------------------------------------------------

    def leagues(self):
        """
        Retrieve available football leagues from Highlightly.
        """

        response = self.request("/leagues")

        return self.extract_data(response)
    # --------------------------------------------------
    # TEAM SEARCH
    # --------------------------------------------------

    def search_team(self, team_name):

        if not team_name:
            raise APIFootballError("Team name is required.")

        response = self.request(
            "/teams",
            params={
                "name": team_name,
                "type": "club",
                "limit": 20,
            },
        )

        return self.extract_data(response)

    # --------------------------------------------------
    # TEAM DETAILS
    # --------------------------------------------------

    def team_details(self, team_id):

        if not team_id:
            raise APIFootballError("Team ID is required.")

        response = self.request(f"/teams/{team_id}")

        return response

    # --------------------------------------------------
    # RECENT MATCHES
    # --------------------------------------------------

    def recent_matches(
        self,
        team_id,
        last=10,
        season=None,
    ):

        if not team_id:
            raise APIFootballError("Team ID is required.")

        today = date.today()

        current_season = season or today.year

        matches = []

        # First obtain the official last-five form guide.
        try:
            response = self.request(
                "/last-five-games",
                params={"teamId": team_id},
            )

            matches.extend(
                self.extract_data(response)
            )

        except APIFootballError:
            pass

        # Obtain additional match history through the matches endpoint.
        seasons = [
            current_season,
            current_season - 1,
        ]

        for year in seasons:

            for side in ("homeTeamId", "awayTeamId"):

                response = self.request(
                    "/matches",
                    params={
                        side: team_id,
                        "season": year,
                        "limit": 100,
                        "offset": 0,
                    },
                )

                matches.extend(
                    self.extract_data(response)
                )

        # Remove duplicates.
        unique_matches = {}

        for match in matches:

            match_id = match.get("id")

            if match_id is not None:
                unique_matches[match_id] = match

        normalized = [
            self.normalize_match(match)
            for match in unique_matches.values()
        ]

        # Only completed matches with actual scores.
        normalized = [
            match for match in normalized
            if match.get("is_finished")
            and match.get("home_goals") is not None
            and match.get("away_goals") is not None
        ]

        normalized.sort(
            key=lambda x: x.get("date") or "",
            reverse=True,
        )

        return normalized[:last]

    # --------------------------------------------------
    # UPCOMING MATCHES
    # --------------------------------------------------

    def upcoming_matches(
        self,
        team_id=None,
        days=14,
    ):

        matches = {}

        today = date.today()

        for offset in range(days + 1):

            match_date = (
                today + timedelta(days=offset)
            ).isoformat()

            filters = [
                {"date": match_date}
            ]

            if team_id:
                filters = [
                    {
                        "date": match_date,
                        "homeTeamId": team_id,
                    },
                    {
                        "date": match_date,
                        "awayTeamId": team_id,
                    },
                ]

            for params in filters:

                response = self.request(
                    "/matches",
                    params=params,
                )

                for match in self.extract_data(response):

                    normalized = self.normalize_match(match)

                    if (
                        normalized.get("fixture_id") is not None
                        and not normalized.get("is_finished")
                    ):
                        matches[
                            normalized["fixture_id"]
                        ] = normalized

        return sorted(
            matches.values(),
            key=lambda x: x.get("date") or "",
        )

    # --------------------------------------------------
    # MATCH DETAILS
    # --------------------------------------------------

    def fixture_details(self, fixture_id):

        if not fixture_id:
            raise APIFootballError("Fixture ID is required.")

        response = self.request(
            f"/matches/{fixture_id}"
        )

        if isinstance(response, dict):
            if isinstance(response.get("data"), dict):
                response = response["data"]

        return self.normalize_match(response)

    # --------------------------------------------------
    # MATCH STATISTICS
    # --------------------------------------------------

    def fixture_statistics(self, fixture_id):

        if not fixture_id:
            raise APIFootballError("Fixture ID is required.")

        response = self.request(
            f"/statistics/{fixture_id}"
        )

        return response

    # --------------------------------------------------
    # TEAM STATISTICS
    # --------------------------------------------------

    def team_statistics(
        self,
        team_id,
        from_date=None,
    ):

        if not team_id:
            raise APIFootballError("Team ID is required.")

        if from_date is None:
            from_date = (
                date.today() - timedelta(days=365)
            ).isoformat()

        response = self.request(
            f"/teams/statistics/{team_id}",
            params={
                "fromDate": from_date,
                "timezone": "Africa/Nairobi",
            },
        )

        return response

    # --------------------------------------------------
    # MATCH LINEUPS
    # --------------------------------------------------

    def fixture_lineups(self, fixture_id):

        if not fixture_id:
            raise APIFootballError("Fixture ID is required.")

        response = self.request(
            f"/lineups/{fixture_id}"
        )

        return response

    # --------------------------------------------------
    # INJURIES / PLAYER AVAILABILITY
    # --------------------------------------------------

    def injuries(self, fixture_id=None, team_id=None):

        """
        Highlightly's documented football endpoints do not
        provide a dedicated injuries endpoint.

        Return None rather than inventing injury information
        or treating unavailable information as zero injuries.
        """

        return None

    # --------------------------------------------------
    # VALIDATE DATA
    # --------------------------------------------------

    @staticmethod
    def validate_match_data(matches):

        if not matches:
            return {
                "valid": False,
                "message": "No match history available.",
                "missing_fields": ["match_history"],
            }

        required_fields = [
            "date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
        ]

        missing = []

        for index, match in enumerate(matches):

            for field in required_fields:

                if match.get(field) is None:
                    missing.append(
                        f"Match {index + 1}: {field}"
                    )

        return {
            "valid": len(missing) == 0,
            "message": (
                "Match data validated."
                if not missing
                else "Some match data is missing."
            ),
            "missing_fields": missing,
        }

    # --------------------------------------------------
    # CLOSE CONNECTION
    # --------------------------------------------------

    def close(self):
        self.session.close()
