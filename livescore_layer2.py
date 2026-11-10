"""Fail-closed LiveScoreFootball result fallback for missing Sportmonks scores.

LiveScoreFootball is a stored snapshot service. Its data is eligible only after
both global metadata freshness and an exact, season-specific competition
crosswalk pass. It can fill only missing full-time scores on an already-known,
completed Sportmonks fixture; it never replaces a valid Sportmonks score.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from canonical_data import MatchNormalizationError, canonicalize_livescore_event, match_identity
from competition_crosswalk import build_competition_crosswalk, verified_livescore_slug
from provider_health import assess_livescore_metadata
from sportmonks_canonical import canonicalize_sportmonks_fixture
from sportmonks_layer2 import _CORE_STATISTICS, _provider_id, _state


def _utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _has_explicit_current_score_rows(fixture: Mapping[str, Any]) -> bool:
    rows = fixture.get("scores")
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        score_type = row.get("type") if isinstance(row.get("type"), Mapping) else {}
        label = row.get("description") or score_type.get("name") or ""
        if str(label).strip().casefold() == "current":
            return True
    return False


def _fixture_participants(fixture: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    participants = fixture.get("participants")
    if not isinstance(participants, list):
        return None
    by_side = {
        str((row.get("meta") or {}).get("location") or "").casefold(): row
        for row in participants
        if isinstance(row, Mapping)
    }
    home, away = by_side.get("home"), by_side.get("away")
    if not isinstance(home, dict) or not isinstance(away, dict):
        return None
    if _provider_id(home.get("id")) is None or _provider_id(away.get("id")) is None:
        return None
    if not home.get("name") or not away.get("name"):
        return None
    return home, away


def collect_livescore_verified_result_fallback(
    client: Any,
    *,
    source_competition: Mapping[str, Any],
    sportmonks_fixtures: list[Mapping[str, Any]],
    selected_team_ids: set[int],
    competition_key: str,
    season: int,
    season_id: int,
    now: datetime | None = None,
    max_age_seconds: int = 24 * 60 * 60,
    max_unique_date_requests: int = 10,
) -> dict[str, Any]:
    """Collect LiveScore results only for missing scores on completed SM fixtures."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    started_at = current.isoformat()
    expected_season_id = _provider_id(season_id)
    expected_competition_id = _provider_id(source_competition.get("id"))
    if expected_season_id is None or expected_competition_id is None:
        return {
            "status": "skipped",
            "reason": "invalid_sportmonks_competition_or_season_id",
            "verified_matches": [],
        }

    candidates: list[tuple[Mapping[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for fixture in sportmonks_fixtures:
        if not isinstance(fixture, Mapping):
            continue
        if _provider_id(fixture.get("season_id")) != expected_season_id:
            continue
        if _provider_id(fixture.get("league_id")) != expected_competition_id:
            continue
        if _state(dict(fixture)) != "finished" or _has_explicit_current_score_rows(fixture):
            continue
        participants = _fixture_participants(fixture)
        if participants is None:
            continue
        home, away = participants
        home_id, away_id = _provider_id(home.get("id")), _provider_id(away.get("id"))
        if home_id not in selected_team_ids and away_id not in selected_team_ids:
            continue
        try:
            canonical_sm = canonicalize_sportmonks_fixture(
                fixture, competition_key=competition_key, season=season
            )
        except MatchNormalizationError:
            continue
        if (
            canonical_sm.get("status") != "finished"
            or canonical_sm.get("home_score") is not None
            or canonical_sm.get("away_score") is not None
        ):
            continue
        kickoff = _utc_timestamp(canonical_sm.get("kickoff_utc"))
        if kickoff is None:
            continue
        candidates.append((fixture, canonical_sm, home, away))

    report: dict[str, Any] = {
        "status": "no_missing_completed_scores" if not candidates else "pending",
        "reason": None,
        "fallback_eligible": False,
        "crosswalk": [],
        "metadata_assessment": {},
        "verified_matches": [],
        "candidates_considered": len(candidates),
        "date_requests": 0,
        "date_cache_hits": 0,
        "date_request_limit_reached": 0,
        "max_unique_date_requests": max(1, min(int(max_unique_date_requests), 10)),
        "collection_started_at": started_at,
        "collection_completed_at": None,
    }
    if not candidates:
        report["collection_completed_at"] = datetime.now(timezone.utc).isoformat()
        return report

    metadata = client.meta()
    metadata_assessment = assess_livescore_metadata(
        metadata, now=current, domain="fixtures", max_age_seconds=max_age_seconds
    )
    report["metadata_assessment"] = metadata_assessment
    if metadata_assessment.get("fallback_eligible") is not True:
        report.update({
            "status": "skipped",
            "reason": metadata_assessment.get("reason") or "global_livescore_metadata_not_fresh",
            "collection_completed_at": datetime.now(timezone.utc).isoformat(),
        })
        return report

    leagues = client.leagues(kind="club", available=True)
    crosswalk = build_competition_crosswalk(
        [source_competition],
        leagues,
        requested_season=season,
        source_provider="sportmonks",
        now=current,
        max_age_seconds=max_age_seconds,
    )
    report["crosswalk"] = crosswalk
    slug = verified_livescore_slug(
        crosswalk, expected_competition_id, source_provider="sportmonks"
    )
    if not slug:
        report.update({
            "status": "skipped",
            "reason": "exact_season_competition_crosswalk_not_verified",
            "collection_completed_at": datetime.now(timezone.utc).isoformat(),
        })
        return report

    crosswalk_row = next(
        row for row in crosswalk
        if str(row.get("source_competition_id")) == str(expected_competition_id)
        and row.get("verified") is True
    )
    coverage = crosswalk_row.get("coverage") or {}
    competition_last_synced_at = coverage.get("lastSyncedAt")
    report["fallback_eligible"] = True
    report["livescore_slug"] = slug
    report["competition_last_synced_at"] = competition_last_synced_at

    by_date: dict[str, list[dict[str, Any]]] = {}
    limit = report["max_unique_date_requests"]
    for fixture, canonical_sm, home, away in candidates:
        kickoff = _utc_timestamp(canonical_sm.get("kickoff_utc"))
        if kickoff is None:
            continue
        date_key = kickoff.date().isoformat()
        if date_key not in by_date:
            if report["date_requests"] >= limit:
                report["date_request_limit_reached"] += 1
                continue
            by_date[date_key] = client.fixtures(
                slug,
                status="finished",
                date_from=date_key,
                date_to=date_key,
                max_pages=1,
                page_size=200,
            )
            report["date_requests"] += 1
        else:
            report["date_cache_hits"] += 1

        exact_events: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
        for event in by_date[date_key]:
            if not isinstance(event, Mapping):
                continue
            try:
                canonical_live = canonicalize_livescore_event(
                    event, competition_key=competition_key, season=season
                )
            except MatchNormalizationError:
                continue
            if (
                canonical_live.get("status") == "finished"
                and canonical_live.get("home_score") is not None
                and canonical_live.get("away_score") is not None
                and match_identity(canonical_sm, canonical_live, kickoff_tolerance_seconds=300)
            ):
                exact_events.append((event, canonical_live))
        if len(exact_events) != 1:
            continue

        raw_event, canonical_live = exact_events[0]
        event_id = str((canonical_live.get("source_ids") or {}).get("livescore_football") or "")
        if not event_id:
            continue
        report["verified_matches"].append({
            "status": "verified_missing_score_fallback",
            "crosswalk_verified": True,
            "match_identity_verified": True,
            "sportmonks_fixture_id": _provider_id(fixture.get("id")),
            "season_id": expected_season_id,
            "competition_id": expected_competition_id,
            "competition_key": competition_key,
            "livescore_slug": slug,
            "livescore_event_id": event_id,
            "home_team_id": _provider_id(home.get("id")),
            "away_team_id": _provider_id(away.get("id")),
            "home": str(home.get("name")),
            "away": str(away.get("name")),
            "kickoff_utc": canonical_sm["kickoff_utc"],
            "home_score": canonical_live["home_score"],
            "away_score": canonical_live["away_score"],
            "competition_last_synced_at": competition_last_synced_at,
            "global_last_successful_sync_at": metadata.get("lastSuccessfulSyncAt"),
            "raw_source_updated_at": canonical_live.get("raw_source_updated_at"),
            "collection_started_at": started_at,
            "score_source_provider": "livescore_football",
        })

    completed_at = datetime.now(timezone.utc).isoformat()
    report["collection_completed_at"] = completed_at
    for match in report["verified_matches"]:
        match["collection_completed_at"] = completed_at
    report["status"] = "completed" if report["verified_matches"] else "no_exact_fresh_livescore_matches"
    return report


def apply_livescore_verified_result_fallback_to_profiles(
    profiles: list[dict[str, Any]],
    verified_matches: list[Mapping[str, Any]],
    *,
    history_limit: int = 10,
) -> dict[str, Any]:
    """Append verified LiveScore scores to matching SM team profiles, never overwrite."""
    from form_analyzer import analyze_form, venue_rating
    from provider_core import normalize_team_name
    from tactical_indicators import analyze_tactics

    original_profiles = profiles
    profiles = deepcopy(profiles)
    safe_limit = max(1, min(int(history_limit), 10))
    summary = {"status": "completed", "profiles_updated": 0, "matches_added": 0, "duplicates_skipped": 0}

    for item in verified_matches:
        if not isinstance(item, Mapping):
            continue
        if (
            item.get("status") != "verified_missing_score_fallback"
            or item.get("crosswalk_verified") is not True
            or item.get("match_identity_verified") is not True
            or item.get("score_source_provider") != "livescore_football"
        ):
            continue
        fixture_id = _provider_id(item.get("sportmonks_fixture_id"))
        home_id, away_id = _provider_id(item.get("home_team_id")), _provider_id(item.get("away_team_id"))
        home_name, away_name = str(item.get("home") or ""), str(item.get("away") or "")
        home_score, away_score = item.get("home_score"), item.get("away_score")
        kickoff = _utc_timestamp(item.get("kickoff_utc"))
        completed_at = _utc_timestamp(item.get("collection_completed_at"))
        if (
            fixture_id is None or home_id is None or away_id is None
            or not home_name or not away_name or kickoff is None or completed_at is None
            or isinstance(home_score, bool) or not isinstance(home_score, int) or home_score < 0
            or isinstance(away_score, bool) or not isinstance(away_score, int) or away_score < 0
        ):
            continue

        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = _provider_id(profile.get("id"))
            profile_name = normalize_team_name(profile.get("name") or "")
            if profile_id == home_id and profile_name == normalize_team_name(home_name):
                venue, opponent_id, opponent_name = "home", away_id, away_name
                goals_for, goals_against = home_score, away_score
            elif profile_id == away_id and profile_name == normalize_team_name(away_name):
                venue, opponent_id, opponent_name = "away", home_id, home_name
                goals_for, goals_against = away_score, home_score
            else:
                continue

            matches = profile.get("matches")
            if not isinstance(matches, list):
                matches = []
            if any(
                str(match.get("fixture_id")) == str(fixture_id)
                for match in matches if isinstance(match, Mapping)
            ):
                summary["duplicates_skipped"] += 1
                continue
            matches.append({
                "fixture_id": fixture_id,
                "date": kickoff.isoformat(),
                "venue": venue,
                "opponent_id": opponent_id,
                "opponent_name": opponent_name,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "opponent_strength": None,
                "statistics": {},
                "opponent_statistics": {},
                "statistics_provenance": [],
                "statistics_raw_diagnostics": [],
                "collection_fetched_at": completed_at.isoformat(),
                "repository_collected_at": None,
                "provider_updated_at": item.get("raw_source_updated_at"),
                "history_source": "sportmonks_fixture_with_verified_livescore_score",
                "source_ids": {
                    "sportmonks": str(fixture_id),
                    "livescore_football": str(item.get("livescore_event_id") or ""),
                },
                "result_verification": {
                    "score_source_provider": "livescore_football",
                    "identity_anchor_provider": "sportmonks",
                    "livescore_event_id": str(item.get("livescore_event_id") or ""),
                    "livescore_slug": str(item.get("livescore_slug") or ""),
                    "competition_last_synced_at": item.get("competition_last_synced_at"),
                    "global_last_successful_sync_at": item.get("global_last_successful_sync_at"),
                    "raw_source_updated_at": item.get("raw_source_updated_at"),
                    "collection_completed_at": completed_at.isoformat(),
                    "crosswalk_verified": True,
                    "match_identity_verified": True,
                },
            })
            matches.sort(
                key=lambda match: (
                    _utc_timestamp(match.get("date")).timestamp()
                    if isinstance(match, Mapping) and _utc_timestamp(match.get("date"))
                    else -1
                ),
                reverse=True,
            )
            recent = matches[:safe_limit]
            profile["matches"] = recent
            profile["form_summary"] = analyze_form(recent)
            profile["home_rating"] = venue_rating(recent, "home")
            profile["away_rating"] = venue_rating(recent, "away")
            tactics = analyze_tactics(recent)
            profile["tactical_summary"] = tactics
            for field in ("playing_style", "defensive_structure", "attacking_approach"):
                if field in tactics:
                    profile[field] = tactics[field]
            data_quality = profile.setdefault("data_quality", {})
            data_quality["history_source"] = "cockroachdb_plus_verified_livescore_result_fallback"
            data_quality["livescore_verified_result_fallback_added"] = (
                int(data_quality.get("livescore_verified_result_fallback_added") or 0) + 1
            )
            diagnostics = profile.setdefault("history_collection_diagnostics", {})
            diagnostics["livescore_verified_result_candidates_added"] = (
                int(diagnostics.get("livescore_verified_result_candidates_added") or 0) + 1
            )
            diagnostics["history_shortfall"] = max(0, safe_limit - len(recent))
            valid_dates = [
                _utc_timestamp(match.get("date"))
                for match in recent
                if isinstance(match, Mapping) and _utc_timestamp(match.get("date")) is not None
            ]
            if valid_dates:
                diagnostics["history_latest_match_at"] = max(valid_dates).isoformat()
                diagnostics["history_oldest_match_at"] = min(valid_dates).isoformat()
            diagnostics["history_order"] = "newest_first_by_parsed_utc_kickoff"
            summary["profiles_updated"] += 1
            summary["matches_added"] += 1

    for original, updated in zip(original_profiles, profiles):
        if isinstance(original, dict) and isinstance(updated, dict):
            original.clear()
            original.update(updated)
    return summary
