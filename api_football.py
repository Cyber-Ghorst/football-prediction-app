"""
API Ninjas Football API Client
Football Prediction App - Layer 2

Provider: https://api.api-ninjas.com/v1

Compatible imports:
    from api_football import APIFootballClient, APIFootballError

Required secret:
    API_NINJAS_API_KEY
"""

import os
import requests

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


class APIFootballError(Exception):
    """Football API request error."""
    pass


class APIFootballClient:

    BASE_URL = "https://api.api-ninjas.com/v1"

    LEAGUES = [
        {"id": "epl", "name": "Premier League"},
        {"id": "laliga", "name": "La Liga"},
        {"id": "bundesliga", "name": "Bundesliga"},
        {"id": "seriea", "name": "Serie A"},
        {"id": "ligue1", "name": "Ligue 1"},
        {"id": "ucl", "name": "Champions League"},
        {"id": "uel", "name": "Europa League"},
        {"id": "uecl", "name": "Conference League"},
        {"id": "mls", "name": "MLS"},
        {"id": "championship", "name": "Championship"},
        {"id": "eredivisie", "name": "Eredivisie"},
        {"id": "primeiraliga", "name": "Primeira Liga"},
        {"id": "scottishpremiership", "name": "Scottish Premiership"},
        {"id": "superlig", "name": "Turkish Super Lig"},
        {"id": "saudiproleague", "name": "Saudi Pro League"},
        {"id": "brasileirao", "name": "Brasileirao"},
        {"id": "ligamx", "name": "Liga MX"},
        {"id": "afcon", "name": "Africa Cup of Nations"},
        {"id": "worldcup", "name": "World Cup"},
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 25
    ):
        self.api_key = (
            api_key
            or os.getenv("API_NINJAS_API_KEY")
            or os.getenv("API_NINJAS_KEY")
        )

        if not self.api_key:
            try:
                import streamlit as st

                self.api_key = (
                    st.secrets.get("API_NINJAS_API_KEY")
                    or st.secrets.get("API_NINJAS_KEY")
                )

            except Exception:
                self.api_key = None

        if not self.api_key:
            raise APIFootballError(
                "API key missing. Configure API_NINJAS_API_KEY "
                "in Streamlit Secrets."
            )

        self.timeout = timeout
        self.last_warning = None

        self.session = requests.Session()

        self.session.headers.update({
            "X-Api-Key": self.api_key,
            "Accept": "application/json"
        })

    # --------------------------------------------------
    # CORE REQUEST HANDLER
    # --------------------------------------------------

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:
            raise APIFootballError(
                f"Football API request failed: {exc}"
            ) from exc

        except ValueError as exc:
            raise APIFootballError(
                "Invalid JSON returned by API."
            ) from exc

    # --------------------------------------------------
    # RESPONSE NORMALIZATION
    # --------------------------------------------------

    @staticmethod
    def _as_list(data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [
                item for item in data
                if isinstance(item, dict)
            ]

        if isinstance(data, dict):
            for key in (
                "results",
                "data",
                "matches",
                "standings",
                "teams",
                "players"
            ):
                value = data.get(key)

                if isinstance(value, list):
                    return [
                        item for item in value
                        if isinstance(item, dict)
                    ]

            return [data]

        return []

    @staticmethod
    def _normalize_match(match: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(match)

        home = result.get("home_team")
        away = result.get("away_team")

        if isinstance(home, dict):
            result["home_team_name"] = home.get("name")
        elif home is not None:
            result["home_team_name"] = str(home)

        if isinstance(away, dict):
            result["away_team_name"] = away.get("name")
        elif away is not None:
            result["away_team_name"] = str(away)

        result.setdefault("fixture_id", result.get("game_id"))
        result.setdefault("id", result.get("game_id"))

        return result

    # --------------------------------------------------
    # LEAGUES
    # --------------------------------------------------

    def leagues(self, season: Optional[int] = None):
        return [dict(league) for league in self.LEAGUES]

    def get_leagues(self, season: Optional[int] = None):
        return self.leagues(season)

    # --------------------------------------------------
    # MATCHES AND FIXTURES
    # --------------------------------------------------

    def matches(
        self,
        league: Optional[str] = None,
        date: Optional[Any] = None,
        team: Optional[str] = None,
        season: Optional[int] = None,
        game_id: Optional[str] = None,
        status: Optional[str] = None,
        **kwargs
    ):
        params = {}

        if league:
            params["league"] = league

        if date:
            if isinstance(date, datetime):
                date = date.date()

            if isinstance(date, date):
                date = date.isoformat()

            params["date"] = str(date)

        if team:
            params["team"] = team

        if season is not None:
            params["season"] = season

        if game_id:
            params["game_id"] = game_id

        if status:
            params["status"] = status

        params.update({
            key: value
            for key, value in kwargs.items()
            if value is not None
        })

        data = self._request(
            "soccermatches",
            params
        )

        return [
            self._normalize_match(match)
            for match in self._as_list(data)
        ]

    def get_matches(self, *args, **kwargs):
        return self.matches(*args, **kwargs)

    def fixtures(self, *args, **kwargs):
        return self.matches(*args, **kwargs)

    def get_fixtures(self, *args, **kwargs):
        return self.matches(*args, **kwargs)

    # --------------------------------------------------
    # UPCOMING MATCHES
    # --------------------------------------------------

    def upcoming_matches(
        self,
        league: str = "epl",
        days: int = 7,
        date_from: Optional[Any] = None,
        season: Optional[int] = None
    ):
        if not league:
            raise APIFootballError(
                "League identifier is required."
            )

        if isinstance(date_from, datetime):
            start_date = date_from.date()

        elif isinstance(date_from, date):
            start_date = date_from

        elif date_from:
            start_date = date.fromisoformat(str(date_from))

        else:
            start_date = date.today()

        days = max(1, min(int(days), 60))

        collected = {}

        for offset in range(days):
            match_date = start_date + timedelta(days=offset)

            daily_matches = self.matches(
                league=league,
                date=match_date.isoformat(),
                season=season
            )

            for match in daily_matches:
                game_id = (
                    match.get("game_id")
                    or match.get("fixture_id")
                )

                if game_id:
                    collected[str(game_id)] = match

        results = list(collected.values())

        results.sort(
            key=lambda x: str(
                x.get("start_time") or x.get("date") or ""
            )
        )

        return [
            match for match in results
            if match.get("status") == "scheduled"
        ]

    def get_upcoming_matches(self, *args, **kwargs):
        return self.upcoming_matches(*args, **kwargs)

    # --------------------------------------------------
    # TEAM MATCH HISTORY
    # --------------------------------------------------

    def team_matches(
        self,
        team: str,
        season: Optional[int] = None,
        league: Optional[str] = None
    ):
        if not team:
            raise APIFootballError(
                "Team name or team ID is required."
            )

        params = {
            "team": team
        }

        if season is not None:
            params["season"] = season

        if league:
            params["league"] = league

        data = self._request(
            "soccermatches",
            params
        )

        results = [
            self._normalize_match(match)
            for match in self._as_list(data)
        ]

        results.sort(
            key=lambda x: str(
                x.get("start_time") or x.get("date") or ""
            )
        )

        return results

    def get_team_matches(self, *args, **kwargs):
        return self.team_matches(*args, **kwargs)

    def last_fixtures(
        self,
        team: str,
        count: int = 10,
        league: Optional[str] = None,
        season: Optional[int] = None
    ):
        fixtures = self.team_matches(
            team=team,
            league=league,
            season=season
        )

        completed = [
            match for match in fixtures
            if match.get("status") == "final"
        ]

        completed.reverse()

        return completed[:max(1, int(count))]

    def next_fixture(
        self,
        team: str,
        league: Optional[str] = None,
        season: Optional[int] = None
    ):
        fixtures = self.team_matches(
            team=team,
            league=league,
            season=season
        )

        upcoming = [
            match for match in fixtures
            if match.get("status") == "scheduled"
        ]

        return upcoming[0] if upcoming else None

    def match_details(self, game_id: str):
        if not game_id:
            raise APIFootballError("Game ID is required.")

        data = self._request(
            "soccermatches",
            {"game_id": game_id}
        )

        results = self._as_list(data)

        if not results:
            return None

        return self._normalize_match(results[0])

    # --------------------------------------------------
    # STANDINGS
    # --------------------------------------------------

    def standings(
        self,
        league: str,
        season: Optional[int] = None,
        tournament: Optional[str] = None,
        conference: Optional[str] = None
    ):
        if not league:
            raise APIFootballError(
                "League identifier is required."
            )

        params = {
            "league": league
        }

        if season is not None:
            params["season"] = season

        if tournament:
            params["tournament"] = tournament

        if conference:
            params["conference"] = conference

        data = self._request(
            "soccerstandings",
            params
        )

        return self._as_list(data)

    def get_standings(self, *args, **kwargs):
        return self.standings(*args, **kwargs)

    # --------------------------------------------------
    # CLUBS / TEAMS
    # --------------------------------------------------

    def clubs(
        self,
        league: Optional[str] = None,
        team: Optional[str] = None,
        active: Optional[bool] = None
    ):
        params = {}

        if league:
            params["league"] = league

        if team:
            params["team"] = team

        if active is False:
            params["active"] = "false"

        data = self._request(
            "soccerclubs",
            params
        )

        return self._as_list(data)

    def get_clubs(self, *args, **kwargs):
        return self.clubs(*args, **kwargs)

    def teams(self, *args, **kwargs):
        return self.clubs(*args, **kwargs)

    # --------------------------------------------------
    # PLAYERS / SQUADS
    # --------------------------------------------------

    def players(
        self,
        league: Optional[str] = None,
        team: Optional[str] = None,
        name: Optional[str] = None,
        player_id: Optional[str] = None,
        position: Optional[str] = None
    ):
        params = {}

        if league:
            params["league"] = league

        if team:
            params["team"] = team

        if name:
            params["name"] = name

        if player_id:
            params["player_id"] = player_id

        if position:
            params["position"] = position

        data = self._request(
            "soccerplayers",
            params
        )

        return self._as_list(data)

    def get_players(self, *args, **kwargs):
        return self.players(*args, **kwargs)

    def team_squad(
        self,
        team: str,
        league: Optional[str] = None
    ):
        return self.players(
            team=team,
            league=league
        )

    # --------------------------------------------------
    # LAYER 2 OPTIONAL DATA
    # --------------------------------------------------

    def fixture_statistics(self, fixture_id: Any):
        self.last_warning = (
            "API Ninjas does not currently provide detailed "
            "fixture statistics such as possession, shots and corners."
        )

        return []

    def get_fixture_statistics(self, fixture_id: Any):
        return self.fixture_statistics(fixture_id)

    def injuries(
        self,
        team: Optional[str] = None,
        fixture_id: Any = None
    ):
        self.last_warning = (
            "Injury reports are not available through the "
            "current API Ninjas football endpoints."
        )

        return []

    def get_injuries(self, *args, **kwargs):
        return self.injuries(*args, **kwargs)

    def fixture_lineups(self, fixture_id: Any):
        self.last_warning = (
            "Confirmed match lineups are not available through "
            "the current API Ninjas football endpoints."
        )

        return []

    def get_lineups(self, fixture_id: Any):
        return self.fixture_lineups(fixture_id)

    # --------------------------------------------------
    # CONNECTION TEST
    # --------------------------------------------------

    def test_connection(self):
        self._request(
            "soccermatches",
            {
                "league": "epl",
                "date": date.today().isoformat()
            }
        )

        return True

    # --------------------------------------------------
    # CLOSE CONNECTION
    # --------------------------------------------------

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
