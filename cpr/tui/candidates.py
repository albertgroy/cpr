"""Candidate resolution glue for the TUI.

The static resolver pulls children of the current node out of the command
tree. agent1's dynamic provider (T-001 commit 6) plugs in via the same
``CandidateResolver`` callable, optionally returning an awaitable so the
TUI can fire it through ``run_in_executor`` with a ``(loading…)`` placeholder.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Awaitable, Callable, Protocol

from cpr.core.session import CommandSession
from cpr.i18n import I18nLoader

from cpr.tui.app import Candidate, WorkspaceState


CandidateResolver = Callable[
    [CommandSession, I18nLoader],
    "list[Candidate] | Awaitable[list[Candidate]]",
]


class CandidateRefresher(Protocol):
    async def refresh(self, state: WorkspaceState) -> None: ...


def static_resolver(session: CommandSession, i18n: I18nLoader) -> list[Candidate]:
    """Default resolver: children of the longest-matched node."""
    node = session.current_node
    if node is None:
        # nothing typed yet — surface the tree roots
        candidates: list[Candidate] = []
        for root_id in session.tree.root_ids:
            root = session.tree.get(root_id)
            candidates.append(
                Candidate(
                    token=root.token,
                    label=i18n.node_text(root.title, root.id),
                    desc=i18n.node_text(root.desc, root.id),
                    source="static",
                )
            )
        return candidates

    if node.param is not None:
        # param node itself: no nested children. dynamic provider should
        # have populated candidates upstream; static resolver returns empty.
        return []

    candidates = []
    for child in node.children:
        if child.param is not None:
            candidates.append(
                Candidate(
                    token=child.token,
                    label=i18n.node_text(child.title, child.id),
                    desc=i18n.node_text(child.desc, child.id),
                    source="dynamic-pending",
                )
            )
            continue
        candidates.append(
            Candidate(
                token=child.token,
                label=i18n.node_text(child.title, child.id),
                desc=i18n.node_text(child.desc, child.id),
                source="static",
            )
        )
    return candidates


class AsyncCandidateRefresher:
    """Run a resolver off the UI thread, flip ``loading`` and invalidate the app."""

    def __init__(
        self,
        resolver: CandidateResolver,
        invalidate: Callable[[], None],
    ) -> None:
        self._resolver = resolver
        self._invalidate = invalidate
        self._task: asyncio.Task | None = None

    async def refresh(self, state: WorkspaceState) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        loop = asyncio.get_running_loop()
        state.loading = True
        state.candidate_error = None
        self._invalidate()

        async def _run() -> None:
            try:
                outcome = self._resolver(state.session, state.i18n)
                if inspect.isawaitable(outcome):
                    candidates = await outcome  # type: ignore[assignment]
                else:
                    candidates = await loop.run_in_executor(None, lambda: outcome)
                state.candidates = list(candidates)
                state.reset_selection()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # do not swallow — show in UI
                state.candidates = []
                state.candidate_error = f"{type(exc).__name__}: {exc}"
            finally:
                state.loading = False
                self._invalidate()

        self._task = asyncio.create_task(_run())


__all__ = [
    "AsyncCandidateRefresher",
    "CandidateRefresher",
    "CandidateResolver",
    "static_resolver",
]
