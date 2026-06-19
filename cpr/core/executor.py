from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

ShellMode = str


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

    async def run(self, command: str, shell_mode: ShellMode = "direct", timeout: float | None = None) -> ExecutionResult:
        return await asyncio.to_thread(self.run_sync, command, shell_mode, timeout)

    def run_sync(self, command: str, shell_mode: ShellMode = "direct", timeout: float | None = None) -> ExecutionResult:
        start = time.monotonic()
        timeout = timeout if timeout is not None else (120 if shell_mode == "bash-lc-source" else 30)
        args = self._args(command, shell_mode)
        try:
            process = subprocess.Popen(
                args,
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
            exit_code = process.returncode
            return ExecutionResult(exit_code == 0, stdout, stderr, exit_code, _elapsed(start))
        except subprocess.TimeoutExpired:
            self.cancel()
            return ExecutionResult(False, "", "command timed out", -1, _elapsed(start), "timeout")
        finally:
            self._process = None

    def cancel(self) -> None:
        process = self._process
        if not process or process.poll() is not None:
            return
        for sig, wait_seconds in ((signal.SIGINT, 2), (signal.SIGTERM, 2)):
            try:
                process.send_signal(sig)
                process.wait(wait_seconds)
                return
            except subprocess.TimeoutExpired:
                continue
        process.kill()
        process.wait()

    def list_installed_java_versions(self) -> list[str]:
        path = self.home / ".sdkman" / "candidates" / "java"
        if not path.exists():
            return []
        return sorted(child.name for child in path.iterdir() if child.is_dir() and child.name != "current")

    def _args(self, command: str, shell_mode: ShellMode) -> list[str]:
        if shell_mode == "direct":
            return command.split()
        if shell_mode == "bash-lc-source":
            return ["bash", "-lc", f"source {self._sdkman_init()} && {command}"]
        raise ValueError(f"unsupported shell mode: {shell_mode}")

    def _sdkman_init(self) -> str:
        sdkman_dir = os.environ.get("SDKMAN_DIR")
        if sdkman_dir:
            return str(Path(sdkman_dir) / "bin" / "sdkman-init.sh")
        return str(self.home / ".sdkman" / "bin" / "sdkman-init.sh")

    def _env(self) -> dict[str, str]:
        allowed = {key: value for key, value in os.environ.items() if key in {"HOME", "PATH", "LANG", "LC_ALL", "SDKMAN_DIR"}}
        allowed["HOME"] = str(self.home)
        allowed["LC_ALL"] = "en_US.UTF-8" if platform.system() == "Darwin" else "C.UTF-8"
        return allowed


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
