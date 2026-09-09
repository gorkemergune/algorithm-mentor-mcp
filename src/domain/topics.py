"""Konu bağımlılık grafiği — `data/topics.json` yükleyicisi.

Grafik statiktir (v1): her konu, prerequisite konularının listesini taşır.
`assess_level` seed için, `get_next_topic` aday seçimi için okur.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

TOPICS_PATH = Path(__file__).resolve().parents[2] / "data" / "topics.json"


class TopicDataError(ValueError):
    """`data/topics.json` tutarsızsa atılır."""


def load_topics(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Konu → prerequisite listesi. Sıra dosyadaki sırayı korur."""
    if path is None:
        return _load_default_topics()
    return _parse(json.loads(Path(path).read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _load_default_topics() -> dict[str, tuple[str, ...]]:
    return _parse(json.loads(TOPICS_PATH.read_text(encoding="utf-8")))


def _parse(raw: dict) -> dict[str, tuple[str, ...]]:
    topics = {name: tuple(entry.get("prerequisites", [])) for name, entry in raw.items()}
    for name, prerequisites in topics.items():
        unknown = [prereq for prereq in prerequisites if prereq not in topics]
        if unknown:
            raise TopicDataError(
                f"topic {name!r} lists unknown prerequisite(s): {', '.join(unknown)}"
            )
    return topics


def root_topics(topics: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Prerequisite'i olmayan konular — bir profilin başlayabileceği yerler."""
    return tuple(name for name, prerequisites in topics.items() if not prerequisites)


#: Bir konunun "tamamlandı" sayılması için gereken skor (docs/TOOLS.md →
#: get_next_topic). 0.6, sabit skor tablosunda "2+ hint ile çözdü" seviyesi.
PREREQUISITE_THRESHOLD = 0.6


def candidate_topics(
    topics: dict[str, tuple[str, ...]],
    scores: dict[str, float],
    threshold: float = PREREQUISITE_THRESHOLD,
) -> tuple[str, ...]:
    """Tüm ön koşulları eşik üstünde olan konular; sıra dosyadaki sırayla."""
    return tuple(
        name
        for name, prerequisites in topics.items()
        if all(scores.get(prereq, 0.0) >= threshold for prereq in prerequisites)
    )


def lowest_scoring(candidates: tuple[str, ...], scores: dict[str, float]) -> str:
    """Adaylar arasından en düşük skorlu konu; eşitlikte ilk sıra kazanır."""
    if not candidates:
        raise ValueError("no candidate topic to choose from")
    return min(candidates, key=lambda topic: scores.get(topic, 0.0))
