"""hint tool — bkz. docs/TOOLS.md → hint.

Kademeli ipucu verir: `attempt_number` arttıkça hint netleşir (1: yaklaşım
yönü, 2: veri yapısı/algoritma adı, 3: neredeyse-çözüm pseudocode). Metinler
`data/problems.json`'da problem başına TR/EN tutulur — server serbest metin
üretmez, sabit şablon seçer.
"""

from __future__ import annotations

import sqlite3

from src.domain.problem import FALLBACK_LOCALE, Problem, load_problems, normalize_locale
from src.storage import sqlite as db


def hint(
    problem_id: str,
    attempt_number: int,
    locale: str | None = None,
    *,
    problems: tuple[Problem, ...] | None = None,
    connection: sqlite3.Connection | None = None,
    preferred_language: str | None = None,
) -> dict:
    """`attempt_number`'a karşılık gelen ipucunu döner.

    Deneme sayısı hint listesinin sonunu aşarsa en son (en açık) hint
    tekrar döner — hata değil, kullanıcı takılmaya devam ediyor demektir.
    `locale` boşsa profildeki `preferred_language` kullanılır.
    """
    if attempt_number < 1:
        raise ValueError(f"attempt_number must be 1 or greater, got {attempt_number!r}")

    problem = _find_problem(problem_id, problems)
    resolved_locale = normalize_locale(
        locale or preferred_language or _profile_language(connection),
        default=FALLBACK_LOCALE,
    )

    hints = problem.localized_hints(resolved_locale)
    if not hints:
        raise LookupError(f"problem {problem_id!r} has no hints for locale {resolved_locale!r}")

    hint_level = min(attempt_number, len(hints))
    return {
        "hint_level": hint_level,
        "hint_text": hints[hint_level - 1],
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
