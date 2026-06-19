import sys

from cpr.core.executor import Executor


def test_direct_uses_shlex_split_and_runs_without_shell():
    result = Executor().run_sync(f"{sys.executable} -c 'print(123)'", "direct")
    assert result.ok
    assert result.stdout.strip() == "123"


def test_bash_lc_source_args_uses_sdkman_dir(monkeypatch):
    monkeypatch.setenv("SDKMAN_DIR", "/tmp/sdkman")
    assert Executor()._args("sdk current java", "bash-lc-source") == ["bash", "-lc", "source /tmp/sdkman/bin/sdkman-init.sh && sdk current java"]


def test_env_whitelist(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret")
    env = Executor()._env()
    assert "SECRET_TOKEN" not in env
    assert env["LC_ALL"] in {"en_US.UTF-8", "C.UTF-8"}


def test_timeout_returns_exit_minus_one():
    result = Executor().run_sync(f"{sys.executable} -c 'import time; time.sleep(1)'", timeout=0.01)
    assert not result.ok
    assert result.exit_code == -1
    assert result.error_kind == "timeout"
