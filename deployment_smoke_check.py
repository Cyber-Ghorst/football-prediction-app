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
)


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
