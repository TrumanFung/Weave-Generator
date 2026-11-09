"""Colour helpers shared by the flat and cloth renderers."""

from __future__ import annotations

import numpy as np

from weavegen.core.draft import Draft


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) != 6:
        raise ValueError(f"expected a #rrggbb color, got {color!r}")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def palette_rgb(draft: Draft) -> np.ndarray:
    """The draft's palette as an (n, 3) uint8 array, indexable by thread colour numbers."""
    return np.array([hex_to_rgb(c) for c in draft.palette], dtype=np.uint8)
