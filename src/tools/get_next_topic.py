"""get_next_topic tool — bkz. docs/TOOLS.md → get_next_topic.

Üç kural (STUDENT_PROFILE_SCHEMA.md → "Sonraki konu seçimi"):
ön koşul eşiği, en düşük skor, sıkışma koruması. Tool profili yalnızca
okur — `current_focus`'u `update_profile` günceller.
"""

from __future__ import annotations

import sqlite3

from src.domain.problem import FALLBACK_LOCALE, normalize_locale
from src.domain.topics import (
    PREREQUISITE_THRESHOLD,
    candidate_topics,
    load_topics,
    lowest_scoring,
)
from src.storage import sqlite as db

#: Sıkışma sayılması için gereken art arda başarısız deneme sayısı.
STUCK_ATTEMPT_COUNT = 3

#: Bu skor ve altı "başarısız deneme" demektir (sabit tablonun en alt basamağı).
FAILING_SCORE = 0.2

REASON_LOWEST_SCORE = "lowest_score"
REASON_STUCK_FALLBACK = "stuck_fallback"
REASON_STUCK_NO_PREREQUISITE = "stuck_no_prerequisite"

#: Sabit TR/EN şablonlar — server serbest metin üretmez, şablon doldurur.
REASON_TEMPLATES: dict[str, dict[str, str]] = {
    REASON_LOWEST_SCORE: {
        "tr": "En düşük skor (%{percent}), ön koşullar tamam ({prerequisites})",
        "en": "Lowest score ({percent}%), prerequisites met ({prerequisites})",
    },
    "lowest_score_no_prerequisites": {
        "tr": "En düşük skor (%{percent}), ön koşul gerektirmiyor",
        "en": "Lowest score ({percent}%), no prerequisites",
    },
    REASON_STUCK_FALLBACK: {
        "tr": (
            "{stuck_topic} konusunda son {count} deneme başarısız; "
            "en zayıf ön koşul {topic} (%{percent}) pekiştiriliyor"
        ),
        "en": (
            "Last {count} attempts on {stuck_topic} all failed; "
            "reinforcing its weakest prerequisite {topic} ({percent}%)"
        ),
    },
    REASON_STUCK_NO_PREREQUISITE: {
        "tr": (
            "{topic} konusunda son {count} deneme başarısız ama dönülecek "
            "ön koşul yok; daha kolay bir problemle devam"
        ),
        "en": (
            "Last {count} attempts on {topic} all failed but it has no "
            "prerequisite to fall back to; continue with an easier problem"
        ),
    },
}


def get_next_topic(
    *,
    connection: sqlite3.Connection | None = None,
    topics: dict[str, tuple[str, ...]] | None = None,
    locale: str | None = None,
) -> dict:
    """Bir sonraki konuyu ve gerekçesini döner."""
    conn = connection if connection is not None else db.connect()
    profile = db.get_profile(conn)
    if profile is None:
        raise LookupError("no profile yet — call assess_level first")

    graph = topics if topics is not None else load_topics()
    scores = db.get_topic_scores(conn)
    if not scores:
        raise LookupError("topic_scores is empty — call assess_level first")

    resolved_locale = normalize_locale(
        locale or profile.get("preferred_language"), default=FALLBACK_LOCALE
    )

    candidates = candidate_topics(graph, scores)
    if not candidates:
        raise LookupError("no candidate topic: every topic is blocked by its prerequisites")

    topic = lowest_scoring(candidates, scores)

    if not _is_stuck(conn, topic):
        prerequisites = graph.get(topic, ())
        key = REASON_LOWEST_SCORE if prerequisites else "lowest_score_no_prerequisites"
        return _result(
            topic=topic,
            reason_code=REASON_LOWEST_SCORE,
            locale=resolved_locale,
            template_key=key,
            percent=_percent(scores.get(topic, 0.0)),
            prerequisites=", ".join(prerequisites),
        )

    fallback = _weakest_prerequisite(graph.get(topic, ()), scores)
    if fallback is None:
        return _result(
            topic=topic,
            reason_code=REASON_STUCK_NO_PREREQUISITE,
            locale=resolved_locale,
            template_key=REASON_STUCK_NO_PREREQUISITE,
            topic_name=topic,
            count=STUCK_ATTEMPT_COUNT,
        )

    return _result(
        topic=fallback,
        reason_code=REASON_STUCK_FALLBACK,
        locale=resolved_locale,
        template_key=REASON_STUCK_FALLBACK,
        topic_name=fallback,
        stuck_topic=topic,
        count=STUCK_ATTEMPT_COUNT,
        percent=_percent(scores.get(fallback, 0.0)),
    )


def _result(
    *,
    topic: str,
    reason_code: str,
    locale: str,
    template_key: str,
    topic_name: str | None = None,
    **fields,
) -> dict:
    template = REASON_TEMPLATES[template_key][locale]
    return {
        "recommended_topic": topic,
        "reason_code": reason_code,
        "reason": template.format(topic=topic_name or topic, **fields),
        "locale": locale,
    }


def _percent(score: float) -> int:
    return round(score * 100)


def _is_stuck(connection: sqlite3.Connection, topic: str) -> bool:
    """Konunun kendi son 3 denemesi de başarısız mı?

    Araya başka konuların denemeleri girmiş olabilir — bakılan seri konunun
    kendi geçmişidir (docs/TOOLS.md → get_next_topic, kural 3).
    """
    attempts = db.get_attempts(connection, topic=topic, limit=STUCK_ATTEMPT_COUNT)
    if len(attempts) < STUCK_ATTEMPT_COUNT:
        return False
    return all(attempt["score"] <= FAILING_SCORE for attempt in attempts)


def _weakest_prerequisite(
    prerequisites: tuple[str, ...],
    scores: dict[str, float],
) -> str | None:
    """En düşük skorlu doğrudan ön koşul; ön koşul yoksa `None`."""
    if not prerequisites:
        return None
    return min(prerequisites, key=lambda prereq: scores.get(prereq, 0.0))
