import textwrap

import pytest

from src.domain.problem import Problem, ProblemTestCase
from src.tools.submit_solution import submit_solution


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
                ProblemTestCase(input="[2,7,11,15], 9", expected="[0,1]"),
                ProblemTestCase(input="[3,2,4], 6", expected="[1,2]"),
                ProblemTestCase(input="[3,3], 6", expected="[0,1]", hidden=True),
            ),
        ),
    )


TWO_SUM = textwrap.dedent(
    """
    def solve(nums, target):
        seen = {}
        for index, value in enumerate(nums):
            if target - value in seen:
                return [seen[target - value], index]
            seen[value] = index
        return []
    """
)


def run(code, catalog, **kwargs):
    return submit_solution(code, "arrays_001", problems=catalog, **kwargs)


class TestCorrectSolution:
    def test_all_cases_pass(self, catalog):
        result = run(TWO_SUM, catalog)

        assert result["passed"] is True
        assert result["error"] is None
        assert result["test_results"] == [
            {"case": 1, "passed": True},
            {"case": 2, "passed": True},
            {"case": 3, "passed": True},
        ]

    def test_hidden_cases_are_run_but_never_exposed(self, catalog):
        result = run(TWO_SUM, catalog)

        assert len(result["test_results"]) == 3  # gizli case de çalıştı
        assert all(set(case) == {"case", "passed"} for case in result["test_results"])

    def test_runtime_ms_is_reported(self, catalog):
        assert run(TWO_SUM, catalog)["runtime_ms"] >= 0

    def test_json_expected_is_compared_by_value(self):
        # "true" -> Python True, tam eşitlikle karşılaştırılır.
        problem = Problem(
            id="hashmap_001",
            topic="hashmap",
            difficulty="easy",
            title={"tr": "x", "en": "x"},
            prompt={"tr": "x", "en": "x"},
            starter_code="",
            test_cases=(ProblemTestCase(input='"rat", "car"', expected="false"),),
        )
        result = submit_solution(
            "def solve(s, t):\n    return sorted(s) == sorted(t)",
            "hashmap_001",
            problems=(problem,),
        )
        assert result["passed"] is True

    def test_debug_prints_do_not_break_result_parsing(self, catalog):
        noisy = "print('kullanıcı çıktısı')\n" + TWO_SUM + "\nprint('__MENTOR_RESULT__ sahte')"
        result = run(noisy, catalog)

        assert result["passed"] is True
        assert len(result["test_results"]) == 3


class TestWrongSolution:
    def test_failing_cases_are_marked(self, catalog):
        result = run("def solve(nums, target):\n    return [0, 1]", catalog)

        assert result["passed"] is False
        assert result["error"] is None
        assert [case["passed"] for case in result["test_results"]] == [True, False, True]

    def test_exception_inside_solve_is_reported(self, catalog):
        result = run("def solve(nums, target):\n    raise ValueError('bozuk')", catalog)

        assert result["passed"] is False
        assert result["error"] == "ValueError: bozuk"
        assert all(case["passed"] is False for case in result["test_results"])

    def test_wrong_signature_is_reported_as_type_error(self, catalog):
        result = run("def solve(nums):\n    return [0, 1]", catalog)

        assert result["passed"] is False
        assert "TypeError" in result["error"]


class TestBrokenCode:
    def test_syntax_error_fails_every_case(self, catalog):
        result = run("def solve(:\n    pass", catalog)

        assert result["passed"] is False
        assert "SyntaxError" in result["error"]
        assert [case["passed"] for case in result["test_results"]] == [False, False, False]

    def test_missing_solve_function_is_reported(self, catalog):
        result = run("answer = 42", catalog)

        assert result["passed"] is False
        assert result["error"] == "NameError: solve function is not defined"
        assert all(case["passed"] is False for case in result["test_results"])

    def test_solve_that_is_not_callable_is_rejected(self, catalog):
        result = run("solve = 5", catalog)
        assert "NameError" in result["error"]


class TestTimeout:
    def test_partial_results_survive_a_timeout(self, catalog):
        # 1. case geçer, 2. case sonsuz döngüye girer.
        code = textwrap.dedent(
            """
            _calls = []

            def solve(nums, target):
                _calls.append(1)
                if len(_calls) > 1:
                    while True:
                        pass
                return [0, 1]
            """
        )
        result = run(code, catalog, timeout=1.0)

        assert result["passed"] is False
        assert result["error"].startswith("Timed out")
        assert [case["passed"] for case in result["test_results"]] == [True, False, False]


class TestInputValidation:
    def test_unknown_problem_id_raises(self, catalog):
        with pytest.raises(LookupError, match="graphs_003"):
            submit_solution(TWO_SUM, "graphs_003", problems=catalog)

    def test_unsupported_language_raises(self, catalog):
        with pytest.raises(ValueError, match="cpp"):
            submit_solution(TWO_SUM, "arrays_001", language="cpp", problems=catalog)

    def test_malformed_test_case_json_is_reported_not_crashed(self):
        problem = Problem(
            id="arrays_002",
            topic="arrays",
            difficulty="easy",
            title={"tr": "x", "en": "x"},
            prompt={"tr": "x", "en": "x"},
            starter_code="",
            test_cases=(ProblemTestCase(input="not json", expected="[0]"),),
        )
        result = submit_solution("def solve(x):\n    return [0]", "arrays_002", problems=(problem,))

        assert result["passed"] is False
        assert "JSONDecodeError" in result["error"]


def test_works_against_the_real_problem_set():
    result = submit_solution(TWO_SUM, "arrays_012")
    assert result["passed"] is True
