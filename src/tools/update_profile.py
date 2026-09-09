"""update_profile tool — bkz. docs/TOOLS.md → update_profile.

Kritik kural: bu tool skor **hesaplamaz**. Aldığı `score`, bir önceki
`review_solution` çağrısının sabit tablodan ürettiği değer olmak
zorundadır; doğrulama `mastery.is_valid_score` ile
(`math.isclose(..., abs_tol=1e-9)`) yapılır ve başarısızsa çağrı reddedilir.
EMA formülü de `mastery.update_topic_score`'da yaşar, burada kopyalanmaz.
"""

from __future__ import annotations

import sqlite3

from src.domain import mastery
from src.storage import sqlite as db


def update_profile(
    topic: str,
    problem_id: str,
    score: float,
    evidence: list[str] | None = None,
    mistake_type: str | None = None,
    hints_used: int = 0,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict:
    """Denemeyi profile işler ve güncel özeti döner.

    Dönen değer: `topic_scores`, `recent_evidence`, `level`.
    """
    if hints_used < 0:
        raise ValueError(f"hints_used cannot be negative, got {hints_used!r}")
    if not mastery.is_valid_score(score):
        raise ValueError(
            f"score {score!r} did not come from review_solution's fixed table "
            f"{sorted(mastery.VALID_SCORES)} — update_profile does not accept host-computed scores"
        )

    conn = connection if connection is not None else db.connect()
    if db.get_profile(conn) is None:
        raise LookupError("no profile yet — call assess_level first")

    previous = db.get_topic_score(conn, topic)
    if previous is None:
        raise LookupError(
            f"topic {topic!r} is not seeded in topic_scores — call assess_level first"
        )

    db.set_topic_score(conn, topic, mastery.update_topic_score(previous, score))
    db.insert_attempt(
        conn,
        problem_id=problem_id,
        topic=topic,
        score=score,
        evidence=list(evidence or []),
        hints_used=hints_used,
        mistake_type=mistake_type,
    )
    if evidence:
        db.add_recent_evidence(conn, topic, list(evidence))

    scores = db.get_topic_scores(conn)
    level = mastery.level_for_scores(scores)
    db.update_profile_row(conn, level=level, current_focus=topic)

    return {
        "topic_scores": scores,
        "recent_evidence": db.get_recent_evidence(conn),
        "level": level,
    }
