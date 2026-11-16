import unittest
from unittest.mock import patch

from sportmonks_team_scope_metadata_audit import (
    build_team_scope_inventory,
    resolve_country_ids,
    audit_sportmonks_team_scope,
)


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")
    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []
    def get(self, url, timeout):
        self.urls.append((url, timeout))
        return self.responses[url.rsplit("/", 1)[-1]]


class FakeClient:
    base_url = "https://api.sportmonks.com/v3/football"
    timeout = 20
    def __init__(self, responses):
        self.session = FakeSession(responses)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class SportmonksTeamScopeMetadataAuditTests(unittest.TestCase):
    def test_inventory_counts_native_country_ids_type_and_gender(self):
        report = build_team_scope_inventory([
            {"provider_entity_id": "1", "name": "Club A", "raw_payload": {
                "raw_payload": {"country_id": 32, "type": "domestic", "gender": "male"}}},
            {"provider_entity_id": "2", "name": "Club B", "raw_payload": {
                "raw_payload": {"country_id": 32, "type": "domestic", "gender": "male"}}},
            {"provider_entity_id": "3", "name": "National A", "raw_payload": {
                "raw_payload": {"country_id": 462, "type": "national", "gender": "male"}}},
            {"provider_entity_id": "4", "name": "Unknown", "raw_payload": {
                "raw_payload": {"gender": "male"}}},
        ])
        self.assertEqual(report["team_rows_examined"], 4)
        self.assertEqual(report["country_id_team_counts"], {"32": 2, "462": 1})
        self.assertEqual(report["teams_without_country_id"], 1)
        self.assertEqual(report["team_type_value_counts"], {"domestic": 2, "national": 1})
        self.assertEqual(report["teams_without_team_type"], 1)
        self.assertEqual(report["gender_value_counts"], {"male": 4})

    def test_country_resolution_requires_exact_returned_id(self):
        responses = {
            "32": FakeResponse(200, {"data": {"id": 32, "name": "England", "iso2": "GB"}}),
            "462": FakeResponse(200, {"data": {"id": 999, "name": "Wrong country"}}),
        }
        client = FakeClient(responses)
        report = resolve_country_ids(["32", "462"], client)
        self.assertEqual(report["32"]["status"], "resolved_exact_id")
        self.assertEqual(report["32"]["name"], "England")
        self.assertEqual(report["462"]["status"], "unresolved_response")
        self.assertEqual(client.session.urls, [
            ("https://api.sportmonks.com/v3/core/countries/32", 20),
            ("https://api.sportmonks.com/v3/core/countries/462", 20),
        ])

    def test_database_audit_is_read_only_and_writes_nothing(self):
        class Cursor:
            def __init__(self):
                self.calls = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query):
                self.calls.append(query)
            def fetchall(self):
                return [("1", "Club A", {"raw_payload": {"country_id": 32, "type": "domestic"}})]
        class Connection:
            def __init__(self):
                self.value = Cursor()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def cursor(self):
                return self.value
        connection = Connection()
        client = FakeClient({"32": FakeResponse(200, {"data": {"id": 32, "name": "England"}})})
        with patch("sportmonks_team_scope_metadata_audit._connect", return_value=connection):
            report = audit_sportmonks_team_scope("db", client_factory=lambda: client)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["database_writes"])
        self.assertEqual(report["canonical_ids_assigned"], 0)
        self.assertEqual(report["provider_links_created"], 0)
        self.assertEqual(report["country_ids_resolved"], 1)
        self.assertEqual(connection.value.calls[0], "SET TRANSACTION READ ONLY")
        self.assertTrue(all(query.lstrip().upper().startswith(("SET", "SELECT"))
                            for query in connection.value.calls))


if __name__ == "__main__":
    unittest.main()
