"""Output rendering for the cpr client (form B).

Implements the [1]–[5] structure from 形态-B 需求 §3 / 协议 §2.1:

    [1] command header   ($ cpr <argv>)
    [2] one-line summary (result.summary)
    [3] usage line       (bold; result.usage)
    [4] candidates table (ASCII columns; folded past max_candidates with "… and N more")
    [5] notes            (skipped if empty)
    [6] danger banner    (only when result.danger; printed by render_danger_prompt)

Color is plain ANSI (\\x1b[...m) — no rich/click/textual. Color is disabled
when stdout is not a TTY, when NO_COLOR is set in the environment, or when
the caller passes ``color=False``.

Error and quota copy comes from cpr.i18n; every protocol §2.1 error code has
both zh-CN and en-US strings. ``render_error_payload`` accepts a raw response
or ApiError-shaped dict and produces the user-facing message + hint pair.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from cpr.i18n import I18n, resolve_locale

# All protocol §2.1 error codes the renderer knows how to localize.
KNOWN_ERROR_CODES = (
    "HELP_NOT_FOUND",
    "HELP_TIMEOUT",
    "BAD_REQUEST",
    "INVALID_CLIENT",
    "INVALID_TEMPLATE",
    "SCHEMA_MISMATCH",
    "QUOTA_EXCEEDED",
    "LLM_PARSE_FAILED",
    "LLM_TIMEOUT",
    "SERVER_ERROR",
    "NETWORK_UNREACHABLE",
)

DEFAULT_MAX_CANDIDATES = 10
ANSI_RESET = "\x1b[0m"
ANSI_BOLD = "\x1b[1m"
ANSI_DIM = "\x1b[2m"
ANSI_RED = "\x1b[31m"
ANSI_YELLOW = "\x1b[33m"
ANSI_CYAN = "\x1b[36m"
ANSI_GREEN = "\x1b[32m"


@dataclass(frozen=True)
class ColorPolicy:
    """Whether each ANSI sequence is emitted.

    A single boolean keeps the API simple: ``ColorPolicy.detect()`` honors
    NO_COLOR and TTY status, and individual call sites can pass an explicit
    ``ColorPolicy(enabled=False)`` for tests / piped output.
    """

    enabled: bool = True

    @staticmethod
    def detect(stream: Any | None = None) -> "ColorPolicy":
        if os.environ.get("NO_COLOR"):
            return ColorPolicy(False)
        target = stream if stream is not None else sys.stdout
        try:
            return ColorPolicy(bool(target.isatty()))
        except Exception:
            return ColorPolicy(False)

    def wrap(self, code: str, text: str) -> str:
        if not self.enabled or not text:
            return text
        return f"{code}{text}{ANSI_RESET}"

    def bold(self, text: str) -> str:
        return self.wrap(ANSI_BOLD, text)

    def dim(self, text: str) -> str:
        return self.wrap(ANSI_DIM, text)

    def red(self, text: str) -> str:
        return self.wrap(ANSI_RED, text)

    def yellow(self, text: str) -> str:
        return self.wrap(ANSI_YELLOW, text)

    def cyan(self, text: str) -> str:
        return self.wrap(ANSI_CYAN, text)

    def green(self, text: str) -> str:
        return self.wrap(ANSI_GREEN, text)


def _resolve_i18n(i18n: I18n | None, locale: str | None) -> I18n:
    if i18n is not None:
        return i18n
    return I18n(locale or resolve_locale())


def _resolve_color(color: bool | ColorPolicy | None, stream: Any | None) -> ColorPolicy:
    if isinstance(color, ColorPolicy):
        return color
    if color is True:
        return ColorPolicy(True)
    if color is False:
        return ColorPolicy(False)
    return ColorPolicy.detect(stream)


def _visible_width(text: str) -> int:
    """Approximate display width: CJK / fullwidth count as 2 cells, the rest as 1.

    Good enough for an MVP ASCII table that mostly contains ASCII tokens with
    a sprinkling of zh-CN descriptions. Keeps `render.py` dependency-free.
    """
    width = 0
    for ch in text:
        code = ord(ch)
        if code < 0x20:
            continue
        if (
            0x1100 <= code <= 0x115F
            or 0x2E80 <= code <= 0x303E
            or 0x3041 <= code <= 0x33FF
            or 0x3400 <= code <= 0x4DBF
            or 0x4E00 <= code <= 0x9FFF
            or 0xA000 <= code <= 0xA4CF
            or 0xAC00 <= code <= 0xD7A3
            or 0xF900 <= code <= 0xFAFF
            or 0xFE30 <= code <= 0xFE4F
            or 0xFF00 <= code <= 0xFF60
            or 0xFFE0 <= code <= 0xFFE6
        ):
            width += 2
        else:
            width += 1
    return width


def _pad(text: str, target: int) -> str:
    pad = target - _visible_width(text)
    return text + (" " * pad if pad > 0 else "")


def _format_argv(tool: str, args: Iterable[str]) -> str:
    pieces = [tool]
    for arg in args:
        pieces.append(str(arg))
    return " ".join(pieces)


def _format_candidates_table(
    candidates: list[Mapping[str, Any]],
    color: ColorPolicy,
    i18n: I18n,
    max_rows: int,
) -> list[str]:
    """Render candidates as a 3-column ASCII table; fold beyond ``max_rows``.

    Output rules ("不通过条件" guard rails): no Unicode box drawing, no emoji.
    Two spaces between columns, a single dim hyphen rule under the header.
    """
    if not candidates:
        return [color.dim(i18n.t("render.empty_candidates"))]

    visible = candidates[:max_rows]
    overflow = max(0, len(candidates) - max_rows)

    header_token = i18n.t("render.table_header_token")
    header_kind = i18n.t("render.table_header_kind")
    header_desc = i18n.t("render.table_header_desc")

    rows: list[tuple[str, str, str]] = [(header_token, header_kind, header_desc)]
    for cand in visible:
        token = str(cand.get("token", ""))
        kind = _localize_kind(str(cand.get("kind", "")), i18n)
        desc = str(cand.get("desc", "") or "")
        rows.append((token, kind, desc))

    token_w = max(_visible_width(r[0]) for r in rows)
    kind_w = max(_visible_width(r[1]) for r in rows)
    desc_w = max(_visible_width(r[2]) for r in rows)

    out: list[str] = []
    for index, (token, kind, desc) in enumerate(rows):
        if index == 0:
            line = "  ".join(
                (
                    color.bold(_pad(token, token_w)),
                    color.bold(_pad(kind, kind_w)),
                    color.bold(desc),
                )
            )
        else:
            line = "  ".join(
                (
                    color.green(_pad(token, token_w)),
                    color.dim(_pad(kind, kind_w)),
                    desc,
                )
            )
        out.append(line)

    rule_len = token_w + kind_w + desc_w + 2 + 2  # two two-space gaps
    out.insert(1, color.dim("-" * rule_len))

    if overflow > 0:
        out.append(color.dim(i18n.t("render.candidates_more", count=overflow)))
    return out


def _localize_kind(kind: str, i18n: I18n) -> str:
    """Map a candidate ``kind`` enum to a localized short label.

    Falls back to the raw string if the loader has no entry; the i18n loader
    will log the missing key so future enum additions surface in CI.
    """
    if not kind:
        return ""
    return i18n.t(f"render.candidates_kind.{kind}")


def render_response(
    tool: str,
    args: Iterable[str],
    response: Mapping[str, Any],
    *,
    i18n: I18n | None = None,
    locale: str | None = None,
    color: bool | ColorPolicy | None = None,
    stream: Any | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> str:
    """Render a successful /resolve response as the [1]–[5] block.

    Caller still handles the danger y/N step via ``confirm_danger`` — this
    function only prints the [6] banner line so the user sees *why* it's
    dangerous before being prompted.
    """
    i18n = _resolve_i18n(i18n, locale)
    palette = _resolve_color(color, stream)
    result = response.get("result") if isinstance(response, Mapping) else None
    if not isinstance(result, Mapping):
        result = {}

    lines: list[str] = []
    header = palette.bold(i18n.t("render.header_prefix") + _format_argv(tool, args))
    lines.append(header)

    summary = str(result.get("summary") or "").strip()
    if summary:
        lines.append(summary)

    usage = str(result.get("usage") or "").strip()
    if usage:
        lines.append(f"{i18n.t('render.usage_label')}: {palette.bold(palette.cyan(usage))}")

    raw_candidates = result.get("candidates") or []
    candidates = [c for c in raw_candidates if isinstance(c, Mapping)]
    if candidates or raw_candidates is None or raw_candidates == []:
        lines.append(palette.bold(i18n.t("render.candidates_label") + ":"))
        lines.extend("  " + line for line in _format_candidates_table(candidates, palette, i18n, max_candidates))

    notes = [str(n).strip() for n in (result.get("notes") or []) if str(n).strip()]
    if notes:
        lines.append(palette.bold(i18n.t("render.notes_label") + ":"))
        for note in notes:
            lines.append(f"  - {note}")

    if result.get("danger"):
        reason = str(result.get("danger_reason") or "").strip()
        banner = i18n.t("danger.banner", reason=reason or i18n.t("danger.banner", reason=""))
        lines.append(palette.yellow(palette.bold(banner)))

    return "\n".join(lines)


def render_exec_template_line(
    rendered_command: str,
    *,
    i18n: I18n | None = None,
    locale: str | None = None,
    color: bool | ColorPolicy | None = None,
    stream: Any | None = None,
) -> str:
    i18n = _resolve_i18n(i18n, locale)
    palette = _resolve_color(color, stream)
    label = i18n.t("danger.exec_template_label")
    return f"{palette.bold(label)}: {palette.cyan(rendered_command)}"


def render_danger_prompt(
    *,
    i18n: I18n | None = None,
    locale: str | None = None,
) -> str:
    """Localized prompt string for ``input(...)``; default answer is N."""
    i18n = _resolve_i18n(i18n, locale)
    return i18n.t("danger.prompt")


def confirm_danger(
    *,
    yes: bool = False,
    i18n: I18n | None = None,
    locale: str | None = None,
    input_func=input,
) -> bool:
    """Return True iff the user typed an explicit y/Y. Empty / N / EOF → False.

    ``yes=True`` (matching ``confirm_danger=never`` from 协议 §6 / ``-y`` /
    ``--yes``) skips the prompt. Any other input keeps the safe default of
    "do not execute".
    """
    if yes:
        return True
    prompt = render_danger_prompt(i18n=i18n, locale=locale)
    try:
        answer = input_func(prompt)
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def render_quota_status(
    quota: Mapping[str, Any] | None,
    *,
    i18n: I18n | None = None,
    locale: str | None = None,
) -> str:
    """Format a /quota or response.quota dict using ``reset_in_seconds``.

    Per 协议 P1-2 the client must avoid local-timezone math on ``reset_at``;
    this helper rounds ``reset_in_seconds`` up to whole hours so users see
    the same "N hours" everywhere.
    """
    i18n = _resolve_i18n(i18n, locale)
    if not isinstance(quota, Mapping):
        return i18n.t("quota.unknown")
    used = quota.get("used")
    limit = quota.get("limit")
    seconds = quota.get("reset_in_seconds")
    if used is None or limit is None or seconds is None:
        return i18n.t("quota.unknown")
    try:
        seconds_int = max(0, int(seconds))
    except (TypeError, ValueError):
        return i18n.t("quota.unknown")
    hours = (seconds_int + 3599) // 3600  # round up so "N 小时后重置" never says 0
    return i18n.t("quota.status", used=used, limit=limit, hours=hours)


def render_error_payload(
    error: Mapping[str, Any] | None,
    *,
    response: Mapping[str, Any] | None = None,
    tool: str | None = None,
    timeout: float | None = None,
    client_version: str | None = None,
    server_version: str | None = None,
    i18n: I18n | None = None,
    locale: str | None = None,
    color: bool | ColorPolicy | None = None,
    stream: Any | None = None,
) -> str:
    """Render a single error block: title (red) + hint (dim).

    The renderer is permissive about input — it accepts either the raw
    ``error`` sub-object or the full response; missing fields fall back to
    sensible defaults. Quota-aware codes (QUOTA_EXCEEDED) read ``response.quota``
    so the title matches ``render_quota_status`` wording.
    """
    i18n = _resolve_i18n(i18n, locale)
    palette = _resolve_color(color, stream)

    if error is None and isinstance(response, Mapping):
        error = response.get("error")
    if not isinstance(error, Mapping):
        error = {}

    code = str(error.get("code") or "")
    message = str(error.get("message") or "")
    fmt: dict[str, Any] = {
        "tool": tool or "",
        "timeout": "" if timeout is None else _fmt_timeout(timeout),
        "message": message,
        "client": client_version or "",
        "server": server_version or "",
    }

    if code == "QUOTA_EXCEEDED":
        seconds = error.get("retry_after_seconds")
        used = limit = None
        if isinstance(response, Mapping):
            quota = response.get("quota")
            if isinstance(quota, Mapping):
                used = quota.get("used")
                limit = quota.get("limit")
                if seconds is None:
                    seconds = quota.get("reset_in_seconds")
        try:
            seconds_int = max(0, int(seconds)) if seconds is not None else 0
        except (TypeError, ValueError):
            seconds_int = 0
        fmt["used"] = "?" if used is None else used
        fmt["limit"] = "?" if limit is None else limit
        fmt["hours"] = (seconds_int + 3599) // 3600

    title_key = f"error.{code}.title" if code in KNOWN_ERROR_CODES else "error.generic_title"
    hint_key = f"error.{code}.hint" if code in KNOWN_ERROR_CODES else None

    title = i18n.t(title_key, **fmt)
    if title_key == "error.generic_title" and message:
        title = f"{title}: {message}"

    lines = [palette.red(palette.bold(title))]
    if hint_key:
        hint = i18n.t(hint_key, **fmt)
        if hint and hint != hint_key:
            lines.append(palette.dim(hint))
    return "\n".join(lines)


def render_no_args(
    *,
    i18n: I18n | None = None,
    locale: str | None = None,
    color: bool | ColorPolicy | None = None,
    stream: Any | None = None,
) -> str:
    """Output for bare ``cpr`` (no subcommand)."""
    i18n = _resolve_i18n(i18n, locale)
    palette = _resolve_color(color, stream)
    title = palette.bold(f"{i18n.t('app.name')} — {i18n.t('app.tagline')}")
    body = i18n.t("cli.no_args")
    return f"{title}\n\n{body}".rstrip() + "\n"


def _fmt_timeout(seconds: float) -> str:
    if float(seconds).is_integer():
        return str(int(seconds))
    return f"{float(seconds):.1f}"


__all__ = [
    "ColorPolicy",
    "DEFAULT_MAX_CANDIDATES",
    "KNOWN_ERROR_CODES",
    "confirm_danger",
    "render_danger_prompt",
    "render_error_payload",
    "render_exec_template_line",
    "render_no_args",
    "render_quota_status",
    "render_response",
]
