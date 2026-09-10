import pytest

from src.domain.problem import Problem
from src.storage import sqlite as db
from src.tools.assess_level import assess_level
from src.tools.explain_approach import explain_approach
from src.tools.get_reference_approach import get_reference_approach
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
            starter_code="",
            test_cases=(),
            reference_approach={
                "tags": ["hashmap", "single_pass"],
                "summary": {"tr": "Tek geçişte tamamlayıcıyı ara.", "en": "Single pass lookup."},
            },
            hints={"tr": ["ipucu"], "en": ["hint"]},
        ),
    )


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


class TestExplainApproach:
    def test_explanation_is_acknowledged(self, catalog):
        result = explain_approach("arrays_001", "hashmap ile tek geçiş", problems=catalog)

        assert result == {"received": True, "problem_id": "arrays_001"}

    def test_unknown_problem_id_raises(self, catalog):
        with pytest.raises(LookupError, match="graphs_003"):
            explain_approach("graphs_003", "bir anlatım", problems=catalog)

    def test_empty_explanation_is_rejected(self, catalog):
        for explanation in ("", "   ", "\n"):
            with pytest.raises(ValueError, match="explanation"):
                explain_approach("arrays_001", explanation, problems=catalog)

    def test_nothing_is_written_to_the_database(self, catalog, conn):
        assess_level("tr", connection=conn, topics={"arrays": ()})
        before_attempts = db.get_attempts(conn)
        before_evidence = db.get_recent_evidence(conn)

        explain_approach("arrays_001", "uzun uzun anlatım", problems=catalog)

        assert db.get_attempts(conn) == before_attempts
        assert db.get_recent_evidence(conn) == before_evidence

    def test_works_against_the_real_problem_set(self):
        assert explain_approach("arrays_012", "hashmap")["received"] is True


class TestGetReferenceApproach:
    def test_tags_and_turkish_summary(self, catalog):
        result = get_reference_approach("arrays_001", locale="tr", problems=catalog)

        assert result["approach_tags"] == ["hashmap", "single_pass"]
        assert result["approach_summary"] == "Tek geçişte tamamlayıcıyı ara."
        assert result["locale"] == "tr"

    def test_english_summary(self, catalog):
        result = get_reference_approach("arrays_001", locale="en", problems=catalog)

        assert result["approach_summary"] == "Single pass lookup."
        assert result["locale"] == "en"

    def test_tags_are_language_independent(self, catalog):
        turkish = get_reference_approach("arrays_001", locale="tr", problems=catalog)
        english = get_reference_approach("arrays_001", locale="en", problems=catalog)

        assert turkish["approach_tags"] == english["approach_tags"]

    def test_locale_falls_back_to_the_profile(self, catalog, conn):
        assess_level("tr", connection=conn, topics={"arrays": ()})

        result = get_reference_approach("arrays_001", problems=catalog, connection=conn)

        assert result["locale"] == "tr"

    def test_without_a_profile_it_falls_back_to_english(self, catalog, conn):
        result = get_reference_approach("arrays_001", problems=catalog, connection=conn)

        assert result["locale"] == "en"

    def test_unsupported_locale_falls_back_to_english(self, catalog):
        result = get_reference_approach("arrays_001", locale="de", problems=catalog)

        assert result["approach_summary"] == "Single pass lookup."

    def test_unknown_problem_id_raises(self, catalog):
        with pytest.raises(LookupError, match="graphs_003"):
            get_reference_approach("graphs_003", locale="tr", problems=catalog)

    def test_problem_without_a_reference_approach_raises(self):
        bare = Problem(
            id="arrays_002",
            topic="arrays",
            difficulty="easy",
            title={"tr": "x", "en": "x"},
            prompt={"tr": "x", "en": "x"},
            starter_code="",
            test_cases=(),
        )
        with pytest.raises(LookupError, match="reference_approach"):
            get_reference_approach("arrays_002", locale="tr", problems=(bare,))

    def test_shipped_problems_expose_tags_and_both_summaries(self):
        for problem_id in ("arrays_012", "hashmap_004"):
            turkish = get_reference_approach(problem_id, locale="tr")
            english = get_reference_approach(problem_id, locale="en")

            assert turkish["approach_tags"]
            assert turkish["approach_summary"] != english["approach_summary"]


class TestFlowEndToEnd:
    def test_matching_explanation_scores_half(self, catalog, conn):
        assess_level("tr", connection=conn, topics={"arrays": ()})

        assert explain_approach("arrays_001", "hashmap ile tek geçiş", problems=catalog)
        reference = get_reference_approach("arrays_001", locale="tr", problems=catalog)
        assert "hashmap" in reference["approach_tags"]

        review = review_solution(
            "arrays_001", "explanation", reference_match=True, problems=catalog
        )

        assert review["score"] == 0.5
        assert review["mistake_type"] == "none"

    def test_mismatching_explanation_scores_lowest(self, catalog):
        review = review_solution(
            "arrays_001", "explanation", reference_match=False, problems=catalog
        )

        assert review["score"] == 0.2
        assert review["mistake_type"] == "wrong_approach"
