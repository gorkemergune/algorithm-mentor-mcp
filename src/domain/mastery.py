"""Skorlama mantığının TEK yaşadığı yer.

`docs/STUDENT_PROFILE_SCHEMA.md` → "Skorlama formülü" ve `docs/TOOLS.md` →
`review_solution` sabit tablosu burada birebir uygulanır. Başka hiçbir modül
(özellikle `update_profile`) kendi skor hesabını yazmaz; buradaki
fonksiyonları çağırır.
"""

from __future__ import annotations

import math

# --- Sabit skor tablosu (docs/TOOLS.md → review_solution) --------------------

PASSED_NO_HINT = 1.0
PASSED_ONE_HINT = 0.8
PASSED_MULTI_HINT = 0.6
EXPLAINED_CORRECT = 0.5
FAILED = 0.2

#: `update_profile`'ın kabul ettiği tek skor kümesi. Host bu beşin dışında bir
#: sayı gönderemez — mimari karar, bkz. STUDENT_PROFILE_SCHEMA.md.
VALID_SCORES: frozenset[float] = frozenset(
    {PASSED_NO_HINT, PASSED_ONE_HINT, PASSED_MULTI_HINT, EXPLAINED_CORRECT, FAILED}
)

#: EMA ağırlığı (v1 sabit).
ALPHA = 0.3

# --- Seviye eşikleri (docs/STUDENT_PROFILE_SCHEMA.md) ------------------------

BEGINNER_MAX = 0.4
INTERMEDIATE_MAX = 0.75

ATTEMPT_TYPE_CODE = "code"
ATTEMPT_TYPE_EXPLANATION = "explanation"

_SCORE_TOLERANCE = 1e-9


def attempt_score(
    attempt_type: str,
    *,
    passed: bool | None = None,
    hints_used: int = 0,
    reference_match: bool | None = None,
) -> float:
    """Bir denemenin skorunu sabit tablodan üretir.

    `attempt_type="code"` için `passed` ve `hints_used`, `"explanation"` için
    `reference_match` zorunludur. Serbest sayı üretilmez — dönen değer her
    zaman `VALID_SCORES` içindedir.
    """
    if attempt_type == ATTEMPT_TYPE_CODE:
        if passed is None:
            raise ValueError("attempt_type='code' requires 'passed'")
        if hints_used < 0:
            raise ValueError("hints_used cannot be negative")
        if not passed:
            return FAILED
        if hints_used == 0:
            return PASSED_NO_HINT
        if hints_used == 1:
            return PASSED_ONE_HINT
        return PASSED_MULTI_HINT

    if attempt_type == ATTEMPT_TYPE_EXPLANATION:
        if reference_match is None:
            raise ValueError("attempt_type='explanation' requires 'reference_match'")
        return EXPLAINED_CORRECT if reference_match else FAILED

    raise ValueError(
        f"unknown attempt_type: {attempt_type!r} "
        f"(expected {ATTEMPT_TYPE_CODE!r} or {ATTEMPT_TYPE_EXPLANATION!r})"
    )


def is_valid_score(score: float) -> bool:
    """Skorun sabit tablodaki beş değerden biri olup olmadığını söyler."""
    return any(math.isclose(score, valid, abs_tol=_SCORE_TOLERANCE) for valid in VALID_SCORES)


def update_topic_score(previous_score: float, score: float, alpha: float = ALPHA) -> float:
    """EMA ile konu skorunu günceller: `eski*(1-alpha) + score*alpha`.

    `score`, `review_solution`'ın sabit tablosundan gelmek zorundadır; aksi
    halde `ValueError` atar (host'un profili serbest sayıyla manipüle etmesini
    engelleyen doğrulama).
    """
    if not is_valid_score(score):
        raise ValueError(
            f"score {score!r} is not one of the fixed review_solution scores "
            f"{sorted(VALID_SCORES)}"
        )
    if not 0.0 <= previous_score <= 1.0:
        raise ValueError(f"previous_score must be in [0.0, 1.0], got {previous_score!r}")
    return previous_score * (1 - alpha) + score * alpha


def level_for_scores(topic_scores: dict[str, float]) -> str:
    """Konu skorlarının ortalamasından seviyeyi belirler.

    Skor yoksa (henüz deneme yapılmamış) `"beginner"` döner.
    """
    if not topic_scores:
        return "beginner"
    average = sum(topic_scores.values()) / len(topic_scores)
    if average < BEGINNER_MAX:
        return "beginner"
    if average < INTERMEDIATE_MAX:
        return "intermediate"
    return "advanced"
