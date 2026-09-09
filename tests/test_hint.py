import pytest

from src.domain.problem import Problem, ProblemTestCase
from src.storage import sqlite as db
from src.tools.assess_level import assess_level
from src.tools.hint import hint


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
            test_cases=(ProblemTestCase(input="[1], 1", expected="[0]"),),
            hints={
                "tr": ["yön", "veri yapısı", "pseudocode"],
                "en": ["direction", "data structure", "pseudocode"],
            },
        ),
    )


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


class TestLevels:
    @pytest.mark.parametrize(
        "attempt_number,expected",
        [(1, "yön"), (2, "veri yapısı"), (3, "pseudocode")],
    )
    def test_levels_come_back_in_order(self, catalog, attempt_number, expected):
        result = hint("arrays_001", attempt_number, locale="tr", problems=catalog)

        assert result["hint_level"] == attempt_number
        assert result["hint_text"] == expected

    def test_hint_level_matches_the_attempt_number(self, catalog):
        assert hint("arrays_001", 2, locale="tr", problems=catalog)["hint_level"] == 2

    def test_english_list_is_used_for_en(self, catalog):
        result = hint("arrays_001", 2, locale="en", problems=catalog)

        assert result["hint_text"] == "data structure"
        assert result["locale"] == "en"


class TestBoundary:
    @pytest.mark.parametrize("attempt_number", [4, 5, 12])
    def test_past_the_end_repeats_the_last_hint(self, catalog, attempt_number):
        result = hint("arrays_001", attempt_number, locale="tr", problems=catalog)

        assert result["hint_level"] == 3
        assert result["hint_text"] == "pseudocode"

    def test_no_error_is_raised_past_the_end(self, catalog):
        assert hint("arrays_001", 99, locale="tr", problems=catalog)["hint_text"] == "pseudocode"

    def test_attempt_number_below_one_is_rejected(self, catalog):
        for attempt_number in (0, -1):
            with pytest.raises(ValueError, match="attempt_number"):
                hint("arrays_001", attempt_number, locale="tr", problems=catalog)

    def test_shorter_hint_list_still_works(self):
        problem = Problem(
            id="arrays_002",
            topic="arrays",
            difficulty="easy",
            title={"tr": "x", "en": "x"},
            prompt={"tr": "x", "en": "x"},
            starter_code="",
            test_cases=(),
            hints={"tr": ["tek ipucu"], "en": ["only hint"]},
        )
        result = hint("arrays_002", 3, locale="tr", problems=(problem,))

        assert result["hint_level"] == 1
        assert result["hint_text"] == "tek ipucu"


class TestLocaleResolution:
    def test_empty_locale_reads_the_profile_language(self, catalog, conn):
        assess_level("tr", connection=conn, topics={"arrays": ()})

        result = hint("arrays_001", 1, problems=catalog, connection=conn)

        assert result["locale"] == "tr"
        assert result["hint_text"] == "yön"

    def test_english_profile_gets_english_hints(self, catalog, conn):
        assess_level("en", connection=conn, topics={"arrays": ()})

        result = hint("arrays_001", 1, problems=catalog, connection=conn)

        assert result["locale"] == "en"
        assert result["hint_text"] == "direction"

    def test_explicit_locale_beats_the_profile(self, catalog, conn):
        assess_level("tr", connection=conn, topics={"arrays": ()})

        result = hint("arrays_001", 1, locale="en", problems=catalog, connection=conn)

        assert result["locale"] == "en"

    def test_without_a_profile_it_falls_back_to_english(self, catalog, conn):
        result = hint("arrays_001", 1, problems=catalog, connection=conn)

        assert result["locale"] == "en"
        assert result["hint_text"] == "direction"

    def test_unsupported_locale_falls_back_to_english(self, catalog):
        assert hint("arrays_001", 1, locale="de", problems=catalog)["locale"] == "en"

    def test_preferred_language_argument_is_used_when_locale_is_empty(self, catalog):
        result = hint("arrays_001", 1, problems=catalog, preferred_language="tr")

        assert result["locale"] == "tr"


class TestErrors:
    def test_unknown_problem_id_raises(self, catalog):
        with pytest.raises(LookupError, match="graphs_003"):
            hint("graphs_003", 1, locale="tr", problems=catalog)

    def test_problem_without_hints_raises(self):
        problem = Problem(
            id="arrays_003",
            topic="arrays",
            difficulty="easy",
            title={"tr": "x", "en": "x"},
            prompt={"tr": "x", "en": "x"},
            starter_code="",
            test_cases=(),
            hints={},
        )
        with pytest.raises(LookupError, match="no hints"):
            hint("arrays_003", 1, locale="tr", problems=(problem,))


class TestRealData:
    def test_shipped_problem_set_has_three_levels_in_both_languages(self):
        for locale in ("tr", "en"):
            texts = [hint("arrays_012", level, locale=locale)["hint_text"] for level in (1, 2, 3)]

            assert len(set(texts)) == 3
            assert all(text.strip() for text in texts)

    def test_shipped_problem_repeats_the_last_hint_past_the_end(self):
        third = hint("hashmap_004", 3, locale="tr")
        fourth = hint("hashmap_004", 4, locale="tr")

        assert fourth == third
