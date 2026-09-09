import pytest

from src.domain import mastery
from src.domain.problem import Problem, ProblemTestCase
from src.domain.review import EVIDENCE_TEMPLATES
from src.tools.review_solution import review_solution


@pytest.fixture
def catalog():
    return (
        Problem(
            id="arrays_001",
            topic="arrays",
            difficulty="easy",
            title={"tr": "Başlık", "en": "Title"},
            prompt={"tr": "Soru", "en": "Problem"},
            starter_code="def solve(nums, target):\n    pass",
            test_cases=(
                ProblemTestCase(input="[2,7], 9", expected="[0,1]"),
                ProblemTestCase(input="[3,2,4], 6", expected="[1,2]"),
                ProblemTestCase(input="[3,3], 6", expected="[0,1]", hidden=True, edge_case=True),
            ),
        ),
    )


def submit_output(*case_flags, error=None):
    """`submit_solution` çıktısını taklit eder."""
    results = [{"case": index, "passed": flag} for index, flag in enumerate(case_flags, start=1)]
    return {
        "passed": all(case_flags) and error is None,
        "test_results": results,
        "runtime_ms": 12,
        "error": error,
    }


def review(catalog, results, hints_used=0):
    return review_solution("arrays_001", "code", results, hints_used, problems=catalog)


class TestPassingCode:
    def test_no_hints_scores_full(self, catalog):
        result = review(catalog, submit_output(True, True, True), hints_used=0)

        assert result["score"] == 1.0
        assert result["evidence"] == [EVIDENCE_TEMPLATES["passed_no_hint"]]
        assert result["mistake_type"] == "none"
        assert result["suggested_topic_reinforcement"] is None

    def test_one_hint(self, catalog):
        result = review(catalog, submit_output(True, True, True), hints_used=1)

        assert result["score"] == 0.8
        assert result["evidence"] == [EVIDENCE_TEMPLATES["passed_one_hint"]]
        assert result["mistake_type"] == "none"
        assert result["suggested_topic_reinforcement"] == "arrays"

    @pytest.mark.parametrize("hints_used", [2, 5])
    def test_multiple_hints(self, catalog, hints_used):
        result = review(catalog, submit_output(True, True, True), hints_used=hints_used)

        assert result["score"] == 0.6
        assert result["evidence"] == [EVIDENCE_TEMPLATES["passed_multi_hint"]]
        assert result["suggested_topic_reinforcement"] == "arrays"


class TestFailingCode:
    def test_only_edge_case_failing_is_missing_edge_case(self, catalog):
        result = review(catalog, submit_output(True, True, False))

        assert result["mistake_type"] == "missing_edge_case"
        assert result["evidence"] == [EVIDENCE_TEMPLATES["missing_edge_case"]]
        assert result["score"] == 0.2
        assert result["suggested_topic_reinforcement"] == "arrays"

    def test_normal_case_failing_is_wrong_approach(self, catalog):
        result = review(catalog, submit_output(True, False, True))

        assert result["mistake_type"] == "wrong_approach"
        assert result["evidence"] == [EVIDENCE_TEMPLATES["wrong_approach"]]
        assert result["score"] == 0.2

    def test_everything_failing_is_wrong_approach(self, catalog):
        result = review(catalog, submit_output(False, False, False))
        assert result["mistake_type"] == "wrong_approach"

    def test_normal_plus_edge_failure_is_wrong_approach(self, catalog):
        # Edge case dışında da hata varsa yaklaşım yanlıştır, eksik edge değil.
        result = review(catalog, submit_output(True, False, False))
        assert result["mistake_type"] == "wrong_approach"

    def test_hints_do_not_rescue_a_failed_attempt(self, catalog):
        assert review(catalog, submit_output(False, True, True), hints_used=0)["score"] == 0.2
        assert review(catalog, submit_output(False, True, True), hints_used=2)["score"] == 0.2

    def test_execution_error_keeps_the_attempt_failed(self, catalog):
        # submit_solution passed=False dediyse, case bayrakları temiz olsa bile
        # deneme başarısızdır (örn. timeout sonrası eksik rapor).
        payload = submit_output(True, True, True, error="Timed out after 5s")
        result = review(catalog, payload)

        assert result["score"] == 0.2
        assert result["mistake_type"] == "wrong_approach"

    def test_error_text_does_not_drive_classification(self, catalog):
        # error dolu ama edge case dışında hata yok → yine missing_edge_case.
        payload = submit_output(True, True, False, error="ValueError: bozuk")
        assert review(catalog, payload)["mistake_type"] == "missing_edge_case"


class TestExplanation:
    def test_matching_explanation(self, catalog):
        result = review_solution(
            "arrays_001", "explanation", reference_match=True, problems=catalog
        )

        assert result["score"] == 0.5
        assert result["evidence"] == [EVIDENCE_TEMPLATES["explained_correct"]]
        assert result["mistake_type"] == "none"
        assert result["suggested_topic_reinforcement"] == "arrays"

    def test_non_matching_explanation(self, catalog):
        result = review_solution(
            "arrays_001", "explanation", reference_match=False, problems=catalog
        )

        assert result["score"] == 0.2
        assert result["evidence"] == [EVIDENCE_TEMPLATES["explanation_mismatch"]]
        assert result["mistake_type"] == "wrong_approach"

    def test_hints_used_is_irrelevant_for_explanations(self, catalog):
        result = review_solution(
            "arrays_001", "explanation", hints_used=3, reference_match=True, problems=catalog
        )
        assert result["score"] == 0.5

    def test_missing_reference_match_is_rejected(self, catalog):
        with pytest.raises(ValueError, match="reference_match"):
            review_solution("arrays_001", "explanation", problems=catalog)


class TestContract:
    def test_score_is_always_from_the_fixed_table(self, catalog):
        payloads = [
            review(catalog, submit_output(True, True, True), hints_used=hints)
            for hints in (0, 1, 2)
        ]
        payloads.append(review(catalog, submit_output(False, False, False)))
        payloads.append(
            review_solution("arrays_001", "explanation", reference_match=True, problems=catalog)
        )

        assert all(mastery.is_valid_score(payload["score"]) for payload in payloads)

    def test_no_feedback_field_is_returned(self, catalog):
        # Doğal dil yorumu host'un işi; server serbest metin üretmez.
        result = review(catalog, submit_output(True, True, True))

        assert set(result) == {
            "score",
            "evidence",
            "mistake_type",
            "suggested_topic_reinforcement",
        }

    def test_evidence_comes_from_the_fixed_templates(self, catalog):
        result = review(catalog, submit_output(True, False, True))
        assert result["evidence"][0] in EVIDENCE_TEMPLATES.values()

    def test_inefficient_is_never_produced_in_v1(self, catalog):
        for flags in [(True, True, True), (True, True, False), (False, False, False)]:
            assert review(catalog, submit_output(*flags))["mistake_type"] != "inefficient"


class TestInputValidation:
    def test_missing_test_results_is_a_wiring_error(self, catalog):
        with pytest.raises(ValueError, match="test_results"):
            review_solution("arrays_001", "code", None, 0, problems=catalog)

    def test_empty_test_results_is_a_wiring_error(self, catalog):
        with pytest.raises(ValueError, match="test_results"):
            review_solution("arrays_001", "code", {}, 0, problems=catalog)

    def test_payload_without_per_case_results_is_rejected(self, catalog):
        with pytest.raises(ValueError, match="per-case"):
            review_solution(
                "arrays_001", "code", {"passed": False, "test_results": []}, 0, problems=catalog
            )

    def test_case_count_mismatch_is_rejected(self, catalog):
        with pytest.raises(ValueError, match="defines 3"):
            review(catalog, submit_output(True, True))

    def test_unknown_attempt_type_is_rejected(self, catalog):
        with pytest.raises(ValueError, match="attempt_type"):
            review_solution("arrays_001", "telepathy", problems=catalog)

    def test_unknown_problem_id_is_rejected(self, catalog):
        with pytest.raises(LookupError, match="graphs_003"):
            review_solution("graphs_003", "explanation", reference_match=True, problems=catalog)

    def test_negative_hints_are_rejected(self, catalog):
        with pytest.raises(ValueError, match="hints_used"):
            review(catalog, submit_output(True, True, True), hints_used=-1)


def test_works_against_the_real_problem_set():
    payload = {
        "passed": False,
        "test_results": [
            {"case": 1, "passed": True},
            {"case": 2, "passed": True},
            {"case": 3, "passed": False},
        ],
        "runtime_ms": 9,
        "error": None,
    }
    result = review_solution("arrays_012", "code", payload, 0)

    # arrays_012'nin 3. case'i edge_case: true olarak etiketli.
    assert result["mistake_type"] == "missing_edge_case"
    assert result["suggested_topic_reinforcement"] == "arrays"
