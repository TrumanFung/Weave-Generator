"""PNG export of a whole draft (colour strips, threading, tie-up, treadling, drawdown and rulers)."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont  # type: ignore

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import render_panels

LABEL_COLOR = "#b45a5a"


def render_draft_image(draft: Draft, cell: int = 12, cloth_thickness: float | None = None) -> Image.Image:
    """Render every panel with the draft's own thread colours. With ``cloth_thickness`` the
    drawdown is drawn as woven yarn instead of flat squares."""
    layout = DraftLayout.build(draft, cell)
    img = Image.new("RGB", (int(layout.width), int(layout.height)), "white")
    for name, pixels in render_panels(draft, cell, cloth_thickness).items():
        grid = layout.grid(name)
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
