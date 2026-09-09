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
