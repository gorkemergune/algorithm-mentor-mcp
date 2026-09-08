"""Problem veri modeli ve `data/problems.json` yükleyicisi.

Problem metinleri veride `{"tr": ..., "en": ...}` olarak tutulur (i18n kuralı,
bkz. CLAUDE.md); dışarıya düz string dönmek bu modelin işidir — host'a çift
dil karmaşası yansımaz.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

SUPPORTED_LOCALES = ("tr", "en")
FALLBACK_LOCALE = "en"

DIFFICULTIES = ("easy", "medium", "hard")

PROBLEMS_PATH = Path(__file__).resolve().parents[2] / "data" / "problems.json"


@dataclass(frozen=True)
class ProblemTestCase:
    input: str
    expected: str
    hidden: bool = False


@dataclass(frozen=True)
class Problem:
    id: str
    topic: str
    difficulty: str
    title: dict[str, str]
    prompt: dict[str, str]
    starter_code: str
    test_cases: tuple[ProblemTestCase, ...]
    reference_approach: dict = field(default_factory=dict)
    hints: dict[str, list[str]] = field(default_factory=dict)

    def localized(self, field_value: dict[str, str], locale: str) -> str:
        """Çok dilli bir alandan `locale`'e uyanı seçer, yoksa EN'e düşer."""
        return field_value.get(locale) or field_value[FALLBACK_LOCALE]

    def localized_title(self, locale: str) -> str:
        return self.localized(self.title, locale)

    def localized_prompt(self, locale: str) -> str:
        return self.localized(self.prompt, locale)

    def visible_test_cases(self) -> tuple[ProblemTestCase, ...]:
        """Kullanıcıya gösterilebilir test case'ler — gizliler `submit_solution`'a kalır."""
        return tuple(case for case in self.test_cases if not case.hidden)


def _to_problem(raw: dict) -> Problem:
    return Problem(
        id=raw["id"],
        topic=raw["topic"],
        difficulty=raw["difficulty"],
        title=raw["title"],
        prompt=raw["prompt"],
        starter_code=raw["starter_code"],
        test_cases=tuple(
            ProblemTestCase(
                input=case["input"],
                expected=case["expected"],
                hidden=case.get("hidden", False),
            )
            for case in raw.get("test_cases", [])
        ),
        reference_approach=raw.get("reference_approach", {}),
        hints=raw.get("hints", {}),
    )


def load_problems(path: Path | None = None) -> tuple[Problem, ...]:
    """Problem setini yükler. Yol verilmezse `data/problems.json` cache'lenir."""
    if path is None:
        return _load_default_problems()
    raw_problems = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(_to_problem(raw) for raw in raw_problems)


@lru_cache(maxsize=1)
def _load_default_problems() -> tuple[Problem, ...]:
    raw_problems = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    return tuple(_to_problem(raw) for raw in raw_problems)


def normalize_locale(locale: str | None, default: str = FALLBACK_LOCALE) -> str:
    """Boş/desteklenmeyen locale'i güvenli bir değere indirger."""
    if not locale:
        return default
    locale = locale.lower()
    return locale if locale in SUPPORTED_LOCALES else default
