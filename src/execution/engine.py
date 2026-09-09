"""ExecutionEngine — kod çalıştırmanın dilden bağımsız arayüzü.

v1'de tek implementasyon `PythonRunner` (subprocess + kaynak limitleri), ama
çağıran taraf (`submit_solution`) hep bu arayüzü görür. Docker tabanlı ya da
başka dillere ait runner'lar (v2) aynı arayüzün altına eklenir; bugünkü
subprocess kararı çağıranlara sızmaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

#: Wall-clock varsayılanı (saniye). Çağıran isterse `execute(timeout=...)`.
DEFAULT_TIMEOUT_SECONDS = 5.0


class ExecutionError(RuntimeError):
    """Kodun kendisiyle değil, çalıştırma altyapısıyla ilgili hata."""


class UnsupportedLanguageError(ExecutionError):
    """Runner'ın desteklemediği bir dil istendi."""


@dataclass(frozen=True)
class ExecutionResult:
    """Bir çalıştırmanın ham sonucu — yorumlamak çağıranın işi.

    `error`, kullanıcı kodundan kaynaklanan hatayı (syntax, exception,
    timeout) insan tarafından okunabilir tek bir metin olarak taşır; hata
    yoksa `None`. `submit_solution` bunu doğrudan kendi `error` alanına
    yazar (bkz. docs/TOOLS.md → submit_solution).
    """

    stdout: str
    stderr: str
    exit_code: int | None
    runtime_ms: int
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.exit_code == 0


class ExecutionEngine(ABC):
    """Kod çalıştırıcıların ortak arayüzü."""

    #: Bu runner'ın kabul ettiği diller.
    supported_languages: tuple[str, ...] = ()

    @abstractmethod
    def execute(
        self,
        code: str,
        language: str,
        stdin: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ExecutionResult:
        """`code`'u `stdin` ile çalıştırır, `timeout` saniyede keser."""

    def ensure_language_supported(self, language: str) -> None:
        if language not in self.supported_languages:
            raise UnsupportedLanguageError(
                f"unsupported language: {language!r} "
                f"(this runner supports {self.supported_languages})"
            )
