"""`data/problems.json` şema testi.

Yeni problem eklendiğinde elle kontrol gerekmesin diye her problem tek tek
doğrulanır: TR/EN metinler, gizli ve edge case etiketleri, referans
yaklaşım, harness sözleşmesine uyan test case'ler.
"""

import json

import pytest

from src.domain.problem import DIFFICULTIES, SUPPORTED_LOCALES, load_problems
from src.domain.topics import load_topics

RAW_PROBLEMS = json.loads(
    (__import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "problems.json").read_text(
        encoding="utf-8"
    )
)
PROBLEM_IDS = [problem["id"] for problem in RAW_PROBLEMS]


@pytest.fixture(scope="module")
def by_id():
    return {problem["id"]: problem for problem in RAW_PROBLEMS}


@pytest.mark.parametrize("problem_id", PROBLEM_IDS)
class TestEachProblem:
    def test_titles_and_prompts_exist_in_both_languages(self, by_id, problem_id):
        problem = by_id[problem_id]
        for field in ("title", "prompt"):
            for locale in SUPPORTED_LOCALES:
                assert problem[field].get(locale, "").strip(), f"{problem_id}: {field}.{locale}"

    def test_three_hint_levels_in_both_languages(self, by_id, problem_id):
        hints = by_id[problem_id]["hints"]
        for locale in SUPPORTED_LOCALES:
            assert len(hints[locale]) == 3, f"{problem_id}: hints.{locale}"
            assert all(text.strip() for text in hints[locale])

    def test_hint_levels_match_across_languages(self, by_id, problem_id):
        hints = by_id[problem_id]["hints"]
        assert len(hints["tr"]) == len(hints["en"])

    def test_topic_and_difficulty_are_known(self, by_id, problem_id):
        problem = by_id[problem_id]
        assert problem["topic"] in load_topics()
        assert problem["difficulty"] in DIFFICULTIES

    def test_starter_code_defines_solve(self, by_id, problem_id):
        assert "def solve(" in by_id[problem_id]["starter_code"]

    def test_has_at_least_one_hidden_case(self, by_id, problem_id):
        cases = by_id[problem_id]["test_cases"]
        assert any(case.get("hidden") for case in cases), f"{problem_id}: gizli case yok"

    def test_has_at_least_one_edge_case(self, by_id, problem_id):
        cases = by_id[problem_id]["test_cases"]
        assert any(case.get("edge_case") for case in cases), f"{problem_id}: edge_case yok"

    def test_has_at_least_one_visible_non_edge_case(self, by_id, problem_id):
        # Kullanıcı en az bir örnek görebilmeli, o da edge case olmamalı.
        cases = by_id[problem_id]["test_cases"]
        assert any(not case.get("hidden") and not case.get("edge_case") for case in cases)

    def test_test_cases_follow_the_harness_contract(self, by_id, problem_id):
        # input JSON argüman listesi, expected JSON değeri (docs/TOOLS.md).
        for index, case in enumerate(by_id[problem_id]["test_cases"], start=1):
            arguments = json.loads("[" + case["input"] + "]")
            assert isinstance(arguments, list), f"{problem_id} case {index}"
            json.loads(case["expected"])

    def test_argument_count_matches_the_starter_signature(self, by_id, problem_id):
        problem = by_id[problem_id]
        signature = problem["starter_code"].split("def solve(", 1)[1].split(")", 1)[0]
        expected_count = len([part for part in signature.split(",") if part.strip()])

        for case in problem["test_cases"]:
            assert len(json.loads("[" + case["input"] + "]")) == expected_count

    def test_reference_approach_is_complete(self, by_id, problem_id):
        reference = by_id[problem_id].get("reference_approach") or {}
        assert reference.get("tags"), f"{problem_id}: tags yok"
        for locale in SUPPORTED_LOCALES:
            assert reference["summary"].get(locale, "").strip(), f"{problem_id}: summary.{locale}"

    def test_translations_are_not_copies_of_each_other(self, by_id, problem_id):
        problem = by_id[problem_id]
        assert problem["title"]["tr"] != problem["title"]["en"] or len(problem["title"]["tr"]) < 4
        assert problem["prompt"]["tr"] != problem["prompt"]["en"]


class TestCatalog:
    def test_ids_are_unique(self):
        assert len(PROBLEM_IDS) == len(set(PROBLEM_IDS))

    def test_loader_accepts_the_whole_file(self):
        assert len(load_problems()) == len(RAW_PROBLEMS)

    def test_every_topic_in_the_graph_has_problems(self):
        covered = {problem["topic"] for problem in RAW_PROBLEMS}
        assert covered == set(load_topics())

    def test_every_topic_has_an_easy_and_a_medium_problem(self):
        pairs = {(problem["topic"], problem["difficulty"]) for problem in RAW_PROBLEMS}
        for topic in load_topics():
            assert (topic, "easy") in pairs, f"{topic}: easy problem yok"
            assert (topic, "medium") in pairs, f"{topic}: medium problem yok"
