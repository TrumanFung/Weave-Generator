"""PNG export of a whole draft (threading, tie-up, treadling, drawdown and rulers)."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont  # type: ignore

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import render_panels

LABEL_COLOR = "#b45a5a"


def render_draft_image(draft: Draft, warp_color: str, weft_color: str, cell: int = 12) -> Image.Image:
    layout = DraftLayout.build(draft, cell)
    img = Image.new("RGB", (int(layout.width), int(layout.height)), "white")
    grids = {
        "threading": layout.threading,
        "tieup": layout.tieup,
        "treadling": layout.treadling,
        "liftplan": layout.treadling,
        "drawdown": layout.drawdown,
    }
    for name, pixels in render_panels(draft, cell, warp_color, weft_color).items():
        grid = grids[name]
        img.paste(Image.fromarray(pixels), (int(grid.x), int(grid.y)))

    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for label in layout.labels():
        left, top, right, bottom = draw.textbbox((0, 0), label.text, font=font)
        w, h = right - left, bottom - top
        if label.anchor == "s":
            xy = (label.x - w / 2 - left, label.y - h - top)
        else:
            xy = (label.x - left, label.y - h / 2 - top)
        draw.text(xy, label.text, fill=LABEL_COLOR, font=font)
    return img
