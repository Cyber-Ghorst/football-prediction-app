"""Football Prediction Lab — Layer 2 automatic data collection."""
from __future__ import annotations
import json
import streamlit as st
from api_football import APIFootballClient, APIFootballError
from api_ninjas import APINinjasClient, APINinjasError
from highlightly import HighlightlyClient, HighlightlyError
from sportmonks import SportmonksClient, SportmonksError
from data_layer2 import collect_team_profile
from engine import predict_match, WEIGHTS
from tvd import run_tvd
from provider_config import provider_readiness
from livescore_football import LiveScoreFootballClient, LiveScoreFootballError
from competition_crosswalk import build_competition_crosswalk
from provider_health import assess_api_football_status, assess_livescore_metadata

st.set_page_config(page_title="Football Prediction Lab", page_icon="⚽", layout="wide")
st.title("⚽ Football Prediction Lab")
st.caption("Layer 2 • Automatic API-Football data collection + weighted prediction engine + TVD")

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

with st.sidebar:
    st.header("Data configuration")
    season = st.number_input("Season start year", min_value=2015, max_value=2035, value=2026, step=1,
                             help="For a 2026/27 season, enter 2026. Use the season year supported by your API plan.")
    include_stats = st.checkbox("Fetch match statistics (more API requests)", value=True)
    st.caption("Add APISPORTS_API_KEY for API-Football v3 in Streamlit Secrets. Provider keys are separate; never paste keys into public code.")
    with st.expander("Provider readiness", expanded=True):
        for provider in provider_readiness():
            credential = ("not required" if provider.get("credential_required") is False else ("configured" if provider["credential_configured"] else "not configured"))
            st.write(f"**{provider['provider']}** — {provider['adapter']}; credential {credential}; {provider['app_integration']}.")
        run_provider_diagnostics = st.button("Run provider health & coverage check", use_container_width=True)

try:
    client = APIFootballClient()
except APIFootballError as exc:
    st.error(str(exc))
    st.markdown("**Setup:** create an API-Football key, then add this to Streamlit Secrets:\n```toml\nAPISPORTS_API_KEY = \"YOUR_API_SPORTS_KEY_HERE\"\n```")
    st.stop()

try:
    if run_provider_diagnostics:
        st.subheader("Provider health and competition coverage")
        try:
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
    if int(season) > 2024:
        st.error("API-Football on the configured plan only accepts seasons 2022–2024. Sportmonks has been added as the intended current-season provider, but its account token, competition coverage and Layer 2 data mapping must be verified before predictions can use it. Add SPORTMONKS_API_TOKEN to Streamlit Secrets, run the provider diagnostic, and share the result.")
        st.stop()
    leagues = get_leagues(client, int(season))
    league_options = {f"{x['league']['name']} — {x.get('country',{}).get('name','')}": x['league']['id']
                      for x in leagues if x.get('league',{}).get('id')}
    if not league_options:
        st.warning("No competitions were returned for this season under the current API plan.")
        st.stop()
    selected_league = st.selectbox("Competition", list(league_options))
    league_id = int(league_options[selected_league])
    team_rows = get_teams(client, league_id, int(season))
    team_map = {x['team']['name']: x['team'] for x in team_rows if x.get('team',{}).get('id')}
    if len(team_map) < 2:
        st.warning("The provider returned fewer than two teams for this competition.")
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
            standings = get_standings(client, league_id, int(season))
            home = get_profile(client, team_map[home_name], league_id, int(season), standings, include_stats)
            away = get_profile(client, team_map[away_name], league_id, int(season), standings, include_stats)
        st.subheader("Data validation")
        for profile in (home, away):
            quality = profile["data_quality"]
            st.write(f"**{profile['name']}** — {quality['matches_returned']} completed matches; {quality['opponent_strength_matches']} with opponent-strength data; {quality['statistics_matches']} with match statistics.")
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
        with st.expander("Reported injuries and next-match lineups (when provider data exists)"):
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
    - Data provider: API-Football v3. API key is stored in Streamlit Secrets.
    - Ten most recent completed matches are requested per team.
    - Latest five matches carry 60% of history weight; matches 6–10 carry 40%.
    - Home and away performance are calculated from matches at that venue.
    - Opponent strength is derived from competition standings; unavailable ranks stay unknown.
    - Injuries are displayed, but no arbitrary availability score is assigned.
    - Tactical indicators use returned statistics only; absent metrics remain unknown.
    - Existing Layer 1 component weights and TVD logic are retained.
    - Missing components are excluded and the known weights are normalized for the rating.
    """)
