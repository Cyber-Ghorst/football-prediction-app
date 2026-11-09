"""
API Ninjas Football API Client
Football Prediction App - Layer 2

Provider: https://api.api-ninjas.com/v1

Provider-specific imports:
    from api_ninjas import APINinjasClient, APINinjasError

Required secret:
    API_NINJAS_API_KEY
"""

import os
import requests

from datetime import date as Date, datetime, timedelta
from typing import Any, Dict, List, Optional


class APINinjasError(Exception):
    """Football API request error."""
    pass


class APINinjasClient:

    BASE_URL = "https://api.api-ninjas.com/v1"

    LEAGUES = [
        {"id": "epl", "name": "Premier League"},
        {"id": "laliga", "name": "La Liga"},
        {"id": "bundesliga", "name": "Bundesliga"},
        {"id": "seriea", "name": "Serie A"},
        {"id": "ligue1", "name": "Ligue 1"},
        {"id": "ucl", "name": "Champions League"},
        {"id": "uel", "name": "Europa League"},
        {"id": "mls", "name": "MLS"},
        {"id": "championship", "name": "EFL Championship"},
        {"id": "leagueone", "name": "EFL League One"},
        {"id": "leaguetwo", "name": "EFL League Two"},
        {"id": "scottishpremiership", "name": "Scottish Premiership"},
        {"id": "laliga2", "name": "La Liga 2"},
        {"id": "bundesliga2", "name": "2. Bundesliga"},
        {"id": "serieb", "name": "Serie B"},
        {"id": "ligue2", "name": "Ligue 2"},
        {"id": "eredivisie", "name": "Eredivisie"},
        {"id": "primeiraliga", "name": "Primeira Liga"},
        {"id": "superlig", "name": "Turkish Super Lig"},
        {"id": "belgianproleague", "name": "Belgian Pro League"},
        {"id": "greeksuperleague", "name": "Greek Super League"},
        {"id": "austrianbundesliga", "name": "Austrian Bundesliga"},
        {"id": "danishsuperliga", "name": "Danish Superliga"},
        {"id": "allsvenskan", "name": "Allsvenskan"},
        {"id": "eliteserien", "name": "Eliteserien"},
        {"id": "rpl", "name": "Russian Premier League"},
        {"id": "uecl", "name": "Conference League"},
        {"id": "brasileirao", "name": "Brasileirao"},
        {"id": "libertadores", "name": "Copa Libertadores"},
        {"id": "sudamericana", "name": "Copa Sudamericana"},
        {"id": "uslc", "name": "USL Championship"},
        {"id": "saudiproleague", "name": "Saudi Pro League"},
        {"id": "csl", "name": "Chinese Super League"},
        {"id": "isl", "name": "Indian Super League"},
        {"id": "aleague", "name": "A-League Men"},
        {"id": "acl", "name": "AFC Champions League Elite"},
        {"id": "cafcl", "name": "CAF Champions League"},
        {"id": "ligamx", "name": "Liga MX"},
        {"id": "ligaprofesional", "name": "Argentine Liga Profesional"},
        {"id": "j1league", "name": "J1 League"},
        {"id": "facup", "name": "FA Cup"},
        {"id": "eflcup", "name": "EFL Cup"},
        {"id": "copadelrey", "name": "Copa del Rey"},
        {"id": "dfbpokal", "name": "DFB-Pokal"},
        {"id": "coppaitalia", "name": "Coppa Italia"},
        {"id": "coupedefrance", "name": "Coupe de France"},
        {"id": "usopencup", "name": "U.S. Open Cup"},
        {"id": "leaguescup", "name": "Leagues Cup"},
        {"id": "concacafcc", "name": "CONCACAF Champions Cup"},
        {"id": "clubworldcup", "name": "FIFA Club World Cup"},
        {"id": "wsl", "name": "Women's Super League"},
        {"id": "ligaf", "name": "Liga F"},
        {"id": "premiereligue", "name": "Premiere Ligue"},
        {"id": "aleaguewomen", "name": "A-League Women"},
        {"id": "nsl", "name": "Northern Super League"},
        {"id": "uslsuperleague", "name": "USL Super League"},
        {"id": "uwcl", "name": "Women's Champions League"},
        {"id": "worldcup", "name": "World Cup"},
        {"id": "wcqeurope", "name": "World Cup Qualifying - Europe"},
        {"id": "wcqsouthamerica", "name": "World Cup Qualifying - South America"},
        {"id": "wcqnorthamerica", "name": "World Cup Qualifying - North America"},
        {"id": "wcqasia", "name": "World Cup Qualifying - Asia"},
        {"id": "wcqafrica", "name": "World Cup Qualifying - Africa"},
        {"id": "nationsleague", "name": "UEFA Nations League"},
        {"id": "euro", "name": "Euro"},
        {"id": "euroqualifying", "name": "Euro Qualifying"},
        {"id": "copaamerica", "name": "Copa America"},
        {"id": "afcon", "name": "Africa Cup of Nations"},
        {"id": "asiancup", "name": "Asian Cup"},
        {"id": "goldcup", "name": "Gold Cup"},
        {"id": "concacafnationsleague", "name": "CONCACAF Nations League"},
        {"id": "friendlies", "name": "International Friendlies"},
        {"id": "womensworldcup", "name": "Women's World Cup"},
        {"id": "womenseuro", "name": "Women's Euro"},
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
        if isinstance(self.api_key, str):
            self.api_key = self.api_key.strip()

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
            raise APINinjasError(
                "API key missing. Configure API_NINJAS_API_KEY "
                "in Streamlit Secrets."
            )

        self.timeout = timeout
        self.last_warning = None
        self.last_metadata: Dict[str, Any] = {}

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

            self.last_metadata = {
                "http_status": response.status_code,
                "requests_limit": response.headers.get("X-RateLimit-Limit"),
                "requests_remaining": response.headers.get("X-RateLimit-Remaining"),
            }
            response.raise_for_status()

            return response.json()

        except requests.RequestException as exc:
            raise APINinjasError(
                f"Football API request failed: {exc}"
            ) from exc

        except ValueError as exc:
            raise APINinjasError(
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

            if isinstance(date, Date):
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
            raise APINinjasError(
                "League identifier is required."
            )

        if isinstance(date_from, datetime):
            start_date = date_from.date()

        elif isinstance(date_from, Date):
            start_date = date_from

        elif date_from:
            start_date = date.fromisoformat(str(date_from))

        else:
            start_date = Date.today()

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
            raise APINinjasError(
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
            raise APINinjasError("Game ID is required.")

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
            raise APINinjasError(
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
                "date": Date.today().isoformat()
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
