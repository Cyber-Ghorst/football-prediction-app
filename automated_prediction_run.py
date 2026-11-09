"""Execute the existing Streamlit prediction flow non-interactively in CI.

This uses Streamlit's supported AppTest harness, so the same app.py collection,
validation, TVD, prediction and ledger code runs instead of a parallel model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

APP_PATH = Path(__file__).resolve().with_name("app.py")


def resolve_option(options: Iterable[object], requested: str, label: str) -> str:
    """Resolve an exact option, or one unique display-label prefix."""
    values = [str(value) for value in options]
    wanted = str(requested or "").strip()
    if not wanted:
        raise ValueError(f"A {label} value is required.")
    if wanted in values:
        return wanted
    matches = [value for value in values if value.split(" — ", 1)[0].casefold() == wanted.casefold()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"{label} '{wanted}' is ambiguous; pass the full display label including country.")
    raise ValueError(f"{label} '{wanted}' was not returned by the selected provider. Available options: {values[:30]}")


def _widget_by_label(widgets, label: str):
    matches = [widget for widget in widgets if getattr(widget, "label", None) == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Streamlit widget labelled '{label}', found {len(matches)}.")
    return matches[0]


def _safe_text(value: object) -> str:
    text = str(value)
    for key, secret in os.environ.items():
        if key in {
            "SPORTMONKS_API_TOKEN", "SPORTMONKS_API_KEY", "PROVIDER_DATABASE_URL",
            "DATABASE_URL", "GITHUB_REPORT_TOKEN", "APISPORTS_API_KEY",
            "API_FOOTBALL_KEY", "HIGHLIGHTLY_API_KEY", "API_NINJAS_API_KEY",
            "SPORTMONKS_API_TOKEN", "SPORTMONKS_API_KEY",
        } and secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(postgres(?:ql)?://[^:/\s]+:)[^@/\s]+@", r"\1[REDACTED]@", text)
    return text[:1200]


def _upload_report(report: dict) -> dict:
    import base64
    import requests

    token = os.environ.get("GITHUB_REPORT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_REPORT_TOKEN is not configured.")
    owner_repo = "Cyber-Ghorst/football-prediction-app"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive = f"reports/automated_prediction_run/archive/{stamp}.json"
    latest = "reports/automated_prediction_run/latest.json"
    serialized = json.dumps(report, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    encoded = base64.b64encode(serialized).decode("ascii")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    def put(path: str, message: str, sha: str | None = None) -> dict:
        body = {"message": message, "content": encoded}
        if sha:
            body["sha"] = sha
        response = requests.put(
            f"https://api.github.com/repos/{owner_repo}/contents/{path}",
            headers=headers, json=body, timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"GitHub report upload failed (HTTP {response.status_code}).")
        return response.json()

    put(archive, "Archive automated prediction run report")
    current = requests.get(
        f"https://api.github.com/repos/{owner_repo}/contents/{latest}",
        headers=headers, timeout=20,
    )
    if current.status_code not in (200, 404):
        raise RuntimeError(f"GitHub latest-report lookup failed (HTTP {current.status_code}).")
    sha = current.json().get("sha") if current.status_code == 200 else None
    put(latest, "Update latest automated prediction run report", sha)
    return {
        "latest_url": f"https://github.com/{owner_repo}/blob/main/{latest}",
        "archive_url": f"https://github.com/{owner_repo}/tree/main/reports/automated_prediction_run/archive",
    }


def run_prediction(season: int, competition: str, home_team: str, away_team: str) -> dict:
    if not all(os.environ.get(key, "").strip() for key in ("SPORTMONKS_API_TOKEN", "GITHUB_REPORT_TOKEN")):
        raise RuntimeError("SPORTMONKS_API_TOKEN and GITHUB_REPORT_TOKEN must be configured as GitHub Actions secrets.")
    if season <= 2024:
        raise ValueError("Automated CI prediction currently supports the Sportmonks current-season path (season start year 2025 or later).")

    # Streamlit AppTest reads secrets from the standard local secrets file.
    # This file exists only on the ephemeral GitHub runner and is never uploaded.
    secret_keys = (
        "SPORTMONKS_API_TOKEN", "SPORTMONKS_API_KEY", "PROVIDER_DATABASE_URL",
        "DATABASE_URL", "GITHUB_REPORT_TOKEN", "APISPORTS_API_KEY",
        "API_FOOTBALL_KEY", "HIGHLIGHTLY_API_KEY", "API_NINJAS_API_KEY",
        "LIVESCORE_FOOTBALL_BASE_URL",
    )
    secrets_dir = Path(".streamlit")
    secrets_dir.mkdir(exist_ok=True)
    secret_lines = []
    for key in secret_keys:
        value = os.environ.get(key, "")
        if value:
            secret_lines.append(f"{key} = {json.dumps(value)}")
    secrets_path = secrets_dir / "secrets.toml"
    secrets_path.write_text("\n".join(secret_lines) + "\n", encoding="utf-8")

    from streamlit.testing.v1 import AppTest

    started = datetime.now(timezone.utc)
    app = AppTest.from_file(str(APP_PATH), default_timeout=900)
    app.run(timeout=900)
    if app.exception:
        raise RuntimeError("Streamlit app failed during initial load: " + "; ".join(_safe_text(getattr(item, "message", item)) for item in app.exception))

    season_widget = _widget_by_label(app.number_input, "Season start year")
    season_widget.set_value(int(season))
    app.run(timeout=900)

    competition_widget = _widget_by_label(app.selectbox, "Sportmonks competition")
    selected_competition = resolve_option(competition_widget.options, competition, "competition")
    competition_widget.select(selected_competition)
    app.run(timeout=900)

    home_widget = _widget_by_label(app.selectbox, "Home team")
    selected_home = resolve_option(home_widget.options, home_team, "home team")
    home_widget.select(selected_home)
    app.run(timeout=900)

    away_widget = _widget_by_label(app.selectbox, "Away team")
    selected_away = resolve_option(away_widget.options, away_team, "away team")
    if selected_home == selected_away:
        raise ValueError("Home and away teams must be different.")
    away_widget.select(selected_away)
    app.run(timeout=900)

    prediction_button = _widget_by_label(app.button, "Collect data and predict")
    prediction_button.click()
    app.run(timeout=900)

    exceptions = [_safe_text(getattr(item, "message", item)) for item in app.exception]
    errors = [_safe_text(getattr(item, "value", item)) for item in app.error]
    warnings = [_safe_text(getattr(item, "value", item)) for item in app.warning]
    if exceptions:
        raise RuntimeError("Prediction execution raised an exception: " + " | ".join(exceptions))

    try:
        ledger = list(app.session_state["prediction_ledger"])
    except Exception:
        ledger = []
    matching = [
        row for row in ledger
        if str(row.get("season")) == str(season)
        and str(row.get("home_team")) == selected_home
        and str(row.get("away_team")) == selected_away
    ]
    if not matching:
        raise RuntimeError(
            "The app completed its Streamlit run but did not create a matching prediction-ledger record. "
            "Review the captured app errors/warnings; no successful prediction is claimed."
        )
    record = matching[-1]
    report = {
        "report_name": "automated_prediction_run",
        "status": "prediction_record_created",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
        "execution_method": "streamlit_app_test_harness",
        "same_app_prediction_flow": True,
        "selection": {
            "season": int(season),
            "competition": selected_competition,
            "home_team": selected_home,
            "away_team": selected_away,
        },
        "prediction": {
            "predicted_at": record.get("predicted_at"),
            "kickoff_at": record.get("kickoff_at"),
            "prediction_before_kickoff": record.get("prediction_before_kickoff"),
            "fixture_id": record.get("fixture_id"),
            "fixture_provider": record.get("fixture_provider"),
            "model_home_win_pct": record.get("model_home_win"),
            "model_draw_pct": record.get("model_draw"),
            "model_away_win_pct": record.get("model_away_win"),
            "model_version": record.get("model_version"),
            "model_recency_policy": record.get("model_recency_policy"),
        },
        "app_errors": errors,
        "app_warnings": warnings,
        "notes": [
            "The existing app.py workflow was executed through Streamlit AppTest; no parallel prediction implementation was used.",
            "Provider corroboration remains diagnostic-only and does not alter prediction inputs.",
            "The app's existing Neon ledger persistence is used when DATABASE_URL is configured.",
        ],
    }
    links = _upload_report(report)
    report["github_reports"] = links
    Path("prediction-run-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--competition", required=True)
    parser.add_argument("--home-team", required=True)
    parser.add_argument("--away-team", required=True)
    args = parser.parse_args()
    try:
        run_prediction(args.season, args.competition, args.home_team, args.away_team)
        return 0
    except Exception as exc:
        failure = {
            "report_name": "automated_prediction_run",
            "status": "failed",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "error": _safe_text(f"{type(exc).__name__}: {exc}"),
        }
        Path("prediction-run-report.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
