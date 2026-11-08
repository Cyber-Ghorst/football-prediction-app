"""Football Prediction Lab — Layer 2 automatic data collection."""
from __future__ import annotations
import json
import base64
import hashlib
from datetime import datetime, timezone
import requests
import pandas as pd
import streamlit as st
from api_football import APIFootballClient, APIFootballError
from api_ninjas import APINinjasClient, APINinjasError
from highlightly import HighlightlyClient, HighlightlyError
from sportmonks import SportmonksClient, SportmonksError
from data_layer2 import collect_team_profile
from sportmonks_layer2 import collect_sportmonks_team_profile, find_upcoming_match_fixture, find_exact_match_fixture, extract_sportmonks_match_details
from sportmonks_candidate_verification import verify_highlightly_candidate
from provider_core import normalize_team_name
from engine import predict_match, WEIGHTS, most_likely_outcome
from tvd import run_tvd
from provider_config import provider_readiness
from livescore_football import LiveScoreFootballClient, LiveScoreFootballError
from competition_crosswalk import build_competition_crosswalk
from provider_health import assess_api_football_status, assess_livescore_metadata
from provider_corroboration import collect_recent_result_corroboration
from highlightly_match_enrichment import collect_highlightly_match_enrichment
from highlightly_player_enrichment import collect_highlightly_player_enrichment
from prediction_evaluation import build_prediction_record, evaluate_prediction_ledger, merge_prediction_records
from prediction_storage import load_prediction_ledger, save_prediction_records
from prediction_results import verified_final_score, group_completed_fixture_candidates, automatic_result_check_due
from prediction_readiness import build_prediction_readiness
from player_availability import assess_player_availability
from statistics_coverage import build_statistics_coverage
from system_diagnostics import build_system_diagnostics
from provider_data_storage import (
    check_provider_storage_connection,
    verify_provider_storage_round_trip,
    build_provider_cache_key,
    load_provider_snapshot,
    save_provider_snapshot,
    record_provider_collection_run,
)
from football_repository import (
    ensure_football_repository, repository_table_counts, import_sportmonks_season,
    get_repository_leagues, get_repository_seasons, get_repository_teams,
    get_repository_fixtures, get_repository_team_history, diagnose_repository_fixture_history,
)

st.set_page_config(page_title="Football Prediction Lab", page_icon="⚽", layout="wide")
st.title("⚽ Football Prediction Lab")
st.caption("Layer 2 • Sportmonks current-season / API-Football historical data collection + weighted prediction engine + TVD")
report_download_slot = st.empty()
report_download_slot.info("Collect data and predict to generate the system report. Its download shortcut will appear here.")
st.session_state.setdefault("prediction_ledger", [])

try:
    DATABASE_URL = st.secrets.get("DATABASE_URL", "")
    PROVIDER_DATABASE_URL = st.secrets.get("PROVIDER_DATABASE_URL", "")
except Exception:
    DATABASE_URL = ""
    PROVIDER_DATABASE_URL = ""

def _ledger_signature(records):
    return json.dumps(records, sort_keys=True, ensure_ascii=False, default=str)

def _upload_report_to_github(report_name, report, latest_path=None):
    """Archive a generated report and maintain a latest copy in GitHub."""
    token = st.secrets.get("GITHUB_REPORT_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_REPORT_TOKEN is not configured in Streamlit Secrets.")

    owner_repo = "Cyber-Ghorst/football-prediction-app"
    safe_name = "".join(
        character.lower() if character.isalnum() else "_"
        for character in str(report_name)
    ).strip("_")
    if not safe_name:
        raise ValueError("A report name is required.")

    generated_at = datetime.now(timezone.utc)
    report_payload = dict(report) if isinstance(report, dict) else {"data": report}
    report_payload.setdefault("generated_at_utc", generated_at.isoformat())
    report_payload.setdefault("report_name", safe_name)
    serialized = json.dumps(
        report_payload, ensure_ascii=False, indent=2, default=str
    ).encode("utf-8")
    content_hash = hashlib.sha256(serialized).hexdigest()
    archive_path = (
        f"reports/{safe_name}/archive/"
        f"{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    latest_path = latest_path or f"reports/{safe_name}/latest.json"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def _put_file(path, message, existing_sha=None):
        api_url = f"https://api.github.com/repos/{owner_repo}/contents/{path}"
        payload = {
            "message": message,
            "content": base64.b64encode(serialized).decode("ascii"),
        }
        if existing_sha:
            payload["sha"] = existing_sha
        saved = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if saved.status_code not in (200, 201):
            raise RuntimeError(
                f"GitHub report upload failed for {path} (HTTP {saved.status_code})."
            )
        result = saved.json()
        return {
            "path": path,
            "html_url": result.get("content", {}).get("html_url"),
            "commit_sha": result.get("commit", {}).get("sha"),
        }

    # The timestamped archive is immutable; the latest copy is replaced on each run.
    archived = _put_file(archive_path, f"Archive {safe_name} report")
    latest_url = f"https://api.github.com/repos/{owner_repo}/contents/{latest_path}"
    current = requests.get(latest_url, headers=headers, timeout=20)
    if current.status_code not in (200, 404):
        raise RuntimeError(
            f"GitHub report lookup failed for {latest_path} (HTTP {current.status_code})."
        )
    latest_sha = current.json().get("sha") if current.status_code == 200 else None
    latest = _put_file(
        latest_path,
        f"Update latest {safe_name} report",
        existing_sha=latest_sha,
    )
    return {
        "archive_path": archived["path"],
        "archive_url": archived["html_url"],
        "latest_path": latest["path"],
        "latest_url": latest["html_url"],
        "content_sha256": content_hash,
    }


def _upload_fixture_diagnostic_to_github(report):
    """Keep the existing fixture-diagnostic path while archiving each run."""
    return _upload_report_to_github(
        "fixture_history",
        report,
        latest_path="reports/fixture_history_diagnostics/latest.json",
    )


def _upload_report_once(report_name, report):
    """Avoid creating duplicate archive commits during ordinary Streamlit reruns."""
    payload = dict(report) if isinstance(report, dict) else {"data": report}
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    uploaded = st.session_state.setdefault("_github_report_fingerprints", {})
    if uploaded.get(report_name) == fingerprint:
        return None
    result = _upload_report_to_github(report_name, payload)
    uploaded[report_name] = fingerprint
    return result


def _load_database_ledger():
    if not DATABASE_URL:
        st.session_state["_ledger_db_status"] = "not_configured"
        st.session_state["_ledger_db_message"] = "Add DATABASE_URL in Streamlit Secrets to enable permanent storage."
        st.session_state["_ledger_db_loaded"] = True
        return
    try:
        database_records = load_prediction_ledger(DATABASE_URL)
        st.session_state["prediction_ledger"] = merge_prediction_records(
            database_records, st.session_state["prediction_ledger"]
        )
        st.session_state["_ledger_db_status"] = "connected"
        st.session_state["_ledger_db_message"] = f"Neon connected • {len(database_records)} saved prediction(s) loaded."
        st.session_state["_ledger_db_last_saved"] = _ledger_signature(st.session_state["prediction_ledger"])
    except Exception:
        st.session_state["_ledger_db_status"] = "error"
        st.session_state["_ledger_db_message"] = "Neon connection failed. Check DATABASE_URL in Streamlit Secrets, then retry."
    st.session_state["_ledger_db_loaded"] = True

def _persist_database_ledger():
    if not DATABASE_URL:
        return
    signature = _ledger_signature(st.session_state["prediction_ledger"])
    if signature == st.session_state.get("_ledger_db_last_saved"):
        return
    try:
        count = save_prediction_records(DATABASE_URL, st.session_state["prediction_ledger"])
        st.session_state["_ledger_db_status"] = "connected"
        st.session_state["_ledger_db_message"] = f"Neon connected • {count} saved prediction(s)."
        st.session_state["_ledger_db_last_saved"] = signature
    except Exception:
        st.session_state["_ledger_db_status"] = "error"
        st.session_state["_ledger_db_message"] = "Could not save to Neon. Your current browser-session data is still available; check DATABASE_URL."

def _sync_completed_sportmonks_results():
    """Fetch each completed fixture once and apply its verified score to blank ledger rows."""
    now = datetime.now(timezone.utc)
    updated = 0
    checked = 0
    skipped = 0
    errors = 0
    records = st.session_state["prediction_ledger"]
    # Repeated predictions for one fixture share a single provider lookup.
    # The helper includes only linked Sportmonks records with a passed kickoff
    # and blank actual-score fields; manual scores are never overwritten.
    fixture_groups = group_completed_fixture_candidates(records, now)
    candidates = fixture_groups[:10]

    if candidates:
        with SportmonksClient() as client:
            for group in candidates:
                representative = group[0]
                try:
                    fixture = client.fixture(
                        representative["fixture_id"],
                        include="participants;scores;state;league;season",
                    )
                    checked += 1
                    if not isinstance(fixture, dict):
                        skipped += 1
                        continue
                    fixture_updated = 0
                    for row in group:
                        score = verified_final_score(row, fixture)
                        if score is None:
                            continue
                        home_goals, away_goals = score
                        row["actual_home_goals"] = home_goals
                        row["actual_away_goals"] = away_goals
                        row["actual_result"] = (
                            "home" if home_goals > away_goals
                            else "away" if home_goals < away_goals
                            else "draw"
                        )
                        row["actual_result_provider"] = "sportmonks"
                        row["actual_result_fixture_id"] = str(fixture.get("id"))
                        row["actual_result_verified_at"] = datetime.now(timezone.utc).isoformat()
                        row["actual_result_verification"] = "exact_fixture_team_competition_season_and_score"
                        updated += 1
                        fixture_updated += 1
                    if not fixture_updated:
                        skipped += 1
                except SportmonksError:
                    errors += 1
                except Exception:
                    errors += 1

    if updated:
        _persist_database_ledger()
    return {
        "eligible_checked": checked,
        "updated": updated,
        "not_verified_or_not_finished": skipped,
        "errors": errors,
        "limit_reached": len(fixture_groups) > 10,
    }

@st.fragment(run_every="15m")
def _automatic_result_collection(enabled):
    """Refresh verified results periodically while this Streamlit session is open."""
    if not enabled:
        st.caption("Automatic result checks are paused. The manual check remains available.")
        return

    now = datetime.now(timezone.utc)
    last_checked = st.session_state.get("_automatic_result_check_last_at")
    if not automatic_result_check_due(last_checked, now, interval_minutes=15):
        st.caption("Automatic result collection is active • next check within 15 minutes.")
        return

    # Set the timestamp before the request so a transient error does not cause
    # repeated API calls on every ordinary Streamlit rerun.
    st.session_state["_automatic_result_check_last_at"] = now
    try:
        with st.spinner("Automatically checking completed Sportmonks fixtures..."):
            report = _sync_completed_sportmonks_results()
        st.caption(
            f"Automatic result check • {report['eligible_checked']} unique fixture(s) checked • "
            f"{report['updated']} verified prediction result(s) saved."
        )
        if report["errors"]:
            st.warning(
                f"{report['errors']} automatic result request(s) failed. "
                "No unverified result was saved; another check will run later."
            )
        if report["limit_reached"]:
            st.info("The automatic check reached its 10-fixture safety limit; remaining fixtures will be checked later.")
        if report["updated"]:
            st.rerun()
    except SportmonksError as exc:
        st.warning(f"Automatic Sportmonks result check failed: {exc}")


if not st.session_state.get("_ledger_db_loaded"):
    _load_database_ledger()

@st.cache_data(ttl=3600, show_spinner=False)
def get_leagues(_client, season):
    return _client.leagues(season)

@st.cache_data(ttl=3600, show_spinner=False)
def get_teams(_client, league_id, season):
    return _client.teams(league_id, season)

@st.cache_data(ttl=1800, show_spinner=False)
def get_standings(_client, league_id, season):
    return _client.standings(league_id, season)

@st.cache_data(ttl=1800, show_spinner=False)
def get_profile(_client, team, league_id, season, standings, include_stats):
    return collect_team_profile(_client, team, league_id, season, standings, include_stats)

def _collect_sportmonks_with_archive(resource_type, request_params, fetcher, ttl_seconds):
    """Read a fresh CockroachDB snapshot or fetch and archive a Sportmonks response."""
    if not PROVIDER_DATABASE_URL:
        return fetcher()

    cache_key = build_provider_cache_key(
        "sportmonks", resource_type, request_params
    )
    try:
        cached = load_provider_snapshot(PROVIDER_DATABASE_URL, cache_key)
        if cached:
            return cached.get("payload")
    except Exception:
        # The archive is an additional persistence layer; a read failure must
        # not prevent a live provider request from supplying prediction data.
        if not st.session_state.get("_provider_archive_read_warning"):
            st.warning(
                "CockroachDB snapshot lookup failed. Live Sportmonks collection "
                "will continue; check the provider archive diagnostics."
            )
            st.session_state["_provider_archive_read_warning"] = True

    try:
        payload = fetcher()
    except Exception as exc:
        try:
            record_provider_collection_run(
                PROVIDER_DATABASE_URL,
                provider="sportmonks",
                resource_type=resource_type,
                cache_key=cache_key,
                succeeded=False,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except Exception:
            pass
        raise

    source_ids = [
        row.get("id") for row in payload
        if isinstance(row, dict) and row.get("id") is not None
    ] if isinstance(payload, list) else []
    try:
        save_provider_snapshot(
            PROVIDER_DATABASE_URL,
            provider="sportmonks",
            resource_type=resource_type,
            cache_key=cache_key,
            request_params=request_params,
            payload=payload,
            source_ids=source_ids,
            ttl_seconds=ttl_seconds,
        )
    except Exception as exc:
        try:
            record_provider_collection_run(
                PROVIDER_DATABASE_URL,
                provider="sportmonks",
                resource_type=resource_type,
                cache_key=cache_key,
                succeeded=False,
                error_type=f"ArchiveWrite:{type(exc).__name__}",
                error_message=str(exc),
            )
        except Exception:
            pass
        # Keep the live response usable even if archival storage is temporarily
        # unavailable. Warn once per Streamlit session rather than hiding it.
        if not st.session_state.get("_provider_archive_write_warning"):
            st.warning(
                "Sportmonks data was collected, but CockroachDB could not archive "
                "the response. Prediction processing can continue."
            )
            st.session_state["_provider_archive_write_warning"] = True
    else:
        try:
            record_provider_collection_run(
                PROVIDER_DATABASE_URL,
                provider="sportmonks",
                resource_type=resource_type,
                cache_key=cache_key,
                succeeded=True,
            )
        except Exception:
            # The snapshot is already safely stored; diagnostics are secondary.
            pass
    return payload


@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_leagues():
    return _collect_sportmonks_with_archive(
        "leagues", {"include": "country"},
        lambda: _fetch_sm_leagues(), 3600,
    )


def _fetch_sm_leagues():
    with SportmonksClient() as sm:
        return sm.available_leagues(include="country")


@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_seasons():
    return _collect_sportmonks_with_archive(
        "seasons", {},
        lambda: _fetch_sm_seasons(), 3600,
    )


def _fetch_sm_seasons():
    with SportmonksClient() as sm:
        return sm.available_seasons()


@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_teams(season_id):
    return _collect_sportmonks_with_archive(
        "teams", {"season_id": int(season_id)},
        lambda: _fetch_sm_teams(season_id), 3600,
    )


def _fetch_sm_teams(season_id):
    with SportmonksClient() as sm:
        return sm.teams_by_season(season_id)


@st.cache_data(ttl=1800, show_spinner=False)
def get_sm_standings(season_id):
    return _collect_sportmonks_with_archive(
        "standings", {"season_id": int(season_id), "include": "participant"},
        lambda: _fetch_sm_standings(season_id), 1800,
    )


def _fetch_sm_standings(season_id):
    with SportmonksClient() as sm:
        return sm.standings_by_season(season_id, include="participant")


@st.cache_data(ttl=1800, show_spinner=False)
def get_sm_fixtures(season_id, include_stats, team_ids):
    normalized_team_ids = [int(value) for value in team_ids]
    return _collect_sportmonks_with_archive(
        "fixtures",
        {
            "season_id": int(season_id),
            "include_statistics": bool(include_stats),
            "team_ids": normalized_team_ids,
        },
        lambda: _fetch_sm_fixtures(season_id, include_stats, normalized_team_ids),
        1800,
    )


def _fetch_sm_fixtures(season_id, include_stats, team_ids):
    with SportmonksClient() as sm:
        return sm.fixtures_by_season(
            season_id,
            include_statistics=include_stats,
            team_ids=team_ids,
        )

with st.sidebar:
    st.header("Data configuration")
    season = st.number_input("Season start year", min_value=2015, max_value=2035, value=2026, step=1,
                             help="For a 2026/27 season, enter 2026. Use the season year supported by your API plan.")
    include_stats = st.checkbox("Fetch match statistics (more API requests)", value=True)
    cross_check_recent_results = st.checkbox(
        "Cross-check recent results with Highlightly and API Ninjas",
        value=True,
        help="Makes additional read-only requests. Results are diagnostic only and do not change prediction inputs.",
    )
    cross_check_highlightly_details = st.checkbox(
        "Cross-check match statistics and lineups with Highlightly",
        value=False,
        help="Optional extra requests: compares up to ten recent matches per selected team and checks lineups for the exact upcoming fixture. Diagnostic only; does not change predictions.",
    )
    cross_check_highlightly_players = st.checkbox(
        "Fetch player and team-season performance statistics",
        value=False,
        help="Uses exact selected-fixture starters. Performs a quota preflight and skips collection when remaining requests are unknown or insufficient. Maximum 22 player-stat requests plus two team-stat requests. Diagnostic only.",
    )
    st.caption("For 2022–2024 add APISPORTS_API_KEY; for 2025+ add SPORTMONKS_API_TOKEN in Streamlit Secrets. Never paste keys into public code.")
    with st.expander("Provider readiness", expanded=True):
        for provider in provider_readiness():
            credential = ("not required" if provider.get("credential_required") is False else ("configured" if provider["credential_configured"] else "not configured"))
            st.write(f"**#{provider['rank']} {provider['provider']} — {provider['role']}**; credential {credential}.")
            st.caption(f"Domains: {', '.join(provider['domains'])}. {provider['app_integration']}. Limitation: {provider['limitation']}")
        run_provider_diagnostics = st.button("Run provider health & coverage check", use_container_width=True)
        test_provider_database = st.button("Test CockroachDB connection", use_container_width=True)
        test_provider_storage = st.button("Verify CockroachDB write/read", use_container_width=True)
        initialize_football_repository = st.button(
            "Initialize central football database", use_container_width=True,
            help="Creates the normalized CockroachDB tables. Does not import or delete football records."
        )
        verify_repository_reads = st.button(
            "Verify central repository reads", use_container_width=True,
            help="Reads leagues, seasons, teams, fixtures and a team's verified completed-match history from CockroachDB."
        )
        upload_fixture_report = st.button(
            "Generate and upload fixture diagnostic report",
            use_container_width=True,
            help="Writes the latest fixture status and score diagnostic to diagnostics/fixture_history_report.json in GitHub."
        )
        if not PROVIDER_DATABASE_URL:
            st.caption("CockroachDB is not configured yet. Add PROVIDER_DATABASE_URL in Streamlit Secrets.")

if test_provider_database:
    if not PROVIDER_DATABASE_URL:
        st.warning("Add PROVIDER_DATABASE_URL in Streamlit Secrets before testing CockroachDB.")
    else:
        try:
            with st.spinner("Testing CockroachDB and preparing provider storage tables..."):
                check_provider_storage_connection(PROVIDER_DATABASE_URL)
            st.success("CockroachDB connected. Provider storage tables are ready.")
        except Exception as exc:
            # Do not display the raw exception: database errors can contain connection details.
            st.error(
                f"CockroachDB connection test failed ({type(exc).__name__}). "
                "Check the connection string and TLS settings in Streamlit Secrets."
            )


if test_provider_storage:
    if not PROVIDER_DATABASE_URL:
        st.warning("Add PROVIDER_DATABASE_URL in Streamlit Secrets before testing CockroachDB storage.")
    else:
        try:
            with st.spinner("Writing a diagnostic snapshot and retrieving it from CockroachDB..."):
                storage_test = verify_provider_storage_round_trip(PROVIDER_DATABASE_URL)
            st.success("CockroachDB storage verified: the diagnostic record was written and read back successfully.")
            st.caption("A short-lived diagnostic snapshot was saved; it expires from the fresh-cache view after five minutes.")
        except Exception as exc:
            # Keep credentials and connection details out of the user-facing error.
            st.error(f"CockroachDB storage verification failed ({type(exc).__name__}). Check the storage tables and database permissions.")


if initialize_football_repository:
    if not PROVIDER_DATABASE_URL:
        st.warning("Add PROVIDER_DATABASE_URL in Streamlit Secrets before initializing the central football database.")
    else:
        try:
            with st.spinner("Creating and verifying the central football database tables..."):
                repository_status = ensure_football_repository(PROVIDER_DATABASE_URL)
                repository_counts = repository_table_counts(PROVIDER_DATABASE_URL)
            st.success(
                f"Central football database ready: {repository_status['table_count']} tables verified."
            )
            st.json({
                "tables": repository_status["tables_created_or_verified"],
                "record_counts": repository_counts,
                "records_imported": 0,
                "existing_provider_snapshots_preserved": True,
                "neon_prediction_ledger_modified": False,
            })
        except Exception as exc:
            st.error(
                f"Central football database initialization failed ({type(exc).__name__}). "
                "Check CockroachDB permissions and the provider database connection."
            )


if upload_fixture_report:
    if not PROVIDER_DATABASE_URL:
        st.warning("Add PROVIDER_DATABASE_URL in Streamlit Secrets before generating the report.")
    else:
        try:
            with st.spinner("Generating the fixture diagnostic and uploading it to GitHub..."):
                fixture_report = diagnose_repository_fixture_history(PROVIDER_DATABASE_URL)
                fixture_report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
                fixture_report["repository"] = "Cyber-Ghorst/football-prediction-app"
                github_report_result = _upload_fixture_diagnostic_to_github(fixture_report)
            st.success("Fixture diagnostic report archived in GitHub.")
            st.write(f"Latest report: {github_report_result['latest_path']}")
            st.write(f"Archived copy: {github_report_result['archive_path']}")
            if github_report_result.get("latest_url"):
                st.markdown(f"[Open latest fixture diagnostic]({github_report_result['latest_url']})")
            if github_report_result.get("archive_url"):
                st.markdown(f"[Open timestamped archive]({github_report_result['archive_url']})")
        except Exception as exc:
            st.error(f"Diagnostic report upload failed ({type(exc).__name__}): {exc}")


if verify_repository_reads:
    if not PROVIDER_DATABASE_URL:
        st.warning("Add PROVIDER_DATABASE_URL in Streamlit Secrets before verifying repository reads.")
    else:
        try:
            with st.spinner("Reading normalized football records from CockroachDB..."):
                repository_leagues = get_repository_leagues(PROVIDER_DATABASE_URL)
                repository_seasons = get_repository_seasons(PROVIDER_DATABASE_URL)
                repository_teams = get_repository_teams(PROVIDER_DATABASE_URL)
                repository_fixture_sample = get_repository_fixtures(
                    PROVIDER_DATABASE_URL, limit=5
                )
                fixture_history_diagnostics = diagnose_repository_fixture_history(
                    PROVIDER_DATABASE_URL
                )
                sample_history = []
                if repository_teams:
                    sample_history = get_repository_team_history(
                        PROVIDER_DATABASE_URL, repository_teams[0]["team_id"], limit=10
                    )
            repository_verification_report = {
                "verification_status": "success",
                "read_counts": {
                    "leagues": len(repository_leagues),
                    "seasons": len(repository_seasons),
                    "teams": len(repository_teams),
                    "fixture_sample_returned": len(repository_fixture_sample),
                    "sample_team_completed_history": len(sample_history),
                },
                "league_names": [row.get("name") for row in repository_leagues],
                "season_names": [row.get("name") for row in repository_seasons],
                "sample_team": (
                    repository_teams[0].get("name") if repository_teams else None
                ),
                "sample_fixtures": repository_fixture_sample,
                "fixture_history_diagnostics": fixture_history_diagnostics,
                "sample_team_history": sample_history,
                "prediction_engine_modified": False,
                "neon_prediction_ledger_modified": False,
            }
            st.success("Central repository read test completed successfully.")
            st.json(repository_verification_report)
            try:
                github_repository_report = _upload_report_once(
                    "central_repository_verification",
                    repository_verification_report,
                )
                if github_repository_report:
                    st.success("Central repository verification report archived in GitHub.")
                    st.markdown(
                        f"[Latest report]({github_repository_report['latest_url']}) · "
                        f"[Timestamped archive]({github_repository_report['archive_url']})"
                    )
                else:
                    st.caption("This unchanged verification report is already archived in GitHub.")
            except Exception as upload_exc:
                st.warning(
                    f"Verification completed, but GitHub report upload failed "
                    f"({type(upload_exc).__name__}). Check GITHUB_REPORT_TOKEN permissions."
                )
        except Exception as exc:
            st.error(
                f"Central repository read verification failed ({type(exc).__name__}). "
                "Check that the repository schema and CockroachDB connection are ready."
            )


client = None
leagues = []
if int(season) <= 2024:
    try:
        client = APIFootballClient()
        leagues = get_leagues(client, int(season))
    except APIFootballError as exc:
        st.error(str(exc))
        st.markdown("**Setup:** add APISPORTS_API_KEY to Streamlit Secrets for historical seasons 2022–2024.")
        st.stop()

try:
    if run_provider_diagnostics:
        st.subheader("Provider health and competition coverage")
        try:
            if client is None:
                st.info("API-Football diagnostics skipped for this season; your account only supports seasons 2022–2024.")
            else:
                api_status = assess_api_football_status(client.status())
                st.write("**API-Football account status**")
                st.json(api_status)
        except APIFootballError as exc:
            st.warning(f"API-Football status could not be verified: {exc}")
        try:
            with APINinjasClient() as ninjas_client:
                ninjas_ok = ninjas_client.test_connection()
                ninjas_metadata = dict(ninjas_client.last_metadata)
            st.write("**API Ninjas connection test**")
            st.json({
                "transport_status": "responding" if ninjas_ok else "unknown",
                "credential_configured": True,
                "quota_metadata": ninjas_metadata,
                "fallback_enabled": False,
                "note": "Connection verified; match records are not yet wired into Layer 2.",
            })
        except APINinjasError as exc:
            st.warning(f"API Ninjas connection could not be verified: {exc}")
        try:
            with HighlightlyClient() as highlightly_client:
                highlightly_status = highlightly_client.test_connection()
            st.write("**Highlightly connection test**")
            st.json({
                **highlightly_status,
                "credential_configured": True,
                "fallback_enabled": False,
                "note": "Connection verified; match records are not yet wired into Layer 2.",
            })
        except HighlightlyError as exc:
            st.warning(f"Highlightly connection could not be verified: {exc}")
        try:
            with SportmonksClient() as sportmonks_client:
                sportmonks_status = sportmonks_client.test_connection()
            st.write("**Sportmonks Football API v3 connection test**")
            st.json({
                **sportmonks_status,
                "credential_configured": True,
                "current_season_primary": "candidate; validate selected league and season before use",
            })
        except SportmonksError as exc:
            st.warning(f"Sportmonks connection could not be verified: {exc}")
        try:
            with LiveScoreFootballClient() as live_client:
                live_health = live_client.health()
                live_meta = live_client.meta()
                live_competitions = live_client.leagues(kind="club", available=True)
            st.write("**LiveScoreFootball service health**")
            st.json({"health": live_health, "metadata_assessment": assess_livescore_metadata(live_meta)})
            if int(season) > 2024:
                crosswalk_source = get_sm_leagues()
                crosswalk_provider = "sportmonks"
            else:
                crosswalk_source = leagues
                crosswalk_provider = "api_football"
            crosswalk = build_competition_crosswalk(
                crosswalk_source,
                live_competitions,
                requested_season=int(season),
                source_provider=crosswalk_provider,
            )
            st.write(f"**{crosswalk_provider.replace('_', ' ').title()} → LiveScoreFootball competition crosswalk**")
            st.caption("Verification requires exact competition/country identity, matching season, active stored data, and a fresh per-competition coverage.lastSyncedAt timestamp. Fixture-level update timestamps must also be fresh before any individual fixture can be considered. Automatic fallback remains disabled.")
            if crosswalk:
                st.dataframe([
                    {key: row.get(key) for key in (
                        "source_provider", "source_competition_id", "name", "country",
                        "livescore_slug", "livescore_season", "coverage_freshness",
                        "verified", "reason"
                    )}
                    for row in crosswalk
                ], use_container_width=True, hide_index=True)
            else:
                st.info("No competition crosswalk candidates were returned.")
        except LiveScoreFootballError as exc:
            st.warning(f"LiveScoreFootball could not be verified: {exc}")
    sportmonks_mode = int(season) > 2024
    selected_season_id = None
    if sportmonks_mode:
        try:
            sm_leagues = get_sm_leagues()
            sm_seasons = get_sm_seasons()
        except SportmonksError as exc:
            st.error(f"Sportmonks competition discovery failed: {exc}")
            st.stop()

        league_by_id = {int(row["id"]): row for row in sm_leagues if row.get("id") is not None}
        eligible_seasons = [
            row for row in sm_seasons
            if row.get("league_id") is not None
            and (str(row.get("starting_at") or "")[:4].isdigit()
                 and int(str(row.get("starting_at"))[:4]) == int(season)
                 or str(row.get("name") or "").startswith(str(int(season))))
        ]
        eligible_league_ids = {int(row["league_id"]) for row in eligible_seasons}
        league_options = {}
        for league_id_value in sorted(eligible_league_ids):
            league = league_by_id.get(league_id_value)
            if not league:
                continue
            country = league.get("country") or {}
            league_options[f"{league.get('name', 'Unknown league')} — {country.get('name', 'Unknown country')}"] = league_id_value
        if not league_options:
            st.warning(f"Sportmonks returned no covered competitions with a season starting in {int(season)}. This is a coverage result, not a reason to substitute another competition.")
            st.stop()
        selected_league = st.selectbox("Sportmonks competition", list(league_options))
        league_id = int(league_options[selected_league])
        matching_seasons = [row for row in eligible_seasons if int(row["league_id"]) == league_id]
        season_options = {
            f"{row.get('name') or row.get('starting_at')} (season ID {row['id']})": int(row["id"])
            for row in matching_seasons if row.get("id") is not None
        }
        if not season_options:
            st.warning("No exact Sportmonks season ID was found for this competition and start year.")
            st.stop()
        selected_season_label = st.selectbox("Verified season", list(season_options))
        selected_season_id = season_options[selected_season_label]
        try:
            team_rows = get_sm_teams(selected_season_id)
        except SportmonksError as exc:
            st.error(f"Sportmonks team coverage could not be loaded: {exc}")
            st.stop()
        team_map = {str(row.get("name")): row for row in team_rows if row.get("id") is not None and row.get("name")}
        st.caption(f"Sportmonks source mapping: league ID {league_id} → season ID {selected_season_id}. Team IDs are retained from the same provider.")

        if st.button(
            "Import selected Sportmonks season into central database",
            use_container_width=True,
            help="Imports the selected league, season, teams and season fixtures into CockroachDB. Existing records are updated safely; Neon is not touched."
        ):
            if not PROVIDER_DATABASE_URL:
                st.warning("Configure PROVIDER_DATABASE_URL before importing into the central database.")
            else:
                try:
                    selected_season_row = next(
                        row for row in matching_seasons
                        if int(row.get("id")) == int(selected_season_id)
                    )
                    selected_team_ids = tuple(sorted(
                        int(row["id"]) for row in team_rows if row.get("id") is not None
                    ))
                    with st.spinner("Collecting and importing the selected Sportmonks season..."):
                        season_fixtures = get_sm_fixtures(
                            int(selected_season_id), False, selected_team_ids
                        )
                        import_report = import_sportmonks_season(
                            PROVIDER_DATABASE_URL,
                            league=league_by_id[int(league_id)],
                            season=selected_season_row,
                            teams=team_rows,
                            fixtures=season_fixtures,
                        )
                        current_counts = repository_table_counts(PROVIDER_DATABASE_URL)
                    st.success("Sportmonks season imported into the central football database.")
                    st.json({
                        "import_report": import_report,
                        "central_table_counts": current_counts,
                    })
                except SportmonksError as exc:
                    st.error(f"Sportmonks season collection failed: {exc}")
                except Exception as exc:
                    st.error(
                        f"Central season import failed ({type(exc).__name__}). "
                        "No prediction ledger changes were made. Check the selected season data and CockroachDB."
                    )
    else:
        league_options = {f"{x['league']['name']} — {x.get('country',{}).get('name','')}": x['league']['id']
                          for x in leagues if x.get('league',{}).get('id')}
        if not league_options:
            st.warning("No competitions were returned for this season under the API-Football account.")
            st.stop()
        selected_league = st.selectbox("API-Football competition", list(league_options))
        league_id = int(league_options[selected_league])
        team_rows = get_teams(client, league_id, int(season))
        team_map = {x['team']['name']: x['team'] for x in team_rows if x.get('team',{}).get('id')}
    if len(team_map) < 2:
        st.warning("The selected provider returned fewer than two teams for this competition and season.")
        st.stop()
    c1,c2 = st.columns(2)
    with c1: home_name = st.selectbox("Home team", list(team_map))
    with c2:
        away_name = st.selectbox("Away team", [x for x in team_map if x != home_name])
    with st.expander("Opta Supercomputer benchmark (optional)"):
        st.caption("Enter published Opta Analyst match probabilities as a separate benchmark. Do not treat Opta as ground truth or copy market odds into these fields.")
        record_opta_benchmark = st.checkbox("Record Opta probabilities for this fixture", value=False)
        opta_home = opta_draw = opta_away = None
        opta_source_url = ""
        if record_opta_benchmark:
            oc1, oc2, oc3 = st.columns(3)
            with oc1:
                opta_home = st.number_input("Opta home win %", min_value=0.0, max_value=100.0, value=None, placeholder="Unknown", key="opta_home")
            with oc2:
                opta_draw = st.number_input("Opta draw %", min_value=0.0, max_value=100.0, value=None, placeholder="Unknown", key="opta_draw")
            with oc3:
                opta_away = st.number_input("Opta away win %", min_value=0.0, max_value=100.0, value=None, placeholder="Unknown", key="opta_away")
            opta_source_url = st.text_input("Opta Analyst source URL", placeholder="Paste the public match-prediction article URL", key="opta_source_url")
            if all(value is not None for value in (opta_home, opta_draw, opta_away)):
                if abs(opta_home + opta_draw + opta_away - 100.0) > 0.6:
                    st.warning("Opta probabilities must sum to 100%. They will not be saved until corrected.")
                elif not opta_source_url.strip():
                    st.warning("Add the Opta Analyst source URL so this benchmark can be audited.")
    # TVD inputs are collected before the action button so Streamlit reruns retain them.
    use_tvd = st.checkbox("Use manually evidenced TVD ratings for this matchup", value=False)
    tvd_profiles = None
    if use_tvd:
        st.info("Enter evidence-backed scores only. Blank fields remain unknown and are excluded.")
        vulnerabilities = ["space_behind","press_resistance","aerial_defence","transition_recovery","central_compactness","wide_defending","central_penetration"]
        weapons = ["pace_through_balls","pressing_intensity","aerial_threat","counterattack_threat","midfield_overloads","wing_threat","between_lines_threat"]
        def profile_inputs(name, prefix):
            profile={"name":name,"vulnerabilities":{},"weapons":{}}
            confidence=st.slider(f"{name} TVD evidence confidence",0,100,60,5,key=f"{prefix}_conf")
            left,right=st.columns(2)
            with left:
                st.markdown("**Defensive vulnerabilities**")
                for key in vulnerabilities:
                    value=st.number_input(f"{key}",min_value=0,max_value=100,value=None,placeholder="Unknown",key=f"{prefix}_v_{key}")
                    if value is not None: profile["vulnerabilities"][key]={"score":value,"confidence":confidence}
            with right:
                st.markdown("**Attacking weapons**")
                for key in weapons:
                    value=st.number_input(f"{key}",min_value=0,max_value=100,value=None,placeholder="Unknown",key=f"{prefix}_w_{key}")
                    if value is not None: profile["weapons"][key]={"score":value,"confidence":confidence}
            return profile
        left,right=st.columns(2)
        with left: home_tvd=profile_inputs(home_name,"home")
        with right: away_tvd=profile_inputs(away_name,"away")
        tvd_profiles=(home_tvd,away_tvd)

    if st.button("Collect data and predict", type="primary", use_container_width=True):
        player_report = None
        selected_match_fixture = None
        prediction_fixture = None
        highlightly_enrichment = None
        corroboration = None
        with st.spinner("Collecting recent results, standings and available match statistics..."):
            if sportmonks_mode:
                try:
                    standings = get_sm_standings(selected_season_id)
                except SportmonksError as exc:
                    st.error(f"Sportmonks standings collection failed: {exc}")
                    st.stop()
                try:
                    fixtures = get_sm_fixtures(
                        selected_season_id,
                        include_stats,
                        [
                            int(team_map[home_name]["id"]),
                            int(team_map[away_name]["id"]),
                        ],
                    )
                except SportmonksError as exc:
                    st.error(f"Sportmonks fixture collection failed: {exc}")
                    st.stop()
                home = collect_sportmonks_team_profile(team_map[home_name], selected_season_id, fixtures, standings)
                away = collect_sportmonks_team_profile(team_map[away_name], selected_season_id, fixtures, standings)

                # Ledger identity uses the closest exact pairing in this season,
                # including live/completed fixtures. Lineup enrichment stays upcoming-only.
                prediction_fixture = find_exact_match_fixture(
                    fixtures,
                    home_team_id=int(team_map[home_name]["id"]),
                    away_team_id=int(team_map[away_name]["id"]),
                    season_id=int(selected_season_id),
                )
                selected_match_fixture = find_upcoming_match_fixture(
                    fixtures,
                    home_team_id=int(team_map[home_name]["id"]),
                    away_team_id=int(team_map[away_name]["id"]),
                    season_id=int(selected_season_id),
                )
                if selected_match_fixture:
                    try:
                        with SportmonksClient() as detail_client:
                            match_detail = detail_client.fixture(
                                selected_match_fixture["id"],
                                include="participants;state;lineups.details.type;formations;sidelined.player;sidelined.type;sidelined.sideline",
                            )
                        if match_detail:
                            match_details = extract_sportmonks_match_details(
                                match_detail,
                                home_team_id=int(team_map[home_name]["id"]),
                                away_team_id=int(team_map[away_name]["id"]),
                                season_id=int(selected_season_id),
                            )
                            home["lineups"] = match_details["teams"]["home"]
                            away["lineups"] = match_details["teams"]["away"]
                            home["availability"] = match_details["availability"]["home"]
                            away["availability"] = match_details["availability"]["away"]
                        else:
                            st.info("Sportmonks returned no detail record for the exact selected fixture; lineups and player availability remain unknown.")
                    except Exception as exc:
                        st.warning(f"Fixture-specific Sportmonks lineups/sidelined data unavailable: {exc}. Prediction inputs remain unchanged.")
                else:
                    st.info("No exact upcoming Sportmonks fixture was found for this home/away pairing. Lineups and player availability remain unknown.")

                if cross_check_recent_results or cross_check_highlightly_details or cross_check_highlightly_players:
                    selected_league_row = league_by_id.get(league_id, {})
                    selected_country = selected_league_row.get("country") or {}
                    selected_country_name = selected_country.get("name") if isinstance(selected_country, dict) else str(selected_country or "")
                    hl_client = ninjas_client = None
                    corroboration_errors = {}
                    try:
                        hl_client = HighlightlyClient()
                    except HighlightlyError as exc:
                        corroboration_errors["highlightly"] = str(exc)
                    if cross_check_recent_results:
                        try:
                            ninjas_client = APINinjasClient()
                        except APINinjasError as exc:
                            corroboration_errors["api_ninjas"] = str(exc)

                    corroboration = None
                    highlightly_enrichment = None
                    try:
                        if cross_check_recent_results:
                            corroboration = collect_recent_result_corroboration(
                                sportmonks_fixtures=fixtures,
                                competition=str(selected_league_row.get("name") or selected_league),
                                country=selected_country_name,
                                season=int(season),
                                sportmonks_season_id=int(selected_season_id),
                                home_team_name=home_name,
                                away_team_name=away_name,
                                highlightly_client=hl_client,
                                api_ninjas_client=ninjas_client,
                            )
                            corroboration["errors"].update(corroboration_errors)

                            # Target each unmatched Highlightly result by its UTC calendar date.
                            # This deliberately bypasses the ten-match history sample and remains
                            # diagnostic-only: no candidate is appended to either team profile.
                            candidate_rows = []
                            seen_candidate_keys = set()
                            for team_report in (corroboration.get("team_history_coverage") or {}).values():
                                for candidate in team_report.get("unmatched_completed_candidates") or []:
                                    candidate_key = str(candidate.get("highlightly_match_id") or "|".join((
                                        str(candidate.get("kickoff_utc") or ""),
                                        str(candidate.get("home") or ""),
                                        str(candidate.get("away") or ""),
                                    )))
                                    if candidate_key not in seen_candidate_keys:
                                        seen_candidate_keys.add(candidate_key)
                                        candidate_rows.append(candidate)

                            candidate_verification = []
                            if candidate_rows:
                                try:
                                    with SportmonksClient() as verifier_client:
                                        fixtures_by_date = {}
                                        for candidate in candidate_rows:
                                            try:
                                                candidate_kickoff = datetime.fromisoformat(
                                                    str(candidate.get("kickoff_utc")).replace("Z", "+00:00")
                                                )
                                                if candidate_kickoff.tzinfo is None:
                                                    candidate_kickoff = candidate_kickoff.replace(tzinfo=timezone.utc)
                                                candidate_date = candidate_kickoff.astimezone(timezone.utc).date().isoformat()
                                            except (TypeError, ValueError):
                                                candidate_verification.append({
                                                    "highlightly_match_id": candidate.get("highlightly_match_id"),
                                                    "verification_status": "invalid_highlightly_kickoff",
                                                })
                                                continue

                                            if candidate_date not in fixtures_by_date:
                                                fixtures_by_date[candidate_date] = verifier_client.fixtures_between(
                                                    candidate_date,
                                                    candidate_date,
                                                    include="participants;state;scores",
                                                )
                                            candidate_team_mapping = {}

                                            def exact_team_id(candidate_team_name):
                                                target_name = normalize_team_name(candidate_team_name or "")
                                                matches = [
                                                    row for name, row in team_map.items()
                                                    if normalize_team_name(name) == target_name
                                                ]
                                                if len(matches) == 1:
                                                    candidate_team_mapping[str(candidate_team_name)] = {
                                                        "team_id": int(matches[0]["id"]),
                                                        "status": "exact_name_resolved_from_selected_season_team_list",
                                                        "matched_provider_names": [str(matches[0].get("name") or "")],
                                                    }
                                                    return int(matches[0]["id"])
                                                # Candidate opponents may not be present in the selected
                                                # season's team list. Resolve only from exact participant
                                                # names returned by Sportmonks for this candidate date.
                                                from sportmonks_candidate_verification import resolve_candidate_team_id
                                                resolution = resolve_candidate_team_id(
                                                    candidate_team_name,
                                                    fixtures_by_date[candidate_date],
                                                )
                                                candidate_team_mapping[str(candidate_team_name)] = resolution
                                                return resolution["team_id"]

                                            report = verify_highlightly_candidate(
                                                candidate,
                                                fixtures_by_date[candidate_date],
                                                season_id=int(selected_season_id),
                                                league_id=int(league_id),
                                                home_team_id=exact_team_id(candidate.get("home")),
                                                away_team_id=exact_team_id(candidate.get("away")),
                                            )
                                            report["team_mapping_details"] = candidate_team_mapping
                                            report["sportmonks_request_metadata"] = dict(
                                                verifier_client.last_metadata or {}
                                            )
                                            candidate_verification.append(report)
                                except SportmonksError as exc:
                                    corroboration["errors"]["sportmonks_candidate_verification"] = str(exc)
                            corroboration["candidate_verification"] = candidate_verification

                        if cross_check_highlightly_details or cross_check_highlightly_players:
                            if hl_client is None:
                                corroboration_errors["highlightly_details"] = corroboration_errors.get(
                                    "highlightly", "Highlightly client unavailable."
                                )
                            else:
                                highlightly_enrichment = collect_highlightly_match_enrichment(
                                    client=hl_client,
                                    sportmonks_fixtures=fixtures,
                                    competition=str(selected_league_row.get("name") or selected_league),
                                    country=selected_country_name,
                                    season=int(season),
                                    home_team_name=home_name,
                                    away_team_name=away_name,
                                    selected_upcoming_fixture=selected_match_fixture,
                                    history_per_team=10 if cross_check_highlightly_details else 0,
                                )
                    except Exception as exc:
                        st.warning(f"Optional Highlightly enrichment could not be completed: {exc}. Sportmonks prediction inputs remain unchanged.")
                    finally:
                        if hl_client is not None:
                            hl_client.close()
                        if ninjas_client is not None:
                            ninjas_client.close()

                    if cross_check_recent_results:
                        if corroboration is not None:
                            st.subheader("Independent result corroboration")
                            st.caption("This report compares matching fixtures only. It does not replace Sportmonks data or alter prediction calculations.")
                            st.json({
                                key: value for key, value in corroboration.items()
                                if key not in {"matches", "team_history_coverage"}
                            })
                            st.markdown("**Independent team-history check (Highlightly)**")
                            st.caption("Compares completed, score-valid results by exact competition, season, team orientation and kickoff. Any unmatched Highlightly result is a review candidate only; it is not added to the model history.")
                            history_checks = corroboration.get("team_history_coverage") or {}
                            history_columns = st.columns(2)
                            for history_column, team_label in zip(history_columns, (home_name, away_name)):
                                with history_column:
                                    st.markdown(f"**{team_label}**")
                                    history_check = history_checks.get(team_label)
                                    if history_check:
                                        st.metric(
                                            "Highlightly completed matches",
                                            history_check.get("highlightly_completed_score_valid", 0),
                                            help="Completed Highlightly results with a valid home-away score in the exact selected competition and season.",
                                        )
                                        st.write(
                                            f"Sportmonks: {history_check.get('sportmonks_completed_score_valid', 0)}; "
                                            f"exact cross-source matches: {history_check.get('exact_matches_across_sources', 0)}; "
                                            f"unmatched candidates: {history_check.get('highlightly_results_not_found_in_sportmonks', 0)}."
                                        )
                                        if history_check.get("unmatched_completed_candidates"):
                                            st.warning("Highlightly reported completed result(s) not found among Sportmonks' completed, score-valid fixtures. Review the candidates below; none has been added automatically.")
                                        st.json(history_check)
                                    else:
                                        st.info("No independent Highlightly history report was available for this team.")
                            if corroboration.get("candidate_verification"):
                                with st.expander("Targeted Sportmonks verification of unmatched Highlightly candidates", expanded=True):
                                    st.caption("Each candidate is checked against Sportmonks fixtures returned for its UTC date, using exact season, competition, home/away team IDs and kickoff. This is diagnostic only; no candidate is imported.")
                                    st.json(corroboration["candidate_verification"])
                        if corroboration is None:
                            st.warning("Cross-provider result corroboration did not complete; Sportmonks prediction data remains unchanged.")
                        elif corroboration.get("matches"):
                            with st.expander("Matched source records and field-level result conflicts", expanded=True):
                                for match_record in corroboration["matches"]:
                                    st.write(
                                        f"{match_record.get('home', {}).get('name')} vs "
                                        f"{match_record.get('away', {}).get('name')} — "
                                        f"{match_record.get('kickoff_utc')}"
                                    )
                                    st.json({
                                        "selected_score": [match_record.get("home_score"), match_record.get("away_score")],
                                        "source_ids": match_record.get("source_ids"),
                                        "diagnostic_status": match_record.get("diagnostic_status"),
                                        "agreement_fields": match_record.get("agreement_fields"),
                                        "conflict_fields": match_record.get("conflict_fields"),
                                        "providers_seen": match_record.get("providers_seen"),
                                        "field_observations": match_record.get("field_observations"),
                                        "reconciliation": match_record.get("reconciliation"),
                                    })
                        elif corroboration_errors or corroboration.get("errors"):
                            st.warning("No cross-provider fixture could be reconciled. Check provider errors and exact competition/team identity mapping.")
                        else:
                            st.info("No exact cross-provider fixture matches were found. No substitute data was used.")

                    if cross_check_highlightly_details:
                        st.subheader("Highlightly match-statistics and lineup corroboration")
                        st.caption("Only exact competition, country, season, home/away and kickoff matches are compared. Highlightly values remain diagnostic and never overwrite Sportmonks prediction inputs.")
                        if highlightly_enrichment is not None:
                            st.json({
                                key: value for key, value in highlightly_enrichment.items()
                                if key not in {"statistics", "lineups"}
                            })
                            with st.expander("Highlightly statistics: source observations and disagreements", expanded=True):
                                st.json(highlightly_enrichment.get("statistics", []))
                            with st.expander("Highlightly selected-fixture lineups"):
                                if highlightly_enrichment.get("lineups"):
                                    st.json(highlightly_enrichment["lineups"])
                                else:
                                    st.info("No exact Highlightly lineup record was available. The selected fixture's lineup remains unknown from this provider.")
                            if highlightly_enrichment.get("errors"):
                                st.warning(highlightly_enrichment["errors"])
                        else:
                            st.warning("Highlightly statistics and lineup corroboration did not complete. No substitute data was used.")

                    if cross_check_highlightly_players:
                        st.subheader("Highlightly player and team-season performance")
                        st.caption("Player statistics are matched by Highlightly player ID, exact club, competition and season. Only provider-reported starters are queried; no names-only joins or availability inferences are made.")
                        if highlightly_enrichment is not None:
                            try:
                                with HighlightlyClient() as player_client:
                                    selected_lineups = highlightly_enrichment.get("lineups")
                                    quota_preflight = (
                                        player_client.test_connection()
                                        if selected_lineups else {"metadata": {}}
                                    )
                                    player_report = collect_highlightly_player_enrichment(
                                        client=player_client,
                                        lineups=selected_lineups,
                                        competition=str(selected_league_row.get("name") or selected_league),
                                        season=int(season),
                                        home_team_name=home_name,
                                        away_team_name=away_name,
                                        from_date=f"{int(season)}-01-01",
                                        timezone_name="Africa/Nairobi",
                                        max_players=22,
                                        require_quota_metadata=True,
                                    )
                                    player_report["quota_preflight"] = quota_preflight.get("metadata", {})
                                st.json({
                                    key: value for key, value in player_report.items()
                                    if key not in {"players", "teams", "unknown_players", "errors"}
                                })
                                with st.expander("Exact player season statistics", expanded=True):
                                    st.json(player_report.get("players", []))
                                with st.expander("Team season statistics"):
                                    st.json(player_report.get("teams", {}))
                                if player_report.get("unknown_players"):
                                    st.json({"players_without_exact_statistics": player_report["unknown_players"]})
                                if player_report.get("errors"):
                                    st.warning(player_report["errors"])
                            except Exception as exc:
                                st.warning(f"Highlightly player statistics unavailable: {exc}. No player data was inferred.")
                        else:
                            st.info("Player statistics were not requested because the exact selected-fixture Highlightly lineup was unavailable.")

            else:
                standings = get_standings(client, league_id, int(season))
                home = get_profile(client, team_map[home_name], league_id, int(season), standings, include_stats)
                away = get_profile(client, team_map[away_name], league_id, int(season), standings, include_stats)
        # Player availability is scored only when the provider supplies a complete
        # roster, known statuses and evidenced player-importance weights.
        for profile in (home, away):
            availability_evidence = profile.get("availability") or {}
            assessment = assess_player_availability(availability_evidence)
            profile["player_availability_assessment"] = assessment
            profile["player_availability"] = assessment["score"]

        st.subheader("Data validation")
        if st.session_state.get("_latest_collection_report_github_url"):
            st.caption("Full data-collection evidence is archived in GitHub.")
            st.markdown(
                f"[Open latest collection report]({st.session_state['_latest_collection_report_github_url']})"
                + (
                    f" · [Open timestamped archive]({st.session_state['_latest_collection_report_github_archive_url']})"
                    if st.session_state.get("_latest_collection_report_github_archive_url") else ""
                )
            )
        for profile in (home, away):
            quality = profile["data_quality"]
            st.write(f"**{profile['name']}** — source: {quality.get('provider', 'api_football')}; {quality['matches_returned']} completed matches; {quality['opponent_strength_matches']} with opponent-strength data; {quality['statistics_matches']} with match statistics; {quality.get('statistics_observations', 0)} normalized statistic observations.")

        with st.expander("History Collection Diagnostics", expanded=True):
            st.caption(
                "Shows how each selected team's season fixtures were screened. "
                "Counters follow the collection pipeline; missing season IDs are reported separately "
                "and are not silently described as confirmed same-season records."
            )
            history_columns = st.columns(2)
            for column, profile in zip(history_columns, (home, away)):
                with column:
                    st.markdown(f"**{profile['name']}**")
                    history_report = profile.get("history_collection_diagnostics")
                    if history_report:
                        st.metric(
                            "Valid completed matches",
                            f"{history_report.get('fixtures_with_valid_scores', 0)}",
                            help="Finished fixtures for this team with both home and away scores available.",
                        )
                        st.json(history_report)
                    else:
                        st.info(
                            "Detailed fixture-screening counters are not supplied by this data path."
                        )

        readiness = build_prediction_readiness(
            home,
            away,
            selected_fixture=selected_match_fixture,
            home_team_id=int(team_map[home_name]["id"]),
            away_team_id=int(team_map[away_name]["id"]),
            season_id=int(selected_season_id) if selected_season_id is not None else None,
        )
        statistics_reports = {
            profile["name"]: build_statistics_coverage(profile.get("matches", []))
            for profile in (home, away)
        }
        diagnostic_report = build_system_diagnostics(
            season=int(season),
            competition=selected_league,
            home_profile=home,
            away_profile=away,
            readiness=readiness,
            statistics_coverage=statistics_reports,
            provider_configuration=provider_readiness(),
            corroboration=corroboration,
            model_weights=WEIGHTS,
        )
        collection_evidence_report = {
            "season": int(season),
            "competition": selected_league,
            "selected_fixture": selected_match_fixture,
            "teams": {
                profile["name"]: {
                    "data_quality": profile.get("data_quality"),
                    "history_collection_diagnostics": profile.get("history_collection_diagnostics"),
                    "player_availability_assessment": profile.get("player_availability_assessment"),
                }
                for profile in (home, away)
            },
            "statistics_coverage": statistics_reports,
            "prediction_readiness": readiness,
            "corroboration": corroboration,
            "player_enrichment": player_report,
            "system_diagnostics": diagnostic_report,
        }
        try:
            github_collection_report = _upload_report_once(
                "data_collection_evidence", collection_evidence_report
            )
            if github_collection_report:
                st.session_state["_latest_collection_report_github_url"] = github_collection_report.get("latest_url")
                st.session_state["_latest_collection_report_github_archive_url"] = github_collection_report.get("archive_url")
        except Exception as upload_error:
            st.warning(f"Data collection evidence report could not be archived to GitHub ({type(upload_error).__name__}). Check GITHUB_REPORT_TOKEN and GitHub permissions.")
        try:
            github_system_report = _upload_report_once("system_diagnostics", diagnostic_report)
            if github_system_report:
                st.session_state["_latest_system_report_github_url"] = github_system_report.get("latest_url")
                st.session_state["_latest_system_report_github_archive_url"] = github_system_report.get("archive_url")
        except Exception as upload_error:
            st.warning(f"System report could not be archived to GitHub ({type(upload_error).__name__}). Check GITHUB_REPORT_TOKEN and GitHub permissions.")
        st.subheader("Automated System Health & Diagnostics")
        if st.session_state.get("_latest_system_report_github_url"):
            st.caption("System report is archived in GitHub automatically.")
            st.markdown(
                f"[Open latest system report]({st.session_state['_latest_system_report_github_url']})"
                + (
                    f" · [Open timestamped archive]({st.session_state['_latest_system_report_github_archive_url']})"
                    if st.session_state.get("_latest_system_report_github_archive_url") else ""
                )
            )
        st.caption("Automatically generated after each data collection. Provider credentials are shown only as configured/not configured; actual connectivity is tested separately using the provider health button. This report is read-only.")
        diagnostic_status = diagnostic_report["overall_status"]
        if diagnostic_status == "healthy":
            st.success("System diagnostics: healthy")
        elif diagnostic_status == "blocked":
            st.error("System diagnostics: blocked — critical data or configuration checks failed")
        else:
            st.warning("System diagnostics: attention required — review the checks below")
        summary_columns = st.columns(4)
        summary_columns[0].metric("Checks", diagnostic_report["summary"]["checks_total"])
        summary_columns[1].metric("Passed", diagnostic_report["summary"]["passed"])
        summary_columns[2].metric("Warnings", diagnostic_report["summary"]["warnings"])
        summary_columns[3].metric("Failed", diagnostic_report["summary"]["failed"])
        st.subheader("Recommended next steps")
        st.caption(
            "The diagnostic report is analyzed automatically in memory after collection. "
            "You do not need to download or upload the JSON to get these recommendations."
        )
        recommended_actions = diagnostic_report.get("recommended_actions", [])
        if recommended_actions:
            for index, action in enumerate(recommended_actions, start=1):
                priority_label = "URGENT" if action["priority"] == "urgent" else "NEXT"
                st.markdown(f"**{index}. {priority_label} — {action['issue']}**")
                st.write(action["action"])
        else:
            st.success("No corrective actions are currently recommended by the available checks.")
        with st.expander("Diagnostic checks and recommended actions", expanded=False):
            st.dataframe(
                pd.DataFrame(diagnostic_report["checks"]),
                use_container_width=True,
                hide_index=True,
            )
            st.json({
                "selected_context": diagnostic_report["selected_context"],
                "providers": diagnostic_report["providers"],
                "fixture": diagnostic_report["fixture"],
                "teams": diagnostic_report["teams"],
                "corroboration": diagnostic_report["corroboration"],
                "model_configuration": diagnostic_report["model_configuration"],
            })
        with report_download_slot.container():
            st.success(f"System report ready — {diagnostic_report['overall_status'].replace('_', ' ').title()}")
            st.download_button(
                "⬇️ Download system report (JSON)",
                data=json.dumps(diagnostic_report, indent=2, default=str).encode("utf-8"),
                file_name="football_prediction_system_diagnostics.json",
                mime="application/json",
                use_container_width=True,
                key="top_system_diagnostics_download",
                on_click="ignore",
            )
        st.download_button(
            "Download complete system diagnostic (JSON)",
            data=json.dumps(diagnostic_report, indent=2, default=str).encode("utf-8"),
            file_name="football_prediction_system_diagnostics.json",
            mime="application/json",
            use_container_width=True,
            on_click="ignore",
        )
        st.subheader("Upcoming fixture & prediction readiness")
        st.caption("A transparent diagnostic of exact fixture identity, recent-history depth and evidence coverage. Unknown data remains unknown; this report does not alter the model.")
        status_labels = {
            "ready": "Ready — exact fixture verified and both teams meet the five-match minimum",
            "limited_history": "Limited sample — prediction allowed; at least one team has 5–9 completed matches (10 preferred)",
            "fixture_unverified": "Fixture unverified — matchup comparison may be possible, but no exact upcoming fixture is confirmed",
            "insufficient_history": "Insufficient history — at least one team has fewer than five completed matches",
        }
        st.info(status_labels.get(readiness["overall_status"], readiness["overall_status"]))
        fixture_diagnostic = readiness["fixture"]
        freshness = fixture_diagnostic.get("source_freshness", "unknown")
        if freshness == "fresh":
            st.success("Fixture data is fresh — retrieved less than 24 hours ago.")
        elif freshness == "stale":
            st.warning("Fixture data is stale — retrieved 24 hours ago or earlier. Refresh it before relying on it.")
        else:
            st.info("Fixture data freshness is unknown — no valid retrieval age is available.")
        if fixture_diagnostic.get("source_fetched_at"):
            if fixture_diagnostic.get("source_age_minutes") is not None:
                st.caption(
                    "Sportmonks detailed fixture retrieved at "
                    f"{fixture_diagnostic['source_fetched_at']} (UTC) — "
                    f"{fixture_diagnostic['source_age_minutes']} minutes ago. "
                    "Freshness threshold: 24 hours."
                )
            else:
                st.caption(
                    "Sportmonks retrieval timestamp: "
                    f"{fixture_diagnostic['source_fetched_at']} (UTC). "
                    "Its age cannot be measured because the timestamp is later than the diagnostic clock."
                )
        else:
            st.caption("Sportmonks detailed-fixture retrieval time is unavailable; source age remains unknown.")
        st.json(readiness)
        if not readiness["prediction_minimum_history_met"]:
            st.error("Prediction stopped: at least one team has fewer than five completed matches. No missing matches or ratings will be fabricated.")
            st.stop()
        st.subheader("Recent form and data coverage")
        st.json({home_name:home["form_summary"], away_name:away["form_summary"]})
        tvd_result = run_tvd(tvd_profiles[0],tvd_profiles[1]) if tvd_profiles else None
        overrides = {}
        if tvd_result:
            home_score=tvd_result["team_a_attacks_b"]["compatibility_score"]
            away_score=tvd_result["team_b_attacks_a"]["compatibility_score"]
            if home_score is not None: overrides["home"]=home_score
            if away_score is not None: overrides["away"]=away_score
        try:
            result=predict_match(home,away,tactical_compatibility=overrides)
        except ValueError as exc:
            st.error(str(exc)); st.stop()
        selected_league_row = league_by_id.get(league_id, {}) if sportmonks_mode else {}
        selected_country = selected_league_row.get("country") or {}
        selected_country_name = selected_country.get("name") if isinstance(selected_country, dict) else str(selected_country or "")
        if not selected_country_name:
            selected_country_name = selected_league.rsplit(" — ", 1)[-1] if " — " in selected_league else ""
        opta_values = None
        if record_opta_benchmark and all(value is not None for value in (opta_home, opta_draw, opta_away)) and abs(opta_home + opta_draw + opta_away - 100.0) <= 0.6 and opta_source_url.strip():
            opta_values = {"home_win": opta_home, "draw": opta_draw, "away_win": opta_away}
        player_snapshot = player_report if isinstance(player_report, dict) else None
        prediction_row = build_prediction_record(
            competition=str(selected_league_row.get("name") or selected_league.split(" — ")[0]),
            country=selected_country_name,
            season=int(season),
            home_team=home_name,
            away_team=away_name,
            probabilities=result["probabilities"],
            predicted_at=datetime.now(timezone.utc).isoformat(),
            kickoff_at=(prediction_fixture or {}).get("starting_at") or (prediction_fixture or {}).get("starting_at_at") or (datetime.fromtimestamp(int(prediction_fixture["starting_at_timestamp"]), timezone.utc).isoformat() if prediction_fixture and prediction_fixture.get("starting_at_timestamp") else None),
            fixture_id=(prediction_fixture or {}).get("id"),
            fixture_provider="sportmonks" if prediction_fixture else "",
            opta_probabilities=opta_values,
            opta_source_url=opta_source_url.strip() if opta_values else "",
            opta_captured_at=datetime.now(timezone.utc).isoformat() if opta_values else "",
            player_snapshot=player_snapshot,
        )
        st.session_state["prediction_ledger"] = merge_prediction_records(
            st.session_state["prediction_ledger"], [prediction_row]
        )
        _persist_database_ledger()
        st.subheader(f"{home_name} vs {away_name}")
        probabilities=result["probabilities"]
        outcome = most_likely_outcome(probabilities, home_name, away_name)
        st.success(outcome["label"])
        st.caption(f"Model's most likely 1X2 outcome: {outcome['probability']:.1f}% — an estimate, not a guaranteed result.")
        if not prediction_fixture:
            st.warning("No exact Sportmonks fixture was found for this home/away pairing and season. This prediction is saved but cannot be auto-linked for result collection or fixture-based backtesting.")
        elif prediction_row.get("prediction_before_kickoff") is False:
            st.warning("This prediction was recorded at or after kickoff. Its fixture is linked, but it will not be counted as a pre-match forecast in accuracy reports.")
        cols=st.columns(3)
        cols[0].metric(f"{home_name} win",f"{probabilities['home_win']}%")
        cols[1].metric("Draw",f"{probabilities['draw']}%")
        cols[2].metric(f"{away_name} win",f"{probabilities['away_win']}%")
        st.subheader("Goals market")
        cols=st.columns(4)
        cols[0].metric("Home expected goals",result["home_expected_goals"])
        cols[1].metric("Away expected goals",result["away_expected_goals"])
        cols[2].metric("Over 2.5 goals",f"{probabilities['over_2_5']}%")
        cols[3].metric("BTTS — Yes",f"{probabilities['btts_yes']}%")
        st.subheader("Most likely correct scores")
        st.dataframe(result["most_likely_scores"],use_container_width=True,hide_index=True)
        st.subheader("Team ratings and coverage")
        left,right=st.columns(2)
        left.metric(f"{home_name} rating",result["home_rating"],f"Known model weight: {result['data_coverage']['home_known_weight']*100:.0f}%")
        right.metric(f"{away_name} rating",result["away_rating"],f"Known model weight: {result['data_coverage']['away_known_weight']*100:.0f}%")
        st.caption(result["note"])
        with st.expander("Detailed component ratings"):
            st.json(result["component_ratings"]); st.json(result["tactical_component_ratings"])
        with st.expander("Tactical indicators and match statistics"):
            st.json({home_name:home["tactical_summary"],away_name:away["tactical_summary"]})
            st.subheader("Statistics coverage dashboard")
            st.caption("Coverage is calculated across each team's most recent completed matches. 'Missing' means the provider did not supply a usable value for that match; it is not filled with zero or estimated.")
            coverage_columns = st.columns(2)
            for column, profile in zip(coverage_columns, (home, away)):
                report = statistics_reports[profile["name"]]
                with column:
                    st.markdown(f"**{profile['name']}**")
                    st.metric(
                        "Core metrics with any data",
                        f"{report['core_metrics_with_any_data']}/{report['core_metrics_total']}",
                        help="Number of the eight model inputs present in at least one recent match.",
                    )
                    st.metric(
                        "Metrics present in every match",
                        f"{report['core_metrics_complete']}/{report['core_metrics_total']}",
                        help="A strict coverage measure across the matches checked.",
                    )
                    st.caption(
                        f"{report['fixtures_checked']} matches checked • "
                        f"{report['mapping_visibility']} for raw alias diagnostics"
                    )
                    st.dataframe(
                        pd.DataFrame(report["metrics"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if report["unmapped_statistics"]:
                        st.markdown("**Unmapped provider statistic names**")
                        st.dataframe(
                            pd.DataFrame(report["unmapped_statistics"]),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No unmapped raw statistic names were reported in this sample.")
            st.caption("Only the eight existing tactical model inputs are counted in the core coverage score. Other provider statistics remain visible as diagnostics and are not automatically added to the prediction model.")
            st.caption("Normalized values and source provenance are shown alongside every raw Sportmonks statistic row for each team. Unmapped names are diagnostic only and never enter tactical ratings or prediction inputs.")
            st.json({
                home_name: [
                    {"fixture_id": row.get("fixture_id"), "date": row.get("date"),
                     "statistics": row.get("statistics"),
                     "statistics_provenance": row.get("statistics_provenance", []),
                     "statistics_raw_diagnostics": row.get("statistics_raw_diagnostics", [])}
                    for row in home.get("matches", [])
                ],
                away_name: [
                    {"fixture_id": row.get("fixture_id"), "date": row.get("date"),
                     "statistics": row.get("statistics"),
                     "statistics_provenance": row.get("statistics_provenance", [])}
                    for row in away.get("matches", [])
                ],
            })
        with st.expander("Reported sidelined players, lineups and availability scoring evidence (when provider data exists)"):
            st.json({
                home_name: {
                    "availability_assessment": home.get("player_availability_assessment"),
                    "reported_sidelined": home["availability"],
                    "lineups": home["lineups"],
                },
                away_name: {
                    "availability_assessment": away.get("player_availability_assessment"),
                    "reported_sidelined": away["availability"],
                    "lineups": away["lineups"],
                },
            })
            st.caption("The 5% player-availability component is used only when a complete squad roster, known player statuses and evidenced importance weights are supplied. Partial sidelined lists and unconfirmed lineups remain unknown.")
        if tvd_result:
            st.subheader("Tactical Vulnerability Detector")
            st.json(tvd_result)
        st.caption(f"Model weights: {WEIGHTS}. Latest five matches carry 60% of recent-history weight; previous five carry 40%.")

except APIFootballError as exc:
    st.error(f"Data provider error: {exc}")
except Exception as exc:
    st.error(f"Unexpected data-collection error: {exc}")

with st.expander("Prediction tracking, Opta comparison and backtesting", expanded=True):
    db_status = st.session_state.get("_ledger_db_status", "not_configured")
    if db_status == "connected":
        st.success(st.session_state.get("_ledger_db_message", "Neon database connected."))
    elif db_status == "error":
        st.warning(st.session_state.get("_ledger_db_message", "Neon connection needs attention."))
        if st.button("Retry Neon connection", key="retry_neon_connection"):
            st.session_state["_ledger_db_loaded"] = False
            _load_database_ledger()
            st.rerun()
    else:
        st.info(st.session_state.get("_ledger_db_message", "Neon is not configured; predictions remain in this browser session only."))
    st.caption("When Neon is connected, prediction records are saved across browser sessions and app restarts. CSV import/export remains available as a backup.")
    st.caption("Automatic result collection checks each unique completed Sportmonks fixture once, then applies its exact verified 90-minute score to every matching blank prediction record. Manual scores are never overwritten.")
    auto_result_checks = st.checkbox(
        "Automatically check for completed results every 15 minutes while this app is open",
        value=True,
        key="automatic_result_collection_enabled",
        help="Checks run when the app opens and periodically while this browser session stays connected. The manual check remains available.",
    )
    _automatic_result_collection(auto_result_checks)
    if st.button("Check for completed match results", key="sync_verified_match_results"):
        try:
            with st.spinner("Checking eligible completed Sportmonks fixtures..."):
                sync_report = _sync_completed_sportmonks_results()
            st.success(
                f"Checked {sync_report['eligible_checked']} unique fixture(s); "
                f"updated {sync_report['updated']} prediction record(s) with verified result(s)."
            )
            if sync_report["not_verified_or_not_finished"]:
                st.info(f"{sync_report['not_verified_or_not_finished']} fixture(s) were not confirmed as completed with an exact, valid score.")
            if sync_report["errors"]:
                st.warning(f"{sync_report['errors']} provider request(s) failed. No unverified result was saved.")
            if sync_report["limit_reached"]:
                st.info("The safety limit of 10 fixtures per check was reached. Run the check again for remaining fixtures.")
            if sync_report["updated"]:
                st.rerun()
        except SportmonksError as exc:
            st.error(f"Sportmonks result check failed: {exc}")
    uploaded_ledger = st.file_uploader("Import a saved prediction ledger CSV", type=["csv"], key="prediction_ledger_upload")
    if uploaded_ledger is not None:
        try:
            imported = pd.read_csv(uploaded_ledger)
            imported_records = imported.where(pd.notna(imported), "").to_dict("records")
            st.session_state["prediction_ledger"] = merge_prediction_records(
                st.session_state["prediction_ledger"], imported_records
            )
            _persist_database_ledger()
            st.success(f"Imported {len(imported_records)} ledger rows. Duplicate record IDs were merged.")
        except Exception as exc:
            st.error(f"Could not import prediction ledger: {exc}")
    ledger = st.session_state["prediction_ledger"]
    if ledger:
        display_columns = [
            "record_id", "predicted_at", "competition", "home_team", "away_team",
            "model_home_win", "model_draw", "model_away_win",
            "opta_home_win", "opta_draw", "opta_away_win",
            "actual_home_goals", "actual_away_goals",
        ]
        frame = pd.DataFrame(ledger)
        for column in display_columns:
            if column not in frame:
                frame[column] = ""
        edited = st.data_editor(
            frame[display_columns],
            key="prediction_ledger_editor",
            hide_index=True,
            use_container_width=True,
            disabled=display_columns[:-2],
            column_config={
                "actual_home_goals": st.column_config.NumberColumn("Final home goals", min_value=0, step=1, format="%d"),
                "actual_away_goals": st.column_config.NumberColumn("Final away goals", min_value=0, step=1, format="%d"),
            },
        )
        edited_records = edited.where(pd.notna(edited), "").to_dict("records")
        st.session_state["prediction_ledger"] = merge_prediction_records(ledger, edited_records)
        _persist_database_ledger()
        report = evaluate_prediction_ledger(st.session_state["prediction_ledger"])
        try:
            github_performance_report = _upload_report_once("prediction_performance", report)
            if github_performance_report:
                st.session_state["_latest_performance_report_github_url"] = github_performance_report.get("latest_url")
                st.session_state["_latest_performance_report_github_archive_url"] = github_performance_report.get("archive_url")
        except Exception as upload_error:
            st.warning(f"Prediction performance report could not be archived to GitHub ({type(upload_error).__name__}). Check GITHUB_REPORT_TOKEN and GitHub permissions.")
        st.subheader("Backtest summary")
        if st.session_state.get("_latest_performance_report_github_url"):
            st.caption("Prediction performance report is archived in GitHub automatically.")
            st.markdown(
                f"[Open latest performance report]({st.session_state['_latest_performance_report_github_url']})"
                + (
                    f" · [Open timestamped archive]({st.session_state['_latest_performance_report_github_archive_url']})"
                    if st.session_state.get("_latest_performance_report_github_archive_url") else ""
                )
            )
        st.write(f"Pre-match forecasts: {report['pre_match_predictions']} • Completed and scored: {report['completed_pre_match_predictions']}")
        st.subheader("Prediction eligibility audit")
        audit = report["eligibility_audit"]
        audit_rows = [
            {"Category": "Total saved records", "Count": audit["records_total"]},
            {"Category": "Valid pre-kickoff records", "Count": audit["valid_pre_kickoff_records"]},
            {"Category": "Missing prediction timestamp", "Count": audit["missing_prediction_timestamp"]},
            {"Category": "Missing kickoff timestamp", "Count": audit["missing_kickoff_timestamp"]},
            {"Category": "Recorded at/after kickoff", "Count": audit["at_or_after_kickoff"]},
            {"Category": "Invalid probability sets", "Count": audit["invalid_probabilities"]},
            {"Category": "Unidentifiable pre-match records", "Count": audit["unidentifiable_pre_match_records"]},
            {"Category": "Duplicate records excluded", "Count": audit["duplicate_records_excluded"]},
            {"Category": "Unique pre-match fixtures", "Count": audit["unique_pre_match_fixtures"]},
            {"Category": "Awaiting a valid final score", "Count": audit["awaiting_valid_score"]},
            {"Category": "Completed with valid scores", "Count": audit["completed_with_valid_scores"]},
        ]
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
        st.caption("Exclusion categories are mutually exclusive. Fixture-level counts are calculated after duplicate removal; a valid score does not by itself prove that a result came from the automatic verifier.")
        if report["duplicate_records_excluded"]:
            st.caption(f"Excluded {report['duplicate_records_excluded']} repeated forecast record(s); only the latest valid pre-kickoff forecast per identifiable fixture is scored.")
        if report["unidentifiable_pre_match_records"]:
            st.warning(f"{report['unidentifiable_pre_match_records']} pre-kickoff record(s) lack enough fixture identity to be scored safely.")
        st.subheader("Historical performance dashboard")
        history = report.get("performance_history", [])
        if history:
            history_frame = pd.DataFrame(history)
            history_frame["kickoff_date"] = pd.to_datetime(
                history_frame["kickoff_at"], utc=True, errors="coerce"
            )
            history_frame = history_frame.dropna(subset=["kickoff_date"]).sort_values("kickoff_date")
            if not history_frame.empty:
                history_frame["cumulative_accuracy_pct"] = (
                    history_frame["correct"].astype(float).expanding().mean() * 100
                )
                history_frame["cumulative_brier"] = history_frame["brier"].astype(float).expanding().mean()
                h1, h2, h3 = st.columns(3)
                h1.metric("Verified pre-match fixtures", len(history_frame))
                h2.metric("Correct predictions", int(history_frame["correct"].sum()))
                h3.metric(
                    "Historical accuracy",
                    f"{history_frame['correct'].mean() * 100:.1f}%",
                )
                st.caption("Each point represents one unique fixture, using the latest valid pre-kickoff forecast and an exact verified final score. Lower Brier score is better.")
                st.write("Cumulative prediction accuracy")
                st.line_chart(
                    history_frame.set_index("kickoff_date")[["cumulative_accuracy_pct"]]
                )
                st.write("Cumulative multiclass Brier score")
                st.line_chart(
                    history_frame.set_index("kickoff_date")[["cumulative_brier"]]
                )
                st.write("Verified match-by-match history")
                st.dataframe(
                    history_frame[[
                        "kickoff_at", "competition", "home_team", "away_team",
                        "score", "predicted_outcome", "actual_outcome", "correct",
                        "top_confidence_pct", "brier", "log_loss",
                    ]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No completed pre-match fixtures have a usable kickoff date for the history chart.")
        else:
            st.info("The historical dashboard will populate as eligible pre-match forecasts receive verified final scores.")

        model_metrics = report["model"]
        opta_metrics = report["opta_same_fixtures"]
        m1, m2, m3 = st.columns(3)
        m1.metric("Model accuracy", f"{model_metrics['accuracy_pct']}%" if model_metrics["accuracy_pct"] is not None else "—")
        m2.metric("Model Brier score", f"{model_metrics['multiclass_brier']}" if model_metrics["multiclass_brier"] is not None else "—", help="Lower is better; multiclass score over home/draw/away.")
        m3.metric("Model log loss", f"{model_metrics['log_loss']}" if model_metrics["log_loss"] is not None else "—", help="Lower is better; penalizes confident incorrect forecasts.")
        if report["opta_comparable_fixtures"]:
            st.write(f"Opta comparison on the same {report['opta_comparable_fixtures']} completed fixtures")
            o1, o2, o3 = st.columns(3)
            o1.metric("Opta accuracy", f"{opta_metrics['accuracy_pct']}%")
            o2.metric("Opta Brier score", f"{opta_metrics['multiclass_brier']}")
            o3.metric("Opta log loss", f"{opta_metrics['log_loss']}")
        else:
            st.info("No Opta benchmark has been captured for a completed fixture yet. Add published Opta probabilities before kickoff to enable a fair same-match comparison.")
        st.write("Player-stat snapshots captured before kickoff:", report["player_snapshots_pre_kickoff"])
        st.write("Team-season snapshots captured before kickoff:", report["team_snapshots_pre_kickoff"])
        if report["player_snapshot_coverage_by_competition"]:
            st.json(report["player_snapshot_coverage_by_competition"])
        if report["model_metrics_by_competition"]:
            st.write("Model results by competition")
            st.dataframe(pd.DataFrame(report["model_metrics_by_competition"]).T, use_container_width=True)
        st.download_button(
            "Download prediction ledger CSV",
            data=pd.DataFrame(st.session_state["prediction_ledger"]).to_csv(index=False).encode("utf-8"),
            file_name="football_prediction_ledger.csv",
            mime="text/csv",
            use_container_width=True,
            on_click="ignore",
        )
        st.caption("Only forecasts timestamped before kickoff are scored. Player-stat snapshots after kickoff are excluded from validation to prevent future-data leakage. No weights are changed by this report.")
    else:
        st.info("No predictions have been logged in this session yet. Make a prediction to start the ledger, or import an existing CSV.")

with st.expander("Layer 2 data rules"):
    st.markdown("""
    - Data providers: Sportmonks for current seasons; API-Football for supported historical seasons (2022–2024).
    - Optional Highlightly and API Ninjas recent-result corroboration is diagnostic only; it does not replace Layer 2 inputs.
    - Ten most recent completed matches are requested per team.
    - Latest five matches carry 60% of history weight; matches 6–10 carry 40%.
    - Home and away performance are calculated from matches at that venue.
    - Opponent strength is derived from competition standings; unavailable ranks stay unknown.
    - Injuries are displayed, but no arbitrary availability score is assigned.
    - Tactical indicators use returned statistics only; absent metrics remain unknown.
    - Existing Layer 1 component weights and TVD logic are retained.
    - Missing components are excluded and the known weights are normalized for the rating.
    """)
