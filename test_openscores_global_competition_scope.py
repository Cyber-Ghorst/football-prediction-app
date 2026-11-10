import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from openscores_fixture_observation_sync import run_sync


class FakeOpenScores:
    def __init__(self, pages, leagues=None, seasons=None):
        self.pages = pages
        self.seasons = seasons if seasons is not None else {
            "1": [
                {"id": 2025, "league_id": 1},
                {"id": 2026, "league_id": 1},
            ],
            "2": [{"id": 2027, "league_id": 2}],
        }
        self.missing_season_returned = False
        self.leagues = leagues if leagues is not None else [
            {"id": 1, "name": "League One"},
            {"id": 2, "name": "League Two"},
        ]
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def list_leagues(self):
        return {"data": {"leagues": self.leagues}}

    def list_seasons(self, league_id):
        return {"data": {"seasons": self.seasons.get(str(league_id), [])}}

    @staticmethod
    def _league_collection(data):
        return data["leagues"], "$"

    def list_fixtures(self, **filters):
        self.calls.append(filters)
        payload = self.pages[filters["page"] - 1]
        items = payload["data"]["items"]
        selected = [
            row for row in items
            if row.get("season_id") is not None
            and str(row.get("season_id")) == str(filters["season_id"])
        ]
        for row in items:
            if row.get("season_id") is None and not self.missing_season_returned:
                selected.append(row)
                self.missing_season_returned = True
        return {
            "retrieved_at_utc": payload["retrieved_at_utc"],
            "data": {
                "items": selected,
                "pagination": {
                    "page": filters["page"],
                    "total_pages": payload["data"]["pagination"]["total_pages"],
                },
            },
        }


def fixture(fid, league_id, season_id, kickoff="2026-11-12T19:00:00Z"):
    return {
        "id": fid,
        "league_id": league_id,
        "season_id": season_id,
        "scheduled_kickoff_at": kickoff,
        "home_team": {"id": f"h{fid}", "name": f"Home {fid}"},
        "away_team": {"id": f"a{fid}", "name": f"Away {fid}"},
        "status": "scheduled",
    }


def page(items, total_pages=1):
    return {
        "retrieved_at_utc": "2026-11-10T17:00:00Z",
        "data": {"items": items, "pagination": {"page": 1, "total_pages": total_pages}},
    }


class GlobalCompetitionScopeTests(unittest.TestCase):
    def _run(self, client):
        with patch(
            "openscores_fixture_observation_sync.upsert_openscores_observations",
            side_effect=lambda _db, rows: {
                "observations_upserted": len(rows),
                "canonical_fixtures_written": 0,
            },
        ) as save, patch(
            "openscores_fixture_observation_sync.mark_outside_upcoming_window_observations",
            return_value=0,
        ), patch(
            "openscores_fixture_observation_sync.reconcile_openscores_observations",
            return_value={"observations_checked": 0, "matched": 0, "pending_entity_mapping": 0},
        ):
            report = run_sync(
                client_factory=lambda: client,
                database_url="postgresql://db",
                now=datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc),
            )
        return report, save

    def test_global_query_groups_each_fixture_by_its_own_league_and_season(self):
        client = FakeOpenScores([page([
            fixture(77, 1, 2025),
            fixture(78, 2, 2027),
            fixture(79, 1, 2026),
        ])])
        report, save = self._run(client)

        self.assertEqual(len(client.calls), 3)
        self.assertEqual(
            {call["season_id"] for call in client.calls},
            {"2025", "2026", "2027"},
        )
        for filters in client.calls:
            self.assertEqual(filters["status"], "scheduled")
            self.assertEqual(filters["date_from"], "2026-11-10T18:00:00Z")
            self.assertEqual(filters["date_to"], "2026-11-17T18:00:00Z")
            self.assertEqual(filters["page"], 1)
            self.assertEqual(filters["page_size"], 200)
        rows = save.call_args.args[1]
        self.assertEqual(
            {(row["provider_fixture_id"], row["provider_league_id"], row["provider_season_id"])
             for row in rows},
            {("77", "1", "2025"), ("78", "2", "2027"), ("79", "1", "2026")},
        )
        self.assertEqual(report["fixtures_accepted_for_window"], 3)
        self.assertEqual(report["seasons_sampled"], 3)
        self.assertEqual(report["status"], "pass")

    def test_missing_or_unknown_competition_identity_is_never_guessed(self):
        client = FakeOpenScores([page([
            fixture(80, 1, 2026),
            {"id": 81, "season_id": 2026, "status": "scheduled",
             "scheduled_kickoff_at": "2026-11-12T19:00:00Z",
             "home_team": {"id": "h81", "name": "Home"},
             "away_team": {"id": "a81", "name": "Away"}},
            fixture(82, 999, 2026),
            {
                "id": 83, "league_id": 2, "status": "scheduled",
                "scheduled_kickoff_at": "2026-11-12T19:00:00Z",
                "home_team": {"id": "h83", "name": "Home"},
                "away_team": {"id": "a83", "name": "Away"},
            },
        ])])
        report, save = self._run(client)

        self.assertEqual(report["fixtures_missing_league_id"], 0)
        self.assertEqual(report["fixtures_unknown_league_id"], 1)
        self.assertEqual(report["fixtures_missing_season_id"], 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 2)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(
            {row["provider_fixture_id"] for row in save.call_args.args[1]},
            {"80", "81"},
        )

    def test_pagination_fetches_all_reported_pages(self):
        client = FakeOpenScores([
            page([fixture(90, 1, 2026)], total_pages=2),
            page([fixture(91, 2, 2027)], total_pages=2),
        ])
        report, save = self._run(client)

        self.assertEqual(len(client.calls), 6)
        self.assertEqual(report["pages_fetched"], 6)
        self.assertEqual(report["fixtures_accepted_for_window"], 2)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(len(save.call_args.args[1]), 2)


    def test_global_query_recognizes_all_discovered_leagues_by_default(self):
        leagues = [{"id": index, "name": f"League {index}"} for index in range(1, 9)]
        client = FakeOpenScores(
            [page([fixture(101, 8, 8008)])],
            leagues=leagues,
            seasons={"8": [{"id": 8008, "league_id": 8}]},
        )
        report, save = self._run(client)

        self.assertEqual(report["leagues_discovered"], 8)
        self.assertEqual(report["fixtures_unknown_league_id"], 0)
        self.assertEqual(report["fixtures_accepted_for_window"], 1)
        self.assertEqual(save.call_args.args[1][0]["provider_league_id"], "8")


    def test_fixture_without_league_id_uses_explicit_season_parent_mapping(self):
        client = FakeOpenScores(
            [page([fixture(112, None, 2026)])],
            seasons={"1": [{"id": 2026, "league_id": 1}]},
        )
        report, save = self._run(client)

        self.assertEqual(report["season_mappings_discovered"], 1)
        self.assertEqual(report["fixtures_missing_league_id"], 0)
        self.assertEqual(report["fixtures_accepted_for_window"], 1)
        self.assertEqual(save.call_args.args[1][0]["provider_league_id"], "1")
        self.assertEqual(report["status"], "pass")

    def test_explicit_league_conflicting_with_season_parent_is_rejected(self):
        client = FakeOpenScores(
            [page([fixture(113, 2, 2026)])],
            seasons={"1": [{"id": 2026, "league_id": 1}]},
        )
        report, save = self._run(client)

        self.assertEqual(report["fixtures_season_league_mismatch"], 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 0)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(save.call_args.args[1], [])


    def test_explicit_fixture_league_resolves_reused_season_id(self):
        client = FakeOpenScores(
            [page([fixture(114, 2, 2026)])],
            seasons={
                "1": [{"id": 2026, "league_id": 1}],
                "2": [{"id": 2026, "league_id": 2}],
            },
        )
        report, save = self._run(client)

        self.assertEqual(report["fixtures_ambiguous_season_id"], 0)
        self.assertEqual(report["fixtures_season_league_mismatch"], 0)
        self.assertEqual(report["fixtures_accepted_for_window"], 1)
        self.assertEqual(save.call_args.args[1][0]["provider_league_id"], "2")

    def test_conflicting_provider_fixture_identity_is_excluded(self):
        client = FakeOpenScores([page([
            fixture(111, 1, 2026),
            fixture(111, 2, 2027),
        ])])
        report, save = self._run(client)

        self.assertEqual(report["fixtures_duplicate_provider_id"], 1)
        self.assertEqual(report["fixtures_conflicting_provider_id"], 1)
        self.assertEqual(report["fixtures_accepted_for_window"], 0)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(save.call_args.args[1], [])

    def test_pagination_cap_is_reported_as_partial(self):
        full_page = [fixture(i + 1, 1, 2026) for i in range(200)]
        client = FakeOpenScores(
            [page(full_page, total_pages=12) for _ in range(10)],
            seasons={"1": [{"id": 2026, "league_id": 1}]},
        )
        report, _ = self._run(client)

        self.assertEqual(len(client.calls), 10)
        self.assertTrue(report["pagination_truncated"])
        self.assertEqual(report["status"], "partial")


if __name__ == "__main__":
    unittest.main()
