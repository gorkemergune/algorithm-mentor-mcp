import json

import pytest

from src.domain.problem import ProblemDataError, load_problems


def _valid_raw() -> dict:
    return {
        "id": "arrays_001",
        "topic": "arrays",
        "difficulty": "easy",
        "title": {"tr": "Başlık", "en": "Title"},
        "prompt": {"tr": "Soru", "en": "Problem"},
        "starter_code": "def solve(nums):\n    pass",
        "test_cases": [{"input": "[1]", "expected": "[0]"}],
        "hints": {"tr": ["ipucu"], "en": ["hint"]},
    }


def _write(tmp_path, raw_problems):
    path = tmp_path / "problems.json"
    path.write_text(json.dumps(raw_problems, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_problem_loads(tmp_path):
    problems = load_problems(_write(tmp_path, [_valid_raw()]))
    assert problems[0].id == "arrays_001"


@pytest.mark.parametrize("field_name", ["title", "prompt", "hints"])
def test_missing_locale_is_rejected_with_problem_id_and_field(tmp_path, field_name):
    raw = _valid_raw()
    del raw[field_name]["tr"]

    with pytest.raises(ProblemDataError) as excinfo:
        load_problems(_write(tmp_path, [raw]))

    message = str(excinfo.value)
    assert "arrays_001" in message
    assert field_name in message
    assert "'tr'" in message


@pytest.mark.parametrize("field_name", ["title", "prompt", "hints"])
def test_missing_field_entirely_is_rejected(tmp_path, field_name):
    raw = _valid_raw()
    del raw[field_name]

    with pytest.raises(ProblemDataError, match=field_name):
        load_problems(_write(tmp_path, [raw]))


def test_empty_translation_counts_as_missing(tmp_path):
    raw = _valid_raw()
    raw["prompt"]["en"] = ""

    with pytest.raises(ProblemDataError, match="'en'"):
        load_problems(_write(tmp_path, [raw]))


def test_non_dict_translation_field_is_rejected(tmp_path):
    raw = _valid_raw()
    raw["title"] = "Sadece tek dil"

    with pytest.raises(ProblemDataError, match="dil sözlüğü"):
        load_problems(_write(tmp_path, [raw]))


def test_failing_problem_is_named_even_among_valid_ones(tmp_path):
    broken = _valid_raw() | {"id": "hashmap_004", "title": {"en": "Only English"}}

    with pytest.raises(ProblemDataError, match="hashmap_004"):
        load_problems(_write(tmp_path, [_valid_raw(), broken]))


def test_shipped_problem_set_passes_validation():
    assert len(load_problems()) >= 2
