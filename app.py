import json
import streamlit as st
from engine import predict_match, WEIGHTS
from tvd import MATCHUPS, run_tvd

st.set_page_config(page_title="Football Prediction Lab", page_icon="⚽", layout="wide")
st.title("⚽ Football Prediction Lab")
st.caption("Layer 1 • Weighted match-rating engine + Poisson score model + Tactical Vulnerability Detector")

with open("sample_teams.json", "r", encoding="utf-8") as f:
    teams = json.load(f)

st.info("Demo profiles are included so the app works immediately. Replace sample_teams.json with verified, current data before relying on predictions. Automatic data feeds are planned for Layer 2.")

c1, c2 = st.columns(2)
names = list(teams.keys())
with c1:
    home_name = st.selectbox("Home team", names, index=0)
with c2:
    away_options = [n for n in names if n != home_name]
    away_name = st.selectbox("Away team", away_options, index=0)

st.subheader("Optional match-specific adjustments")
st.write("These manual ratings remain available as a fallback when TVD inputs are missing.")
a, b = st.columns(2)
with a:
    home_avail = st.slider(f"{home_name} player availability", 0, 100, int(teams[home_name]["player_availability"]))
    home_compat = st.slider(f"{home_name} tactical matchup fallback", 0, 100, int(teams[home_name]["tactical_compatibility"]))
with b:
    away_avail = st.slider(f"{away_name} player availability", 0, 100, int(teams[away_name]["player_availability"]))
    away_compat = st.slider(f"{away_name} tactical matchup fallback", 0, 100, int(teams[away_name]["tactical_compatibility"]))

# TVD input labels and keys. Vulnerability scores increase with weakness;
# weapon scores increase with attacking capability.
VULNERABILITIES = [
    ("space_behind", "Space behind defensive line"),
    ("press_resistance", "Poor press resistance"),
    ("aerial_defence", "Weak aerial defense"),
    ("transition_recovery", "Slow defensive recovery"),
    ("central_compactness", "Weak central compactness"),
    ("wide_defending", "Poor wide defending"),
    ("central_penetration", "Vulnerability between the lines"),
]
WEAPONS = [
    ("pace_through_balls", "Pace and through balls"),
    ("pressing_intensity", "Pressing intensity"),
    ("aerial_threat", "Aerial threat"),
    ("counterattack_threat", "Counterattack threat"),
    ("midfield_overloads", "Midfield overloads"),
    ("wing_threat", "Wing threat"),
    ("between_lines_threat", "Central penetration threat"),
]

def collect_tvd_profile(team_name: str, side: str):
    """Collect optional TVD ratings; blank fields remain unknown."""
    profile = {"name": team_name, "vulnerabilities": {}, "weapons": {}}
    confidence = st.slider(
        f"{team_name}: evidence confidence for these ratings",
        min_value=0, max_value=100, value=60, step=5,
        key=f"{side}_tvd_confidence",
        help="Use lower confidence for estimates or incomplete evidence; higher confidence for verified match/video data."
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**Defensive vulnerabilities**")
        for key, label in VULNERABILITIES:
            value = st.number_input(
                label, min_value=0, max_value=100, value=None,
                placeholder="Unknown", step=5,
                key=f"{side}_vuln_{key}",
                help="0 = no clear weakness; 100 = severe weakness. Leave blank if unknown."
            )
            if value is not None:
                profile["vulnerabilities"][key] = {"score": value, "confidence": confidence}
    with right:
        st.markdown("**Attacking weapons**")
        for key, label in WEAPONS:
            value = st.number_input(
                label, min_value=0, max_value=100, value=None,
                placeholder="Unknown", step=5,
                key=f"{side}_weapon_{key}",
                help="0 = no meaningful weapon; 100 = elite threat. Leave blank if unknown."
            )
            if value is not None:
                profile["weapons"][key] = {"score": value, "confidence": confidence}
    return profile

use_tvd = st.checkbox("Enable Tactical Vulnerability Detector (TVD)", value=False)
tvd_profiles = None
if use_tvd:
    st.markdown("TVD checks whether one team's attacking strengths match the opponent's defensive weaknesses. Enter only ratings supported by evidence; blank fields are excluded.")
    tab_home, tab_away = st.tabs([f"{home_name} profile", f"{away_name} profile"])
    with tab_home:
        home_tvd = collect_tvd_profile(home_name, "home")
    with tab_away:
        away_tvd = collect_tvd_profile(away_name, "away")
    t1, t2 = st.columns(2)
    with t1:
        st.caption("TVD evaluates this team's weapons against the opponent's vulnerabilities.")
    with t2:
        st.caption("Confidence is currently entered once per team and applied to its supplied metrics.")
    tvd_profiles = (home_tvd, away_tvd)

if st.button("Predict match", type="primary", use_container_width=True):
    home = json.loads(json.dumps(teams[home_name]))
    away = json.loads(json.dumps(teams[away_name]))
    home["player_availability"], away["player_availability"] = home_avail, away_avail

    tvd_result = None
    compatibility_override = {"home": home_compat, "away": away_compat}
    if use_tvd and tvd_profiles:
        try:
            tvd_result = run_tvd(tvd_profiles[0], tvd_profiles[1])
            home_tvd_score = tvd_result["team_a_attacks_b"]["compatibility_score"]
            away_tvd_score = tvd_result["team_b_attacks_a"]["compatibility_score"]
            if home_tvd_score is not None:
                compatibility_override["home"] = home_tvd_score
            if away_tvd_score is not None:
                compatibility_override["away"] = away_tvd_score
        except ValueError as exc:
            st.error(f"TVD input error: {exc}")
            st.stop()

    try:
        result = predict_match(home, away, tactical_compatibility=compatibility_override)
        st.subheader(f'{home_name} vs {away_name}')
        p = result["probabilities"]
        cols = st.columns(3)
        cols[0].metric(f"{home_name} win", f'{p["home_win"]}%')
        cols[1].metric("Draw", f'{p["draw"]}%')
        cols[2].metric(f"{away_name} win", f'{p["away_win"]}%')
        st.subheader("Goals market")
        cols = st.columns(4)
        cols[0].metric("Home expected goals", result["home_expected_goals"])
        cols[1].metric("Away expected goals", result["away_expected_goals"])
        cols[2].metric("Over 2.5 goals", f'{p["over_2_5"]}%')
        cols[3].metric("BTTS — Yes", f'{p["btts_yes"]}%')
        st.subheader("Most likely correct scores")
        st.dataframe(result["most_likely_scores"], use_container_width=True, hide_index=True)
        st.subheader("Team ratings")
        cols = st.columns(2)
        cols[0].metric(f"{home_name} model rating", result["home_rating"])
        cols[1].metric(f"{away_name} model rating", result["away_rating"])

        if tvd_result:
            st.subheader("Tactical Vulnerability Detector")
            st.caption("These are tactical matchup ratings, not win probabilities. TVD scores replace the tactical compatibility input only where enough data is available; otherwise the manual fallback is used.")
            d1, d2 = st.columns(2)
            for col, title, direction in [
                (d1, f"{home_name} attacks {away_name}", tvd_result["team_a_attacks_b"]),
                (d2, f"{away_name} attacks {home_name}", tvd_result["team_b_attacks_a"]),
            ]:
                with col:
                    if direction["compatibility_score"] is None:
                        st.metric(title, "Insufficient data")
                    else:
                        st.metric(title, f'{direction["compatibility_score"]}/100', direction["risk_level"])
                    st.caption(f'Coverage: {direction["data_coverage"]}% • Missing pairings: {direction["missing_pairings"]}/7')
                    if direction["findings"]:
                        rows = [{
                            "Defensive weakness": x["vulnerability"],
                            "Opponent weapon": x["attacking_weapon"],
                            "Matchup": x["matchup_score"],
                            "Risk": x["risk"],
                            "Confidence": x["confidence"],
                        } for x in direction["findings"]]
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                    else:
                        st.info("No complete vulnerability/weapon pairings were supplied for this direction.")
            st.write("Stronger tactical matchup:", tvd_result["stronger_tactical_matchup"])

        with st.expander("Model breakdown and weights"):
            st.write("Weights:", WEIGHTS)
            st.json(result["component_ratings"])
            st.write("Tactical compatibility actually used:", result["tactical_compatibility_used"])
        st.caption(result["note"])
    except (ValueError, KeyError) as exc:
        st.error(str(exc))

with st.expander("How the model works"):
    st.markdown("""
    - Recent form: **20%**
    - Goals scored: **10%**
    - Goals conceded: **10%**
    - Home/away performance: **10%**
    - Strength of schedule: **15%**
    - Player availability: **5%**
    - Tactical analysis: **30%** (style 6%, defence 7%, attack 7%, matchup compatibility 10%)

    The last 10 matches are used, with the latest five weighted 1.5 times more heavily.
    TVD evaluates seven weakness-versus-weapon matchups in both directions. Unknown inputs are excluded rather than assumed to be average.
    Score probabilities are estimated using independent Poisson goal distributions.
    """)
