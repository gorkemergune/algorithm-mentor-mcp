import pytest

from src.domain import mastery


class TestAttemptScore:
    @pytest.mark.parametrize(
        "hints_used,expected",
        [(0, 1.0), (1, 0.8), (2, 0.6), (5, 0.6)],
    )
    def test_passing_code_scores_by_hint_count(self, hints_used, expected):
        assert mastery.attempt_score("code", passed=True, hints_used=hints_used) == expected

    def test_failing_code_scores_lowest_regardless_of_hints(self):
        assert mastery.attempt_score("code", passed=False, hints_used=0) == 0.2
        assert mastery.attempt_score("code", passed=False, hints_used=3) == 0.2

    def test_correct_explanation_scores_half(self):
        assert mastery.attempt_score("explanation", reference_match=True) == 0.5

    def test_wrong_explanation_scores_lowest(self):
        assert mastery.attempt_score("explanation", reference_match=False) == 0.2

    def test_score_is_always_from_the_fixed_table(self):
        for score in (
            mastery.attempt_score("code", passed=True, hints_used=0),
            mastery.attempt_score("code", passed=True, hints_used=2),
            mastery.attempt_score("explanation", reference_match=True),
        ):
            assert mastery.is_valid_score(score)

    def test_missing_required_input_is_rejected(self):
        with pytest.raises(ValueError):
            mastery.attempt_score("code")
        with pytest.raises(ValueError):
            mastery.attempt_score("explanation")
        with pytest.raises(ValueError):
            mastery.attempt_score("telepathy", passed=True)


class TestUpdateTopicScore:
    def test_ema_formula(self):
        # 0.5 * 0.7 + 1.0 * 0.3
        assert mastery.update_topic_score(0.5, 1.0) == pytest.approx(0.65)

    def test_failure_pulls_score_down(self):
        assert mastery.update_topic_score(0.8, 0.2) == pytest.approx(0.62)

    def test_repeated_passes_converge_upward_without_exceeding_one(self):
        score = 0.0
        for _ in range(50):
            score = mastery.update_topic_score(score, 1.0)
        assert 0.99 < score <= 1.0

    def test_rejects_scores_outside_the_fixed_table(self):
        # Host'un profili serbest sayıyla manipüle etmesini engelleyen doğrulama.
        for forged in (0.95, 0.0, 1.5, 0.61):
            with pytest.raises(ValueError):
                mastery.update_topic_score(0.5, forged)

    def test_accepts_float_imprecision_on_valid_scores(self):
        assert mastery.update_topic_score(0.5, 0.1 + 0.7) == pytest.approx(0.59)


class TestLevelForScores:
    def test_empty_profile_is_beginner(self):
        assert mastery.level_for_scores({}) == "beginner"

    @pytest.mark.parametrize(
        "scores,expected",
        [
            ({"arrays": 0.2, "dp": 0.3}, "beginner"),
            ({"arrays": 0.4}, "intermediate"),
            ({"arrays": 0.9, "dp": 0.5}, "intermediate"),
            ({"arrays": 0.75}, "advanced"),
            ({"arrays": 0.9, "dp": 0.8}, "advanced"),
        ],
    )
    def test_thresholds(self, scores, expected):
        assert mastery.level_for_scores(scores) == expected
