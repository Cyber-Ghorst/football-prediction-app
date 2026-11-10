import unittest

from tipmaster_refresh_job import run_refresh


def _record(match_id):
    return {
        "source": "tipmaster",
        "source_match_id": match_id,
        "kickoff_at": "2026-11-11T18:00:00+00:00",
        "fetched_at": "2026-11-10T04:13:00+00:00",
        "prediction_inputs_eligible": False,
        "groups": {"top20": {"sample": 100, "shares": {"home": .7, "draw": .2, "away": .1}}},
    }


class ScheduledTipMasterRefreshTests(unittest.TestCase):
    def test_refresh_verifies_every_saved_record_and_never_touches_ledger(self):
        rows = [_record("one"), _record("two")]
        stored = {}

        def fetcher():
            return {"matches": rows, "counts": {"received": 2, "accepted": 2}}

        def loader(_database_url):
            return list(stored.values())

        def saver(_database_url, incoming):
            stored.update({row["source_match_id"]: row for row in incoming})
            return len(incoming)

        report = run_refresh("postgresql://test", fetcher=fetcher, loader=loader, saver=saver)
        self.assertEqual(report["incoming_records"], 2)
        self.assertEqual(report["saved_records"], 2)
        self.assertTrue(report["round_trip_verified"])
        self.assertEqual(report["missing_reloaded_ids_count"], 0)
        self.assertFalse(report["prediction_ledger_touched"])

    def test_refresh_fails_when_any_saved_record_is_missing_after_reload(self):
        rows = [_record("one"), _record("two")]
        report = None

        def fetcher():
            return {"matches": rows}

        def loader(_database_url):
            return [_record("one")]

        def saver(_database_url, incoming):
            return len(incoming)

        with self.assertRaises(RuntimeError):
            run_refresh("postgresql://test", fetcher=fetcher, loader=loader, saver=saver)

    def test_refresh_rejects_empty_feed(self):
        with self.assertRaises(RuntimeError):
            run_refresh(
                "postgresql://test",
                fetcher=lambda: {"matches": []},
                loader=lambda _url: [],
                saver=lambda _url, _rows: 0,
            )

    def test_refresh_requires_database_url(self):
        with self.assertRaises(ValueError):
            run_refresh("")


if __name__ == "__main__":
    unittest.main()
