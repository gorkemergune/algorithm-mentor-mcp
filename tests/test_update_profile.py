import pytest

from src.domain import mastery
from src.storage import sqlite as db
from src.tools.assess_level import assess_level
from src.tools.update_profile import update_profile


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


@pytest.fixture
def topics():
    return {"arrays": (), "hashmap": ("arrays",)}


@pytest.fixture
def seeded(conn, topics):
    assess_level("tr", connection=conn, topics=topics)
    return conn


def update(conn, **overrides):
    kwargs = {
        "topic": "arrays",
        "problem_id": "arrays_012",
        "score": 1.0,
        "evidence": ["Correct algorithm, no hints needed"],
        "mistake_type": None,
        "hints_used": 0,
    }
    kwargs.update(overrides)
    return update_profile(connection=conn, **kwargs)


class TestScoreValidation:
    @pytest.mark.parametrize("score", [1.0, 0.8, 0.6, 0.5, 0.2])
    def test_table_scores_are_accepted(self, seeded, score):
        result = update(seeded, score=score)
        assert result["topic_scores"]["arrays"] == pytest.approx(score * mastery.ALPHA)

    @pytest.mark.parametrize("score", [0.95, 0.0, 1.5, 0.61, -0.2, 0.75])
    def test_host_invented_scores_are_rejected(self, seeded, score):
        with pytest.raises(ValueError, match="review_solution"):
            update(seeded, score=score)

    def test_float_imprecision_does_not_break_a_valid_score(self, seeded):
        # 0.1 + 0.7 == 0.7999999999999999; isclose(abs_tol=1e-9) kabul etmeli.
        result = update(seeded, score=0.1 + 0.7)
        assert result["topic_scores"]["arrays"] == pytest.approx(0.24)

    def test_a_rejected_score_writes_nothing(self, seeded):
        with pytest.raises(ValueError):
            update(seeded, score=0.99)

        assert db.get_topic_scores(seeded)["arrays"] == 0.0
        assert db.get_attempts(seeded) == []
        assert db.get_recent_evidence(seeded) == {}

    def test_negative_hints_are_rejected(self, seeded):
        with pytest.raises(ValueError, match="hints_used"):
            update(seeded, hints_used=-1)


class TestEma:
    def test_first_update_applies_alpha_to_the_seed(self, seeded):
        # 0.0 * 0.7 + 1.0 * 0.3
        assert update(seeded, score=1.0)["topic_scores"]["arrays"] == pytest.approx(0.3)

    def test_second_update_builds_on_the_first(self, seeded):
        update(seeded, score=1.0)
        # 0.3 * 0.7 + 0.2 * 0.3
        assert update(seeded, score=0.2)["topic_scores"]["arrays"] == pytest.approx(0.27)

    def test_matches_the_domain_formula(self, seeded):
        expected = mastery.update_topic_score(
            mastery.update_topic_score(0.0, 0.6), 0.8
        )
        update(seeded, score=0.6)
        result = update(seeded, score=0.8)

        assert result["topic_scores"]["arrays"] == pytest.approx(expected)

    def test_other_topics_are_untouched(self, seeded):
        result = update(seeded, score=1.0)
        assert result["topic_scores"]["hashmap"] == 0.0

    def test_level_is_recomputed_from_the_scores(self, seeded):
        for _ in range(12):
            update(seeded, score=1.0, topic="arrays")
            update(seeded, score=1.0, topic="hashmap", problem_id="hashmap_004")

        result = update(seeded, score=1.0)
        assert result["level"] == mastery.level_for_scores(result["topic_scores"])
        assert result["level"] == "advanced"
        assert db.get_profile(seeded)["level"] == "advanced"


class TestRecentErrors:
    def test_evidence_is_recorded_for_the_topic(self, seeded):
        result = update(seeded, score=0.2, evidence=["Approach incorrect"])
        assert result["recent_evidence"]["arrays"] == ["Approach incorrect"]

    def test_only_the_last_three_entries_survive(self, seeded):
        for index in range(5):
            update(seeded, score=0.2, evidence=[f"hata {index}"])

        stored = db.get_recent_evidence(seeded)["arrays"]
        assert stored == ["hata 4", "hata 3", "hata 2"]

    def test_a_multi_entry_evidence_list_is_also_trimmed(self, seeded):
        update(seeded, score=0.2, evidence=["bir", "iki", "üç", "dört"])
        assert len(db.get_recent_evidence(seeded)["arrays"]) == 3

    def test_empty_evidence_writes_nothing(self, seeded):
        result = update(seeded, score=1.0, evidence=[])
        assert result["recent_evidence"] == {}

    def test_topics_keep_separate_error_lists(self, seeded):
        update(seeded, score=0.2, evidence=["arrays hatası"])
        update(seeded, topic="hashmap", problem_id="hashmap_004", score=0.2,
               evidence=["hashmap hatası"])

        errors = db.get_recent_evidence(seeded)
        assert errors["arrays"] == ["arrays hatası"]
        assert errors["hashmap"] == ["hashmap hatası"]


class TestAttemptHistory:
    def test_every_update_appends_to_history(self, seeded):
        update(seeded, score=1.0)
        update(seeded, score=0.2, mistake_type="wrong_approach", hints_used=2)

        attempts = db.get_attempts(seeded)
        assert len(attempts) == 2
        assert attempts[0]["mistake_type"] == "wrong_approach"
        assert attempts[0]["hints_used"] == 2
        assert attempts[1]["score"] == 1.0

    def test_history_survives_pruned_recent_evidence(self, seeded):
        for index in range(5):
            update(seeded, score=0.2, evidence=[f"hata {index}"])

        assert len(db.get_attempts(seeded)) == 5
        assert len(db.get_recent_evidence(seeded)["arrays"]) == 3


class TestPreconditions:
    def test_without_a_profile_it_refuses(self, conn):
        with pytest.raises(LookupError, match="assess_level"):
            update(conn)

    def test_unseeded_topic_is_refused(self, seeded):
        with pytest.raises(LookupError, match="assess_level"):
            update(seeded, topic="graphs")

    def test_refusal_leaves_the_database_clean(self, conn):
        with pytest.raises(LookupError):
            update(conn)

        assert db.get_attempts(conn) == []
        assert db.get_topic_scores(conn) == {}


class TestReturnedSummary:
    def test_summary_shape(self, seeded):
        result = update(seeded, score=0.8)
        assert set(result) == {"topic_scores", "recent_evidence", "level"}

    def test_current_focus_follows_the_updated_topic(self, seeded):
        update(seeded, topic="hashmap", problem_id="hashmap_004", score=0.8)
        assert db.get_profile(seeded)["current_focus"] == "hashmap"
