from datetime import datetime, timezone\n\nfrom prediction_results import verified_final_score, group_completed_fixture_candidates


def _record():
    return {
        "fixture_id": "19721930",
        "home_team": "Brighton & Hove Albion",
        "away_team": "Fulham",
        "competition": "Premier League",
        "season": "2026",
    }


def _fixture(state_id=5, description="2ND_HALF"):
    return {
        "id": 19721930,
        "state_id": state_id,
        "league": {"name": "Premier League"},
        "season": {"starting_at": "2026-07-01"},
        "participants": [
            {"name": "Brighton & Hove Albion", "meta": {"location": "home"}},
            {"name": "Fulham", "meta": {"location": "away"}},
        ],
        "scores": [
            {"description": description, "score": {"participant": "home", "goals": 2}},
            {"description": description, "score": {"participant": "away", "goals": 1}},
        ],
    }


def test_verified_completed_score_is_returned():
    assert verified_final_score(_record(), _fixture()) == (2, 1)


def test_wrong_fixture_id_is_rejected():
    fixture = _fixture()
    fixture["id"] = 999
    assert verified_final_score(_record(), fixture) is None


def test_wrong_home_or_away_identity_is_rejected():
    fixture = _fixture()
    fixture["participants"][0]["name"] = "Brighton City"
    assert verified_final_score(_record(), fixture) is None


def test_wrong_competition_or_season_is_rejected():
    fixture = _fixture()
    fixture["league"]["name"] = "FA Cup"
    assert verified_final_score(_record(), fixture) is None
    fixture = _fixture()
    fixture["season"]["starting_at"] = "2025-07-01"
    assert verified_final_score(_record(), fixture) is None


def test_unfinished_fixture_is_rejected():
    assert verified_final_score(_record(), _fixture(state_id=3)) is None


def test_extra_time_match_requires_regulation_score():
    fixture = _fixture(state_id=7, description="CURRENT")
    assert verified_final_score(_record(), fixture) is None
    fixture = _fixture(state_id=7, description="2ND_HALF")
    assert verified_final_score(_record(), fixture) == (2, 1)


def test_regular_time_match_can_use_current_score_if_needed():
    assert verified_final_score(_record(), _fixture(description="CURRENT")) == (2, 1)


def test_missing_or_invalid_score_is_rejected():
    fixture = _fixture()
    fixture["scores"] = fixture["scores"][:1]
    assert verified_final_score(_record(), fixture) is None
    fixture = _fixture()
    fixture["scores"][0]["score"]["goals"] = -1
    assert verified_final_score(_record(), fixture) is None



def test_result_sync_groups_duplicate_records_by_fixture():
    now = datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)
    first = {**_record(), "fixture_provider": "sportmonks",
             "kickoff_at": "2026-11-08T16:00:00+00:00"}
    duplicate = {**first, "record_id": "second"}
    other = {**first, "fixture_id": "19721931"}
    future = {**first, "fixture_id": "19721932",
              "kickoff_at": "2026-11-09T16:00:00+00:00"}
    unlinked = {**first, "fixture_id": ""}
    wrong_provider = {**first, "fixture_id": "api-1",
                      "fixture_provider": "highlightly"}
    groups = group_completed_fixture_candidates(
        [first, duplicate, other, future, unlinked, wrong_provider], now
    )
    assert len(groups) == 2
    assert [len(group) for group in groups] == [2, 1]


def test_result_sync_does_not_overwrite_records_with_existing_scores():
    now = datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)
    manual = {**_record(), "fixture_provider": "sportmonks",
              "kickoff_at": "2026-11-08T16:00:00+00:00",
              "actual_home_goals": "1", "actual_away_goals": "0"}
    blank = {**manual, "record_id": "blank",
             "actual_home_goals": "", "actual_away_goals": ""}
    groups = group_completed_fixture_candidates([manual, blank], now)
    assert len(groups) == 1
    assert groups[0] == [blank]
