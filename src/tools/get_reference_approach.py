"""get_reference_approach tool — bkz. docs/TOOLS.md → get_reference_approach.

Problemin gizli referans yaklaşımını döner: dilden bağımsız `tags` ve
`locale`'e göre seçilmiş `summary`. Yalnızca `explain_approach` sonrasında
kullanılır — önceden gösterilirse spoiler olur (bu sıra host'un
sorumluluğunda; `get_problem` bu alanı zaten çıktısına koymaz).
"""

from __future__ import annotations

import sqlite3

from src.domain.problem import FALLBACK_LOCALE, Problem, load_problems, normalize_locale
from src.storage import sqlite as db


def get_reference_approach(
    problem_id: str,
    locale: str | None = None,
    *,
    problems: tuple[Problem, ...] | None = None,
    connection: sqlite3.Connection | None = None,
    preferred_language: str | None = None,
) -> dict:
    """Referans yaklaşımın etiketlerini ve `locale` dilindeki özetini döner."""
    problem = _find_problem(problem_id, problems)
    reference = problem.reference_approach
    if not reference:
        raise LookupError(f"problem {problem_id!r} has no reference_approach")

    resolved_locale = normalize_locale(
        locale or preferred_language or _profile_language(connection),
        default=FALLBACK_LOCALE,
    )

    summaries = reference.get("summary") or {}
    summary = summaries.get(resolved_locale) or summaries.get(FALLBACK_LOCALE)
    if not summary:
        raise LookupError(
            f"problem {problem_id!r} has no reference_approach summary "
            f"for locale {resolved_locale!r}"
        )

    return {
        "approach_tags": list(reference.get("tags", [])),
        "approach_summary": summary,
        "locale": resolved_locale,
    }


def _find_problem(problem_id: str, problems: tuple[Problem, ...] | None) -> Problem:
    catalog = problems if problems is not None else load_problems()
    for problem in catalog:
        if problem.id == problem_id:
            return problem
    raise LookupError(f"unknown problem_id: {problem_id!r}")


def _profile_language(connection: sqlite3.Connection | None) -> str | None:
    """Profildeki `preferred_language`; profil yoksa `None` (EN'e düşülür)."""
    conn = connection if connection is not None else db.connect()
    profile = db.get_profile(conn)
    return profile["preferred_language"] if profile is not None else None
