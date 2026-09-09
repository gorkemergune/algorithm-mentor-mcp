import pytest

from src.domain.topics import load_topics
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
    return {"arrays": (), "hashmap": ("arrays",), "trees": ()}


class TestSeeding:
    def test_every_topic_is_seeded_at_zero(self, conn, topics):
        result = assess_level("tr", connection=conn, topics=topics)

        assert result["topic_estimates"] == {"arrays": 0.0, "hashmap": 0.0, "trees": 0.0}
        assert db.get_topic_scores(conn) == {"arrays": 0.0, "hashmap": 0.0, "trees": 0.0}

    def test_new_profile_starts_as_beginner(self, conn, topics):
        assert assess_level("tr", connection=conn, topics=topics)["estimated_level"] == "beginner"

    def test_profile_row_is_created_with_the_language(self, conn, topics):
        assess_level("en", connection=conn, topics=topics)
        profile = db.get_profile(conn)

        assert profile["preferred_language"] == "en"
        assert profile["level"] == "beginner"

    def test_current_focus_is_the_recommended_topic(self, conn, topics):
        result = assess_level("tr", connection=conn, topics=topics)
        assert db.get_profile(conn)["current_focus"] == result["recommended_start_topic"]

    def test_real_topic_graph_seeds_every_topic(self, conn):
        result = assess_level("tr", connection=conn)
        assert set(result["topic_estimates"]) == set(load_topics())
        assert result["recommended_start_topic"] == "arrays"


class TestRecommendedStartTopic:
    def test_prerequisite_free_topic_is_chosen(self, conn, topics):
        result = assess_level("tr", connection=conn, topics=topics)
        assert result["recommended_start_topic"] in ("arrays", "trees")

    def test_ties_follow_the_file_order(self, conn, topics):
        assert assess_level("tr", connection=conn, topics=topics)[
            "recommended_start_topic"
        ] == "arrays"

    def test_lowest_scoring_root_wins(self, conn, topics):
        assess_level("tr", connection=conn, topics=topics)
        db.set_topic_score(conn, "arrays", 0.9)

        result = assess_level("tr", connection=conn, topics=topics)
        assert result["recommended_start_topic"] == "trees"

    def test_graph_without_a_root_is_rejected(self, conn):
        with pytest.raises(ValueError, match="prerequisite-free"):
            assess_level("tr", connection=conn, topics={"a": ("b",), "b": ("a",)})


class TestRepeatedCalls:
    def test_second_call_without_retake_changes_nothing(self, conn, topics):
        assess_level("tr", connection=conn, topics=topics)
        update_profile("arrays", "arrays_012", 1.0, ["kanıt"], connection=conn)

        result = assess_level("tr", connection=conn, topics=topics)

        assert result["topic_estimates"]["arrays"] == pytest.approx(0.3)
        assert db.get_recent_evidence(conn)["arrays"] == ["kanıt"]

    def test_retake_reseeds_scores_and_clears_errors(self, conn, topics):
        assess_level("tr", connection=conn, topics=topics)
        update_profile("arrays", "arrays_012", 1.0, ["kanıt"], connection=conn)

        result = assess_level("tr", retake=True, connection=conn, topics=topics)

        assert result["topic_estimates"]["arrays"] == 0.0
        assert result["estimated_level"] == "beginner"
        assert db.get_recent_evidence(conn) == {}

    def test_retake_keeps_the_attempt_history(self, conn, topics):
        assess_level("tr", connection=conn, topics=topics)
        update_profile("arrays", "arrays_012", 1.0, ["kanıt"], connection=conn)

        assess_level("tr", retake=True, connection=conn, topics=topics)

        assert len(db.get_attempts(conn)) == 1

    def test_retake_can_switch_the_language(self, conn, topics):
        assess_level("tr", connection=conn, topics=topics)
        assess_level("en", retake=True, connection=conn, topics=topics)

        assert db.get_profile(conn)["preferred_language"] == "en"


class TestInputValidation:
    def test_unsupported_language_is_rejected(self, conn, topics):
        with pytest.raises(ValueError, match="preferred_language"):
            assess_level("de", connection=conn, topics=topics)

    def test_rejected_language_creates_no_profile(self, conn, topics):
        with pytest.raises(ValueError):
            assess_level("de", connection=conn, topics=topics)

        assert db.get_profile(conn) is None
