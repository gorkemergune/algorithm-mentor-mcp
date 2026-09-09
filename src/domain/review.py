"""review_solution'ın kural tabanlı çekirdeği — bkz. docs/TOOLS.md.

Skor `mastery.py`'de kalır; burada yalnızca `mistake_type` sınıflandırması,
sabit `evidence` şablonları ve pekiştirme önerisi yaşar. Şablonlar probleme
özgü değil global olduğu için `data/problems.json`'da değil burada durur.
"""

from __future__ import annotations

from src.domain.mastery import PASSED_NO_HINT
from src.domain.problem import ProblemTestCase

# --- mistake_type (docs/TOOLS.md → review_solution) --------------------------

MISTAKE_NONE = "none"
MISTAKE_MISSING_EDGE_CASE = "missing_edge_case"
MISTAKE_WRONG_APPROACH = "wrong_approach"
#: v1'de üretilmez — karmaşıklık analizi gerektirir (v2).
MISTAKE_INEFFICIENT = "inefficient"

# --- evidence şablonları (docs/TOOLS.md → review_solution tablosu) -----------

EVIDENCE_PASSED_NO_HINT = "Correct algorithm, no hints needed"
EVIDENCE_PASSED_ONE_HINT = "Correct algorithm, needed one hint"
EVIDENCE_PASSED_MULTI_HINT = "Correct algorithm, needed multiple hints"
EVIDENCE_EXPLAINED_CORRECT = "Correct approach described verbally, no code written"
EVIDENCE_MISSING_EDGE_CASE = "Approach correct but missing edge case handling"
EVIDENCE_WRONG_APPROACH = "Approach incorrect"
EVIDENCE_EXPLANATION_MISMATCH = "Approach described did not match expected solution"

#: Durum etiketi → sabit evidence metni. Host bu metni okuyup kullanıcının
#: dilinde yorumlar; server serbest metin üretmez.
EVIDENCE_TEMPLATES: dict[str, str] = {
    "passed_no_hint": EVIDENCE_PASSED_NO_HINT,
    "passed_one_hint": EVIDENCE_PASSED_ONE_HINT,
    "passed_multi_hint": EVIDENCE_PASSED_MULTI_HINT,
    "explained_correct": EVIDENCE_EXPLAINED_CORRECT,
    "missing_edge_case": EVIDENCE_MISSING_EDGE_CASE,
    "wrong_approach": EVIDENCE_WRONG_APPROACH,
    "explanation_mismatch": EVIDENCE_EXPLANATION_MISMATCH,
}


def classify_code_mistake(
    passed: bool,
    failed_cases: tuple[ProblemTestCase, ...],
) -> str:
    """Başarısız case'lerin `edge_case` etiketinden `mistake_type` üretir.

    - Hepsi geçti → `"none"`
    - Sadece `edge_case=True` case'ler kaldı → `"missing_edge_case"`
    - `edge_case=False` bir case kaldı → `"wrong_approach"`

    `submit_solution`'ın `error` alanı sınıflandırmayı etkilemez; o yalnızca
    kullanıcıya gösterilecek ham hata metnidir (docs/TOOLS.md).
    """
    if passed:
        return MISTAKE_NONE
    if any(not case.edge_case for case in failed_cases):
        return MISTAKE_WRONG_APPROACH
    if failed_cases:
        return MISTAKE_MISSING_EDGE_CASE
    # Case'lerin hepsi geçmiş görünüyor ama deneme başarısız (örn. çalıştırma
    # hatası): sessizce "none" demek yanlış olur.
    return MISTAKE_WRONG_APPROACH


def classify_explanation_mistake(reference_match: bool) -> str:
    """Sözlü anlatım için: eşleşti → `"none"`, eşleşmedi → `"wrong_approach"`."""
    return MISTAKE_NONE if reference_match else MISTAKE_WRONG_APPROACH


def evidence_for_code(passed: bool, hints_used: int, mistake_type: str) -> list[str]:
    """Kod denemesi için sabit evidence şablonunu seçer."""
    if passed:
        if hints_used == 0:
            return [EVIDENCE_TEMPLATES["passed_no_hint"]]
        if hints_used == 1:
            return [EVIDENCE_TEMPLATES["passed_one_hint"]]
        return [EVIDENCE_TEMPLATES["passed_multi_hint"]]
    if mistake_type == MISTAKE_MISSING_EDGE_CASE:
        return [EVIDENCE_TEMPLATES["missing_edge_case"]]
    return [EVIDENCE_TEMPLATES["wrong_approach"]]


def evidence_for_explanation(reference_match: bool) -> list[str]:
    """Sözlü anlatım için sabit evidence şablonunu seçer."""
    key = "explained_correct" if reference_match else "explanation_mismatch"
    return [EVIDENCE_TEMPLATES[key]]


def suggested_reinforcement(score: float, topic: str) -> str | None:
    """Skor 1.0'ın altındaysa konuyu pekiştirme için işaretler, 1.0'da bırakır."""
    return None if score >= PASSED_NO_HINT else topic
