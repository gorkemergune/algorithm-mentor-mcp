"""PythonRunner — v1'in tek `ExecutionEngine` implementasyonu.

Kod, ayrı bir yorumlayıcı process'inde (`python -I`), geçici bir dizinde,
CPU/bellek/dosya-boyutu limitleri ve wall-clock timeout altında çalışır.
Docker'a geçiş (v2) bu dosyayı değiştirir, arayüzü değil.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from src.execution.engine import (
    DEFAULT_TIMEOUT_SECONDS,
    ExecutionEngine,
    ExecutionResult,
)

#: Çocuk process'in adres alanı limiti (bayt). Yorumlayıcının kendi
#: ihtiyacını da kapsadığı için cömert tutulur.
DEFAULT_MEMORY_BYTES = 512 * 1024 * 1024

#: Diske yazılabilecek en büyük dosya (bayt) — disk doldurmayı engeller.
DEFAULT_FILE_SIZE_BYTES = 8 * 1024 * 1024

#: stdout/stderr'den saklanacak en fazla karakter — print bombasına karşı.
MAX_OUTPUT_CHARS = 64 * 1024

_TRUNCATION_NOTE = "\n...[çıktı kısaltıldı]"


class PythonRunner(ExecutionEngine):
    supported_languages = ("python",)

    def __init__(
        self,
        *,
        interpreter: str | None = None,
        memory_bytes: int | None = DEFAULT_MEMORY_BYTES,
        file_size_bytes: int | None = DEFAULT_FILE_SIZE_BYTES,
        max_output_chars: int = MAX_OUTPUT_CHARS,
    ) -> None:
        self.interpreter = interpreter or sys.executable
        self.memory_bytes = memory_bytes
        self.file_size_bytes = file_size_bytes
        self.max_output_chars = max_output_chars

    # --- ExecutionEngine ----------------------------------------------------

    def execute(
        self,
        code: str,
        language: str,
        stdin: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult:
        self.ensure_language_supported(language)
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout!r}")

        with tempfile.TemporaryDirectory(prefix="mentor-run-") as workdir:
            script = Path(workdir) / "solution.py"
            script.write_text(code, encoding="utf-8")
            return self._run(script, workdir, stdin, timeout)

    # --- iç ayrıntılar ------------------------------------------------------

    def _run(self, script: Path, workdir: str, stdin: str, timeout: float) -> ExecutionResult:
        started = time.perf_counter()
        process = subprocess.Popen(
            [self.interpreter, "-I", "-B", str(script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={"PATH": os.defpath, "HOME": workdir, "TMPDIR": workdir},
            start_new_session=True,
            preexec_fn=self._apply_limits(timeout),  # noqa: PLW1509 - kasıtlı
        )

        timed_out = False
        try:
            stdout, stderr = process.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_process_group(process)
            stdout, stderr = process.communicate()

        runtime_ms = int((time.perf_counter() - started) * 1000)
        exit_code = process.returncode
        stdout = self._truncate(stdout)
        stderr = self._truncate(stderr)

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            runtime_ms=runtime_ms,
            timed_out=timed_out,
            error=describe_error(stderr, exit_code, timed_out, timeout),
        )

    def _apply_limits(self, timeout: float):
        """Çocuk process'te (fork sonrası, exec öncesi) çalışacak limitleri kurar."""
        memory_bytes = self.memory_bytes
        file_size_bytes = self.file_size_bytes
        cpu_seconds = int(timeout) + 1

        def set_limits() -> None:  # pragma: no cover - çocuk process'te çalışır
            try:
                import resource
            except ImportError:
                return  # POSIX dışı platform; wall-clock timeout yine geçerli

            def limit(name: str, value: int | None) -> None:
                """Limiti kurar; platform kabul etmiyorsa sessizce geçer.

                macOS `RLIMIT_AS`'i reddediyor (setrlimit hata veriyor) —
                orada bellek limiti uygulanmaz, CPU ve wall-clock limitleri
                tek koruma olarak kalır. Linux'ta üçü de geçerlidir.
                """
                if value is None:
                    return
                try:
                    resource.setrlimit(getattr(resource, name), (value, value))
                except (ValueError, OSError, AttributeError):
                    pass

            limit("RLIMIT_CPU", cpu_seconds)
            limit("RLIMIT_FSIZE", file_size_bytes)
            limit("RLIMIT_AS", memory_bytes)

        return set_limits

    @staticmethod
    def _kill_process_group(process: subprocess.Popen) -> None:
        """Zaman aşımında yalnız çocuğu değil, torunlarını da öldürür."""
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):  # pragma: no cover
            process.kill()

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + _TRUNCATION_NOTE


def describe_error(
    stderr: str,
    exit_code: int | None,
    timed_out: bool,
    timeout: float,
) -> str | None:
    """Çalıştırma sonucundan tek satırlık, okunabilir bir hata metni üretir.

    Hata yoksa `None` döner. `submit_solution` bu metni olduğu gibi kendi
    `error` alanına yazar.
    """
    if timed_out:
        return f"Timed out after {timeout:g}s"
    if exit_code == 0:
        return None

    last_line = next(
        (line.strip() for line in reversed(stderr.splitlines()) if line.strip()),
        "",
    )
    if last_line:
        return last_line
    if exit_code is not None and exit_code < 0:
        return f"Process killed by signal {-exit_code}"
    return f"Process exited with code {exit_code}"
