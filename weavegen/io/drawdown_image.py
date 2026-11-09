"""Read a picture of a drawdown: one pixel per cell, dark pixels where the warp is on top."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError  # type: ignore

from weavegen.core.draft import MAX_ENDS, MAX_PICKS


class ImageImportError(ValueError):
    """The image cannot be used as a drawdown. The message says why."""


def drawdown_from_image(path: str | Path, threshold: int = 128) -> np.ndarray:
    """Load an image as a ``(picks, ends)`` bool drawdown, in draft coordinates.

    Each pixel is one cell and the picture is read the way the drawdown is drawn on screen: the top
    row is pick 1 and the left column is the highest-numbered end. Pixels darker than ``threshold``
    (0 to 255, measured as grey) are cells where the warp is on top. Transparent pixels count as
    white. Images larger than 400 x 400 are refused rather than resampled, because shrinking them
    would blur cells together.
    """
    if not 0 <= threshold <= 255:
        raise ImageImportError(f"the threshold must be between 0 and 255, got {threshold}")
    try:
        with Image.open(path) as opened:
            opened.load()
            image = opened.convert("RGBA")
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageImportError(f"{Path(path).name} is not an image this program can read ({exc})") from None
    width, height = image.size
    if width > MAX_ENDS or height > MAX_PICKS:
        raise ImageImportError(f"the image is {width} x {height} pixels; at most {MAX_ENDS} x {MAX_PICKS} "
                               "are supported. Shrink it so that one pixel is one cell.")
    flat = Image.new("RGBA", image.size, (255, 255, 255, 255))
    flat.alpha_composite(image)                       # transparent pixels become white
    grey = np.asarray(flat.convert("L"))
    return (grey < threshold)[:, ::-1]                # the left column of the picture is the last end
