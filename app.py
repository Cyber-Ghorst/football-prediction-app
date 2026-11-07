"""Football Prediction Lab — Layer 2 automatic data collection."""
from __future__ import annotations
import json
import streamlit as st
from api_football import APIFootballClient, APIFootballError
from api_ninjas import APINinjasClient, APINinjasError
from highlightly import HighlightlyClient, HighlightlyError
from sportmonks import SportmonksClient, SportmonksError
from data_layer2 import collect_team_profile
from sportmonks_layer2 import collect_sportmonks_team_profile, find_upcoming_match_fixture, extract_sportmonks_match_details
from engine import predict_match, WEIGHTS
from tvd import run_tvd
from provider_config import provider_readiness
from livescore_football import LiveScoreFootballClient, LiveScoreFootballError
from competition_crosswalk import build_competition_crosswalk
from provider_health import assess_api_football_status, assess_livescore_metadata
from provider_corroboration import collect_recent_result_corroboration
from highlightly_match_enrichment import collect_highlightly_match_enrichment

st.set_page_config(page_title="Football Prediction Lab", page_icon="⚽", layout="wide")
st.title("⚽ Football Prediction Lab")
st.caption("Layer 2 • Sportmonks current-season / API-Football historical data collection + weighted prediction engine + TVD")

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

@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_leagues():
    with SportmonksClient() as sm:
        return sm.available_leagues(include="country")

@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_seasons():
    with SportmonksClient() as sm:
        return sm.available_seasons()

@st.cache_data(ttl=3600, show_spinner=False)
def get_sm_teams(season_id):
    with SportmonksClient() as sm:
        return sm.teams_by_season(season_id)

@st.cache_data(ttl=1800, show_spinner=False)
def get_sm_standings(season_id):
    with SportmonksClient() as sm:
        return sm.standings_by_season(season_id, include="participant")

@st.cache_data(ttl=1800, show_spinner=False)
def get_sm_fixtures(season_id, include_stats):
    with SportmonksClient() as sm:
        return sm.fixtures_by_season(season_id, include_statistics=include_stats)

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
    st.caption("For 2022–2024 add APISPORTS_API_KEY; for 2025+ add SPORTMONKS_API_TOKEN in Streamlit Secrets. Never paste keys into public code.")
    with st.expander("Provider readiness", expanded=True):
        for provider in provider_readiness():
            credential = ("not required" if provider.get("credential_required") is False else ("configured" if provider["credential_configured"] else "not configured"))
            st.write(f"**#{provider['rank']} {provider['provider']} — {provider['role']}**; credential {credential}.")
            st.caption(f"Domains: {', '.join(provider['domains'])}. {provider['app_integration']}. Limitation: {provider['limitation']}")
        run_provider_diagnostics = st.button("Run provider health & coverage check", use_container_width=True)

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
            st.write("**API Ninjas connection test**")
            st.json({
                "transport_status": "responding" if ninjas_ok else "unknown",
                "credential_configured": True,
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
            crosswalk = build_competition_crosswalk(
                leagues, live_competitions, requested_season=int(season)
            )
            st.write("**Exact competition crosswalk**")
            st.caption("Only exact competition-name + country matches with active stored coverage and a matching season are marked verified. Unverified competitions are not eligible for fallback.")
            if crosswalk:
                st.dataframe([
                    {key: row.get(key) for key in (
                        "api_football_id", "name", "country", "livescore_slug",
                        "livescore_season", "verified", "reason"
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
        with st.spinner("Collecting recent results, standings and available match statistics..."):
            if sportmonks_mode:
                try:
                    standings = get_sm_standings(selected_season_id)
                    fixtures = get_sm_fixtures(selected_season_id, include_stats)
                except SportmonksError as exc:
                    st.error(f"Sportmonks season data collection failed: {exc}")
                    st.stop()
                home = collect_sportmonks_team_profile(team_map[home_name], selected_season_id, fixtures, standings)
                away = collect_sportmonks_team_profile(team_map[away_name], selected_season_id, fixtures, standings)

                # Only enrich an actual upcoming fixture when the selected home/away
                # teams and season match exactly. A team's unrelated next match is not substituted.
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

                if cross_check_recent_results or cross_check_highlightly_details:
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
                                home_team_name=home_name,
                                away_team_name=away_name,
                                highlightly_client=hl_client,
                                api_ninjas_client=ninjas_client,
                            )
                            corroboration["errors"].update(corroboration_errors)

                        if cross_check_highlightly_details:
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
                                    history_per_team=10,
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
                                if key != "matches"
                            })
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
                                        "reconciliation": match_record.get("reconciliation"),
                                        "providers_seen": match_record.get("providers_seen"),
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

            else:
                standings = get_standings(client, league_id, int(season))
                home = get_profile(client, team_map[home_name], league_id, int(season), standings, include_stats)
                away = get_profile(client, team_map[away_name], league_id, int(season), standings, include_stats)
        st.subheader("Data validation")
        for profile in (home, away):
            quality = profile["data_quality"]
            st.write(f"**{profile['name']}** — source: {quality.get('provider', 'api_football')}; {quality['matches_returned']} completed matches; {quality['opponent_strength_matches']} with opponent-strength data; {quality['statistics_matches']} with match statistics; {quality.get('statistics_observations', 0)} normalized statistic observations.")
            if quality["matches_returned"] < 5:
                st.error(f"{profile['name']}: fewer than five completed matches. Prediction stopped; no data was fabricated.")
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
        st.subheader(f"{home_name} vs {away_name}")
        probabilities=result["probabilities"]; cols=st.columns(3)
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
            st.caption("Recent per-match statistics include normalized values and their Sportmonks source provenance. Raw observations are retained for audit; only supported, unit-normalized metrics contribute to tactical indicators.")
            st.json({
                home_name: [
                    {"fixture_id": row.get("fixture_id"), "date": row.get("date"),
                     "statistics": row.get("statistics"),
                     "statistics_provenance": row.get("statistics_provenance", [])}
                    for row in home.get("matches", [])
                ],
                away_name: [
                    {"fixture_id": row.get("fixture_id"), "date": row.get("date"),
                     "statistics": row.get("statistics"),
                     "statistics_provenance": row.get("statistics_provenance", [])}
                    for row in away.get("matches", [])
                ],
            })
        with st.expander("Reported sidelined players and selected-fixture lineups (when provider data exists)"):
            st.json({home_name:{"injuries":home["availability"],"lineups":home["lineups"]},away_name:{"injuries":away["availability"],"lineups":away["lineups"]}})
        if tvd_result:
            st.subheader("Tactical Vulnerability Detector")
            st.json(tvd_result)
        st.caption(f"Model weights: {WEIGHTS}. Latest five matches carry 60% of recent-history weight; previous five carry 40%.")

except APIFootballError as exc:
    st.error(f"Data provider error: {exc}")
except Exception as exc:
    st.error(f"Unexpected data-collection error: {exc}")

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
