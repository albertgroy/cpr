"""prompt_toolkit workspace layout for CPR.

This module provides the visual skeleton:

- input area: top single-line buffer where the user types tokens or slash commands.
- content area: scrollable read-only buffer that shows current node title/desc and execution output.
- candidates area: bottom list of available next tokens for the current node.

Keybindings beyond a minimal Ctrl-C/Ctrl-D exit live in :mod:`cpr.tui.keys` and are
wired in by :func:`build_app` once the core session glue is ready.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style

from cpr.core.model import CommandTree
from cpr.core.session import CommandSession
from cpr.i18n import I18nLoader

LOG_PATH = Path.home() / ".cpr" / "logs" / "cpr.log"

STYLE = Style.from_dict(
    {
        "title": "bold",
        "prompt": "bold ansicyan",
        "candidates.header": "bold",
        "candidates.selected": "reverse",
        "candidates.token": "ansigreen",
        "candidates.desc": "ansiwhite",
        "content.stderr": "ansiyellow",
        "content.error": "ansired",
        "content.loading": "italic ansibrightblack",
        "status": "ansibrightblack",
    }
)


@dataclass
class Candidate:
    token: str
    label: str = ""
    desc: str = ""
    source: str = "static"


@dataclass
class WorkspaceState:
    session: CommandSession
    i18n: I18nLoader
    candidates: list[Candidate]
    selected_index: int = 0
    loading: bool = False
    candidate_error: str | None = None

    def select_next(self) -> None:
        if self.candidates:
            self.selected_index = (self.selected_index + 1) % len(self.candidates)

    def select_prev(self) -> None:
        if self.candidates:
            self.selected_index = (self.selected_index - 1) % len(self.candidates)

    def reset_selection(self) -> None:
        self.selected_index = 0


def _refuse_on_windows() -> None:
    if sys.platform == "win32":
        sys.stderr.write(
            "CPR MVP does not support Windows yet. Use macOS or Linux.\n"
        )
        raise SystemExit(2)


def _print_log_path() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    sys.stderr.write(f"[cpr] log path: {LOG_PATH}\n")


def _build_input_buffer() -> Buffer:
    return Buffer(multiline=False)


def _build_content_buffer(state: WorkspaceState) -> Buffer:
    initial = _initial_content(state)
    return Buffer(document=Document(initial, cursor_position=0), read_only=False)


def _initial_content(state: WorkspaceState) -> str:
    title = state.i18n.text("app.name")
    intro = (
        "Enter / 选择候选 -> 追加 token；Backspace / Esc 在输入区为空时弹出 token。\n"
        "Slash 命令：/help /back /clear /ai /explain /fix。"
    )
    return f"{title}\n{intro}\n"


def _candidate_text(state: WorkspaceState) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    header = "候选" if state.i18n.locale == "zh-CN" else "Candidates"
    current_path = " ".join(state.session.current_tokens) or "(root)"
    fragments.append(("class:candidates.header", f"{header} :: {current_path}\n"))

    if state.loading:
        fragments.append(("class:content.loading", "(loading…)\n"))
        return fragments

    if state.candidate_error:
        prefix = "动态候选解析失败：" if state.i18n.locale == "zh-CN" else "Dynamic candidate error: "
        fragments.append(("class:content.error", f"{prefix}{state.candidate_error}\n"))
        return fragments

    if not state.candidates:
        empty = "(无候选 / no candidates)"
        fragments.append(("class:status", f"{empty}\n"))
        return fragments

    for index, candidate in enumerate(state.candidates):
        marker = "▶ " if index == state.selected_index else "  "
        style = "class:candidates.selected" if index == state.selected_index else "class:candidates.token"
        line = f"{marker}{candidate.token}"
        if candidate.label and candidate.label != candidate.token:
            line += f"  {candidate.label}"
        if candidate.desc:
            line += f"  — {candidate.desc}"
        line += f"  [{candidate.source}]\n"
        fragments.append((style, line))
    return fragments


def _status_text(state: WorkspaceState) -> list[tuple[str, str]]:
    locale = state.i18n.locale
    node = state.session.current_node
    node_label = node.id if node else "(no node)"
    return [
        ("class:status", f"locale={locale}  node={node_label}  log={LOG_PATH}\n"),
    ]


def build_layout(
    state: WorkspaceState,
    input_buffer: Buffer,
    content_buffer: Buffer,
) -> Layout:
    input_window = Window(
        content=BufferControl(
            buffer=input_buffer,
            input_processors=[BeforeInput(text="cpr> ", style="class:prompt")],
        ),
        height=1,
        wrap_lines=False,
    )

    content_window = Window(
        content=BufferControl(buffer=content_buffer),
        wrap_lines=True,
        always_hide_cursor=True,
    )

    candidates_window = Window(
        content=FormattedTextControl(text=lambda: _candidate_text(state), focusable=False),
        height=D(min=3, max=10),
        wrap_lines=False,
    )

    status_window = Window(
        content=FormattedTextControl(text=lambda: _status_text(state), focusable=False),
        height=1,
    )

    return Layout(
        HSplit(
            [
                input_window,
                Window(height=1, char="─", style="class:status"),
                content_window,
                Window(height=1, char="─", style="class:status"),
                candidates_window,
                status_window,
            ]
        ),
        focused_element=input_window,
    )


def _baseline_keybindings() -> KeyBindings:
    """Minimal exit bindings; full Enter/Backspace/Esc/Tab wiring lives in cpr.tui.keys."""
    bindings = KeyBindings()

    @bindings.add("c-c")
    @bindings.add("c-d")
    def _(event) -> None:
        event.app.exit()

    return bindings


def build_app(
    tree: CommandTree,
    *,
    locale: str | None = None,
    extra_keys: Callable[[WorkspaceState, Buffer, Buffer], KeyBindings] | None = None,
) -> tuple[Application, WorkspaceState, Buffer, Buffer]:
    """Build the prompt_toolkit Application without running it.

    ``extra_keys`` lets the keybindings module register Enter/Backspace/Esc/Tab/arrow
    handlers in commit 8 without touching the layout module.
    """
    _refuse_on_windows()
    i18n = I18nLoader(locale=locale)
    session = CommandSession(tree=tree)
    state = WorkspaceState(session=session, i18n=i18n, candidates=[])

    input_buffer = _build_input_buffer()
    content_buffer = _build_content_buffer(state)
    layout = build_layout(state, input_buffer, content_buffer)

    bindings = _baseline_keybindings()
    if extra_keys is not None:
        custom = extra_keys(state, input_buffer, content_buffer)
        bindings = _merge_bindings(bindings, custom)

    app = Application(
        layout=layout,
        key_bindings=bindings,
        full_screen=True,
        mouse_support=False,
        style=STYLE,
    )
    return app, state, input_buffer, content_buffer


def _merge_bindings(base: KeyBindings, extra: KeyBindings) -> KeyBindings:
    merged = KeyBindings()
    for binding in list(base.bindings) + list(extra.bindings):
        merged.bindings.append(binding)
    return merged


def run_app(tree: CommandTree, *, locale: str | None = None) -> None:
    _print_log_path()
    # Wire keybindings + static candidate resolver via a deferred import so
    # cpr.tui.app stays import-cycle-free (keys/candidates depend on app).
    from cpr.core.slash import SlashCommandParser
    from cpr.tui.candidates import AsyncCandidateRefresher, static_resolver
    from cpr.tui.keys import build_keybindings

    holder: dict[str, object] = {}
    parser = SlashCommandParser()

    def extra(state: WorkspaceState, input_buffer: Buffer, content_buffer: Buffer) -> KeyBindings:
        refresher = AsyncCandidateRefresher(
            resolver=static_resolver,
            invalidate=lambda: holder["app"].invalidate() if "app" in holder else None,
        )

        def slash(state: WorkspaceState, text: str) -> None:
            result = parser.handle(text, state.session)
            if not result.add_history:
                return
            content_buffer.text = content_buffer.text + f"{text}\n{result.message}\n"

        return build_keybindings(state, input_buffer, refresher, slash=slash)

    app, state, _input, _content = build_app(tree, locale=locale, extra_keys=extra)
    holder["app"] = app
    app.run()


__all__ = [
    "Candidate",
    "LOG_PATH",
    "STYLE",
    "WorkspaceState",
    "build_app",
    "build_layout",
    "run_app",
]
