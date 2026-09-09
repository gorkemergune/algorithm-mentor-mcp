"""submit_solution tool — bkz. docs/TOOLS.md → submit_solution.

Kullanıcının kodunu sandbox'ta çalıştırır ve problemin test case'lerinden
(gizliler dahil) geçirir. Harness sözleşmesi TOOLS.md'de tanımlıdır:
`input` JSON argüman listesi olarak `solve(*args)`'a açılır, dönen değer
`json.loads(expected)` ile tam eşitlik (`==`) üzerinden karşılaştırılır.

Dışarıya yalnızca sıra numarası ve geçti/kaldı bilgisi döner — gizli test
girdileri, kullanıcının kendi print çıktıları ve sandbox stdout'u sızmaz.
"""

from __future__ import annotations

import json

from src.domain.problem import Problem, load_problems
from src.execution.engine import (
    DEFAULT_TIMEOUT_SECONDS,
    ExecutionEngine,
)
from src.execution.python_runner import PythonRunner

#: v1'de sadece Python (bkz. CLAUDE.md → ExecutionEngine).
SUPPORTED_LANGUAGES = ("python",)

#: Harness'ın sonuç satırlarını kullanıcının kendi çıktısından ayıran işaret.
RESULT_MARKER = "__MENTOR_RESULT__"

_HARNESS = f'''

# --- mentor harness (kullanıcı kodunun altına eklenir) ----------------------
def __mentor_main() -> None:
    import contextlib as _contextlib
    import io as _io
    import json as _json
    import sys as _sys

    _cases = _json.loads(_sys.stdin.read())
    _solve = globals().get("solve")

    for _index, _case in enumerate(_cases, start=1):
        _record = {{"case": _index, "passed": False, "error": None}}
        try:
            if not callable(_solve):
                raise NameError("solve function is not defined")
            _args = _json.loads("[" + _case["input"] + "]")
            _expected = _json.loads(_case["expected"])
            # Kullanıcının debug print'leri sonuç satırlarına karışmasın.
            with _contextlib.redirect_stdout(_io.StringIO()):
                _result = _solve(*_args)
            _record["passed"] = _result == _expected
        except BaseException as _exc:  # noqa: BLE001 - her hata case'e yazılır
            _record["error"] = f"{{type(_exc).__name__}}: {{_exc}}"
        print("{RESULT_MARKER}" + _json.dumps(_record), flush=True)


__mentor_main()
'''


def submit_solution(
    code: str,
    problem_id: str,
    language: str = "python",
    *,
    problems: tuple[Problem, ...] | None = None,
    engine: ExecutionEngine | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Kodu çalıştırır, test sonuçlarını döner.

    Dönen sözlük: `passed`, `test_results` (`[{"case": 1, "passed": true}]`),
    `runtime_ms`, `error`.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported language: {language!r} (v1 supports {SUPPORTED_LANGUAGES})")

    problem = _find_problem(problem_id, problems)
    cases = problem.test_cases
    if not cases:
        raise LookupError(f"problem {problem_id!r} has no test cases")

    runner = engine if engine is not None else PythonRunner()
    payload = json.dumps(
        [{"input": case.input, "expected": case.expected} for case in cases],
        ensure_ascii=False,
    )

    result = runner.execute(code + _HARNESS, language, stdin=payload, timeout=timeout)
    reported = _parse_results(result.stdout)

    test_results = [
        {"case": index, "passed": bool(reported.get(index, {}).get("passed", False))}
        for index in range(1, len(cases) + 1)
    ]
    error = result.error or _first_case_error(reported)

    return {
        "passed": all(case["passed"] for case in test_results) and error is None,
        "test_results": test_results,
        "runtime_ms": result.runtime_ms,
        "error": error,
    }


def _find_problem(problem_id: str, problems: tuple[Problem, ...] | None) -> Problem:
    catalog = problems if problems is not None else load_problems()
    for problem in catalog:
        if problem.id == problem_id:
            return problem
    raise LookupError(f"unknown problem_id: {problem_id!r}")


def _parse_results(stdout: str) -> dict[int, dict]:
    """Harness'ın işaretli satırlarını okur; kullanıcının çıktısını yok sayar."""
    records: dict[int, dict] = {}
    for line in stdout.splitlines():
        if not line.startswith(RESULT_MARKER):
            continue
        try:
            record = json.loads(line[len(RESULT_MARKER) :])
        except json.JSONDecodeError:  # pragma: no cover - harness hep JSON yazar
            continue
        records[record["case"]] = record
    return records


def _first_case_error(reported: dict[int, dict]) -> str | None:
    for index in sorted(reported):
        error = reported[index].get("error")
        if error:
            return error
    return None
