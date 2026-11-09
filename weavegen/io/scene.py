"""A resolution-independent picture of a draft: filled rectangles, grid lines and number labels.

SVG and PDF export both draw from this one description, so they always agree with each other and
with the on-screen layout (``weavegen.core.layout``). Units are layout pixels at ``cell`` per
square; each writer scales them to its own page. The drawdown is the flat colour-and-weave
drawdown (the shaded cloth view is a raster effect and only exists in PNG export).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import INK, LINE, PAPER, display_arrays, drawdown_colors, warp_strip, weft_strip

Color = tuple[int, int, int]

FONT_SIZE = 8.0          # label height in scene units, at the default cell size
LABEL_RGB: Color = (180, 90, 90)
DEFAULT_CELL = 12


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    anchor: str  # "s": centred above (x, y); "w": starts at x, centred on y


@dataclass
class Scene:
    width: float
    height: float
    font_size: float
    rects: dict[Color, list[tuple[float, float, float, float]]] = field(default_factory=dict)
    lines: list[tuple[float, float, float, float]] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    caption: str = ""


def _runs(small: np.ndarray):
    """Yield ``(row, first_col, length, colour)`` for each horizontal run of one colour, skipping
    white (the page is already white)."""
    rows, cols, _ = small.shape
    for row in range(rows):
        values = small[row]
        change = np.flatnonzero((values[1:] != values[:-1]).any(axis=1)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [cols]))
        for start, end in zip(starts, ends):
            color = tuple(int(v) for v in values[start])
            if color != PAPER:
                yield row, int(start), int(end - start), color


def describe(draft: Draft) -> str:
    """A one-line description printed with the draft."""
    shed = "rising" if draft.rising else "sinking"
    side = f"{draft.shafts} shafts" + ("" if draft.liftplan_mode else f", {draft.treadles} treadles")
    return f"{draft.ends} ends x {draft.picks} picks, {side}, {shed} shed"


def build_scene(draft: Draft, cell: int = DEFAULT_CELL) -> Scene:
    layout = DraftLayout.build(draft, cell)
    scene = Scene(layout.width, layout.height, FONT_SIZE * cell / DEFAULT_CELL, caption=describe(draft))

    panels: dict[str, np.ndarray] = {}
    for name, states in display_arrays(draft).items():
        if name != "drawdown":
            panels[name] = np.where(states[..., None], np.array(INK, np.uint8), np.array(PAPER, np.uint8))
    panels["drawdown"] = drawdown_colors(draft)
    panels["warp"] = warp_strip(draft)
    panels["weft"] = weft_strip(draft)

    for name, small in panels.items():
        grid = layout.grid(name)
        for row, col, length, color in _runs(np.ascontiguousarray(small)):
            scene.rects.setdefault(color, []).append(
                (grid.x + col * cell, grid.y + row * cell, length * cell, cell))
        for r in range(grid.rows + 1):  # grid lines, drawn over the fills
            scene.lines.append((grid.x, grid.y + r * cell, grid.right, grid.y + r * cell))
        for c in range(grid.cols + 1):
            scene.lines.append((grid.x + c * cell, grid.y, grid.x + c * cell, grid.bottom))

    scene.texts = [Text(l.x, l.y, l.text, l.anchor) for l in layout.labels()]
    return scene

