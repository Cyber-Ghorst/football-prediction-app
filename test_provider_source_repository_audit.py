import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import provider_source_repository_audit


class ProviderSourceRepositoryAuditTests(unittest.TestCase):
    def test_audit_includes_every_staged_provider_catalogue(self):
        expected_providers = {
            "api_football",
            "api_ninjas",
            "highlightly",
            "livescore_football",
            "sportmonks",
        }
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "provider-source-audit.json"
            with (
                patch.dict(os.environ, {"PROVIDER_DATABASE_URL": "postgresql://readonly"}),
                patch.object(
                    provider_source_repository_audit,
                    "audit_provider_source_evidence",
                    side_effect=lambda _database_url, provider: {"provider": provider},
                ),
                patch.object(provider_source_repository_audit, "REPORT", report_path),
            ):
                result = provider_source_repository_audit.main()

            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(set(report["providers"]), expected_providers)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_writes"])
        self.assertEqual(report["canonical_entities_created"], 0)
        self.assertEqual(report["cross_provider_links_created"], 0)
        self.assertFalse(report["prediction_ledger_touched"])


if __name__ == "__main__":
    unittest.main()
