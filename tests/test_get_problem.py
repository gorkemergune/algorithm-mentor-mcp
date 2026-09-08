import pytest

from src.domain.problem import Problem, ProblemTestCase, load_problems
from src.tools.get_problem import get_problem


@pytest.fixture
def catalog():
    return (
        Problem(
            id="arrays_001",
            topic="arrays",
            difficulty="easy",
            title={"tr": "Başlık", "en": "Title"},
            prompt={"tr": "Soru metni", "en": "Problem text"},
            starter_code="def solve(nums):\n    pass",
            test_cases=(
                ProblemTestCase(input="[1,2]", expected="[0,1]", hidden=False),
                ProblemTestCase(input="[3,3]", expected="[0,1]", hidden=True),
            ),
            reference_approach={"tags": ["hashmap"]},
            hints={"tr": ["ipucu"], "en": ["hint"]},
        ),
    )


def test_returns_localized_strings_not_dicts(catalog):
    tr = get_problem("arrays", "easy", locale="tr", problems=catalog)
    en = get_problem("arrays", "easy", locale="en", problems=catalog)

    assert tr["title"] == "Başlık"
    assert tr["prompt"] == "Soru metni"
    assert tr["locale"] == "tr"
    assert en["title"] == "Title"
    assert en["locale"] == "en"


def test_hidden_test_cases_are_not_exposed(catalog):
    result = get_problem("arrays", "easy", problems=catalog)
    assert result["test_cases"] == [{"input": "[1,2]", "expected": "[0,1]"}]


def test_hints_and_reference_approach_are_not_exposed(catalog):
    result = get_problem("arrays", "easy", problems=catalog)
    assert "hints" not in result
    assert "reference_approach" not in result


def test_locale_falls_back_to_preferred_language(catalog):
    result = get_problem("arrays", "easy", locale=None, preferred_language="tr", problems=catalog)
    assert result["locale"] == "tr"


def test_unsupported_locale_falls_back_to_english(catalog):
    result = get_problem("arrays", "easy", locale="de", problems=catalog)
    assert result["locale"] == "en"
    assert result["title"] == "Title"


def test_no_match_raises(catalog):
    with pytest.raises(LookupError):
        get_problem("graphs", "easy", problems=catalog)
    with pytest.raises(LookupError):
        get_problem("arrays", "hard", problems=catalog)


def test_invalid_difficulty_and_language_are_rejected(catalog):
    with pytest.raises(ValueError):
        get_problem("arrays", "impossible", problems=catalog)
    with pytest.raises(ValueError):
        get_problem("arrays", "easy", language="cpp", problems=catalog)


def test_works_against_the_real_problem_set():
    result = get_problem("arrays", "easy", locale="tr", problems=load_problems())
    assert result["problem_id"] == "arrays_012"
    assert result["title"] == "İki Sayının Toplamı"
    assert all("hidden" not in case for case in result["test_cases"])
