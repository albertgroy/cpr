"""Keybinding wiring for the CPR workspace.

Per archi's contract review (sections 1.3 / 1.6):

- Enter: if current node executable -> execute; else if a candidate is selected -> append its token.
- Backspace: input non-empty -> normal char delete; input empty -> session.popToken().
- Esc: input non-empty -> clear input; input empty -> session.popToken().
- Tab: accept the highlighted candidate and append it as a token.
- ↑ / ↓: move candidate selection (focus stays in the input area).

Slash commands are detected when the input starts with '/' and Enter is pressed;
the actual /back /clear /help dispatch lives in agent1's slash command parser
(commit 7). This module only forwards the buffer text via the supplied callback.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings

from cpr.tui.app import WorkspaceState
from cpr.tui.candidates import CandidateRefresher

ExecuteHook = Callable[[WorkspaceState, str], Awaitable[None] | None]
SlashHook = Callable[[WorkspaceState, str], Awaitable[None] | None]


def build_keybindings(
    state: WorkspaceState,
    input_buffer: Buffer,
    refresher: CandidateRefresher,
    *,
    execute: ExecuteHook | None = None,
    slash: SlashHook | None = None,
) -> KeyBindings:
    bindings = KeyBindings()

    async def _refresh() -> None:
        await refresher.refresh(state)

    def _schedule_refresh(event) -> None:
        event.app.create_background_task(_refresh())

    @bindings.add("enter")
    def _enter(event) -> None:
        text = input_buffer.text
        if text.startswith("/"):
            input_buffer.reset()
            if slash is not None:
                outcome = slash(state, text)
                if outcome is not None:
                    event.app.create_background_task(outcome)
            _schedule_refresh(event)
            return

        # Pure whitespace input + executable node -> execute.
        if not text.strip():
            node = state.session.current_node
            if node is not None and node.executable and execute is not None:
                command = node.execute.command if node.execute else " ".join(node.tokens)
                outcome = execute(state, command)
                if outcome is not None:
                    event.app.create_background_task(outcome)
                input_buffer.reset()
                return
            # otherwise accept selected candidate
            if state.candidates:
                _accept_selected(event)
                return
            return

        # Free-form token: append every whitespace-separated piece.
        for token in text.split():
            state.session.append_token(token)
        input_buffer.reset()
        _schedule_refresh(event)

    def _accept_selected(event) -> None:
        if not state.candidates:
            return
        selected = state.candidates[state.selected_index]
        state.session.append_token(selected.token)
        input_buffer.reset()
        _schedule_refresh(event)

    @bindings.add("tab")
    def _tab(event) -> None:
        _accept_selected(event)

    @bindings.add("backspace")
    def _backspace(event) -> None:
        if input_buffer.text:
            input_buffer.delete_before_cursor(1)
            return
        popped = state.session.pop_token()
        if popped is not None:
            _schedule_refresh(event)

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if input_buffer.text:
            input_buffer.reset()
            return
        popped = state.session.pop_token()
        if popped is not None:
            _schedule_refresh(event)

    @bindings.add("up")
    def _up(_event) -> None:
        state.select_prev()

    @bindings.add("down")
    def _down(_event) -> None:
        state.select_next()

    return bindings


__all__ = [
    "ExecuteHook",
    "SlashHook",
    "build_keybindings",
]
