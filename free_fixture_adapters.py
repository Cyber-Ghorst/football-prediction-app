"""Read-only adapters for selected future-fixture observation sources.

These adapters produce source observations only. They do not write canonical
fixtures or activate provider routing. Every result must pass the application's
canonical crosswalk, freshness, licensing and persistence gates first.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


class FreeFixtureProviderError(RuntimeError):
    """Safe provider error; never includes credentials or request headers."""


@dataclass(frozen=True)
class FixtureObservation:
    provider: str
    provider_fixture_id: str
    competition_key: str | None
    competition_name: str | None
    season_key: str | None
    season_name: str | None
    home_team_key: str | None
    away_team_key: str | None
    home_team_name: str
    away_team_name: str
    kickoff_utc: str | None
    status: str
    fetched_at: str
    source_url: str
    licence: str
    raw_payload: dict[str, Any]
    eligible_for_review: bool
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_aware_datetime(value: Any) -> datetime | None:
    """Accept only precise timestamps carrying an explicit UTC offset."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = (value.get("name") or value.get("teamName") or value.get("TeamName")
                     or value.get("displayName") or value.get("title"))
    return str(value).strip() if value is not None else ""


def _normalise_openligadb_competition_name(value: Any) -> str:
    name = _text(value)
    name = re.sub(r"\s*\((?:Herren|Men)\)$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s+20\d{2}(?:\s*/\s*(?:20)?\d{2})?$", "", name).strip()
    aliases = {
        "1. Fußball-Bundesliga": "Bundesliga",
        "1. Fussball-Bundesliga": "Bundesliga",
        "2. Fußball-Bundesliga": "2. Bundesliga",
        "2. Fussball-Bundesliga": "2. Bundesliga",
        "Champions League": "UEFA Champions League",
    }
    return aliases.get(name, name)


def _stable_dataset_id(provider: str, competition: str, season: str,
                       kickoff: str, home: str, away: str) -> str:
    material = "|".join((provider, competition, season, kickoff, home.casefold(), away.casefold()))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"{provider}:dataset:{digest}"


def _observation(
    provider: str,
    row: Mapping[str, Any],
    *,
    fetched_at: datetime,
    source_url: str,
    licence: str,
    fixture_id: Any = None,
    competition: Any = None,
    competition_name: Any = None,
    season: Any = None,
    season_name: Any = None,
    home: Any = None,
    away: Any = None,
    home_id: Any = None,
    away_id: Any = None,
    kickoff: Any = None,
    status: Any = "scheduled",
    allow_date_only: bool = False,
) -> FixtureObservation:
    home_name, away_name = _text(home), _text(away)
    competition_key, season_key = _text(competition), _text(season)
    competition_display = _text(competition_name) or competition_key
    season_display = _text(season_name) or season_key
    parsed = _parse_aware_datetime(kickoff)
    status_text = _text(status).casefold().replace("_", " ")
    if status_text.startswith("status "):
        status_text = status_text.removeprefix("status ").strip()
    scheduled = status_text in {
        "scheduled", "not started", "not-started", "ns", "upcoming", "fixture"
    }
    reason = None
    if not home_name or not away_name or home_name.casefold() == away_name.casefold():
        reason = "missing_or_invalid_team_identity"
    elif not competition_key or not season_key:
        reason = "missing_competition_or_season_identity"
    elif not scheduled:
        reason = "not_scheduled"
    elif parsed is None:
        reason = "kickoff_missing_timezone_or_precision"
    elif parsed <= fetched_at:
        reason = "kickoff_not_in_future"
    if fixture_id is None or not str(fixture_id).strip():
        if home_name and away_name and competition_key and season_key:
            source_kickoff = parsed.isoformat() if parsed is not None else str(kickoff or "date-unknown")
            fixture_id = _stable_dataset_id(
                provider, competition_key, season_key, source_kickoff, home_name, away_name
            )
        else:
            fixture_id = f"{provider}:unidentified"
            reason = reason or "missing_stable_fixture_identity"
    return FixtureObservation(
        provider=provider,
        provider_fixture_id=str(fixture_id),
        competition_key=competition_key or None,
        competition_name=competition_display or None,
        season_key=season_key or None,
        season_name=season_display or None,
        home_team_key=str(home_id) if home_id is not None else None,
        away_team_key=str(away_id) if away_id is not None else None,
        home_team_name=home_name,
        away_team_name=away_name,
        kickoff_utc=parsed.isoformat().replace("+00:00", "Z") if parsed else None,
        status=status_text or "unknown",
        fetched_at=fetched_at.isoformat().replace("+00:00", "Z"),
        source_url=source_url,
        licence=licence,
        raw_payload=dict(row),
        eligible_for_review=reason is None,
        exclusion_reason=reason,
    )


class _HttpAdapter:
    provider = "unknown"
    default_timeout = 20

    def __init__(self, *, session: requests.Session | None = None, timeout: int = 20):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.setdefault("User-Agent", "football-prediction-app/1.0")
        self.session.headers.setdefault("Accept", "application/json")

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None) -> Any:
        try:
            response = self.session.get(
                url, params=params or {}, headers=headers or {}, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise FreeFixtureProviderError(f"{self.provider} request timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise FreeFixtureProviderError(
                f"{self.provider} request failed{suffix}."
            ) from exc
        except ValueError as exc:
            raise FreeFixtureProviderError(f"{self.provider} returned invalid JSON.") from exc

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class OpenLigaDBAdapter(_HttpAdapter):
    """OpenLigaDB season endpoint; competition shortcut and season are explicit."""
    provider = "openligadb"
    BASE_URL = "https://api.openligadb.de"

    def available_leagues(self, season: int | None = None) -> list[dict[str, Any]]:
        suffix = f"/{int(season)}" if season is not None else ""
        payload = self._get_json(f"{self.BASE_URL}/getavailableleagues{suffix}")
        if not isinstance(payload, list):
            raise FreeFixtureProviderError("OpenLigaDB league catalogue response is not an array.")
        return [row for row in payload if isinstance(row, dict)]

    def discover_scopes(self, seasons: Iterable[int], *, max_scopes: int = 120) -> list[dict[str, Any]]:
        scopes: dict[tuple[str, int], dict[str, Any]] = {}
        for season in seasons:
            for league in self.available_leagues(int(season)):
                sport = league.get("sport") if isinstance(league.get("sport"), Mapping) else {}
                sport_name = _text(sport.get("sportName") or sport.get("name")).casefold()
                if sport_name and not any(
                    token in sport_name for token in ("football", "soccer", "fußball", "fussball")
                ):
                    continue
                shortcut = _text(league.get("leagueShortcut"))
                league_season = league.get("leagueSeason") or season
                if not shortcut or not str(league_season).isdigit():
                    continue
                key = (shortcut, int(league_season))
                scopes[key] = {
                    "league_shortcut": shortcut,
                    "season": int(league_season),
                    "provider_competition_id": league.get("leagueId"),
                    "competition_name": league.get("leagueName") or shortcut,
                    "country": league.get("leagueCountry") or league.get("country") or league.get("countryName"),
                    "country_code": league.get("countryCode") or league.get("country_code"),
                }
        return list(scopes.values())[:max(1, int(max_scopes))]

    def matches(
        self, league_shortcut: str, season: int,
        *, league_metadata: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not league_shortcut.strip() or int(season) < 1900:
            raise ValueError("A league shortcut and valid season are required.")
        url = f"{self.BASE_URL}/getmatchdata/{quote(league_shortcut, safe='')}/{int(season)}"
        payload = self._get_json(url)
        if not isinstance(payload, list):
            raise FreeFixtureProviderError("OpenLigaDB match response is not an array.")
        fetched = _utc_now()
        output = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            match_date = row.get("matchDateTimeUTC") or row.get("MatchDateTimeUTC")
            # OpenLigaDB's field is explicitly UTC; append Z only to its documented
            # UTC timestamp when it is supplied without an offset.
            if isinstance(match_date, str) and "T" in match_date and not (
                match_date.endswith("Z") or "+" in match_date[10:] or "-" in match_date[10:]
            ):
                match_date += "Z"
            team1 = row.get("team1") or row.get("Team1") or {}
            team2 = row.get("team2") or row.get("Team2") or {}
            metadata = league_metadata if isinstance(league_metadata, Mapping) else {}
            country = _text(
                metadata.get("country") or metadata.get("leagueCountry")
                or metadata.get("country_name") or row.get("leagueCountry")
                or row.get("LeagueCountry")
            ) or None
            competition_id = (
                row.get("leagueId") or row.get("LeagueId")
                or metadata.get("provider_competition_id")
                or row.get("leagueShortcut") or row.get("LeagueShortcut") or league_shortcut
            )
            competition_name = (
                metadata.get("competition_name") or row.get("leagueName")
                or row.get("LeagueName") or league_shortcut
            )
            raw_row = dict(row)
            if country:
                raw_row["country"] = country
                raw_row["leagueCountry"] = country
            raw_row["league"] = {
                "id": competition_id, "name": competition_name, "country": country,
            }
            output.append(_observation(
                self.provider, raw_row, fetched_at=fetched, source_url=url,
                licence="OpenLigaDB public API; reuse terms require separate review",
                fixture_id=row.get("matchID") or row.get("MatchID"),
                competition=competition_id,
                competition_name=_normalise_openligadb_competition_name(competition_name),
                season=(row.get("leagueSeason") or row.get("LeagueSeason") or metadata.get("season") or season),
                season_name=str(row.get("leagueSeason") or row.get("LeagueSeason") or metadata.get("season") or season),
                home=team1, away=team2,
                home_id=team1.get("teamId") if isinstance(team1, dict) else None,
                away_id=team2.get("teamId") if isinstance(team2, dict) else None,
                kickoff=match_date,
                status=("finished" if row.get("matchIsFinished") is True else (row.get("matchStatus") or row.get("MatchStatus") or "scheduled")),
            ).to_dict())
        return output


class _StaticDatasetAdapter(_HttpAdapter):
    def _get_text(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.Timeout as exc:
            raise FreeFixtureProviderError(f"{self.provider} download timed out.") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            raise FreeFixtureProviderError(f"{self.provider} download failed{suffix}.") from exc


class OpenFootballAdapter(_StaticDatasetAdapter):
    """Parse football.json schedules; date-only and timezone-less rows stay excluded."""
    provider = "openfootball"
    BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"

    COMPETITION_NAMES = {
        "en.1": "Premier League",
        "en.2": "Championship",
        "de.1": "Bundesliga",
        "de.2": "2. Bundesliga",
        "es.1": "La Liga",
        "it.1": "Serie A",
        "fr.1": "Ligue 1",
        "nl.1": "Eredivisie",
        "pt.1": "Primeira Liga",
        "us.1": "Major League Soccer",
    }

    COUNTRY_NAMES = {
        "en": "England", "eng": "England", "de": "Germany", "es": "Spain", "it": "Italy",
        "fr": "France", "nl": "Netherlands", "pt": "Portugal", "us": "United States",
    }

    def discover_season_files(self, season: str) -> list[dict[str, str]]:
        season_value = str(season or "").strip()
        if not re.fullmatch(r"20\d{2}-\d{2}", season_value):
            raise ValueError("season must use the YYYY-YY football.json directory format.")
        url = f"https://api.github.com/repos/openfootball/football.json/contents/{quote(season_value, safe='')}"
        payload = self._get_json(url, headers={"Accept": "application/vnd.github+json"})
        if not isinstance(payload, list):
            raise FreeFixtureProviderError("OpenFootball season directory response is not an array.")
        datasets = []
        for item in payload:
            if not isinstance(item, dict) or item.get("type") != "file":
                continue
            filename = str(item.get("name") or "")
            if not filename.endswith(".json"):
                continue
            code = filename.removesuffix(".json")
            datasets.append({
                "season_file": f"{season_value}/{filename}",
                "competition": self.COMPETITION_NAMES.get(code, code),
            })
        return sorted(datasets, key=lambda row: row["season_file"])

    @staticmethod
    def _kickoff(date_value: str, time_value: str, row: Mapping[str, Any]) -> Any:
        if not date_value:
            return None
        if not time_value:
            return date_value
        combined = f"{date_value}T{time_value}"
        try:
            parsed = datetime.fromisoformat(combined.replace("Z", "+00:00"))
        except ValueError:
            return combined
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.isoformat()
        zone_value = (
            row.get("timezone") or row.get("time_zone") or row.get("timeZone")
            or row.get("tz") or row.get("utc_offset")
        )
        if not zone_value:
            return combined
        zone_text = str(zone_value).strip()
        if zone_text.casefold() in {"utc", "gmt", "z"}:
            zone = timezone.utc
        else:
            offset = re.fullmatch(
                r"(?:UTC|GMT)?([+-])(\d{1,2})(?::?(\d{2}))?",
                zone_text, flags=re.IGNORECASE,
            )
            if offset:
                hours = int(offset.group(2))
                minutes = int(offset.group(3) or 0)
                delta = timedelta(hours=hours, minutes=minutes)
                zone = timezone(delta if offset.group(1) == "+" else -delta)
            else:
                try:
                    zone = ZoneInfo(zone_text)
                except ZoneInfoNotFoundError:
                    return combined
        return parsed.replace(tzinfo=zone).astimezone(timezone.utc).isoformat()

    def season(self, season_file: str, competition: str) -> list[dict[str, Any]]:
        if not season_file.endswith(".json") or season_file.startswith("/") or ".." in season_file.split("/"):
            raise ValueError("season_file must be a safe JSON path within the dataset.")
        url = f"{self.BASE_URL}/{quote(season_file, safe='/')}"
        payload = self._get_json(url)
        rows = payload.get("matches") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise FreeFixtureProviderError("OpenFootball dataset has no matches array.")
        fetched = _utc_now()
        output = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            date_value = str(row.get("date") or "")
            time_value = str(row.get("time") or "")
            kickoff = self._kickoff(date_value, time_value, row)
            filename = season_file.rsplit("/", 1)[-1].removesuffix(".json")
            code = next(
                (key.split(".", 1)[0] for key, name in self.COMPETITION_NAMES.items()
                 if name == competition and filename == key),
                filename.split(".", 1)[0],
            )
            country = self.COUNTRY_NAMES.get(code)
            raw_row = dict(row)
            if country:
                raw_row["country"] = country
                raw_row["league"] = {"name": competition, "country": country}
            output.append(_observation(
                self.provider, raw_row, fetched_at=fetched, source_url=url,
                licence="CC0-1.0 (football.json dataset; verify upstream source provenance)",
                competition=season_file.rsplit("/", 1)[-1].removesuffix(".json"),
                competition_name=competition,
                season=(season_file.split("/", 1)[0] if "/" in season_file else season_file.removesuffix(".json")),
                season_name=(season_file.split("/", 1)[0] if "/" in season_file else season_file.removesuffix(".json")),
                home=row.get("team1") or row.get("home"), away=row.get("team2") or row.get("away"),
                kickoff=kickoff,
                status=row.get("status") or "scheduled",
            ).to_dict())
        return output


class OpenMatchdayAdapter(_StaticDatasetAdapter):
    """Parse an explicitly supplied Open Matchday season CSV without guessing timezone."""
    provider = "open_matchday"
    DEFAULT_BASE_URL = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master"

    def season_csv(self, csv_url: str, *, competition: str, season: str) -> list[dict[str, Any]]:
        if not csv_url.startswith("https://raw.githubusercontent.com/oladeeayo/open-matchday/"):
            raise ValueError("Only the documented Open Matchday raw GitHub dataset URL is accepted.")
        raw = self._get_text(csv_url)
        reader = csv.DictReader(io.StringIO(raw))
        if not reader.fieldnames:
            raise FreeFixtureProviderError("Open Matchday CSV has no header.")
        fetched = _utc_now()
        output = []
        for row in reader:
            if not row:
                continue
            lowered = {str(k).strip().casefold(): v for k, v in row.items() if k}
            date_value = lowered.get("date") or lowered.get("match_date") or ""
            time_value = lowered.get("time") or lowered.get("kickoff") or ""
            # DATA_DICTIONARY.md defines time as fixed CET-1 (UTC+1), not a
            # daylight-saving-aware local timezone. Convert that documented
            # fixed offset explicitly to UTC; date-only rows remain ineligible.
            kickoff = date_value
            if date_value and time_value:
                try:
                    source_local = datetime.strptime(
                        f"{date_value} {time_value}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone(timedelta(hours=1)))
                    kickoff = source_local.astimezone(timezone.utc).isoformat()
                except ValueError:
                    kickoff = f"{date_value}T{time_value}"
            output.append(_observation(
                self.provider, row, fetched_at=fetched, source_url=csv_url,
                licence="Open Matchday non-commercial-only; upstream rights must be reviewed",
                fixture_id=lowered.get("match_id") or lowered.get("fixture_id"),
                competition=lowered.get("competition_id") or lowered.get("league_id") or csv_url.rstrip("/").split("/")[-2],
                competition_name=lowered.get("competition") or lowered.get("league") or competition,
                season=lowered.get("season_id") or lowered.get("season") or season,
                season_name=lowered.get("season") or season,
                home=lowered.get("home_team") or lowered.get("home") or lowered.get("team1"),
                away=lowered.get("away_team") or lowered.get("away") or lowered.get("team2"),
                kickoff=kickoff,
                status=lowered.get("status") or "scheduled",
            ).to_dict())
        return output


class BzzoiroAdapter(_HttpAdapter):
    """Bzzoiro v2 upcoming-events adapter using the documented events endpoint."""
    provider = "bzzoiro"
    BASE_URL = "https://sports.bzzoiro.com/api/v2/events/"

    def __init__(self, *, token: str | None = None, endpoint: str | None = None,
                 session: requests.Session | None = None, timeout: int = 20):
        super().__init__(session=session, timeout=timeout)
        self.token = token or os.getenv("BZZOIRO_API_TOKEN")
        self.endpoint = endpoint or os.getenv("BZZOIRO_FIXTURES_URL") or self.BASE_URL
        if not self.token:
            raise FreeFixtureProviderError("Bzzoiro requires BZZOIRO_API_TOKEN.")
        if not self.endpoint.startswith("https://sports.bzzoiro.com/"):
            raise FreeFixtureProviderError("BZZOIRO_FIXTURES_URL must use the documented BSD API host.")

    def event(self, event_id: str | int) -> dict[str, Any]:
        """Fetch one event detail for post-match verification."""
        identifier = str(event_id or "").strip()
        if not identifier or not identifier.isdigit():
            raise ValueError("Bzzoiro event ID must be numeric.")
        headers = {"Authorization": f"Token {self.token}"}
        payload = self._get_json(
            f"{self.endpoint.rstrip('/')}/{quote(identifier, safe='')}/",
            headers=headers,
        )
        if not isinstance(payload, dict):
            raise FreeFixtureProviderError("Bzzoiro event detail returned an unexpected schema.")
        event = payload.get("event") or payload.get("result") or payload.get("data") or payload
        if not isinstance(event, dict):
            raise FreeFixtureProviderError("Bzzoiro event detail has no event object.")
        return event

    def upcoming(self, *, params: dict[str, Any] | None = None,
                 max_pages: int = 20) -> list[dict[str, Any]]:
        query = {"status": "upcoming", "limit": 200, "offset": 0, **(params or {})}
        headers = {"Authorization": f"Token {self.token}"}
        fetched = _utc_now()
        output = []
        for _ in range(max(1, int(max_pages))):
            payload = self._get_json(self.endpoint, params=query, headers=headers)
            rows = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise FreeFixtureProviderError("Bzzoiro response has no results array.")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
                season = row.get("season") if isinstance(row.get("season"), Mapping) else {}
                home = row.get("home_team") or row.get("home") or row.get("home_team_name")
                away = row.get("away_team") or row.get("away") or row.get("away_team_name")
                output.append(_observation(
                    self.provider, row, fetched_at=fetched, source_url=self.endpoint,
                    licence="Bzzoiro API licence; app display/derived outputs only, no raw-feed redistribution",
                    fixture_id=row.get("id") or row.get("event_id") or row.get("fixture_id"),
                    competition=row.get("league_id") or league.get("id") or row.get("competition_id"),
                    competition_name=league.get("name") or row.get("competition") or row.get("league_name"),
                    season=row.get("season_id") or season.get("id") or row.get("season"),
                    season_name=season.get("name") or season.get("year") or row.get("season_name") or row.get("season_id"),
                    home=home, away=away,
                    home_id=(home.get("id") if isinstance(home, Mapping) else row.get("home_team_id")),
                    away_id=(away.get("id") if isinstance(away, Mapping) else row.get("away_team_id")),
                    kickoff=row.get("event_date") or row.get("date") or row.get("kickoff"),
                    status=row.get("status") or "unknown",
                ).to_dict())
            if not payload.get("next") or not rows:
                break
            query["offset"] = int(query.get("offset", 0)) + len(rows)
        return output


def normalize_livescore_football_events(
    events: Iterable[Mapping[str, Any]],
    *,
    league_key: str,
    source_url: str,
    league_metadata: Mapping[str, Any] | None = None,
    fetched_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize LiveScoreFootball events while requiring event-level identities."""
    fetched = fetched_at or _utc_now()
    output = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions and isinstance(competitions[0], Mapping) else {}
        competitors = competition.get("competitors") or []
        home = away = None
        for competitor in competitors:
            if not isinstance(competitor, Mapping):
                continue
            side = str(competitor.get("homeAway") or competitor.get("home_away") or "").casefold()
            team = competitor.get("team") if isinstance(competitor.get("team"), Mapping) else competitor
            if side == "home":
                home = team
            elif side == "away":
                away = team
        status = event.get("status") if isinstance(event.get("status"), Mapping) else {}
        status_type = status.get("type") if isinstance(status.get("type"), Mapping) else {}
        status_value = status_type.get("name") or status.get("display") or event.get("status") or "unknown"
        season = event.get("season") if isinstance(event.get("season"), Mapping) else {}
        metadata = league_metadata if isinstance(league_metadata, Mapping) else {}
        league_name = (
            metadata.get("name") or metadata.get("leagueName")
            or competition.get("name") or league_key
        )
        country_value = metadata.get("country") or metadata.get("country_name")
        country = _text(country_value) or None
        raw_event = dict(event)
        if country:
            raw_event["country"] = country
        raw_event["league"] = {
            "id": metadata.get("id") or competition.get("id") or league_key,
            "name": league_name,
            "country": country,
        }
        output.append(_observation(
            "livescore_football", raw_event, fetched_at=fetched, source_url=source_url,
            licence="LiveScoreFootball public API; upstream snapshot freshness and reuse terms require review",
            fixture_id=event.get("id") or event.get("uid"),
            competition=metadata.get("id") or competition.get("id") or league_key,
            competition_name=league_name,
            season=event.get("season_id") or season.get("id") or season.get("year"),
            season_name=season.get("name") or season.get("year") or event.get("season_id"),
            home=home, away=away,
            home_id=home.get("id") if isinstance(home, Mapping) else None,
            away_id=away.get("id") if isinstance(away, Mapping) else None,
            kickoff=event.get("date") or event.get("startDate") or event.get("start_date"),
            status=status_value,
        ).to_dict())
    return output


API_NINJAS_FREE_LEAGUES = (
    "epl", "laliga", "bundesliga", "seriea", "ligue1", "ucl", "uel", "mls",
)

API_NINJAS_LEAGUE_NAMES = {
    "epl": "Premier League", "laliga": "La Liga", "bundesliga": "Bundesliga",
    "seriea": "Serie A", "ligue1": "Ligue 1", "ucl": "Champions League",
    "uel": "Europa League", "mls": "MLS",
}

API_NINJAS_LEAGUE_COUNTRIES = {
    "epl": "England", "laliga": "Spain", "bundesliga": "Germany",
    "seriea": "Italy", "ligue1": "France", "ucl": "Europe",
    "uel": "Europe", "mls": "United States and Canada",
}


def _require_stable_provider_identity(
    observation: dict[str, Any],
    *,
    fixture_id: Any,
    home_id: Any,
    away_id: Any,
) -> dict[str, Any]:
    """Fail closed when a provider omits its documented stable match/team IDs."""
    if fixture_id is None or not str(fixture_id).strip():
        observation["eligible_for_review"] = False
        observation["exclusion_reason"] = "missing_stable_fixture_id"
    elif home_id is None or away_id is None:
        observation["eligible_for_review"] = False
        observation["exclusion_reason"] = "missing_stable_team_ids"
    return observation


def normalize_highlightly_matches(
    rows: Iterable[Mapping[str, Any]],
    *,
    fetched_at: datetime | None = None,
    source_url: str = "https://soccer.highlightly.net/matches",
) -> list[dict[str, Any]]:
    """Normalize Highlightly scheduled matches with explicit IDs and UTC kickoffs."""
    fetched = fetched_at or _utc_now()
    output = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        league = row.get("league") if isinstance(row.get("league"), Mapping) else {}
        home = row.get("homeTeam") if isinstance(row.get("homeTeam"), Mapping) else {}
        away = row.get("awayTeam") if isinstance(row.get("awayTeam"), Mapping) else {}
        state = row.get("state") if isinstance(row.get("state"), Mapping) else {}
        fixture_id = row.get("id") or row.get("matchId")
        home_id = home.get("id")
        away_id = away.get("id")
        season = league.get("season") or row.get("season")
        output.append(_require_stable_provider_identity(
            _observation(
                "highlightly", dict(row), fetched_at=fetched, source_url=source_url,
                licence="Highlightly API; subscription plan, reuse and commercial terms require review",
                fixture_id=fixture_id,
                competition=league.get("id") or row.get("leagueId"),
                competition_name=league.get("name") or row.get("leagueName"),
                season=season,
                season_name=str(season) if season is not None else None,
                home=home, away=away, home_id=home_id, away_id=away_id,
                kickoff=row.get("date") or row.get("startTime"),
                status=state.get("description") or row.get("status") or "unknown",
            ).to_dict(),
            fixture_id=fixture_id, home_id=home_id, away_id=away_id,
        ))
    return output


def normalize_api_ninjas_matches(
    rows: Iterable[Mapping[str, Any]],
    *,
    league: str,
    season: int | str,
    fetched_at: datetime | None = None,
    source_url: str = "https://api.api-ninjas.com/v1/soccermatches",
) -> list[dict[str, Any]]:
    """Normalize API Ninjas scheduled matches using its stable game/team IDs."""
    league_key = str(league or "").strip().casefold()
    league_name = API_NINJAS_LEAGUE_NAMES.get(league_key, league_key)
    country = API_NINJAS_LEAGUE_COUNTRIES.get(league_key)
    fetched = fetched_at or _utc_now()
    output = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        home = row.get("home_team") if isinstance(row.get("home_team"), Mapping) else {}
        away = row.get("away_team") if isinstance(row.get("away_team"), Mapping) else {}
        fixture_id = row.get("game_id") or row.get("fixture_id") or row.get("id")
        home_id = home.get("team_id") or home.get("id")
        away_id = away.get("team_id") or away.get("id")
        raw_row = dict(row)
        if country and not raw_row.get("country"):
            raw_row["country"] = country
        raw_row["league"] = {
            "id": league_key,
            "name": league_name,
            "country": country,
        }
        row_season = row.get("season") or season
        observation = _require_stable_provider_identity(
            _observation(
                "api_ninjas", raw_row, fetched_at=fetched, source_url=source_url,
                licence="API Ninjas; free plan is non-commercial and current-season only",
                fixture_id=fixture_id,
                competition=league_key,
                competition_name=league_name,
                season=row_season,
                season_name=row.get("season_label") or str(row_season),
                home=home or row.get("home_team_name"),
                away=away or row.get("away_team_name"),
                home_id=home_id, away_id=away_id,
                kickoff=row.get("start_time"),
                status=row.get("status") or "unknown",
            ).to_dict(),
            fixture_id=fixture_id, home_id=home_id, away_id=away_id,
        )
        row_league = _text(row.get("league")).casefold()
        if row_league and row_league != league_key:
            observation["eligible_for_review"] = False
            observation["exclusion_reason"] = "competition_scope_mismatch"
        if row.get("season") is not None and str(row.get("season")) != str(season):
            observation["eligible_for_review"] = False
            observation["exclusion_reason"] = "season_scope_mismatch"
        output.append(observation)
    return output


def eligible_observations(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return only timestamped scheduled observations for later canonical review."""
    return [dict(row) for row in rows if row.get("eligible_for_review") is True]


def adapter_capabilities() -> dict[str, dict[str, Any]]:
    """Machine-readable implementation status; none of these routes is activated."""
    return {
        "openligadb": {"implemented": True, "live_verified": False, "route_enabled": False},
        "openfootball": {"implemented": True, "live_verified": False, "route_enabled": False},
        "open_matchday": {"implemented": True, "live_verified": False, "route_enabled": False},
        "livescore_football": {"implemented": True, "live_verified": False, "route_enabled": False},
        "bzzoiro": {"implemented": True, "live_verified": False, "route_enabled": False},
        "highlightly": {"implemented": True, "live_verified": False, "route_enabled": False},
        "api_ninjas": {"implemented": True, "live_verified": False, "route_enabled": False},
    }
