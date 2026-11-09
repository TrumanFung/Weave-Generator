"""Undo/redo over whole-draft snapshots. Drafts are small, so snapshots beat per-edit commands."""

from __future__ import annotations

from weavegen.core.draft import Draft, DraftState


class History:
    def __init__(self, limit: int = 200) -> None:
        self._limit = limit
        self._undo: list[DraftState] = []
        self._redo: list[DraftState] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def record(self, before: DraftState) -> None:
        """Remember the state from before an edit. Any redo history is discarded."""
        self._undo.append(before)
        if len(self._undo) > self._limit:
            del self._undo[0]
        self._redo.clear()

    def undo(self, draft: Draft) -> bool:
        if not self._undo:
            return False
        self._redo.append(draft.snapshot())
        draft.restore(self._undo.pop())
        return True

    def redo(self, draft: Draft) -> bool:
        if not self._redo:
            return False
        self._undo.append(draft.snapshot())
        draft.restore(self._redo.pop())
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
