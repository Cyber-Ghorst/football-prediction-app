import unittest

from openscores_data_shape_audit import extract_id, find_records, payload_shape


class OpenScoresDataShapeAuditTests(unittest.TestCase):
    def test_finds_nested_fixture_collection(self):
        payload = {"response": {"fixtures": [{"id": 42, "home_team": {"id": 7}}]}}
        rows, path = find_records(payload, ("fixtures", "items", "data"))
        self.assertEqual(path, "response.fixtures")
        self.assertEqual(rows[0]["id"], 42)

    def test_extracts_team_id_from_nested_fixture_object(self):
        fixture = {"home_team": {"id": 7, "name": "Example FC"}}
        self.assertEqual(extract_id(fixture, ("home_team_id",), ("home_team",)), 7)

    def test_extracts_direct_provider_id(self):
        self.assertEqual(extract_id({"player_id": "p-123"}, ("id", "player_id")), "p-123")

    def test_schema_report_does_not_publish_values(self):
        shape = payload_shape({"id": 42, "name": "Private Team Name", "players": [{"id": 9}]})
        self.assertEqual(shape["root_keys"], ["id", "name", "players"])
        self.assertNotIn("Private Team Name", str(shape))
        self.assertNotIn("42", str(shape))
        self.assertEqual(shape["fields"]["players"]["first_item_keys"], ["id"])


if __name__ == "__main__":
    unittest.main()
