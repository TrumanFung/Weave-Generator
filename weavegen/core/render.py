"""Turn a draft into RGB pixel arrays, one per panel. NumPy only, so the UI and PNG export share it.

Panels are rendered in *display* orientation (ends right-to-left, shafts bottom-to-top),
matching ``weavegen.core.layout``.
"""

from __future__ import annotations

import numpy as np

from weavegen.core.colors import hex_to_rgb, palette_rgb  # noqa: F401  (hex_to_rgb re-exported)
from weavegen.core.draft import Draft

INK = (0, 0, 0)
PAPER = (255, 255, 255)
LINE = (190, 190, 190)


def display_arrays(draft: Draft) -> dict[str, np.ndarray]:
    """Each visible bool panel (everything but the colours) as a (rows, cols) array in display
    orientation, with the drawdown as warp-on-top = True.

    In liftplan mode the tie-up is hidden (as in the layout) and the liftplan replaces the treadling.
    """
    threaded = draft.threading[None, :] == np.arange(draft.shafts)[:, None]  # (shafts, ends)
    arrays = {
        "threading": threaded[::-1, ::-1],
        "drawdown": draft.drawdown()[:, ::-1],
    }
    if draft.liftplan_mode:
        arrays["liftplan"] = draft.liftplan
    else:
        arrays["tieup"] = draft.tieup.T[::-1, :]
        arrays["treadling"] = draft.treadling
    return arrays


def scale_cells(small: np.ndarray, cell: int, line: tuple[int, int, int] = LINE) -> np.ndarray:
    """Scale a (rows, cols, 3) colour array up to ``cell`` px per cell, adding grid lines when
    cells are big enough to show them."""
    out = small.repeat(cell, axis=0).repeat(cell, axis=1)
    if cell >= 4:
        out[::cell, :] = line
        out[:, ::cell] = line
        out[-1, :] = line
        out[:, -1] = line
    return out


def panel_rgb(states: np.ndarray, cell: int,
              on: tuple[int, int, int], off: tuple[int, int, int],
              line: tuple[int, int, int] = LINE) -> np.ndarray:
    """Scale a bool array up to ``cell`` px per cell, coloured ``on`` / ``off``."""
    # Colour the small per-cell array first, then scale it up: far cheaper than colouring pixels.
    small = np.where(states[..., None], np.array(on, dtype=np.uint8), np.array(off, dtype=np.uint8))
    return scale_cells(small, cell, line)


def drawdown_colors(draft: Draft) -> np.ndarray:
    """The drawdown as a (picks, ends, 3) colour array in display orientation. Where a warp end
    is on top the cell takes that end's colour; otherwise it takes the pick's weft colour."""
    palette = palette_rgb(draft)
    warp = palette[draft.warp_colors]   # (ends, 3)
    weft = palette[draft.weft_colors]   # (picks, 3)
    up = draft.drawdown()
    small = np.where(up[..., None], warp[None, :, :], weft[:, None, :])
    return small[:, ::-1]


def warp_strip(draft: Draft) -> np.ndarray:
    """The warp colours as a (1, ends, 3) array, end 1 at the right."""
    return palette_rgb(draft)[draft.warp_colors][None, ::-1, :]


def weft_strip(draft: Draft) -> np.ndarray:
    """The weft colours as a (picks, 1, 3) array, pick 1 at the top."""
    return palette_rgb(draft)[draft.weft_colors][:, None, :]


FLOAT_TINT = (225, 29, 72)   # the colour long floats are shaded with
FLOAT_STRENGTH = 0.55        # how much of the tint is mixed in (0 to 1)


def tint_cells(pixels: np.ndarray, mask: np.ndarray, cell: int, tint: tuple[int, int, int] = FLOAT_TINT,
               strength: float = FLOAT_STRENGTH) -> np.ndarray:
    """Shade the cells where ``mask`` ((rows, cols), display orientation) is True by mixing in ``tint``.
    ``pixels`` is the panel scaled to ``cell`` px per cell; the grid lines stay as they are."""
    big = mask.repeat(cell, axis=0).repeat(cell, axis=1)
    if cell >= 4:
        big[::cell, :] = False
        big[:, ::cell] = False
    out = pixels.copy()
    mixed = pixels[big].astype(np.float32) * (1 - strength) + np.array(tint, dtype=np.float32) * strength
    out[big] = mixed.astype(np.uint8)
    return out


def render_panels(draft: Draft, cell: int, cloth_thickness: float | None = None,
                  highlight: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """RGB array per visible panel, including the warp and weft colour strips.

    The drawdown shows each thread in its own colour. With ``cloth_thickness`` (0 to 1) it is
    drawn as woven yarn instead of flat squares, see ``weavegen.core.cloth``. ``highlight`` is an
    optional ``(picks, ends)`` bool array in draft coordinates (see ``analysis.float_mask``) whose
    True cells are shaded on the drawdown.
    """
    panels = {}
    for name, states in display_arrays(draft).items():
        if name != "drawdown":
            panels[name] = panel_rgb(states, cell, INK, PAPER)
    if cloth_thickness is None:
        panels["drawdown"] = scale_cells(drawdown_colors(draft), cell)
    else:
        from weavegen.core.cloth import render_cloth
        panels["drawdown"] = render_cloth(draft, cell, cloth_thickness)
    if highlight is not None:
        if highlight.shape != (draft.picks, draft.ends):
            raise ValueError(f"highlight must be {draft.picks} x {draft.ends}, got {highlight.shape}")
        panels["drawdown"] = tint_cells(panels["drawdown"], highlight[:, ::-1], cell)
    panels["warp"] = scale_cells(warp_strip(draft), cell)
    panels["weft"] = scale_cells(weft_strip(draft), cell)
    return panels
