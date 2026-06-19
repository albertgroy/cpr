import os
from pathlib import Path
import subprocess

from cpr.core.executor import Executor


def test_direct_executor_success():
    result = Executor().run_sync("python -c print(123)", "direct")
    assert result.ok
    assert result.stdout.strip() == "123"
    assert result.stderr == ""


def test_bash_lc_source_args_uses_sdkman_dir(monkeypatch):
    monkeypatch.setenv("SDKMAN_DIR", "/tmp/sdkman")
    args = Executor()._args("sdk list java", "bash-lc-source")
    assert args == ["bash", "-lc", "source /tmp/sdkman/bin/sdkman-init.sh && sdk list java"]


def test_env_whitelist(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret")
    env = Executor()._env()
    assert "SECRET_TOKEN" not in env
    assert env["LC_ALL"] in {"en_US.UTF-8", "C.UTF-8"}


def test_timeout_returns_failure():
    result = Executor().run_sync("python -c import time;time.sleep(1)", "direct", timeout=0.01)
    assert not result.ok
    assert result.exit_code == -1
    assert result.error_kind == "timeout"


def test_list_installed_java_versions(tmp_path):
    java = tmp_path / ".sdkman" / "candidates" / "java"
    java.mkdir(parents=True)
    (java / "17.0.10-tem").mkdir()
    (java / "current").mkdir()
    assert Executor(tmp_path).list_installed_java_versions() == ["17.0.10-tem"]
