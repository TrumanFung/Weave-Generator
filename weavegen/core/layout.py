"""Geometry of the four-panel draft view, shared by on-screen drawing, hit-testing and export.

Standard handweaving layout::

    [ threading ] gap [ tie-up   ]
    [ drawdown  ] gap [ treadling]

Ends are numbered right to left and shafts bottom to top; picks run top to bottom and
treadles left to right. In liftplan mode the tie-up is hidden and the treadling area
becomes the liftplan (one column per shaft, shaft 1 at the left).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

from weavegen.core.draft import Draft

MARGIN_L = 6
MARGIN_T = 20
MARGIN_R = 36
MARGIN_B = 6
GAP = 22


@dataclass(frozen=True)
class Grid:
    """A rectangular block of square cells at a fixed position."""

    x: float
    y: float
    cell: float
    cols: int
    rows: int

    @property
    def width(self) -> float:
        return self.cols * self.cell

    @property
    def height(self) -> float:
        return self.rows * self.cell

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def pixel_to_cell(self, px: float, py: float) -> tuple[int, int] | None:
        """(row, col) of the display cell under a point, or None."""
        if px < self.x or px >= self.right or py < self.y or py >= self.bottom:
            return None
        col = int(math.floor((px - self.x) / self.cell))
        row = int(math.floor((py - self.y) / self.cell))
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return row, col
        return None


class Hit(NamedTuple):
    """A cell under the pointer, in draft coordinates (0-based).

    panel is one of: threading (a=end, b=shaft), tieup (a=treadle, b=shaft),
    treadling (a=pick, b=treadle), liftplan (a=pick, b=shaft), drawdown (a=pick, b=end).
    """

    panel: str
    a: int
    b: int


class Label(NamedTuple):
    x: float
    y: float
    text: str
    anchor: str  # "s": text sits above (x, y); "w": text starts right of (x, y), centered


def ruler_step(cell: float, steps: tuple[int, ...], min_px: float) -> int:
    """Smallest label interval whose spacing on screen is at least ``min_px``."""
    for step in steps:
        if step * cell >= min_px:
            return step
    return steps[-1]


@dataclass(frozen=True)
class DraftLayout:
    cell: int
    ends: int
    picks: int
    shafts: int
    treadles: int
    liftplan_mode: bool
    threading: Grid
    tieup: Grid
    treadling: Grid  # the liftplan grid when liftplan_mode
    drawdown: Grid
    width: float
    height: float

    @classmethod
    def build(cls, draft: Draft, cell: int) -> "DraftLayout":
        ends, picks = draft.ends, draft.picks
        shafts, treadles = draft.shafts, draft.treadles
        side_cols = shafts if draft.liftplan_mode else treadles

        thr = Grid(MARGIN_L, MARGIN_T, cell, ends, shafts)
        tie = Grid(thr.right + GAP, MARGIN_T, cell, treadles, shafts)
        draw = Grid(MARGIN_L, thr.bottom + GAP, cell, ends, picks)
        tread = Grid(tie.x, draw.y, cell, side_cols, picks)
        return cls(
            cell=cell, ends=ends, picks=picks, shafts=shafts, treadles=treadles,
            liftplan_mode=draft.liftplan_mode,
            threading=thr, tieup=tie, treadling=tread, drawdown=draw,
            width=tread.right + MARGIN_R,
            height=draw.bottom + MARGIN_B,
        )

    def grid(self, panel: str) -> Grid:
        """The grid a panel is drawn in ("liftplan" shares the treadling grid)."""
        grids = {
            "threading": self.threading,
            "tieup": self.tieup,
            "treadling": self.treadling,
            "liftplan": self.treadling,
            "drawdown": self.drawdown,
        }
        if panel not in grids:
            raise ValueError(f"unknown panel {panel!r}")
        return grids[panel]

    def hit(self, x: float, y: float) -> Hit | None:
        found = self.threading.pixel_to_cell(x, y)
        if found:
            row, col = found
            return Hit("threading", self.ends - 1 - col, self.shafts - 1 - row)

        if not self.liftplan_mode:
            found = self.tieup.pixel_to_cell(x, y)
            if found:
                row, col = found
                return Hit("tieup", col, self.shafts - 1 - row)

        found = self.treadling.pixel_to_cell(x, y)
        if found:
            row, col = found
            return Hit("liftplan" if self.liftplan_mode else "treadling", row, col)

        found = self.drawdown.pixel_to_cell(x, y)
        if found:
            row, col = found
            return Hit("drawdown", row, self.ends - 1 - col)
        return None

    def labels(self) -> list[Label]:
        c = self.cell
        long_step = ruler_step(c, (4, 8, 16, 32, 64), 36)
        short_step = ruler_step(c, (1, 2, 4, 8, 16, 32), 14)
        out: list[Label] = []

        thr, tie, tread, draw = self.threading, self.tieup, self.treadling, self.drawdown

        for col in range(self.ends):  # end numbers run right to left
            number = self.ends - col
            if number % long_step == 0:
                out.append(Label(thr.x + (col + 0.5) * c, thr.y - 3, str(number), "s"))

        for row in range(self.shafts):  # shaft numbers run bottom to top
            number = self.shafts - row
            if number % short_step == 0:
                out.append(Label(thr.right + 3, thr.y + (row + 0.5) * c, str(number), "w"))

        if self.liftplan_mode:
            for col in range(self.shafts):
                number = col + 1
                if number % short_step == 0:
                    out.append(Label(tread.x + (col + 0.5) * c, tread.y - 3, str(number), "s"))
        else:
            for col in range(self.treadles):
                number = col + 1
                if number % short_step == 0:
                    out.append(Label(tie.x + (col + 0.5) * c, tie.y - 3, str(number), "s"))

        for row in range(self.picks):
            number = row + 1
            if number % long_step == 0:
                out.append(Label(tread.right + 4, draw.y + (row + 0.5) * c, str(number), "w"))
        return out
