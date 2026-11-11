"""Fail-closed post-match result verification for promoted free fixture sources."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from free_fixture_adapters import (
    BzzoiroAdapter, OpenFootballAdapter, OpenLigaDBAdapter, OpenMatchdayAdapter,
)
from livescore_football import LiveScoreFootballClient
from provider_data_storage import _connect
from provider_entity_crosswalk import load_provider_entity_links
from free_fixture_canonical_promotion import _ensure_promotion_tables


SUPPORTED_RESULT_PROVIDERS = {
    "openligadb", "openfootball", "open_matchday", "livescore_football", "bzzoiro",
}


def _normalise(value: Any) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _integer_score(home: Any, away: Any) -> tuple[int, int] | None:
    try:
        h, a = float(home), float(away)
    except (TypeError, ValueError):
        return None
    if not h.is_integer() or not a.is_integer() or h < 0 or a < 0:
        return None
    return int(h), int(a)


def _season_year(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"\b(20\d{2})\b", text)
    if match:
        return match.group(1)
    compact = text.strip()
    if re.fullmatch(r"\d{4}", compact):
        start, end = int(compact[:2]), int(compact[2:])
        if end == (start + 1) % 100:
            return f"20{start:02d}"
    return ""


def verify_openligadb_final_score(
    record: Mapping[str, Any],
    match: Mapping[str, Any],
    *,
    provider_fixture_id: str,
    now: datetime,
    source_observation: Mapping[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Require exact source ID, sides, competition, season and one final result row."""
    raw_id = match.get("matchID") or match.get("MatchID")
    if str(raw_id or "") != str(provider_fixture_id):
        return None
    if match.get("matchIsFinished") is not True:
        return None
    team1 = match.get("team1") or match.get("Team1") or {}
    team2 = match.get("team2") or match.get("Team2") or {}
    home = team1.get("teamName") or team1.get("name") if isinstance(team1, Mapping) else None
    away = team2.get("teamName") or team2.get("name") if isinstance(team2, Mapping) else None
    source_observation = source_observation or {}
    expected_home = source_observation.get("home_team_name") or record.get("home_team")
    expected_away = source_observation.get("away_team_name") or record.get("away_team")
    expected_competition = source_observation.get("competition_name") or record.get("competition")
    expected_season = _season_year(
        source_observation.get("season_name") or source_observation.get("season_key")
    ) or str(record.get("season") or "")[:4]
    if _normalise(home) != _normalise(expected_home):
        return None
    if _normalise(away) != _normalise(expected_away):
        return None
    if _normalise(match.get("leagueName")) != _normalise(expected_competition):
        return None
    source_season = str(match.get("leagueSeason") or "")
    if not source_season or source_season != expected_season:
        return None
    kickoff = _timestamp(match.get("matchDateTimeUTC") or match.get("matchDateTime"))
    if kickoff is None or kickoff > now:
        return None
    results = match.get("matchResults")
    if not isinstance(results, list):
        return None
    finals = []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        result_type = item.get("resultTypeID") or item.get("resultTypeId")
        result_name = str(item.get("resultName") or "").casefold()
        if str(result_type) == "2" or "endergebnis" in result_name or "full time" in result_name:
            score = _integer_score(item.get("pointsTeam1"), item.get("pointsTeam2"))
            if score is not None:
                finals.append(score)
    # Multiple conflicting final-score rows are ambiguous; do not guess.
    if not finals or len(set(finals)) != 1:
        return None
    # OpenLigaDB does not consistently expose extra-time metadata. If it
    # exposes an additional result period beyond half-time and full-time, fail closed.
    if len(results) > 2:
        return None
    return finals[0]


def verify_livescore_final_score(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    provider_fixture_id: str,
    now: datetime,
    source_observation: Mapping[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Require exact LiveScore event ID and an explicit 90-minute full-time status."""
    if str(event.get("id") or event.get("uid") or "") != str(provider_fixture_id):
        return None
    status = event.get("status") if isinstance(event.get("status"), Mapping) else {}
    status_type = status.get("type") if isinstance(status.get("type"), Mapping) else {}
    status_name = str(status_type.get("name") or "").casefold()
    detail = str(
        status_type.get("detail") or status_type.get("shortDetail")
        or status.get("display") or ""
    ).casefold()
    if status_type.get("completed") is not True:
        return None
    if status_name not in {"status_final", "final", "finished"}:
        return None
    if not any(token in detail for token in ("full time", "full-time", "ft", "final")):
        return None
    if any(token in detail for token in ("extra time", "after extra", "penalt", "aet")):
        return None

    source_observation = source_observation or {}
    expected_home = source_observation.get("home_team_name") or record.get("home_team")
    expected_away = source_observation.get("away_team_name") or record.get("away_team")
    expected_competition = source_observation.get("competition_name") or record.get("competition")
    expected_season = _season_year(
        source_observation.get("season_name") or source_observation.get("season_key")
    ) or str(record.get("season") or "")[:4]
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return None
    competition = competitions[0]
    if _normalise(competition.get("name")) != _normalise(expected_competition):
        return None
    competitors = competition.get("competitors") or []
    sides: dict[str, Mapping[str, Any]] = {}
    for competitor in competitors:
        if not isinstance(competitor, Mapping):
            continue
        side = str(competitor.get("homeAway") or competitor.get("home_away") or "").casefold()
        if side in {"home", "away"}:
            sides[side] = competitor
    if set(sides) != {"home", "away"}:
        return None
    home_team = sides["home"].get("team") if isinstance(sides["home"].get("team"), Mapping) else sides["home"]
    away_team = sides["away"].get("team") if isinstance(sides["away"].get("team"), Mapping) else sides["away"]
    if _normalise(home_team.get("displayName") or home_team.get("name")) != _normalise(expected_home):
        return None
    if _normalise(away_team.get("displayName") or away_team.get("name")) != _normalise(expected_away):
        return None
    season = event.get("season") if isinstance(event.get("season"), Mapping) else {}
    source_year = _season_year(season.get("year") or season.get("name") or event.get("season_id"))
    if not source_year or source_year != expected_season:
        return None
    kickoff = _timestamp(event.get("date") or event.get("startDate"))
    if kickoff is None or kickoff > now:
        return None
    return _integer_score(sides["home"].get("score"), sides["away"].get("score"))


def verify_openfootball_final_score(
    record: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    provider_fixture_id: str,
    now: datetime,
    source_observation: Mapping[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Use only explicit football.json FT scores for the exact scheduled dataset row."""
    if str(observation.get("provider_fixture_id") or "") != str(provider_fixture_id):
        return None
    source_observation = source_observation or {}
    expected_home = source_observation.get("home_team_name") or record.get("home_team")
    expected_away = source_observation.get("away_team_name") or record.get("away_team")
    expected_competition = source_observation.get("competition_name") or record.get("competition")
    expected_season = _season_year(
        source_observation.get("season_name") or source_observation.get("season_key")
    ) or str(record.get("season") or "")[:4]
    if _normalise(observation.get("home_team_name")) != _normalise(expected_home):
        return None
    if _normalise(observation.get("away_team_name")) != _normalise(expected_away):
        return None
    if _normalise(observation.get("competition_name")) != _normalise(expected_competition):
        return None
    if _season_year(observation.get("season_name") or observation.get("season_key")) != expected_season:
        return None
    kickoff = _timestamp(observation.get("kickoff_utc"))
    recorded_kickoff = _timestamp(record.get("kickoff_at"))
    if kickoff is None or recorded_kickoff is None or kickoff > now:
        return None
    if abs((kickoff - recorded_kickoff).total_seconds()) > 300:
        return None

    competition_key = str(observation.get("competition_key") or "").casefold()
    competition_name = str(observation.get("competition_name") or "").casefold()
    if "cup" in competition_key or "cup" in competition_name or "pokal" in competition_name:
        return None
    raw = observation.get("raw_payload")
    if not isinstance(raw, Mapping):
        return None
    status = str(raw.get("status") or "").casefold()
    if status and status not in {"finished", "complete", "completed", "ft", "full time"}:
        return None
    score = raw.get("score")
    if not isinstance(score, Mapping):
        return None
    if any(score.get(key) not in (None, "", [], {}) for key in (
        "et", "extra_time", "aet", "pens", "penalties", "penalty_shootout"
    )):
        return None
    full_time = score.get("ft") or score.get("full_time") or score.get("fullTime")
    if not isinstance(full_time, (list, tuple)) or len(full_time) != 2:
        return None
    return _integer_score(full_time[0], full_time[1])


def verify_openmatchday_final_score(
    record: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    provider_fixture_id: str,
    now: datetime,
    source_observation: Mapping[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Verify a result-file row against the same deterministic future-fixture key."""
    if str(observation.get("provider_fixture_id") or "") != str(provider_fixture_id):
        return None
    source_observation = source_observation or {}
    expected_home = source_observation.get("home_team_name") or record.get("home_team")
    expected_away = source_observation.get("away_team_name") or record.get("away_team")
    expected_competition = source_observation.get("competition_name") or record.get("competition")
    expected_season = _season_year(
        source_observation.get("season_name") or source_observation.get("season_key")
    ) or str(record.get("season") or "")[:4]
    if _normalise(observation.get("home_team_name")) != _normalise(expected_home):
        return None
    if _normalise(observation.get("away_team_name")) != _normalise(expected_away):
        return None
    if _normalise(observation.get("competition_name")) != _normalise(expected_competition):
        return None
    if _season_year(observation.get("season_name") or observation.get("season_key")) != expected_season:
        return None
    kickoff = _timestamp(observation.get("kickoff_utc"))
    recorded_kickoff = _timestamp(record.get("kickoff_at"))
    if kickoff is None or recorded_kickoff is None or kickoff > now:
        return None
    if abs((kickoff - recorded_kickoff).total_seconds()) > 300:
        return None

    competition_key = str(observation.get("competition_key") or "").casefold()
    competition_name = str(observation.get("competition_name") or "").casefold()
    # Open Matchday does not expose separate extra-time/penalty fields in its
    # results CSV. Do not treat cup results as 90-minute scores.
    if "cup" in competition_key or "cup" in competition_name or "pokal" in competition_name:
        return None

    raw = observation.get("raw_payload")
    if not isinstance(raw, Mapping):
        return None
    score = _integer_score(raw.get("ft_home"), raw.get("ft_away"))
    if score is None:
        return None
    declared_result = str(raw.get("ft_result") or "").strip().upper()
    expected_result = "H" if score[0] > score[1] else "A" if score[0] < score[1] else "D"
    if declared_result and declared_result != expected_result:
        return None
    return score


def verify_bzzoiro_final_score(
    record: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    provider_fixture_id: str,
    now: datetime,
    source_observation: Mapping[str, Any] | None = None,
) -> tuple[int, int] | None:
    """Require exact Bzzoiro event identity and an explicit regulation-time FT score."""
    if str(event.get("id") or event.get("event_id") or "") != str(provider_fixture_id):
        return None
    if str(event.get("status") or "").casefold() != "finished":
        return None
    source_observation = source_observation or {}
    expected_home = source_observation.get("home_team_name") or record.get("home_team")
    expected_away = source_observation.get("away_team_name") or record.get("away_team")
    expected_competition = source_observation.get("competition_name") or record.get("competition")
    expected_season = _season_year(
        source_observation.get("season_name") or source_observation.get("season_key")
    ) or str(record.get("season") or "")[:4]
    home_team = event.get("home_team") if isinstance(event.get("home_team"), Mapping) else event.get("home")
    away_team = event.get("away_team") if isinstance(event.get("away_team"), Mapping) else event.get("away")
    if isinstance(home_team, Mapping):
        home_name = home_team.get("name") or home_team.get("display_name")
    else:
        home_name = home_team
    if isinstance(away_team, Mapping):
        away_name = away_team.get("name") or away_team.get("display_name")
    else:
        away_name = away_team
    if _normalise(home_name) != _normalise(expected_home):
        return None
    if _normalise(away_name) != _normalise(expected_away):
        return None
    league = event.get("league") if isinstance(event.get("league"), Mapping) else {}
    if _normalise(league.get("name") or event.get("competition")) != _normalise(expected_competition):
        return None
    season = event.get("season") if isinstance(event.get("season"), Mapping) else {}
    source_year = _season_year(season.get("name") or season.get("year") or event.get("season_name"))
    if not source_year or source_year != expected_season:
        return None
    kickoff = _timestamp(event.get("date") or event.get("kickoff_at"))
    if kickoff is None or kickoff > now:
        return None
    scores = event.get("scores") if isinstance(event.get("scores"), Mapping) else {}
    full_time = (
        scores.get("ft") or scores.get("full_time") or scores.get("fullTime")
        or scores.get("regular_time") or scores.get("90_minutes")
    )
    if not isinstance(full_time, Mapping):
        return None
    return _integer_score(full_time.get("home"), full_time.get("away"))


def _record_has_canonical_ids(record: Mapping[str, Any]) -> bool:
    return any(str(record.get(key) or "").strip() for key in (
        "league_id", "season_id", "home_team_id", "away_team_id"
    ))


def _crosswalk_matches_record(
    record: Mapping[str, Any],
    source_observation: Mapping[str, Any],
    entity_links: Mapping[str, Mapping[str, str]],
) -> bool:
    expected = {
        "league_id": entity_links.get("league", {}).get(
            str(source_observation.get("competition_key") or "")
        ),
        "season_id": entity_links.get("season", {}).get(
            str(source_observation.get("season_key") or "")
        ),
        "home_team_id": entity_links.get("team", {}).get(
            str(source_observation.get("home_team_key") or "")
        ),
        "away_team_id": entity_links.get("team", {}).get(
            str(source_observation.get("away_team_key") or "")
        ),
    }
    if not all(expected.values()):
        return False
    return all(
        str(record.get(key) or "") == str(value)
        for key, value in expected.items()
    )


def _source_metadata(database_url: str, provider: str, fixture_id: str) -> dict[str, Any] | None:
    with _connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT source_url, raw_payload, fixture_id
                   FROM football_fixture_sources
                   WHERE provider = %s AND provider_fixture_id = %s""",
                (provider, fixture_id),
            )
            row = cursor.fetchone()
    if not row:
        return None
    return {"source_url": row[0], "raw_payload": row[1], "canonical_fixture_id": row[2]}


def _free_candidates(records: list[Mapping[str, Any]], now: datetime) -> list[list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in records:
        provider = str(row.get("fixture_provider") or "").strip().casefold()
        fixture_id = str(row.get("fixture_id") or "").strip()
        if provider not in SUPPORTED_RESULT_PROVIDERS or not fixture_id.startswith(f"{provider}:"):
            continue
        if (
            row.get("actual_home_goals") not in (None, "")
            or row.get("actual_away_goals") not in (None, "")
            or row.get("actual_result") not in (None, "")
        ):
            continue
        kickoff = _timestamp(row.get("kickoff_at"))
        if kickoff is None or kickoff > now:
            continue
        grouped.setdefault((provider, fixture_id), []).append(row)
    return list(grouped.values())


def sync_free_source_results(
    records: list[dict[str, Any]],
    *,
    provider_database_url: str | None,
    now: datetime | None = None,
    limit: int = 10,
    bzzoiro_token: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify and fill blank ledger scores for OpenLigaDB, LiveScoreFootball and Bzzoiro."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    report: dict[str, Any] = {
        "status": "starting",
        "candidate_fixtures": 0,
        "fixtures_checked": 0,
        "records_updated": 0,
        "fixtures_without_verified_score": 0,
        "unsupported_providers": 0,
        "errors": [],
        "fixture_results": [],
    }
    if not provider_database_url:
        report["status"] = "skipped_provider_database_not_configured"
        return report, []
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer between 1 and 50.")
    _ensure_promotion_tables(provider_database_url)
    candidates = _free_candidates(records, current)
    report["candidate_fixtures"] = len(candidates)
    report["limit_reached"] = len(candidates) > limit
    updated_rows: list[dict[str, Any]] = []
    openligadb_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
    livescore_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    entity_link_cache: dict[str, dict[str, dict[str, str]]] = {}

    for group in candidates[:max(1, int(limit))]:
        representative = group[0]
        provider = str(representative.get("fixture_provider") or "").casefold()
        namespaced_id = str(representative.get("fixture_id") or "")
        source_id = namespaced_id.split(":", 1)[1]
        item = {"provider": provider, "fixture_id": namespaced_id, "status": "not_verified"}
        try:
            metadata = _source_metadata(provider_database_url, provider, source_id)
            if not metadata:
                item["reason"] = "promoted_provider_source_link_not_found"
                report["fixtures_without_verified_score"] += 1
                report["fixture_results"].append(item)
                continue
            source_url = str(metadata.get("source_url") or "")
            raw_observation = metadata.get("raw_payload")
            raw_observation = raw_observation if isinstance(raw_observation, Mapping) else {}
            if _record_has_canonical_ids(representative):
                if not all(str(representative.get(key) or "").strip() for key in (
                    "league_id", "season_id", "home_team_id", "away_team_id"
                )):
                    item["reason"] = "prediction_record_has_incomplete_canonical_entity_ids"
                    report["fixtures_without_verified_score"] += 1
                    report["fixture_results"].append(item)
                    continue
                if provider not in entity_link_cache:
                    entity_link_cache[provider] = {
                        "league": load_provider_entity_links(
                            provider_database_url, provider=provider, entity_type="league"
                        ),
                        "season": load_provider_entity_links(
                            provider_database_url, provider=provider, entity_type="season"
                        ),
                        "team": load_provider_entity_links(
                            provider_database_url, provider=provider, entity_type="team"
                        ),
                    }
                if not _crosswalk_matches_record(
                    representative, raw_observation, entity_link_cache[provider]
                ):
                    item["reason"] = "provider_crosswalk_does_not_match_saved_prediction_identity"
                    report["fixtures_without_verified_score"] += 1
                    report["fixture_results"].append(item)
                    continue
            score = None

            if provider == "openligadb":
                parsed = urlparse(source_url)
                match = re.search(r"/getmatchdata/([^/]+)/([0-9]{4})/?$", parsed.path)
                if not match:
                    item["reason"] = "openligadb_source_scope_unavailable"
                else:
                    shortcut, season = match.group(1), int(match.group(2))
                    key = (shortcut, season)
                    if key not in openligadb_cache:
                        with OpenLigaDBAdapter() as client:
                            openligadb_cache[key] = client.matches(shortcut, season)
                    observation = next((
                        row for row in openligadb_cache[key]
                        if str(row.get("provider_fixture_id")) == source_id
                    ), None)
                    if observation and isinstance(observation.get("raw_payload"), Mapping):
                        score = verify_openligadb_final_score(
                            representative, observation["raw_payload"],
                            provider_fixture_id=source_id, now=current,
                            source_observation=raw_observation,
                        )
                    if score is None:
                        item["reason"] = "openligadb_final_score_not_verified"
            elif provider == "livescore_football":
                parsed = urlparse(source_url)
                match = re.search(r"/get/soccer/([^/]+)/fixtures/?$", parsed.path)
                kickoff = _timestamp(representative.get("kickoff_at"))
                if not match or kickoff is None:
                    item["reason"] = "livescore_source_scope_or_kickoff_unavailable"
                else:
                    slug = match.group(1)
                    date_from = (kickoff.date() - timedelta(days=1)).isoformat()
                    date_to = (kickoff.date() + timedelta(days=1)).isoformat()
                    key = (slug, date_from, date_to)
                    if key not in livescore_cache:
                        client = LiveScoreFootballClient()
                        try:
                            livescore_cache[key] = client.fixtures(
                                slug, status="finished", date_from=date_from, date_to=date_to
                            )
                        finally:
                            client.close()
                    event = next((
                        row for row in livescore_cache[key]
                        if str(row.get("id") or row.get("uid") or "") == source_id
                    ), None)
                    if event:
                        score = verify_livescore_final_score(
                            representative, event,
                            provider_fixture_id=source_id, now=current,
                            source_observation=raw_observation,
                        )
                    if score is None:
                        item["reason"] = "livescore_final_90_minute_score_not_verified"
            elif provider == "openfootball":
                source_path = urlparse(source_url).path
                match = re.search(r"/master/(20\d{2}-\d{2}/[^/]+\.json)$", source_path)
                if not match:
                    item["reason"] = "openfootball_season_dataset_url_unavailable"
                else:
                    season_file = match.group(1)
                    competition = str(
                        raw_observation.get("competition_name")
                        or representative.get("competition") or ""
                    )
                    with OpenFootballAdapter() as client:
                        result_rows = client.season(season_file, competition=competition)
                    result_row = next((
                        row for row in result_rows
                        if str(row.get("provider_fixture_id")) == source_id
                    ), None)
                    if result_row:
                        score = verify_openfootball_final_score(
                            representative, result_row,
                            provider_fixture_id=source_id, now=current,
                            source_observation=raw_observation,
                        )
                    if score is None:
                        item["reason"] = "openfootball_full_time_score_not_verified"
            elif provider == "open_matchday":
                source_path = urlparse(source_url).path
                if "/fixtures_" not in source_path or not source_path.endswith(".csv"):
                    item["reason"] = "open_matchday_fixture_dataset_url_unavailable"
                else:
                    results_url = source_url.replace("/fixtures_", "/results_", 1)
                    competition = str(
                        raw_observation.get("competition_name")
                        or representative.get("competition") or ""
                    )
                    season = str(
                        raw_observation.get("season_name")
                        or representative.get("season") or ""
                    )
                    with OpenMatchdayAdapter() as client:
                        result_rows = client.season_csv(
                            results_url, competition=competition, season=season
                        )
                    result_row = next((
                        row for row in result_rows
                        if str(row.get("provider_fixture_id")) == source_id
                    ), None)
                    if result_row:
                        score = verify_openmatchday_final_score(
                            representative, result_row,
                            provider_fixture_id=source_id, now=current,
                            source_observation=raw_observation,
                        )
                    if score is None:
                        item["reason"] = "open_matchday_full_time_score_not_verified"
            elif provider == "bzzoiro":
                with BzzoiroAdapter(token=bzzoiro_token) as client:
                    event = client.event(source_id)
                score = verify_bzzoiro_final_score(
                    representative, event, provider_fixture_id=source_id, now=current,
                    source_observation=raw_observation,
                )
                if score is None:
                    item["reason"] = "bzzoiro_final_90_minute_score_not_verified"

            if score is None:
                report["fixtures_without_verified_score"] += 1
                report["fixture_results"].append(item)
                continue

            verified_at = current.isoformat()
            fixture_updated = 0
            for row in group:
                if not isinstance(row, dict):
                    continue
                if (
                    row.get("actual_home_goals") not in (None, "")
                    or row.get("actual_away_goals") not in (None, "")
                    or row.get("actual_result") not in (None, "")
                ):
                    continue
                row["actual_home_goals"] = score[0]
                row["actual_away_goals"] = score[1]
                row["actual_result"] = (
                    "home" if score[0] > score[1]
                    else "away" if score[0] < score[1]
                    else "draw"
                )
                row["actual_result_provider"] = provider
                row["actual_result_fixture_id"] = source_id
                row["actual_result_verified_at"] = verified_at
                row["actual_result_verification"] = (
                    "exact_provider_fixture_team_competition_season_and_90_minute_score"
                )
                row["actual_result_provider_updated_at"] = str(
                    raw_observation.get("fetched_at") or ""
                )
                updated_rows.append(row)
                fixture_updated += 1
            report["records_updated"] += fixture_updated
            report["fixtures_checked"] += 1
            item.update(
                status="updated" if fixture_updated else "no_matching_blank_ledger_rows",
                records_updated=fixture_updated,
                verified_score=f"{score[0]}-{score[1]}",
            )
            report["fixture_results"].append(item)
        except Exception as exc:
            report["errors"].append({
                "provider": provider,
                "fixture_id": namespaced_id,
                "error_type": type(exc).__name__,
                "message": str(exc)[:250],
            })
            item.update(status="provider_error", error_type=type(exc).__name__)
            report["fixture_results"].append(item)

    report["status"] = (
        "updated_with_errors" if report["records_updated"] and report["errors"]
        else "updated" if report["records_updated"]
        else "attention_required" if report["errors"]
        else "no_verified_results"
    )
    return report, updated_rows
