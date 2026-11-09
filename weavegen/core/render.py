"""Turn a draft into RGB pixel arrays, one per panel. NumPy only, so the UI and PNG export share it.

Panels are rendered in *display* orientation (ends right-to-left, shafts bottom-to-top),
matching ``weavegen.core.layout``.
"""

from __future__ import annotations

import numpy as np

from weavegen.core.draft import Draft

INK = (0, 0, 0)
PAPER = (255, 255, 255)
LINE = (190, 190, 190)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"expected a #rrggbb color, got {color!r}")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def display_arrays(draft: Draft) -> dict[str, np.ndarray]:
    """Each visible panel as a (rows, cols) bool array in display orientation.

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


def panel_rgb(states: np.ndarray, cell: int,
              on: tuple[int, int, int], off: tuple[int, int, int],
              line: tuple[int, int, int] = LINE) -> np.ndarray:
    """Scale a bool array up to ``cell`` px per cell, with grid lines when cells are big enough."""
    # Colour the small per-cell array first, then scale it up: far cheaper than colouring pixels.
    small = np.where(states[..., None], np.array(on, dtype=np.uint8), np.array(off, dtype=np.uint8))
    out = small.repeat(cell, axis=0).repeat(cell, axis=1)
    if cell >= 4:
        out[::cell, :] = line
        out[:, ::cell] = line
        out[-1, :] = line
        out[:, -1] = line
    return out


def render_panels(draft: Draft, cell: int, warp_color: str, weft_color: str) -> dict[str, np.ndarray]:
    """RGB array per panel. In the drawdown, warp-on-top cells use ``warp_color``."""
    warp, weft = hex_to_rgb(warp_color), hex_to_rgb(weft_color)
    out = {}
    for name, states in display_arrays(draft).items():
        if name == "drawdown":
            out[name] = panel_rgb(states, cell, on=warp, off=weft)
        else:
            out[name] = panel_rgb(states, cell, on=INK, off=PAPER)
    return out
