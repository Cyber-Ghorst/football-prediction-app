 
"""
API Ninjas Football API Client
Football Prediction App - Layer 2

Compatible class names:
    APIFootballClient
    APIFootballError

API provider:
    https://api.api-ninjas.com

Environment variable:
    API_NINJAS_API_KEY
"""

import os
import requests

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


class APIFootballError(Exception):
    """Raised when API Ninjas requests fail."""
    pass


class APIFootballClient:

    BASE_URL = "https://api.api-ninjas.com/v1"

    # Competitions supported by API Ninjas
    LEAGUES = [
        "epl",
        "laliga",
        "bundesliga",
        "seriea",
        "ligue1",
        "ucl",
        "uel",
        "uecl",
        "mls",
        "championship",
        "leagueone",
        "leaguetwo",
        "scottishpremiership",
        "eredivisie",
        "primeiraliga",
        "superlig",
        "belgianproleague",
        "greeksuperleague",
        "saudiproleague",
        "brasileirao",
        "ligamx",
        "afcon",
        "worldcup",
        "friendlies",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_key = (
            api_key
            or os.getenv("API_NINJAS_API_KEY")
            or os.getenv("API_NINJAS_KEY")
        )

        if not self.api_key:
            raise APIFootballError(
                "API Ninjas API key is missing. "
                "Set API_NINJAS_API_KEY in your environment."
            )

        self.timeout = timeout

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
    ) -> List[Dict[str, Any]]:

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout
            )

            if response.status_code == 401:
                raise APIFootballError(
                    "Invalid API Ninjas API key."
                )

            if response.status_code == 403:
                raise APIFootballError(
                    "API access denied. Check your subscription."
                )

            if response.status_code == 429:
                raise APIFootballError(
                    "API request limit exceeded. "
                    "Check your API Ninjas quota."
                )

            response.raise_for_status()

            data = response.json()

            if isinstance(data, list):
                return data

            if isinstance(data, dict):
                if "error" in data:
                    raise APIFootballError(str(data["error"]))

                return [data]

            raise APIFootballError(
                "Unexpected API response format."
            )

        except requests.exceptions.Timeout:
            raise APIFootballError(
                "API Ninjas request timed out."
            )

        except requests.exceptions.ConnectionError:
            raise APIFootballError(
                "Unable to connect to API Ninjas."
            )

        except requests.exceptions.HTTPError as exc:
            message = ""

            if exc.response is not None:
                message = exc.response.text[:500]

            raise APIFootballError(
                f"API HTTP error: {exc}. {message}"
            )

        except ValueError:
            raise APIFootballError(
                "API Ninjas returned invalid JSON."
            )

    # --------------------------------------------------
    # LEAGUES
    # --------------------------------------------------

    def leagues(self, season=None):
    """
    Return league objects compatible with app.py.
    """

    return [
        {
            "id": league,
            "name": league.upper(),
            "code": league
        }
        for league in self.LEAGUES
    ]

    def get_leagues(self, season=None):
        return self.leagues(season)
    # --------------------------------------------------
    # MATCHES / FIXTURES
    # --------------------------------------------------

    def matches(
        self,
        league: Optional[str] = None,
        date: Optional[str] = None,
        team: Optional[str] = None,
        season: Optional[int] = None,
        status: Optional[str] = None,
        game_id: Optional[str] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve fixtures, live scores and completed matches.

        Supply at least one of:
            league, team or game_id.

        Date format: YYYY-MM-DD
        """

        params = {}

        if league:
            params["league"] = league

        if date:
            params["date"] = date

        if team:
            params["team"] = team

        if season is not None:
            params["season"] = season

        if status:
            params["status"] = status

        if game_id:
            params["game_id"] = game_id

        if offset:
            params["offset"] = offset

        if not any([league, team, game_id]):
            raise APIFootballError(
                "A league, team or game_id is required."
            )

        return self._request(
            "soccermatches",
            params
        )

    def get_matches(self, **kwargs):
        return self.matches(**kwargs)

    # --------------------------------------------------
    # UPCOMING MATCHES
    # --------------------------------------------------

    def upcoming_matches(
        self,
        league: str = "epl",
        days: int = 7,
        date_from: Optional[str] = None,
        season: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve upcoming fixtures across a date range.

        Requests each date separately because the API's
        date parameter returns matches for one match day.
        """

        if days < 1 or days > 31:
            raise APIFootballError(
                "Days must be between 1 and 31."
            )

        if date_from:
            try:
                start = datetime.strptime(
                    date_from, "%Y-%m-%d"
                ).date()
            except ValueError:
                raise APIFootballError(
                    "date_from must use YYYY-MM-DD format."
                )
        else:
            start = date.today()

        all_matches = []

        for day_number in range(days):

            match_date = (
                start + timedelta(days=day_number)
            ).isoformat()

            results = self.matches(
                league=league,
                date=match_date,
                season=season
            )

            all_matches.extend(results)

        # Remove duplicate games
        unique_matches = {}

        for match in all_matches:
            game_id = match.get("game_id")

            if game_id:
                unique_matches[game_id] = match

        return sorted(
            unique_matches.values(),
            key=lambda match: match.get("start_time", "")
        )

    # --------------------------------------------------
    # TEAM MATCH HISTORY
    # --------------------------------------------------

    def team_matches(
        self,
        team: str,
        season: Optional[int] = None,
        league: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        if not team:
            raise APIFootballError(
                "Team identifier is required."
            )

        matches = self.matches(
            team=team,
            season=season
        )

        if league:
            matches = [
                match for match in matches
                if match.get("league") == league
            ]

        return sorted(
            matches,
            key=lambda match: match.get("start_time", "")
        )

    def get_team_matches(self, team, season=None):
        return self.team_matches(
            team=team,
            season=season
        )

    # --------------------------------------------------
    # SINGLE MATCH
    # --------------------------------------------------

    def match_details(
        self,
        game_id: str
    ) -> Optional[Dict[str, Any]]:

        if not game_id:
            raise APIFootballError(
                "Game ID is required."
            )

        results = self.matches(
            game_id=game_id
        )

        return results[0] if results else None

    # --------------------------------------------------
    # LEAGUE STANDINGS
    # --------------------------------------------------

    def standings(
        self,
        league: str,
        season: Optional[int] = None,
        tournament: Optional[str] = None,
        conference: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        if not league:
            raise APIFootballError(
                "League is required for standings."
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

        return self._request(
            "soccerstandings",
            params
        )

    def get_standings(self, league, season=None):
        return self.standings(
            league=league,
            season=season
        )

    # --------------------------------------------------
    # CLUBS / TEAMS
    # --------------------------------------------------

    def clubs(
        self,
        league: Optional[str] = None,
        team: Optional[str] = None,
        active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:

        params = {}

        if league:
            params["league"] = league

        if team:
            params["team"] = team

        if active is not None:
            params["active"] = str(active).lower()

        return self._request(
            "soccerclubs",
            params
        )

    def get_clubs(self, league=None, team=None):
        return self.clubs(
            league=league,
            team=team
        )

    # --------------------------------------------------
    # PLAYERS / SQUADS
    # --------------------------------------------------

    def players(
        self,
        league: Optional[str] = None,
        team: Optional[str] = None,
        name: Optional[str] = None,
        player_id: Optional[str] = None,
        position: Optional[str] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:

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

        if offset:
            params["offset"] = offset

        if not any([team, name, player_id]):
            raise APIFootballError(
                "Provide a team, player name or player_id."
            )

        return self._request(
            "soccerplayers",
            params
        )

    def get_players(self, **kwargs):
        return self.players(**kwargs)

    def team_squad(
        self,
        team: str,
        league: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        return self.players(
            team=team,
            league=league
        )

    # --------------------------------------------------
    # CONNECTION TEST
    # --------------------------------------------------

    def test_connection(self) -> bool:
        """
        Tests the API connection using the clubs endpoint.
        """

        try:
            self.clubs(
                league="epl"
            )
            return True

        except APIFootballError:
            return False

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    def close(self):
        self.session.close()
