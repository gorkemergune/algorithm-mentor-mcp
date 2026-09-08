"""get_problem tool — bkz. docs/TOOLS.md → get_problem.

Konuya ve zorluğa göre bir problem döner. Gizli test case'ler, hint'ler ve
referans yaklaşım çıktıya girmez (spoiler olur; onlar `submit_solution`,
`hint` ve `get_reference_approach` tool'larının işi).
"""

from __future__ import annotations

from src.domain.problem import (
    DIFFICULTIES,
    Problem,
    load_problems,
    normalize_locale,
)

#: v1'de sadece Python destekleniyor (bkz. CLAUDE.md → ExecutionEngine).
SUPPORTED_LANGUAGES = ("python",)


def get_problem(
    topic: str,
    difficulty: str,
    language: str = "python",
    locale: str | None = None,
    *,
    problems: tuple[Problem, ...] | None = None,
    preferred_language: str | None = None,
) -> dict:
    """Konu + zorluğa uyan bir problemi `locale` dilinde döner.

    `locale` boşsa `StudentProfile.preferred_language` (host tarafından
    `preferred_language` ile geçilir) kullanılır.

    Eşleşen birden çok problem varsa ilki seçilir — "daha önce çözülmüşü atla"
    mantığı profil depolaması (`src/storage`) geldiğinde eklenecek.
    """
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty: {difficulty!r} (expected one of {DIFFICULTIES})")
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported language: {language!r} (v1 supports {SUPPORTED_LANGUAGES})")

    resolved_locale = normalize_locale(locale or preferred_language)
    catalog = problems if problems is not None else load_problems()

    matches = [p for p in catalog if p.topic == topic and p.difficulty == difficulty]
    if not matches:
        raise LookupError(f"no problem found for topic={topic!r} difficulty={difficulty!r}")

    problem = matches[0]
    return {
        "problem_id": problem.id,
        "title": problem.localized_title(resolved_locale),
        "prompt": problem.localized_prompt(resolved_locale),
        "starter_code": problem.starter_code,
        "test_cases": [
            {"input": case.input, "expected": case.expected}
            for case in problem.visible_test_cases()
        ],
        "locale": resolved_locale,
    }
