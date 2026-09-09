"""review_solution tool — bkz. docs/TOOLS.md → review_solution.

Denemenin **skorunu bu tool üretir**, host değil: `score` her zaman
`mastery.attempt_score`'un sabit tablosundan gelir. Host'tan gelen tek
girdiler test sonucu, hint sayısı ve `explanation` durumundaki
`reference_match` boolean'ıdır — ham bir mastery sayısı asla kabul edilmez.

Doğal dil yorumu (kod kalitesi geri bildirimi) host'a aittir; bu tool
`feedback` alanı döndürmez, yalnızca yapısal veri verir.
"""

from __future__ import annotations

from src.domain import mastery
from src.domain.problem import Problem, ProblemTestCase, load_problems
from src.domain.review import (
    classify_code_mistake,
    classify_explanation_mistake,
    evidence_for_code,
    evidence_for_explanation,
    suggested_reinforcement,
)

ATTEMPT_TYPES = (mastery.ATTEMPT_TYPE_CODE, mastery.ATTEMPT_TYPE_EXPLANATION)


def review_solution(
    problem_id: str,
    attempt_type: str,
    test_results: dict | None = None,
    hints_used: int = 0,
    reference_match: bool | None = None,
    *,
    problems: tuple[Problem, ...] | None = None,
) -> dict:
    """Denemeyi değerlendirir: `score`, `evidence`, `mistake_type`, öneri.

    `attempt_type="code"` için `test_results` (`submit_solution` çıktısı)
    zorunludur; boş ya da `None` gelirse `ValueError` atılır — bu gerçek bir
    başarısızlık değil, çağrı zincirindeki bir wiring hatasıdır.
    """
    if attempt_type not in ATTEMPT_TYPES:
        raise ValueError(f"unknown attempt_type: {attempt_type!r} (expected one of {ATTEMPT_TYPES})")

    problem = _find_problem(problem_id, problems)

    if attempt_type == mastery.ATTEMPT_TYPE_EXPLANATION:
        if reference_match is None:
            raise ValueError("attempt_type='explanation' requires 'reference_match'")
        score = mastery.attempt_score(attempt_type, reference_match=reference_match)
        return _result(
            score=score,
            evidence=evidence_for_explanation(reference_match),
            mistake_type=classify_explanation_mistake(reference_match),
            topic=problem.topic,
        )

    passed, failed_cases = _read_test_results(test_results, problem)
    score = mastery.attempt_score(attempt_type, passed=passed, hints_used=hints_used)
    mistake_type = classify_code_mistake(passed, failed_cases)
    return _result(
        score=score,
        evidence=evidence_for_code(passed, hints_used, mistake_type),
        mistake_type=mistake_type,
        topic=problem.topic,
    )


def _result(*, score: float, evidence: list[str], mistake_type: str, topic: str) -> dict:
    return {
        "score": score,
        "evidence": evidence,
        "mistake_type": mistake_type,
        "suggested_topic_reinforcement": suggested_reinforcement(score, topic),
    }


def _find_problem(problem_id: str, problems: tuple[Problem, ...] | None) -> Problem:
    catalog = problems if problems is not None else load_problems()
    for problem in catalog:
        if problem.id == problem_id:
            return problem
    raise LookupError(f"unknown problem_id: {problem_id!r}")


def _read_test_results(
    test_results: dict | None,
    problem: Problem,
) -> tuple[bool, tuple[ProblemTestCase, ...]]:
    """`submit_solution` çıktısını case etiketleriyle eşleştirir."""
    if not test_results:
        raise ValueError(
            "attempt_type='code' requires the submit_solution output in 'test_results' "
            "(empty or missing results mean a broken call chain, not a failed attempt)"
        )

    cases = test_results.get("test_results")
    if not cases:
        raise ValueError("'test_results' carries no per-case results from submit_solution")
    if len(cases) != len(problem.test_cases):
        raise ValueError(
            f"test_results has {len(cases)} case(s) but problem {problem.id!r} "
            f"defines {len(problem.test_cases)}"
        )

    failed_cases = tuple(
        problem.test_cases[case["case"] - 1] for case in cases if not case["passed"]
    )
    all_passed = not failed_cases
    # `submit_solution` çalıştırma hatasında `passed=False` der; case bayrakları
    # temiz görünse bile bu karar geçerlidir.
    reported = test_results.get("passed")
    passed = all_passed if reported is None else bool(reported) and all_passed
    return passed, failed_cases
