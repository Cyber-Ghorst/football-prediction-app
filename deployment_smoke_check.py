"""Deployment-time application smoke check.

This checks the deployed entry point's syntax and imports the same internal
modules used by app.py. It does not claim to authenticate to the live
Streamlit session or exercise provider credentials/database connections.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP_MODULES = (
    "deployment_health_probe",
    "api_football",
    "api_ninjas",
    "highlightly",
    "sportmonks",
    "data_layer2",
    "sportmonks_layer2",
    "sportmonks_candidate_verification",
    "provider_core",
    "engine",
    "tvd",
    "provider_config",
    "livescore_football",
    "competition_crosswalk",
    "provider_health",
    "provider_corroboration",
    "highlightly_match_enrichment",
    "highlightly_player_enrichment",
    "prediction_evaluation",
    "prediction_storage",
    "prediction_results",
    "prediction_readiness",
    "player_availability",
    "statistics_coverage",
    "system_diagnostics",
    "provider_data_storage",
    "football_repository",
    "temporary_fixture_store",
    "free_fixture_adapters",
    "free_fixture_observation_pipeline",
    "provider_entity_crosswalk",
    "provider_crosswalk_review_report",
    "free_fixture_result_sync",
    "free_fixture_canonical_promotion",
    "free_fixture_provider_refresh",
    "free_fixture_crosswalk_audit",
    "learning_dataset",
    "learning_experiments",
    "learning_readiness_audit",
)

APP_SYMBOLS = {
    "temporary_fixture_store": (
        "add_temporary_upcoming_fixtures",
        "search_temporary_upcoming_fixtures",
    ),
    "free_fixture_observation_pipeline": (
        "collect_openligadb_observations",
        "collect_openfootball_observations",
        "collect_openmatchday_observations",
        "collect_livescore_observations",
        "collect_bzzoiro_observations",
    ),
    "provider_entity_crosswalk": (
        "save_explicit_provider_entity_links",
        "load_provider_entity_links",
        "extract_provider_entities_from_observations",
    ),
    "provider_crosswalk_review_report": ("build_provider_crosswalk_review_report",),
    "free_fixture_result_sync": ("sync_free_source_results",),
    "free_fixture_canonical_promotion": ("review_and_promote_free_fixture_observations",),
    "free_fixture_provider_refresh": ("refresh_free_fixture_sources",),
    "free_fixture_crosswalk_audit": ("build_crosswalk_audit",),
    "learning_dataset": ("build_learning_dataset",),
    "learning_experiments": ("run_offline_experiments",),
    "learning_readiness_audit": ("build_learning_readiness_audit",),
}


def main() -> int:
    checks = []
    app_path = Path(__file__).with_name("app.py")
    try:
        source = app_path.read_text(encoding="utf-8")
        compile(source, str(app_path), "exec")
        checks.append({"id": "app_entrypoint_syntax", "status": "pass"})
    except Exception as exc:
        checks.append({
            "id": "app_entrypoint_syntax",
            "status": "fail",
            "error_type": type(exc).__name__,
            "line": getattr(exc, "lineno", None),
        })

    for module_name in APP_MODULES:
        try:
            importlib.import_module(module_name)
            checks.append({"id": f"import:{module_name}", "status": "pass"})
        except Exception as exc:
            # Do not print exception messages: third-party errors can contain
            # connection details or credential-bearing URLs.
            checks.append({
                "id": f"import:{module_name}",
                "status": "fail",
                "error_type": type(exc).__name__,
            })

    for module_name, symbol_names in APP_SYMBOLS.items():
        try:
            module = importlib.import_module(module_name)
            for symbol_name in symbol_names:
                status = "pass" if callable(getattr(module, symbol_name, None)) else "fail"
                check = {"id": f"symbol:{module_name}.{symbol_name}", "status": status}
                if status == "fail":
                    check["error_type"] = "MissingOrNonCallableSymbol"
                checks.append(check)
        except Exception as exc:
            checks.append({
                "id": f"symbols:{module_name}",
                "status": "fail",
                "error_type": type(exc).__name__,
            })

    failed = [check for check in checks if check["status"] == "fail"]
    report = {
        "operation": "application_code_smoke_check",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if failed else "pass",
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
        "scope": (
            "Entry-point syntax and imports of app.py internal modules. "
            "Does not authenticate to the live Streamlit session or test "
            "provider credentials, external APIs, or database connectivity."
        ),
    }
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
