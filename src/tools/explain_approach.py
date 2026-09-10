"""explain_approach tool — bkz. docs/TOOLS.md → explain_approach.

Kullanıcının sözlü anlatımını **alındı** olarak onaylar, başka bir şey
yapmaz: doğruluğu yargılamaz ve metni hiçbir yere kalıcı yazmaz. Ham
anlatım yalnızca bu konuşma turu içinde, host'un `get_reference_approach`
ile karşılaştırması için vardır; kalıcılaşan tek şey `review_solution`'ın
ürettiği sabit `evidence` metnidir (`update_profile` üzerinden).
"""

from __future__ import annotations

from src.domain.problem import Problem, load_problems


def explain_approach(
    problem_id: str,
    explanation: str,
    *,
    problems: tuple[Problem, ...] | None = None,
) -> dict:
    """Anlatımı alındı olarak onaylar. Veritabanına hiçbir şey yazmaz."""
    if not explanation or not explanation.strip():
        raise ValueError("explanation is empty — nothing to compare against the reference")

    _ensure_problem_exists(problem_id, problems)
    return {"received": True, "problem_id": problem_id}


def _ensure_problem_exists(problem_id: str, problems: tuple[Problem, ...] | None) -> None:
    catalog = problems if problems is not None else load_problems()
    if not any(problem.id == problem_id for problem in catalog):
        raise LookupError(f"unknown problem_id: {problem_id!r}")
