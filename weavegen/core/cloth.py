"""Cloth view: the drawdown drawn as woven yarn instead of flat squares.

Each cell shows the thread that is on top as a rounded yarn, lit along its middle and darker at
the edges, with the thread passing underneath visible but shadowed in the gaps beside it. Yarns
run the full length of their cell, so floats appear as continuous threads. ``thickness`` is the
fraction of the cell a yarn fills: 1.0 packs the threads edge to edge, smaller values leave
shadowed gaps that make the weave structure read more clearly.
"""

from __future__ import annotations

import numpy as np

from weavegen.core.colors import palette_rgb
from weavegen.core.draft import Draft

MIN_THICKNESS = 0.3
GAP_SHADE = 0.10        # brightness of the gap between yarns
OVER_BASE = 0.55        # brightness at the edge of a yarn on top
UNDER_BASE = 0.30       # brightness of a yarn passing underneath
UNDER_RANGE = 0.20
_CHUNK_PIXELS = 1_500_000


def _tile_maps(cell: int, thickness: float):
    """For one cell: (mask, scale) when the warp is on top and when the weft is on top.

    ``mask`` is True where the top thread shows (False where the under thread shows) and
    ``scale`` is the brightness multiplier for whichever thread is visible at that pixel.
    """
    position = (np.arange(cell) + 0.5) / cell * 2 - 1          # -1 .. 1 across the cell
    inside = np.abs(position) <= thickness
    height = np.zeros(cell)
    height[inside] = np.sqrt(1 - (position[inside] / thickness) ** 2)   # round cross-section

    over = OVER_BASE + (1 - OVER_BASE) * height                  # lit in the middle
    under = np.where(inside, UNDER_BASE + UNDER_RANGE * height, GAP_SHADE)

    # Warp on top: a vertical yarn varies across x; the weft under it is horizontal, varying across y.
    warp_mask = np.broadcast_to(inside[None, :], (cell, cell))
    warp_scale = np.where(warp_mask, over[None, :], under[:, None]).astype(np.float32)
    # Weft on top: a horizontal yarn varies across y; the warp under it is vertical, varying across x.
    weft_mask = np.broadcast_to(inside[:, None], (cell, cell))
    weft_scale = np.where(weft_mask, over[:, None], under[None, :]).astype(np.float32)
    return (warp_mask, warp_scale), (weft_mask, weft_scale)


def render_cloth(draft: Draft, cell: int, thickness: float = 0.85) -> np.ndarray:
    """The drawdown as a (picks*cell, ends*cell, 3) uint8 array in display orientation,
    the same size as the flat drawdown so the two views are interchangeable."""
    if cell < 1:
        raise ValueError("cell must be at least 1")
    thickness = max(MIN_THICKNESS, min(1.0, thickness))

    palette = palette_rgb(draft)
    warp = palette[draft.warp_colors][::-1]       # (ends, 3), end 1 at the right
    weft = palette[draft.weft_colors]             # (picks, 3)
    up = draft.drawdown()[:, ::-1]                # True where the warp is on top
    picks, ends = up.shape
    (warp_mask, warp_scale), (weft_mask, weft_scale) = _tile_maps(cell, thickness)

    out = np.empty((picks * cell, ends * cell, 3), dtype=np.uint8)
    step = max(1, _CHUNK_PIXELS // (ends * cell * cell))
    for p0 in range(0, picks, step):
        p1 = min(p0 + step, picks)
        n = p1 - p0
        up_cells = up[p0:p1]
        over = np.where(up_cells[..., None], warp[None, :, :], weft[p0:p1, None, :])
        under = np.where(up_cells[..., None], weft[p0:p1, None, :], warp[None, :, :])

        warp_on_top = up_cells.repeat(cell, axis=0).repeat(cell, axis=1)
        mask = np.where(warp_on_top, np.tile(warp_mask, (n, ends)), np.tile(weft_mask, (n, ends)))
        scale = np.where(warp_on_top, np.tile(warp_scale, (n, ends)), np.tile(weft_scale, (n, ends)))
        colour = np.where(mask[..., None],
                          over.repeat(cell, axis=0).repeat(cell, axis=1),
                          under.repeat(cell, axis=0).repeat(cell, axis=1))
        out[p0 * cell:p1 * cell] = (colour * scale[..., None]).astype(np.uint8)
    return out
