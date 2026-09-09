import pytest

from src.domain.topics import load_topics
from src.storage import sqlite as db
from src.tools.assess_level import assess_level
from src.tools.get_next_topic import (
    REASON_LOWEST_SCORE,
    REASON_STUCK_FALLBACK,
    REASON_STUCK_NO_PREREQUISITE,
    get_next_topic,
)


@pytest.fixture
def graph():
    return {
        "arrays": (),
        "trees": (),
        "hashmap": ("arrays",),
        "dfs": ("trees",),
        "graphs": ("dfs", "hashmap"),
    }


@pytest.fixture
def conn(graph):
    connection = db.connect(":memory:")
    assess_level("tr", connection=connection, topics=graph)
    yield connection
    connection.close()


def set_scores(conn, **scores):
    for topic, score in scores.items():
        db.set_topic_score(conn, topic, score)


def fail_attempts(conn, topic, count, score=0.2):
    for _ in range(count):
        db.insert_attempt(
            conn,
            problem_id="p",
            topic=topic,
            score=score,
            evidence=["Approach incorrect"],
            hints_used=0,
            mistake_type="wrong_approach",
        )


class TestPrerequisiteGate:
    def test_blocked_topic_is_not_a_candidate(self, conn, graph):
        # hashmap skoru en düşük ama arrays eşiğin altında -> aday değil.
        set_scores(conn, arrays=0.3, trees=0.9, hashmap=0.0, dfs=0.9, graphs=0.9)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "arrays"

    def test_topic_unlocks_once_the_prerequisite_clears_the_threshold(self, conn, graph):
        set_scores(conn, arrays=0.6, trees=0.9, hashmap=0.1, dfs=0.9, graphs=0.9)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "hashmap"

    def test_threshold_is_inclusive_at_zero_point_six(self, conn, graph):
        set_scores(conn, arrays=0.59, trees=0.9, hashmap=0.0, dfs=0.9, graphs=0.9)
        assert get_next_topic(connection=conn, topics=graph)["recommended_topic"] == "arrays"

        set_scores(conn, arrays=0.6)
        assert get_next_topic(connection=conn, topics=graph)["recommended_topic"] == "hashmap"

    def test_topic_needs_all_of_its_prerequisites(self, conn, graph):
        # graphs: dfs tamam, hashmap değil -> graphs aday olmamalı.
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.5, dfs=0.9, graphs=0.0)

        assert get_next_topic(connection=conn, topics=graph)["recommended_topic"] == "hashmap"

    def test_every_topic_blocked_raises(self, conn):
        blocked = {"a": ("b",), "b": ("a",)}
        db.seed_topic_scores(conn, {"a": 0.0, "b": 0.0})

        with pytest.raises(LookupError, match="blocked"):
            get_next_topic(connection=conn, topics=blocked)


class TestLowestScore:
    def test_lowest_scoring_candidate_wins(self, conn, graph):
        set_scores(conn, arrays=0.8, trees=0.4, hashmap=0.9, dfs=0.7, graphs=0.9)

        assert get_next_topic(connection=conn, topics=graph)["recommended_topic"] == "trees"

    def test_ties_follow_the_topic_file_order(self, conn, graph):
        set_scores(conn, arrays=0.5, trees=0.5, hashmap=0.9, dfs=0.9, graphs=0.9)

        assert get_next_topic(connection=conn, topics=graph)["recommended_topic"] == "arrays"

    def test_reason_carries_the_percentage_and_prerequisites(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.24, dfs=0.9, graphs=0.9)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["reason_code"] == REASON_LOWEST_SCORE
        assert "24" in result["reason"]
        assert "arrays" in result["reason"]

    def test_root_topic_reason_mentions_no_prerequisites(self, conn, graph):
        set_scores(conn, arrays=0.1, trees=0.9, hashmap=0.9, dfs=0.9, graphs=0.9)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["reason_code"] == REASON_LOWEST_SCORE
        assert "ön koşul gerektirmiyor" in result["reason"]


class TestStuckProtection:
    def test_three_failures_fall_back_to_the_weakest_prerequisite(self, conn, graph):
        set_scores(conn, arrays=0.7, trees=0.65, hashmap=0.9, dfs=0.9, graphs=0.1)
        fail_attempts(conn, "graphs", 3)

        result = get_next_topic(connection=conn, topics=graph)

        # graphs'ın ön koşulları dfs ve hashmap eşit skorda (0.9); eşitlikte
        # prerequisite listesindeki ilk sıra kazanır.
        assert result["recommended_topic"] == "dfs"
        assert result["reason_code"] == REASON_STUCK_FALLBACK
        assert "graphs" in result["reason"]

    def test_weakest_prerequisite_is_chosen(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.95, dfs=0.62, graphs=0.1)
        fail_attempts(conn, "graphs", 3)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "dfs"

    def test_two_failures_are_not_enough(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.9, dfs=0.9, graphs=0.1)
        fail_attempts(conn, "graphs", 2)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "graphs"
        assert result["reason_code"] == REASON_LOWEST_SCORE

    def test_a_passing_attempt_breaks_the_streak(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.9, dfs=0.9, graphs=0.1)
        fail_attempts(conn, "graphs", 2)
        fail_attempts(conn, "graphs", 1, score=1.0)
        fail_attempts(conn, "graphs", 2)

        # Kayıt sırası: 0.2, 0.2, 1.0, 0.2, 0.2 -> en son üç kayıt (0.2, 0.2,
        # 1.0) bir başarı içerdiği için sıkışma sayılmaz.
        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "graphs"
        assert result["reason_code"] == REASON_LOWEST_SCORE

    def test_other_topics_in_between_do_not_break_the_streak(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.9, dfs=0.9, graphs=0.1)
        fail_attempts(conn, "graphs", 1)
        fail_attempts(conn, "arrays", 1, score=1.0)
        fail_attempts(conn, "graphs", 1)
        fail_attempts(conn, "trees", 1, score=1.0)
        fail_attempts(conn, "graphs", 1)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["reason_code"] == REASON_STUCK_FALLBACK

    def test_stuck_on_a_root_topic_keeps_the_topic(self, conn, graph):
        set_scores(conn, arrays=0.1, trees=0.9, hashmap=0.9, dfs=0.9, graphs=0.9)
        fail_attempts(conn, "arrays", 3)

        result = get_next_topic(connection=conn, topics=graph)

        assert result["recommended_topic"] == "arrays"
        assert result["reason_code"] == REASON_STUCK_NO_PREREQUISITE
        assert "arrays" in result["reason"]


class TestLocale:
    def test_reason_follows_the_profile_language(self, conn, graph):
        assert get_next_topic(connection=conn, topics=graph)["locale"] == "tr"

    def test_english_profile_gets_english_reason(self, graph):
        connection = db.connect(":memory:")
        assess_level("en", connection=connection, topics=graph)

        result = get_next_topic(connection=connection, topics=graph)

        assert result["locale"] == "en"
        assert "Lowest score" in result["reason"]
        connection.close()

    def test_explicit_locale_overrides_the_profile(self, conn, graph):
        result = get_next_topic(connection=conn, topics=graph, locale="en")

        assert result["locale"] == "en"
        assert "Lowest score" in result["reason"]

    def test_unsupported_locale_falls_back_to_english(self, conn, graph):
        assert get_next_topic(connection=conn, topics=graph, locale="de")["locale"] == "en"

    def test_stuck_reason_exists_in_both_languages(self, conn, graph):
        set_scores(conn, arrays=0.9, trees=0.9, hashmap=0.9, dfs=0.62, graphs=0.1)
        fail_attempts(conn, "graphs", 3)

        turkish = get_next_topic(connection=conn, topics=graph, locale="tr")
        english = get_next_topic(connection=conn, topics=graph, locale="en")

        assert "pekiştiriliyor" in turkish["reason"]
        assert "reinforcing" in english["reason"]


class TestPreconditions:
    def test_without_a_profile_it_refuses(self, graph):
        connection = db.connect(":memory:")
        with pytest.raises(LookupError, match="assess_level"):
            get_next_topic(connection=connection, topics=graph)
        connection.close()

    def test_without_seeded_scores_it_refuses(self, conn, graph):
        db.seed_topic_scores(conn, {})
        with pytest.raises(LookupError, match="assess_level"):
            get_next_topic(connection=conn, topics=graph)

    def test_the_tool_does_not_write_to_the_profile(self, conn, graph):
        before = db.get_profile(conn)
        get_next_topic(connection=conn, topics=graph)

        assert db.get_profile(conn) == before


def test_works_against_the_real_topic_graph():
    connection = db.connect(":memory:")
    assess_level("tr", connection=connection)

    result = get_next_topic(connection=connection)

    assert result["recommended_topic"] in load_topics()
    assert result["reason_code"] == "lowest_score"
    connection.close()
