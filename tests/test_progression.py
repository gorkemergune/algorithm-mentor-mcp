"""Genişleyen problem setiyle uçtan uca ilerleme senaryoları.

`assess_level` → farklı konularda çözüm → `get_next_topic` zincirinin
gerçek veriyle (22 problem, 11 konu) prerequisite grafiğine uygun
öneriler verdiğini doğrular.
"""

import pytest

from src.domain.topics import load_topics
from src.server import build_context, call_tool
from src.storage import sqlite as db

#: Gerçek problemlerin gerçek çözümleri — harness sözleşmesine göre `solve`.
SOLUTIONS = {
    "arrays_012": (
        "def solve(nums, target):\n"
        "    seen = {}\n"
        "    for index, value in enumerate(nums):\n"
        "        if target - value in seen:\n"
        "            return [seen[target - value], index]\n"
        "        seen[value] = index\n"
        "    return []\n"
    ),
    "strings_010": (
        "def solve(s):\n"
        "    letters = [c.lower() for c in s if c.isalnum()]\n"
        "    return letters == letters[::-1]\n"
    ),
    "trees_002": (
        "def solve(tree):\n"
        "    if tree is None:\n"
        "        return 0\n"
        "    return 1 + max(solve(tree[1]), solve(tree[2]))\n"
    ),
}

#: hashmap_004 için kasten yanlış çözüm: uzunluk eşitliğine bakar.
WRONG_ANAGRAM = "def solve(s, t):\n    return len(s) == len(t)\n"

#: hashmap_004'ün doğru çözümü.
RIGHT_ANAGRAM = "def solve(s, t):\n    return sorted(s) == sorted(t)\n"


@pytest.fixture
def context():
    ctx = build_context(":memory:")
    yield ctx
    ctx.connection.close()


def ok(context, name, arguments):
    result = call_tool(context, name, arguments)
    assert result.is_error is not True, result.content[0].text
    return result.structured_content


def attempt(context, problem_id, topic, code, hints_used=0):
    """submit_solution → review_solution → update_profile zinciri."""
    submission = ok(context, "submit_solution", {"code": code, "problem_id": problem_id})
    review = ok(context, "review_solution", {
        "problem_id": problem_id,
        "attempt_type": "code",
        "test_results": submission,
        "hints_used": hints_used,
    })
    profile = ok(context, "update_profile", {
        "topic": topic,
        "problem_id": problem_id,
        "score": review["score"],
        "evidence": review["evidence"],
        "mistake_type": review["mistake_type"],
        "hints_used": hints_used,
    })
    return submission, review, profile


def master(context, problem_id, topic, times=3):
    """Konuyu ön koşul eşiğinin (0.6) üstüne çıkarır."""
    for _ in range(times):
        submission, _, profile = attempt(context, problem_id, topic, SOLUTIONS[problem_id])
        assert submission["passed"] is True
    return profile["topic_scores"][topic]


class TestRealSolutions:
    @pytest.mark.parametrize("problem_id", sorted(SOLUTIONS))
    def test_reference_solutions_pass_every_case(self, context, problem_id):
        submission = ok(context, "submit_solution", {
            "code": SOLUTIONS[problem_id], "problem_id": problem_id
        })

        assert submission["passed"] is True
        assert submission["error"] is None
        assert all(case["passed"] for case in submission["test_results"])


class TestAssessLevelOnTheFullGraph:
    def test_every_topic_is_seeded(self, context):
        assessment = ok(context, "assess_level", {"preferred_language": "en"})

        assert set(assessment["topic_estimates"]) == set(load_topics())
        assert assessment["estimated_level"] == "beginner"
        assert assessment["recommended_start_topic"] == "arrays"

    def test_a_problem_exists_for_the_recommended_start_topic(self, context):
        assessment = ok(context, "assess_level", {})

        problem = ok(context, "get_problem", {
            "topic": assessment["recommended_start_topic"], "difficulty": "easy"
        })
        assert problem["problem_id"]


class TestProgressionUnlocksTopics:
    def test_root_topic_comes_first(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})

        first = ok(context, "get_next_topic", {})

        assert first["recommended_topic"] == "arrays"
        assert "no prerequisites" in first["reason"]

    def test_cleared_topic_gives_way_to_the_next_lowest(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})
        score = master(context, "arrays_012", "arrays")

        following = ok(context, "get_next_topic", {})

        assert score > 0.6
        assert following["recommended_topic"] != "arrays"

    def test_dependent_topic_unlocks_after_its_prerequisite(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})

        # arrays eşiğin altındayken hashmap aday değil.
        db.set_topic_score(context.connection, "arrays", 0.4)
        for topic in ("strings", "trees"):
            db.set_topic_score(context.connection, topic, 0.9)
        assert ok(context, "get_next_topic", {})["recommended_topic"] != "hashmap"

        # arrays'i gerçek çözümlerle eşiğin üstüne çıkar.
        master(context, "arrays_012", "arrays")
        unlocked = ok(context, "get_next_topic", {})

        assert unlocked["recommended_topic"] == "hashmap"
        assert "prerequisites met (arrays)" in unlocked["reason"]

    def test_locked_topic_is_not_recommended_even_when_it_scores_lowest(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})
        # graphs en düşük skorlu (0.0) ama ön koşulları (dfs, bfs) açılmamış.
        for topic in load_topics():
            db.set_topic_score(context.connection, topic, 0.8)
        for topic in ("graphs", "dfs", "bfs"):
            db.set_topic_score(context.connection, topic, 0.0)

        result = ok(context, "get_next_topic", {})

        assert result["recommended_topic"] in ("dfs", "bfs")

    def test_deep_chain_requires_the_whole_path(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})
        for topic in load_topics():
            db.set_topic_score(context.connection, topic, 0.9)
        # two_pointers açık değilse sliding_window da aday olmamalı.
        db.set_topic_score(context.connection, "two_pointers", 0.2)
        db.set_topic_score(context.connection, "sliding_window", 0.0)

        result = ok(context, "get_next_topic", {})

        assert result["recommended_topic"] == "two_pointers"

    def test_a_full_session_walks_several_topics(self, context):
        ok(context, "assess_level", {"preferred_language": "en"})
        visited = []

        for problem_id, topic in (
            ("arrays_012", "arrays"),
            ("strings_010", "strings"),
            ("trees_002", "trees"),
        ):
            visited.append(ok(context, "get_next_topic", {})["recommended_topic"])
            master(context, problem_id, topic)

        scores = db.get_topic_scores(context.connection)

        assert visited[0] == "arrays"
        assert all(scores[topic] > 0.6 for topic in ("arrays", "strings", "trees"))
        # dfs/bfs trees'e bağlıydı, artık aday; graphs hâlâ kilitli.
        assert ok(context, "get_next_topic", {})["recommended_topic"] != "graphs"


class TestStuckProtectionOnRealData:
    def test_three_real_failures_fall_back_to_the_prerequisite(self, context):
        self._prepare_hashmap_focus(context)

        for _ in range(3):
            submission, review, _ = attempt(
                context, "hashmap_004", "hashmap", WRONG_ANAGRAM
            )
            assert submission["passed"] is False
            assert review["score"] == 0.2

        result = ok(context, "get_next_topic", {})

        assert result["reason_code"] == "stuck_fallback"
        assert result["recommended_topic"] == "arrays"
        assert "hashmap" in result["reason"]

    def test_success_on_another_topic_does_not_break_the_streak(self, context):
        # Kural konunun KENDİ son 3 denemesine bakar (docs/TOOLS.md); araya
        # giren arrays başarısı hashmap serisini kırmaz.
        self._prepare_hashmap_focus(context)

        attempt(context, "hashmap_004", "hashmap", WRONG_ANAGRAM)
        attempt(context, "hashmap_004", "hashmap", WRONG_ANAGRAM)
        attempt(context, "arrays_012", "arrays", SOLUTIONS["arrays_012"])
        attempt(context, "hashmap_004", "hashmap", WRONG_ANAGRAM)

        result = ok(context, "get_next_topic", {})

        assert result["reason_code"] == "stuck_fallback"
        assert result["recommended_topic"] == "arrays"

    def test_a_success_on_the_same_topic_breaks_the_streak(self, context):
        self._prepare_hashmap_focus(context)

        attempt(context, "hashmap_004", "hashmap", WRONG_ANAGRAM)
        attempt(context, "hashmap_004", "hashmap", WRONG_ANAGRAM)
        submission, review, _ = attempt(context, "hashmap_004", "hashmap", RIGHT_ANAGRAM)

        result = ok(context, "get_next_topic", {})

        assert submission["passed"] is True
        assert review["score"] == 1.0
        assert result["reason_code"] == "lowest_score"
        assert result["recommended_topic"] == "hashmap"

    @staticmethod
    def _prepare_hashmap_focus(context):
        """hashmap'i en düşük skorlu aday yapar, arrays'i ön koşul olarak açar."""
        ok(context, "assess_level", {"preferred_language": "en"})
        master(context, "arrays_012", "arrays")
        for topic in load_topics():
            if topic not in ("arrays", "hashmap"):
                db.set_topic_score(context.connection, topic, 0.95)
