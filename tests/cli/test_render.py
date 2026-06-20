"""Unit tests for cpr.cli.render (T-002b agent2 scope).

Covers:
- normal [1]–[5] rendering for both locales
- candidates folding past max_candidates
- each of the 11 protocol §2.1 error codes (title + hint)
- danger confirm: y / Y / N / empty / EOF / yes=True
- quota text formatting (uses reset_in_seconds, rounds up)
- ColorPolicy detection (NO_COLOR / TTY)
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from cpr.cli.render import (
    DEFAULT_MAX_CANDIDATES,
    KNOWN_ERROR_CODES,
    ColorPolicy,
    confirm_danger,
    render_danger_prompt,
    render_error_payload,
    render_exec_template_line,
    render_no_args,
    render_quota_status,
    render_response,
)
from cpr.i18n import I18n

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "server" / "scenarios"


def _load(name: str) -> dict:
    with (FIXTURES / name / "response.json").open() as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# render_response — normal [1]–[5] block
# ---------------------------------------------------------------------------


def test_render_response_sdk_install_java_en():
    resp = _load("sdk_install_java")
    out = render_response("sdk", ["install", "java"], resp, i18n=I18n("en-US"), color=False)
    assert out.splitlines()[0] == "$ sdk install java"
    assert "Install Java with SDKMAN" in out
    assert "Usage: sdk install java <identifier>" in out
    assert "Candidates:" in out
    assert "TOKEN" in out and "TYPE" in out and "DESCRIPTION" in out
    assert "17.0.10-tem" in out
    assert "Notes:" in out
    assert "Downloads and writes into ~/.sdkman." in out
    assert "Danger: writes to SDKMAN directories" in out


def test_render_response_sdk_install_java_zh():
    resp = _load("sdk_install_java")
    out = render_response("sdk", ["install", "java"], resp, i18n=I18n("zh-CN"), color=False)
    assert "$ sdk install java" in out
    assert "用法: sdk install java <identifier>" in out
    assert "候选:" in out
    assert "备注:" in out
    assert "危险：writes to SDKMAN directories" in out
    assert "标识" in out  # localized kind label for "id"


def test_render_response_sdk_root_no_danger():
    resp = _load("sdk_root")
    out = render_response("sdk", [], resp, i18n=I18n("en-US"), color=False)
    assert out.splitlines()[0] == "$ sdk"
    assert "Danger" not in out  # not a dangerous command


def test_render_response_no_candidates_emits_empty_marker():
    resp = {"result": {"summary": "x", "usage": "x", "candidates": [], "notes": []}}
    out = render_response("x", [], resp, i18n=I18n("en-US"), color=False)
    assert "(no candidates)" in out


# ---------------------------------------------------------------------------
# candidates folding
# ---------------------------------------------------------------------------


def test_candidates_folding():
    cands = [{"token": f"v{i}", "kind": "id", "desc": f"version {i}"} for i in range(15)]
    resp = {"result": {"summary": "many", "candidates": cands, "notes": []}}
    out = render_response("x", [], resp, i18n=I18n("en-US"), color=False, max_candidates=10)
    # First 10 visible
    for i in range(10):
        assert f"v{i} " in out or f"v{i}\n" in out or f"v{i}  " in out
    # 11..14 collapsed
    assert "v11" not in out
    assert "and 5 more" in out


def test_candidates_no_overflow_when_exact_max():
    cands = [{"token": f"v{i}", "kind": "id", "desc": ""} for i in range(DEFAULT_MAX_CANDIDATES)]
    resp = {"result": {"summary": "n", "candidates": cands}}
    out = render_response("x", [], resp, i18n=I18n("en-US"), color=False)
    assert "more" not in out


# ---------------------------------------------------------------------------
# error payload — all 11 codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", KNOWN_ERROR_CODES)
def test_render_error_payload_each_code_en(code):
    err = {"code": code, "message": "boom"}
    resp = {"quota": {"used": 50, "limit": 50, "reset_in_seconds": 7200}}
    out = render_error_payload(
        err,
        response=resp,
        tool="kubectl",
        timeout=2.5,
        client_version="1",
        server_version="2",
        i18n=I18n("en-US"),
        color=False,
    )
    # Title line + hint line, both non-empty, non-key fallthrough
    lines = out.splitlines()
    assert len(lines) >= 1
    assert lines[0]
    assert not lines[0].startswith("error.")  # localized, not raw key


@pytest.mark.parametrize("code", KNOWN_ERROR_CODES)
def test_render_error_payload_each_code_zh(code):
    err = {"code": code, "message": "boom"}
    resp = {"quota": {"used": 50, "limit": 50, "reset_in_seconds": 7200}}
    out = render_error_payload(
        err,
        response=resp,
        tool="kubectl",
        timeout=2.5,
        client_version="1",
        server_version="2",
        i18n=I18n("zh-CN"),
        color=False,
    )
    assert out
    assert not out.startswith("error.")


def test_render_error_payload_quota_uses_response_quota():
    err = {"code": "QUOTA_EXCEEDED"}
    resp = {"quota": {"used": 50, "limit": 50, "reset_in_seconds": 1}}
    out = render_error_payload(err, response=resp, i18n=I18n("en-US"), color=False)
    assert "50/50" in out
    assert "1h" in out  # rounds up


def test_render_error_payload_help_not_found_includes_tool():
    err = {"code": "HELP_NOT_FOUND"}
    out = render_error_payload(err, tool="nope", i18n=I18n("en-US"), color=False)
    assert "nope" in out


def test_render_error_payload_unknown_code_falls_back_to_generic():
    err = {"code": "TOTALLY_UNKNOWN", "message": "weird thing"}
    out = render_error_payload(err, i18n=I18n("en-US"), color=False)
    assert "weird thing" in out


def test_render_error_payload_accepts_full_response_object():
    resp = {"error": {"code": "HELP_NOT_FOUND"}}
    out = render_error_payload(None, response=resp, tool="missing", i18n=I18n("en-US"), color=False)
    assert "missing" in out


# ---------------------------------------------------------------------------
# danger confirm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("answer,expected", [
    ("y", True),
    ("Y", True),
    ("yes", False),
    ("n", False),
    ("N", False),
    ("", False),
    ("  ", False),
])
def test_confirm_danger_input(answer, expected):
    assert confirm_danger(input_func=lambda _p: answer, i18n=I18n("en-US")) is expected


def test_confirm_danger_eof_is_safe_default():
    def raise_eof(_):
        raise EOFError
    assert confirm_danger(input_func=raise_eof, i18n=I18n("en-US")) is False


def test_confirm_danger_yes_skips_prompt():
    called = {"n": 0}
    def boom(_):
        called["n"] += 1
        return "y"
    assert confirm_danger(yes=True, input_func=boom) is True
    assert called["n"] == 0


def test_render_danger_prompt_localized():
    assert render_danger_prompt(i18n=I18n("en-US")) == "Run it? (y/N) "
    assert render_danger_prompt(i18n=I18n("zh-CN")) == "确认执行？(y/N) "


# ---------------------------------------------------------------------------
# quota text
# ---------------------------------------------------------------------------


def test_render_quota_status_rounds_up():
    out = render_quota_status({"used": 12, "limit": 50, "reset_in_seconds": 7201}, i18n=I18n("en-US"))
    assert out == "AI quota: 12/50 (resets in 3h)"


def test_render_quota_status_one_second_still_one_hour():
    out = render_quota_status({"used": 12, "limit": 50, "reset_in_seconds": 1}, i18n=I18n("en-US"))
    assert "1h" in out


def test_render_quota_status_zero_seconds_zero_hours():
    out = render_quota_status({"used": 12, "limit": 50, "reset_in_seconds": 0}, i18n=I18n("en-US"))
    assert "0h" in out


def test_render_quota_status_unknown_when_missing_field():
    assert render_quota_status({"used": 1, "limit": 50}, i18n=I18n("en-US")) == "AI quota: unknown"
    assert render_quota_status(None, i18n=I18n("en-US")) == "AI quota: unknown"


def test_render_quota_status_unknown_on_bad_seconds():
    out = render_quota_status({"used": 1, "limit": 50, "reset_in_seconds": "soon"}, i18n=I18n("en-US"))
    assert out == "AI quota: unknown"


# ---------------------------------------------------------------------------
# ColorPolicy / misc helpers
# ---------------------------------------------------------------------------


def test_color_policy_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ColorPolicy.detect().enabled is False


def test_color_policy_non_tty_disables(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    buf = io.StringIO()
    assert ColorPolicy.detect(buf).enabled is False


def test_color_policy_wrap_only_when_enabled():
    on = ColorPolicy(True)
    off = ColorPolicy(False)
    assert "\x1b[" in on.bold("hi")
    assert off.bold("hi") == "hi"


def test_render_response_emits_ansi_when_enabled():
    resp = _load("sdk_install_java")
    out = render_response("sdk", ["install", "java"], resp, i18n=I18n("en-US"), color=True)
    assert "\x1b[" in out


def test_render_no_args_includes_app_name_and_examples():
    out = render_no_args(i18n=I18n("en-US"), color=False)
    assert "cpr" in out
    assert "cpr sdk" in out
    assert "cpr --quota" in out


def test_render_exec_template_line_label_and_command():
    out = render_exec_template_line("sdk install java 17", i18n=I18n("en-US"), color=False)
    assert out == "Will run: sdk install java 17"


# ---------------------------------------------------------------------------
# i18n parity sanity check (every error code covered both locales)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", KNOWN_ERROR_CODES)
def test_locales_have_each_error_code(code):
    en = I18n("en-US")
    zh = I18n("zh-CN")
    for key in (f"error.{code}.title", f"error.{code}.hint"):
        en_v = en.t(key, tool="t", timeout=1, message="m", client="1", server="2", used=0, limit=0, hours=0)
        zh_v = zh.t(key, tool="t", timeout=1, message="m", client="1", server="2", used=0, limit=0, hours=0)
        assert en_v != key, f"missing en-US key: {key}"
        assert zh_v != key, f"missing zh-CN key: {key}"
