"""Editing operations on one panel of a draft. No UI imports.

Every operation works on a copy of the panel's matrix (``Draft.matrix``) and writes it back with
``Draft.set_matrix``, so it either applies completely or raises without changing the draft.
Mutating operations return True when the draft changed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from weavegen.core.draft import Draft
from weavegen.core.selection import Rect


@dataclass(frozen=True)
class Clipboard:
    panel: str
    data: np.ndarray  # 2-D bool, in the panel's matrix orientation


def _checked(draft: Draft, panel: str, rect: Rect) -> np.ndarray:
    matrix = draft.matrix(panel)
    if not rect.fits(matrix.shape):
        raise ValueError(f"the selection is outside the {panel} panel")
    return matrix


def copy(draft: Draft, panel: str, rect: Rect) -> Clipboard:
    matrix = _checked(draft, panel, rect)
    return Clipboard(panel, matrix[rect.rows, rect.cols].copy())


def clear(draft: Draft, panel: str, rect: Rect) -> bool:
    matrix = _checked(draft, panel, rect)
    matrix[rect.rows, rect.cols] = False
    return draft.set_matrix(panel, matrix)


def paste(draft: Draft, clip: Clipboard, panel: str, row: int, col: int) -> bool:
    """Paste with the clipboard's top-left at (row, col), clipped to the panel.

    The pasted block replaces what was there, empty cells included. In the threading each pasted
    end is replaced entirely, since an end can only sit on one shaft.
    """
    if clip.panel != panel:
        raise ValueError(f"cannot paste {clip.panel} cells into the {panel} panel")
    matrix = draft.matrix(panel)
    rows, cols = matrix.shape
    if not (0 <= row < rows and 0 <= col < cols):
        raise IndexError(f"paste position ({row}, {col}) is outside the {panel} panel")
    h = min(clip.data.shape[0], rows - row)
    w = min(clip.data.shape[1], cols - col)
    if panel == "threading":
        matrix[row:row + h, :] = False
    matrix[row:row + h, col:col + w] = clip.data[:h, :w]
    return draft.set_matrix(panel, matrix)


def flip(draft: Draft, panel: str, rect: Rect, axis: str) -> bool:
    """Mirror the selection along ``axis`` ("rows" reverses row order, "cols" reverses columns)."""
    if axis not in ("rows", "cols"):
        raise ValueError("axis must be 'rows' or 'cols'")
    matrix = _checked(draft, panel, rect)
    block = matrix[rect.rows, rect.cols]
    matrix[rect.rows, rect.cols] = block[::-1, :] if axis == "rows" else block[:, ::-1]
    return draft.set_matrix(panel, matrix)


def rotate(draft: Draft, panel: str, rect: Rect, turns: int = 1) -> bool:
    """Rotate a square selection by ``turns`` quarter turns (anticlockwise in matrix orientation)."""
    if panel == "threading":
        raise ValueError("the threading cannot be rotated: each end sits on one shaft")
    if rect.height != rect.width:
        raise ValueError("only a square selection can be rotated")
    matrix = _checked(draft, panel, rect)
    matrix[rect.rows, rect.cols] = np.rot90(matrix[rect.rows, rect.cols], turns)
    return draft.set_matrix(panel, matrix)


def repeat(draft: Draft, panel: str, rect: Rect) -> bool:
    """Tile the selected rows (their full width) from the selection toward the last row.

    For the threading these are ends, for the treadling and liftplan picks.
    """
    matrix = _checked(draft, panel, rect)
    block = matrix[rect.r0:rect.r1 + 1, :].copy()
    height = block.shape[0]
    for start in range(rect.r0 + height, matrix.shape[0], height):
        stop = min(start + height, matrix.shape[0])
        matrix[start:stop, :] = block[:stop - start, :]
    return draft.set_matrix(panel, matrix)


def wrap(draft: Draft, panel: str, drow: int, dcol: int) -> bool:
    """Shift the whole panel by (drow, dcol) matrix cells, wrapping around the edges."""
    matrix = draft.matrix(panel)
    return draft.set_matrix(panel, np.roll(matrix, shift=(drow, dcol), axis=(0, 1)))


def invert(draft: Draft, panel: str, rect: Rect | None = None) -> bool:
    """Flip every cell in the selection (or the whole panel) between set and empty."""
    if panel == "threading":
        raise ValueError("the threading cannot be inverted: each end sits on one shaft")
    matrix = draft.matrix(panel)
    if rect is None:
        rect = Rect(0, matrix.shape[0] - 1, 0, matrix.shape[1] - 1)
    matrix = _checked(draft, panel, rect)
    matrix[rect.rows, rect.cols] = ~matrix[rect.rows, rect.cols]
    return draft.set_matrix(panel, matrix)


def line_cells(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells on the straight line between two (row, col) cells, inclusive (Bresenham)."""
    (r0, c0), (r1, c1) = start, end
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    step_r = 1 if r1 > r0 else -1
    step_c = 1 if c1 > c0 else -1
    cells = []
    err = dc - dr
    r, c = r0, c0
    while True:
        cells.append((r, c))
        if (r, c) == (r1, c1):
            return cells
        doubled = 2 * err
        if doubled > -dr:
            err -= dr
            c += step_c
        if doubled < dc:
            err += dc
            r += step_r


def draw_line(draft: Draft, panel: str, start: tuple[int, int], end: tuple[int, int],
              paint: bool) -> bool:
    """Set (``paint``) or clear the cells on a straight line from ``start`` to ``end``.

    In the threading the line runs end by end: each end it crosses is threaded on the shaft the
    line passes through there (or unthreaded when clearing).
    """
    matrix = draft.matrix(panel)
    rows, cols = matrix.shape
    for r, c in (start, end):
        if not (0 <= r < rows and 0 <= c < cols):
            raise IndexError(f"({r}, {c}) is outside the {panel} panel")

    (r0, c0), (r1, c1) = start, end
    if panel == "threading":
        steps = abs(r1 - r0)
        direction = 1 if r1 >= r0 else -1
        for i in range(steps + 1):
            t = i / steps if steps else 1.0
            end_index = r0 + direction * i
            shaft = int(math.floor(c0 + t * (c1 - c0) + 0.5))
            matrix[end_index, :] = False
            if paint:
                matrix[end_index, shaft] = True
    else:
        for r, c in line_cells(start, end):
            matrix[r, c] = paint
    return draft.set_matrix(panel, matrix)
