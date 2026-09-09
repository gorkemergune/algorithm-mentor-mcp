import textwrap

import pytest

from src.execution.engine import (
    ExecutionEngine,
    ExecutionResult,
    UnsupportedLanguageError,
)
from src.execution.python_runner import PythonRunner, describe_error


@pytest.fixture
def runner():
    return PythonRunner()


class TestSuccessfulExecution:
    def test_runs_code_and_captures_stdout(self, runner):
        result = runner.execute("print('merhaba')", "python")

        assert result.stdout == "merhaba\n"
        assert result.exit_code == 0
        assert result.error is None
        assert result.timed_out is False
        assert result.ok

    def test_stdin_is_forwarded(self, runner):
        code = "import sys\nprint(sys.stdin.read().strip().upper())"
        result = runner.execute(code, "python", stdin="veri\n")

        assert result.stdout == "VERI\n"
        assert result.ok

    def test_runtime_ms_is_measured(self, runner):
        result = runner.execute("print(1)", "python")
        assert result.runtime_ms >= 0

    def test_code_runs_in_a_throwaway_directory(self, runner):
        code = "import pathlib; print(sorted(p.name for p in pathlib.Path('.').iterdir()))"
        result = runner.execute(code, "python")

        # Proje dosyaları değil, yalnızca yazılan script görünür.
        assert result.stdout.strip() == "['solution.py']"


class TestFailingExecution:
    def test_syntax_error_is_reported(self, runner):
        result = runner.execute("def solve(:\n    pass", "python")

        assert result.exit_code != 0
        assert result.error is not None
        assert "SyntaxError" in result.error
        assert not result.ok

    def test_runtime_exception_is_reported(self, runner):
        result = runner.execute("raise ValueError('patladı')", "python")

        assert result.error is not None
        assert "ValueError" in result.error
        assert "patladı" in result.error
        assert "Traceback" in result.stderr

    def test_nonzero_exit_without_stderr_is_still_an_error(self, runner):
        result = runner.execute("import sys; sys.exit(3)", "python")

        assert result.exit_code == 3
        assert result.error == "Process exited with code 3"


class TestTimeout:
    def test_infinite_loop_is_killed(self, runner):
        result = runner.execute("while True:\n    pass", "python", timeout=0.5)

        assert result.timed_out is True
        assert result.error == "Timed out after 0.5s"
        assert not result.ok

    def test_timeout_does_not_hang_much_past_the_limit(self, runner):
        result = runner.execute("while True:\n    pass", "python", timeout=0.5)
        assert result.runtime_ms < 5_000

    def test_reading_stdin_gets_eof_instead_of_hanging(self, runner):
        # stdin kapatılır: girdi beklemeyen bir çözüm boşuna timeout yemez.
        result = runner.execute("import sys; print(repr(sys.stdin.read()))", "python")

        assert result.timed_out is False
        assert result.stdout.strip() == "''"

    def test_child_processes_are_killed_too(self, runner):
        # Torun process de öldürülmeli; aksi halde communicate() boruyu
        # kapatamaz ve çağrı timeout'un çok ötesine sarkar.
        code = textwrap.dedent(
            """
            import subprocess, sys
            subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            while True:
                pass
            """
        )
        result = runner.execute(code, "python", timeout=0.5)

        assert result.timed_out is True
        assert result.runtime_ms < 10_000

    def test_non_positive_timeout_is_rejected(self, runner):
        with pytest.raises(ValueError):
            runner.execute("print(1)", "python", timeout=0)


class TestLanguageSupport:
    def test_python_is_supported(self, runner):
        assert runner.supported_languages == ("python",)

    def test_other_languages_are_rejected(self, runner):
        with pytest.raises(UnsupportedLanguageError):
            runner.execute("int main(){}", "cpp")


class TestOutputLimits:
    def test_huge_output_is_truncated(self):
        runner = PythonRunner(max_output_chars=100)
        result = runner.execute("print('x' * 5000)", "python", timeout=5)

        assert len(result.stdout) < 200
        assert "kısaltıldı" in result.stdout


class TestEngineContract:
    def test_python_runner_implements_the_interface(self, runner):
        assert isinstance(runner, ExecutionEngine)

    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            ExecutionEngine()

    def test_result_is_immutable(self):
        result = ExecutionResult(stdout="", stderr="", exit_code=0, runtime_ms=1)
        with pytest.raises(Exception):
            result.stdout = "değişti"


class TestDescribeError:
    def test_timeout_wins_over_everything(self):
        assert describe_error("stderr", -9, True, 2.0) == "Timed out after 2s"

    def test_clean_exit_has_no_error(self):
        assert describe_error("", 0, False, 5.0) is None

    def test_last_stderr_line_is_used(self):
        stderr = "Traceback (most recent call last):\n  File ...\nKeyError: 'x'\n"
        assert describe_error(stderr, 1, False, 5.0) == "KeyError: 'x'"

    def test_signal_death_without_stderr(self):
        assert describe_error("", -9, False, 5.0) == "Process killed by signal 9"
