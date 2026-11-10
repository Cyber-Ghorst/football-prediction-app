import unittest
from unittest.mock import patch

from provider_entity_crosswalk import (
    build_entity_crosswalk_candidates,
    normalize_entity_name,
    save_explicit_provider_entity_links,
)


class FakeCursor:
    def __init__(self, *, canonical_exists=True, existing_link=None):
        self.canonical_exists = canonical_exists
        self.existing_link = existing_link
        self.last_result = None
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT team_id FROM football_teams" in sql:
            self.last_result = (params[0],) if self.canonical_exists else None
        elif "SELECT canonical_entity_id FROM provider_entity_links" in sql:
            self.last_result = self.existing_link
        else:
            self.last_result = None

    def fetchone(self):
        return self.last_result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class ProviderEntityCrosswalkTests(unittest.TestCase):
    def test_name_normalization_removes_accents_and_punctuation(self):
        self.assertEqual(normalize_entity_name("Atlético-Madrid"), "atletico madrid")
        self.assertEqual(normalize_entity_name("A&B FC"), "a and b fc")

    def test_team_exact_name_and_country_is_only_a_candidate(self):
        rows = build_entity_crosswalk_candidates(
            "openligadb", "team",
            [{"id": 99, "name": "Arsenal FC", "country": "England"}],
            [{"team_id": "sportmonks:1", "name": "Arsenal FC", "country": "England"}],
        )
        self.assertEqual(rows[0]["status"], "candidate_requires_manual_approval")
        self.assertEqual(rows[0]["canonical_entity_id"], "sportmonks:1")
        self.assertIn("manual review", rows[0]["reason"])
        
    def test_missing_country_never_creates_automatic_team_candidate(self):
        rows = build_entity_crosswalk_candidates(
            "openfootball", "team",
            [{"name": "Arsenal FC", "id": "team-a"}],
            [{"team_id": "sportmonks:1", "name": "Arsenal FC", "country": "England"}],
        )
        self.assertEqual(rows[0]["status"], "no_exact_contextual_match")
        self.assertIsNone(rows[0]["canonical_entity_id"])

    def test_duplicate_exact_matches_are_flagged_ambiguous(self):
        rows = build_entity_crosswalk_candidates(
            "livescore_football", "team",
            [{"id": "t-1", "name": "United FC", "country": "England"}],
            [
                {"team_id": "sportmonks:1", "name": "United FC", "country": "England"},
                {"team_id": "sportmonks:2", "name": "United FC", "country": "England"},
            ],
        )
        self.assertEqual(rows[0]["status"], "ambiguous_multiple_canonical_matches")
        self.assertIsNone(rows[0]["canonical_entity_id"])

    def test_season_requires_a_previously_verified_parent_competition(self):
        source = [{"id": "s-26", "name": "2026/27", "league_id": "league-9"}]
        canonical = [{"season_id": "sportmonks:2026", "name": "2026/27",
                      "league_id": "sportmonks:league-1"}]
        missing = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
        )
        self.assertEqual(missing[0]["status"], "parent_competition_unmapped")
        mapped = build_entity_crosswalk_candidates(
            "openligadb", "season", source, canonical,
            canonical_parent_ids={"league-9": "sportmonks:league-1"},
        )
        self.assertEqual(mapped[0]["status"], "candidate_requires_manual_approval")

    def test_explicit_link_requires_reason_and_existing_canonical_entity(self):
        with self.assertRaisesRegex(ValueError, "approval_reason"):
            save_explicit_provider_entity_links(
                "provider-db",
                links=[{"provider": "openligadb", "entity_type": "team",
                        "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                approval_reason="approved",
            )
        cursor = FakeCursor(canonical_exists=False)
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            with self.assertRaisesRegex(ValueError, "does not exist"):
                save_explicit_provider_entity_links(
                    "provider-db",
                    links=[{"provider": "openligadb", "entity_type": "team",
                            "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                    approval_reason="Reviewed against the official club identity.",
                )

    def test_explicit_link_inserts_only_after_manual_approval(self):
        cursor = FakeCursor(canonical_exists=True)
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            saved = save_explicit_provider_entity_links(
                "provider-db",
                links=[{"provider": "openligadb", "entity_type": "team",
                        "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                approval_reason="Reviewed against the official club identity.",
            )
        self.assertEqual(saved, 1)
        self.assertTrue(any("INSERT INTO provider_entity_links" in sql for sql, _ in cursor.executed))
        audit = next(params for sql, params in cursor.executed if "INSERT INTO provider_entity_link_approval_audit" in sql)
        self.assertEqual(audit[-1], "Reviewed against the official club identity.")

    def test_conflicting_existing_link_is_not_overwritten(self):
        cursor = FakeCursor(canonical_exists=True, existing_link=("sportmonks:other",))
        with patch("provider_entity_crosswalk.ensure_football_repository"),              patch("provider_entity_crosswalk._connect", return_value=FakeConnection(cursor)):
            with self.assertRaisesRegex(ValueError, "Conflicting existing link"):
                save_explicit_provider_entity_links(
                    "provider-db",
                    links=[{"provider": "openligadb", "entity_type": "team",
                            "provider_entity_id": "99", "canonical_entity_id": "sportmonks:1"}],
                    approval_reason="Reviewed against the official club identity.",
                )
        self.assertFalse(any("INSERT INTO provider_entity_links" in sql for sql, _ in cursor.executed))


if __name__ == "__main__":
    unittest.main()
