"""Optional independent corroboration of Sportmonks recent results.

This module is deliberately diagnostic: it never mutates Layer 2 profiles or
prediction inputs. Only exact competition/season/team/kickoff matches join.
Provider observations retain namespaced IDs and field-level conflicts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from canonical_data import (
    canonicalize_api_ninjas_match,
    canonicalize_highlightly_match,
    match_identity,
)
from competition_crosswalk import normalize_competition_name, normalize_country
from multi_source_reconciliation import reconcile_match_records
from provider_core import normalize_team_name


def competition_key(name: str, country: str | None = None) -> str:
    """Build the same conservative key for the selected competition in each feed."""
    return "|".join((normalize_competition_name(name), normalize_country(country or "")))


def _participants(fixture: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    home = away = None
    rows = fixture.get("participants") or []
    for row in rows:
        location = str((row.get("meta") or {}).get("location") or "").casefold()
        if location == "home":
            home = row
        elif location == "away":
            away = row
    return home, away


def _current_scores(fixture: Mapping[str, Any], home_id: Any, away_id: Any) -> tuple[int | None, int | None]:
    rows = fixture.get("scores") or []
    current = [row for row in rows if str(row.get("description") or "").casefold() == "current"]
    values: dict[str, int] = {}
    for row in current or rows:
        score = row.get("score") or {}
        goals = score.get("goals") if isinstance(score, Mapping) else None
        participant_id = row.get("participant_id")
        if participant_id is None or goals is None:
            continue
        try:
            values[str(participant_id)] = int(goals)
        except (TypeError, ValueError):
            continue
    return values.get(str(home_id)), values.get(str(away_id))


def canonicalize_sportmonks_fixture(
    fixture: Mapping[str, Any], *, competition: str, country: str | None, season: int
) -> dict[str, Any] | None:
    """Normalize a Sportmonks fixture for comparison; unknown fields stay unknown."""
    home, away = _participants(fixture)
    if not home or not away or not home.get("name") or not away.get("name"):
        return None
    kickoff = fixture.get("starting_at")
    if not kickoff:
        return None
    home_score, away_score = _current_scores(fixture, home.get("id"), away.get("id"))
    state = fixture.get("state") or {}
    label = str(state.get("short_name") or state.get("name") or "").casefold()
    state_id = fixture.get("state_id")
    if str(state_id) in {"5", "7", "8"} or any(x in label for x in ("finished", "full time", "after extra", "after penalties")):
        status = "finished"
    elif any(x in label for x in ("live", "in play", "half time", "1st half", "2nd half", "extra time", "penalty")):
        status = "live"
    elif any(x in label for x in ("not started", "scheduled", "to be played")):
        status = "scheduled"
    else:
        status = "unknown"
    return {
        "competition_key": competition_key(competition, country),
        "season": int(season),
        "kickoff_utc": str(kickoff),
        "home": {"name": str(home["name"]), "source_ids": {"sportmonks": str(home.get("id") or "")}},
        "away": {"name": str(away["name"]), "source_ids": {"sportmonks": str(away.get("id") or "")}},
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "source_ids": {"sportmonks": str(fixture.get("id") or "")},
        "source": "sportmonks",
        "raw_source_updated_at": fixture.get("updated_at") or fixture.get("updatedAt"),
    }


def _api_ninjas_league_slug(client: Any, competition: str) -> str | None:
    target = normalize_competition_name(competition)
    matches = [
        row for row in client.LEAGUES
        if normalize_competition_name(row.get("name")) == target
    ]
    return str(matches[0]["id"]) if len(matches) == 1 else None


def collect_recent_result_corroboration(
    *,
    sportmonks_fixtures: list[dict[str, Any]],
    competition: str,
    country: str | None,
    season: int,
    home_team_name: str,
    away_team_name: str,
    highlightly_client: Any | None = None,
    api_ninjas_client: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch independent match records and reconcile against Sportmonks fixtures.

    Highlightly uses documented leagueName/season/countryName filters and
    paginates its /matches endpoint. API Ninjas uses its documented team,
    league and season filters. A provider is skipped if an exact competition
    mapping is not available. No fuzzy team aliases are inferred.
    """
    fetched = now or datetime.now(timezone.utc)
    fetched = fetched.replace(tzinfo=timezone.utc) if fetched.tzinfo is None else fetched.astimezone(timezone.utc)
    key = competition_key(competition, country)
    home_records: list[dict[str, Any]] = []
    away_records: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    provider_counts: dict[str, int] = {}

    if highlightly_client is not None:
        try:
            rows: list[dict[str, Any]] = []
            offset, limit, max_pages = 0, 100, 10
            for _ in range(max_pages):
                page = highlightly_client.matches(
                    leagueName=competition, season=int(season),
                    countryName=country, limit=limit, offset=offset,
                )
                rows.extend(page)
                if len(page) < limit:
                    break
                offset += limit
            else:
                raise RuntimeError("Highlightly pagination exceeded the safe page limit.")
            normalized = []
            for row in rows:
                league_value = row.get("league")
                league = league_value if isinstance(league_value, Mapping) else {}
                league_name = league.get("name") or row.get("leagueName")
                if league_name and normalize_competition_name(league_name) != normalize_competition_name(competition):
                    continue
                country_value = league.get("country")
                row_country = (
                    country_value.get("name") if isinstance(country_value, Mapping)
                    else country_value if isinstance(country_value, str)
                    else league.get("countryName") or row.get("countryName")
                )
                if country and (not row_country or normalize_country(row_country) != normalize_country(country)):
                    continue
                try:
                    normalized.append(canonicalize_highlightly_match(
                        row, competition_key=key, season=int(season)
                    ))
                except (ValueError, TypeError, KeyError):
                    continue
            home_records.extend(normalized)
            away_records.extend(normalized)
            provider_counts["highlightly"] = len(normalized)
        except Exception as exc:
            errors["highlightly"] = str(exc)

    if api_ninjas_client is not None:
        try:
            league_slug = _api_ninjas_league_slug(api_ninjas_client, competition)
            if league_slug is None:
                provider_counts["api_ninjas"] = 0
                errors["api_ninjas"] = "No unique exact competition-name mapping exists in the API Ninjas league catalogue."
            else:
                rows = []
                for team_name in (home_team_name, away_team_name):
                    rows.extend(api_ninjas_client.team_matches(
                        team=team_name, league=league_slug, season=int(season)
                    ))
                seen: set[str] = set()
                normalized = []
                for row in rows:
                    match_id = str(row.get("game_id") or row.get("fixture_id") or "")
                    if match_id and match_id in seen:
                        continue
                    if match_id:
                        seen.add(match_id)
                    if str(row.get("league") or league_slug) != league_slug:
                        continue
                    row_season = row.get("season")
                    if row_season is not None and str(row_season) != str(int(season)):
                        continue
                    try:
                        normalized.append(canonicalize_api_ninjas_match(
                            row, competition_key=key, season=int(season)
                        ))
                    except (ValueError, TypeError, KeyError):
                        continue
                home_records.extend(normalized)
                away_records.extend(normalized)
                provider_counts["api_ninjas"] = len(normalized)
        except Exception as exc:
            errors["api_ninjas"] = str(exc)

    # Restrict the diagnostic to fixtures involving either selected team.
    selected = {normalize_team_name(home_team_name), normalize_team_name(away_team_name)}
    target_fixtures = []
    for fixture in sportmonks_fixtures:
        canonical = canonicalize_sportmonks_fixture(
            fixture, competition=competition, country=country, season=season
        )
        if canonical is None:
            continue
        if canonical["status"] != "finished" or canonical["home_score"] is None or canonical["away_score"] is None:
            continue
        if (normalize_team_name(canonical["home"]["name"]) in selected
                or normalize_team_name(canonical["away"]["name"]) in selected):
            target_fixtures.append(canonical)
    target_fixtures.sort(key=lambda row: row["kickoff_utc"], reverse=True)
    target_fixtures = target_fixtures[:20]

    all_alternates = home_records
    reconciled: list[dict[str, Any]] = []
    matched_providers: set[str] = set()
    for primary in target_fixtures:
        group = [primary]
        for alternate in all_alternates:
            if match_identity(primary, alternate):
                group.append(alternate)
        if len(group) < 2:
            continue
        result = reconcile_match_records(
            group,
            fetched_at={row["source"]: fetched for row in group},
            now=fetched,
            max_age_seconds=24 * 60 * 60,
        )
        if result is not None:
            reconciled.append(result)
            matched_providers.update(result.get("providers_seen", []))

    conflicts = sum(
        1 for row in reconciled
        if any(item.get("status") == "conflict" for item in row["reconciliation"].values())
    )
    corroborated = sum(
        1 for row in reconciled
        if any(item.get("status") == "corroborated" for item in row["reconciliation"].values())
    )
    return {
        "competition": competition,
        "country": country,
        "season": int(season),
        "sportmonks_fixtures_checked": len(target_fixtures),
        "provider_records_returned": provider_counts,
        "fixtures_matched_across_sources": len(reconciled),
        "fixtures_with_agreement": corroborated,
        "fixtures_with_conflicts": conflicts,
        "providers_matched": sorted(matched_providers),
        "errors": errors,
        "matches": reconciled,
        "note": "Corroboration is diagnostic only; Sportmonks Layer 2 profiles and prediction inputs are not modified.",
    }
