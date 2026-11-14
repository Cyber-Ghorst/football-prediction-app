from datetime import datetime, timezone

from priority_a_provider_observation_audit import build_priority_a_observation_audit


def _queue():
    return {
        "entries": [{
            "priority": "A",
            "catalogue_entry_id": "observed_competition_032",
            "display_names": ["Premier League"],
            "countries": ["England"],
            "providers": ["openfootball", "openligadb"],
            "source_records": [
                {
                    "provider": "openfootball",
                    "provider_competition_id": "en.1",
                    "seasons": [{"provider_season_id": "en.1::2026-27", "observation_count": 2}],
                },
                {
                    "provider": "openligadb",
                    "provider_competition_id": "5996",
                    "seasons": [{"provider_season_id": "5996::2026", "observation_count": 2}],
                },
            ],
        }]
    }


def _snapshot(provider, comp_id, season_id, fixture_id):
    return {
        "provider": provider,
        "resource_type": "future_fixture_observations",
        "payload": {"observations": [{
            "competition_key": comp_id,
            "competition_name": "Premier League",
            "country": "England",
            "season_key": season_id,
            "season_name": "2026/27",
            "provider_fixture_id": fixture_id,
            "home_team_name": "Arsenal",
            "away_team_name": "Chelsea",
            "kickoff_utc": "2026-11-20T19:00:00Z",
            "status": "scheduled",
            "eligible_for_review": True,
            "raw_payload": {},
        }]},
    }


def test_exact_fixture_overlap_is_reported_without_approving_identity():
    report = build_priority_a_observation_audit(
        _queue(),
        [
            _snapshot("openfootball", "en.1", "2026-27", "of-1"),
            _snapshot("openligadb", "5996", "2026", "oldb-1"),
        ],
        generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
    )
    assert report["exact_overlap_count"] == 1
    assert report["entries"][0]["exact_cross_provider_fixture_overlap_count"] == 1
    assert report["entries"][0]["identity_decision"] == "not_approved"
    assert report["safeguards"]["provider_link_writes"] == 0


def test_no_matching_snapshot_is_not_interpreted_as_provider_absence():
    report = build_priority_a_observation_audit(
        _queue(), [], generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc)
    )
    statuses = [row["status"] for row in report["entries"][0]["provider_sources"]]
    assert statuses == ["no_matching_raw_observations_in_selected_snapshots"] * 2
    assert "not that the provider lacks the competition" in report["interpretation"]


def test_ineligible_or_timezone_less_rows_do_not_count_as_exact_overlap():
    left = _snapshot("openfootball", "en.1", "2026-27", "of-1")
    right = _snapshot("openligadb", "5996", "2026", "oldb-1")
    right["payload"]["observations"][0]["eligible_for_review"] = False
    report = build_priority_a_observation_audit(
        _queue(), [left, right], generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc)
    )
    assert report["exact_overlap_count"] == 0



def test_date_only_source_payload_is_not_reported_as_completely_missing_kickoff():
    snapshot = _snapshot("openfootball", "en.1", "2026-27", "of-date-only")
    row = snapshot["payload"]["observations"][0]
    row["kickoff_utc"] = None
    row["eligible_for_review"] = False
    row["raw_payload"] = {"date": "2026-11-20", "team1": "Arsenal", "team2": "Chelsea"}
    report = build_priority_a_observation_audit(
        _queue(), [snapshot], generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc)
    )
    source = report["entries"][0]["provider_sources"][0]
    assert source["date_only_kickoffs"] == 1
    assert source["missing_kickoffs"] == 0
    assert source["kickoff_value_examples"] == ["date=2026-11-20"]
    assert report["exact_overlap_count"] == 0


def test_country_alias_usa_matches_united_states_without_rewriting_source_country():
    queue = {
        "entries": [{
            "priority": "A",
            "catalogue_entry_id": "observed_competition_094",
            "display_names": ["MLS"],
            "countries": ["United States"],
            "providers": ["bzzoiro"],
            "source_records": [{
                "provider": "bzzoiro",
                "provider_competition_id": "18",
                "seasons": [{"provider_season_id": "18::158", "observation_count": 1}],
            }],
        }]
    }
    snapshot = {
        "provider": "bzzoiro",
        "resource_type": "future_fixture_observations",
        "payload": {"observations": [{
            "competition_key": "18",
            "competition_name": "MLS",
            "country": "USA",
            "season_key": "158",
            "season_name": "MLS 2026",
            "provider_fixture_id": "mls-1",
            "home_team_name": "Club A",
            "away_team_name": "Club B",
            "kickoff_utc": "2026-11-20T19:00:00Z",
            "status": "scheduled",
            "eligible_for_review": True,
            "raw_payload": {},
        }]},
    }
    report = build_priority_a_observation_audit(
        queue, [snapshot], generated_at=datetime(2026, 11, 14, tzinfo=timezone.utc)
    )
    source = report["entries"][0]["provider_sources"][0]
    assert source["country_matches_queue"] is True
    assert source["countries"] == ["USA"]
    assert report["entries"][0]["identity_decision"] == "not_approved"
