from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shlex
import signal
import subprocess
import time


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error_kind: str | None = None


class Executor:
    def __init__(self, home: Path | None = None) -> None:
        self.home = Path(home or os.path.expanduser("~"))
        self._process: subprocess.Popen[str] | None = None

    def run_sync(self, command: str, shell_mode: str = "direct", timeout: float | None = None) -> ExecutionResult:
        start = time.monotonic()
        timeout = timeout if timeout is not None else (120 if shell_mode == "bash-lc-source" else 30)
        try:
            process = subprocess.Popen(
                self._args(command, shell_mode),
                cwd=str(self.home),
                env=self._env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._process = process
            stdout, stderr = process.communicate(timeout=timeout)
            return ExecutionResult(process.returncode == 0, stdout, stderr, process.returncode, _elapsed(start))
        except subprocess.TimeoutExpired:
            self.cancel()
            return ExecutionResult(False, "", "command timed out", -1, _elapsed(start), "timeout")
        finally:
            self._process = None

    def cancel(self) -> None:
        process = self._process
        if not process or process.poll() is not None:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                process.send_signal(sig)
                process.wait(2)
                return
            except subprocess.TimeoutExpired:
                continue
        process.kill()
        process.wait()

    def _args(self, command: str, shell_mode: str) -> list[str]:
        if shell_mode == "direct":
            return shlex.split(command)
        if shell_mode == "bash-lc-source":
            return ["bash", "-lc", f"source {self._sdkman_init()} && {command}"]
        raise ValueError(f"unsupported shell mode: {shell_mode}")

    def _sdkman_init(self) -> str:
        sdkman_dir = os.environ.get("SDKMAN_DIR")
        if sdkman_dir:
            return str(Path(sdkman_dir) / "bin" / "sdkman-init.sh")
        return str(self.home / ".sdkman" / "bin" / "sdkman-init.sh")

    def _env(self) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items() if key in {"HOME", "PATH", "LANG", "LC_ALL", "SDKMAN_DIR"}}
        env["HOME"] = str(self.home)
        env["LC_ALL"] = "en_US.UTF-8" if platform.system() == "Darwin" else "C.UTF-8"
        return env


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
