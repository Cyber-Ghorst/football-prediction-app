
import requests
import streamlit as st


class APIFootballError(RuntimeError):
    """Raised when API-Football returns an error or request fails."""


class APIFootballClient:
    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key=None):
        self.api_key = api_key or self._get_api_key()

        if not self.api_key:
            raise APIFootballError(
                "API-Football key not found. "
                "Add API_FOOTBALL_KEY to Streamlit Secrets."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "x-apisports-key": self.api_key
        })

    @staticmethod
    def _get_api_key():
        try:
            return st.secrets["API_FOOTBALL_KEY"]
        except Exception:
            return None

    def get(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            raise APIFootballError(
                f"API request failed: {exc}"
            ) from exc

        except ValueError as exc:
            raise APIFootballError(
                "API returned an invalid JSON response."
            ) from exc

        errors = data.get("errors")

        if errors:
            raise APIFootballError(
                f"API-Football error: {errors}"
            )

        return data.get("response", [])

    def leagues(self, country=None, season=None):
        params = {}

        if country:
            params["country"] = country

        if season:
            params["season"] = season

        return self.get("leagues", params)

    def teams(self, league_id, season):
        return self.get(
            "teams",
            {
                "league": league_id,
                "season": season
            }
        )

    def standings(self, league_id, season):
        return self.get(
            "standings",
            {
                "league": league_id,
                "season": season
            }
        )

    def last_fixtures(self, team_id, season, count=10):
        return self.get(
            "fixtures",
            {
                "team": team_id,
                "season": season,
                "last": count
            }
        )

    def next_fixture(self, team_id, count=1):
        return self.get(
            "fixtures",
            {
                "team": team_id,
                "next": count
            }
        )

    def fixture_statistics(self, fixture_id):
        return self.get(
            "fixtures/statistics",
            {
                "fixture": fixture_id
            }
        )

    def injuries(self, fixture_id):
        return self.get(
            "injuries",
            {
                "fixture": fixture_id
            }
        )

    def fixture_lineups(self, fixture_id):
        return self.get(
            "fixtures/lineups",
            {
                "fixture": fixture_id
            }
        )
