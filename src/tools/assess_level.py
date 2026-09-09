"""assess_level tool — bkz. docs/TOOLS.md → assess_level.

v1'de tool kullanıcıya soru çözdürmez ve host'tan sayısal tahmin kabul
etmez: `data/topics.json`'daki her konu `0.0` ile seed'lenir, seviye
`"beginner"` başlar. Gerçek ölçüm normal döngüde (`review_solution` →
`update_profile`) birikir; soru sorarak ölçen değerlendirme akışı v2.
"""

from __future__ import annotations

import sqlite3

from src.domain import mastery
from src.domain.problem import SUPPORTED_LOCALES
from src.domain.topics import load_topics
from src.storage import sqlite as db

#: Yeni profilde her konunun başlangıç skoru.
SEED_SCORE = 0.0


def assess_level(
    preferred_language: str = "tr",
    retake: bool = False,
    *,
    connection: sqlite3.Connection | None = None,
    topics: dict[str, tuple[str, ...]] | None = None,
) -> dict:
    """Profili kurar (ya da `retake` ile yeniden seed'ler) ve özetini döner.

    Profil zaten varsa ve `retake=False` ise hiçbir şey sıfırlanmaz; mevcut
    durum olduğu gibi döner (idempotent).
    """
    if preferred_language not in SUPPORTED_LOCALES:
        raise ValueError(
            f"unsupported preferred_language: {preferred_language!r} "
            f"(expected one of {SUPPORTED_LOCALES})"
        )

    graph = topics if topics is not None else load_topics()
    conn = connection if connection is not None else db.connect()

    existing = db.get_profile(conn)
    if existing is not None and not retake:
        return _summary(conn, graph)

    if existing is None:
        db.create_profile(conn, level="beginner", preferred_language=preferred_language)
    else:
        # retake: skorlar ve kanıt geçmişi sıfırlanır, `attempts` korunur.
        db.update_profile_row(
            conn,
            level="beginner",
            preferred_language=preferred_language,
            current_focus=None,
        )
        db.clear_recent_evidence(conn)

    db.seed_topic_scores(conn, {topic: SEED_SCORE for topic in graph})
    summary = _summary(conn, graph)
    db.update_profile_row(conn, current_focus=summary["recommended_start_topic"])
    return summary


def _summary(conn: sqlite3.Connection, graph: dict[str, tuple[str, ...]]) -> dict:
    scores = db.get_topic_scores(conn)
    return {
        "estimated_level": mastery.level_for_scores(scores),
        "topic_estimates": {topic: scores.get(topic, SEED_SCORE) for topic in graph},
        "recommended_start_topic": recommended_start_topic(scores, graph),
    }


def recommended_start_topic(
    scores: dict[str, float],
    graph: dict[str, tuple[str, ...]],
) -> str:
    """Prerequisite'i olmayan konular arasından en düşük skorlusu.

    Eşitlikte `data/topics.json`'daki sıra kazanır.
    """
    roots = [topic for topic, prerequisites in graph.items() if not prerequisites]
    if not roots:
        raise ValueError("topic graph has no prerequisite-free topic to start from")
    return min(roots, key=lambda topic: scores.get(topic, SEED_SCORE))
