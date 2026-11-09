"""Fabric analysis: work out a draft from a drawdown.

Given only the picture of the cloth (which ends are up on each pick), the threading, tie-up and
treadling can be found by grouping identical threads:

* ends whose columns are identical can share a shaft, so the number of different columns is the
  number of shafts needed (an end that is never lifted needs no shaft at all: it is left unthreaded);
* picks whose rows are identical can share a treadle, so the number of different rows is the
  number of treadles needed (a pick that lifts nothing presses no treadle).

Shafts and treadles are numbered in the order they are first needed, reading ends and picks from
number 1. This is the *smallest* draft for that cloth, so it is also how to reduce a draft to the
fewest shafts and treadles it needs.

If more than 32 different picks are found, the draft is given as a liftplan instead of a tie-up and
treadling. More than 32 different ends cannot be woven on 32 shafts and is an error.
"""

from __future__ import annotations

import numpy as np

from weavegen.core.draft import (
    MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, UNTHREADED, Draft,
)


def draft_from_drawdown(drawdown: np.ndarray, *, rising: bool = True) -> Draft:
    """The smallest draft whose drawdown is ``drawdown`` (picks x ends, True where the warp is on top).

    Raises ValueError for an empty or oversized array, or when more than 32 shafts would be needed.
    """
    drawdown = np.asarray(drawdown)
    if drawdown.ndim != 2 or drawdown.size == 0:
        raise ValueError("the drawdown must be a non-empty grid of cells")
    picks, ends = drawdown.shape
    if ends > MAX_ENDS or picks > MAX_PICKS:
        raise ValueError(f"the drawdown is {ends} x {picks} cells; at most {MAX_ENDS} x {MAX_PICKS} are supported")
    drawdown = drawdown.astype(bool)
    lifts = drawdown if rising else ~drawdown     # lifted shafts, whichever way the shed moves

    # Group identical ends into shafts, and identical picks into treadles.
    column_ids, columns = _group(lifts.T)
    row_ids, rows = _group(lifts)
    if len(columns) > MAX_SHAFTS:
        raise ValueError(f"this cloth needs {len(columns)} shafts, more than the {MAX_SHAFTS} supported")

    use_liftplan = len(rows) > MAX_TREADLES
    draft = Draft(ends=ends, picks=picks, shafts=max(1, len(columns)),
                  treadles=1 if use_liftplan else max(1, len(rows)), rising=rising)
    draft.threading[:] = column_ids
    # lift_of_shaft[s, p]: does pick p lift shaft s? = lifts at the shaft's representative end.
    for shaft, end in enumerate(columns):
        draft.liftplan[:, shaft] = lifts[:, end]
    if use_liftplan:
        draft.liftplan_mode = True
    else:
        for treadle, pick in enumerate(rows):
            draft.tieup[treadle, :len(columns)] = lifts[pick, columns]
        has_treadle = row_ids != UNTHREADED
        draft.treadling[np.flatnonzero(has_treadle), row_ids[has_treadle]] = True
    return draft


def _group(vectors: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Number the distinct non-empty rows of ``vectors`` by first appearance.

    Returns ``(ids, representatives)``: ``ids[i]`` is the group of row ``i`` (UNTHREADED, i.e. -1,
    for an all-False row, which needs no shaft or treadle) and ``representatives[g]`` is the index
    of the first row in group ``g``.
    """
    ids = np.full(vectors.shape[0], UNTHREADED, dtype=np.int16)
    seen: dict[bytes, int] = {}
    reps: list[int] = []
    for index in range(vectors.shape[0]):
        row = vectors[index]
        if not row.any():
            continue
        key = row.tobytes()
        if key not in seen:
            seen[key] = len(reps)
            reps.append(index)
        ids[index] = seen[key]
    return ids, reps


def minimise(draft: Draft) -> Draft:
    """The smallest draft with the same cloth as ``draft``, keeping its palette, thread colours and
    shed. Shafts and treadles are renumbered in order of first use."""
    out = draft_from_drawdown(draft.drawdown(), rising=draft.rising)
    if draft.liftplan_mode:
        out.liftplan_mode = True        # stay in liftplan mode; only the shafts are reduced
    out.palette = list(draft.palette)
    out.warp_colors = draft.warp_colors.copy()
    out.weft_colors = draft.weft_colors.copy()
    return out
