
"""
Highlightly Football API Client
Football Prediction App - Layer 2

Compatible with:
- app.py
- engine.py
- TVD module

API provider: Highlightly
Base URL: https://soccer.highlightly.net
"""

import os
import requests

from datetime import date, datetime, timedelta
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
            base_url
            or os.getenv("HIGHLIGHTLY_BASE_URL", self.BASE_URL)
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

            if response.status_code == 404:
                raise APIFootballError(
                    f"Highlightly endpoint or resource not found: {endpoint}"
                )

            if response.status_code == 429:
                raise APIFootballError(
                    "Highlightly API rate limit exceeded. Try again later."
                )

            if response.status_code >= 400:
                raise APIFootballError(
                    f"Highlightly API error {response.status_code}: "
                    f"{response.text[:500]}"
                )

            try:
                return response.json()

            except ValueError:
                raise APIFootballError(
                    "Highlightly returned invalid JSON."
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

            # Support single-object responses.
            return [response]

        return []

    @staticmethod
    def parse_score(score):

        if isinstance(score, dict):
            score = score.get("current")

        if not isinstance(score, str) or not score.strip():
            return None, None

        try:
            parts = score.replace("-", ":").split(":")

            if len(parts) != 2:
                return None, None

            return (
                int(parts[0].strip()),
                int(parts[1].strip()),
            )

        except (ValueError, TypeError):
            return None, None

    @staticmethod
    def _get_date_key(value):

        if not value:
            return ""

        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).timestamp()

        except (ValueError, TypeError, OverflowError):
            return 0

    @staticmethod
    def _is_finished(status):

        return str(status or "").strip().casefold() in (
            APIFootballClient.FINISHED_STATES
        )

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

        if not isinstance(home, dict):
            home = {}

        if not isinstance(away, dict):
            away = {}

        if not isinstance(league, dict):
            league = {}

        if not isinstance(state, dict):
            state = {}

        score_data = state.get("score") or {}

        if not isinstance(score_data, dict):
            score_data = {}

        current_score = (
            score_data.get("current")
            or match.get("score")
        )

        home_goals, away_goals = cls.parse_score(
            current_score
        )

        if home_goals is None:
            home_goals = match.get("homeGoals")

        if away_goals is None:
            away_goals = match.get("awayGoals")

        status = (
            state.get("description")
            or match.get("status")
            or match.get("statusShort")
        )

        return {

            "fixture_id": (
                match.get("id")
                or match.get("fixture_id")
            ),

            "date": match.get("date"),

            "timestamp": match.get("date"),

            "home_team": (
                home.get("name")
                or match.get("home_team")
            ),

            "away_team": (
                away.get("name")
                or match.get("away_team")
            ),

            "home_team_id": (
                home.get("id")
                or match.get("home_team_id")
            ),

            "away_team_id": (
                away.get("id")
                or match.get("away_team_id")
            ),

            "home_team_logo": home.get("logo"),

            "away_team_logo": away.get("logo"),

            "league": league.get("name"),

            "league_id": league.get("id"),

            "season": league.get("season"),

            "status": status,

            "home_goals": home_goals,

            "away_goals": away_goals,

            "score": current_score,

            "round": match.get("round"),

            "is_finished": cls._is_finished(status),
        }

    # --------------------------------------------------
    # LEAGUES
    # --------------------------------------------------

    def leagues(self, season=None):
        """
        Retrieve available leagues.

        Supports:
            client.leagues()
            client.leagues(season)
        """

        params = {}

        if season is not None:
            params["season"] = season

        response = self.request(
            "/leagues",
            params=params,
        )

        return self.extract_data(response)

    # --------------------------------------------------
    # TEAM SEARCH
    # --------------------------------------------------

    def search_team(self, team_name):

        if not team_name:
            raise APIFootballError(
                "Team name is required."
            )

        response = self.request(
            "/teams",
            params={
                "name": team_name,
                "type": "club",
                "limit": 20,
                "offset": 0,
            },
        )

        return self.extract_data(response)

    # --------------------------------------------------
    # TEAM DETAILS
    # --------------------------------------------------

    def team_details(self, team_id):

        if not team_id:
            raise APIFootballError("Team ID is required.")

        return self.request(
            f"/teams/{team_id}"
        )

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

        if last <= 0:
            raise APIFootballError(
                "Number of recent matches must be positive."
            )

        current_season = season or date.today().year

        matches = []

        # Official Highlightly last-five endpoint.
        try:

            response = self.request(
                "/last-five-games",
                params={
                    "teamId": team_id,
                },
            )

            matches.extend(
                self.extract_data(response)
            )

        except APIFootballError:
            # Continue with the matches endpoint.
            pass

        # Retrieve additional historical matches.
        seasons = [
            current_season,
            current_season - 1,
        ]

        for year in seasons:

            for side in (
                "homeTeamId",
                "awayTeamId",
            ):

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

        # Remove duplicate fixtures.
        unique_matches = {}

        for match in matches:

            if not isinstance(match, dict):
                continue

            match_id = match.get("id")

            if match_id is not None:
                unique_matches[match_id] = match

        normalized = [
            self.normalize_match(match)
            for match in unique_matches.values()
        ]

        # Keep completed matches with actual scores.
        normalized = [
            match
            for match in normalized
            if (
                match.get("is_finished")
                and match.get("home_goals") is not None
                and match.get("away_goals") is not None
            )
        ]

        # Sort newest first.
        normalized.sort(
            key=lambda x: self._get_date_key(
                x.get("date")
            ),
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

        if days < 0:
            raise APIFootballError(
                "Days cannot be negative."
            )

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

                    normalized = self.normalize_match(
                        match
                    )

                    fixture_id = normalized.get(
                        "fixture_id"
                    )

                    if (
                        fixture_id is not None
                        and not normalized.get("is_finished")
                        and normalized.get("status", "").casefold()
                        not in {
                            "cancelled",
                            "postponed",
                            "abandoned",
                        }
                    ):

                        matches[fixture_id] = normalized

        return sorted(
            matches.values(),
            key=lambda x: self._get_date_key(
                x.get("date")
            ),
        )

    # --------------------------------------------------
    # MATCH DETAILS
    # --------------------------------------------------

    def fixture_details(self, fixture_id):

        if not fixture_id:
            raise APIFootballError(
                "Fixture ID is required."
            )

        response = self.request(
            f"/matches/{fixture_id}"
        )

        data = self.extract_data(response)

        if not data:
            return {}

        return self.normalize_match(data[0])

    # --------------------------------------------------
    # MATCH STATISTICS
    # --------------------------------------------------

    def fixture_statistics(self, fixture_id):

        if not fixture_id:
            raise APIFootballError(
                "Fixture ID is required."
            )

        return self.request(
            f"/statistics/{fixture_id}"
        )

    # --------------------------------------------------
    # TEAM STATISTICS
    # --------------------------------------------------

    def team_statistics(
        self,
        team_id,
        from_date=None,
    ):

        if not team_id:
            raise APIFootballError(
                "Team ID is required."
            )

        if from_date is None:

            from_date = (
                date.today() - timedelta(days=365)
            ).isoformat()

        return self.request(
            f"/teams/statistics/{team_id}",
            params={
                "fromDate": from_date,
                "timezone": "Africa/Nairobi",
            },
        )

    # --------------------------------------------------
    # MATCH LINEUPS
    # --------------------------------------------------

    def fixture_lineups(self, fixture_id):

        if not fixture_id:
            raise APIFootballError(
                "Fixture ID is required."
            )

        return self.request(
            f"/lineups/{fixture_id}"
        )

    # --------------------------------------------------
    # INJURIES / PLAYER AVAILABILITY
    # --------------------------------------------------

    def injuries(
        self,
        fixture_id=None,
        team_id=None,
    ):
        """
        Do not invent injury information.

        Return None when injury data is unavailable.
        """

        return None

    # --------------------------------------------------
    # VALIDATE MATCH DATA
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

            if not isinstance(match, dict):

                missing.append(
                    f"Match {index + 1}: invalid_match_object"
                )

                continue

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

