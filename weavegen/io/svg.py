"""SVG export: the draft as vector graphics that scale to any size."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from weavegen.core.draft import Draft
from weavegen.io.scene import LABEL_RGB, LINE, Color, build_scene


def _hex(color: Color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def draft_to_svg(draft: Draft, cell: int = 12) -> str:
    """The whole draft (colour strips, threading, tie-up, treadling, drawdown, numbers) as SVG text."""
    scene = build_scene(draft, cell)
    width, height = _num(scene.width), _num(scene.height)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f"<title>{escape(scene.caption)}</title>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]
    for color, rects in scene.rects.items():
        path = "".join(f"M{_num(x)} {_num(y)}h{_num(w)}v{_num(h)}h{_num(-w)}z" for x, y, w, h in rects)
        out.append(f'<path fill="{_hex(color)}" shape-rendering="crispEdges" d="{path}"/>')
    lines = "".join(f"M{_num(a)} {_num(b)}L{_num(c)} {_num(d)}" for a, b, c, d in scene.lines)
    out.append(f'<path fill="none" stroke="{_hex(LINE)}" stroke-width="1" '
               f'shape-rendering="crispEdges" d="{lines}"/>')
    out.append(f'<g font-family="Helvetica, Arial, sans-serif" font-size="{_num(scene.font_size)}" '
               f'fill="{_hex(LABEL_RGB)}">')
    for t in scene.texts:
        if t.anchor == "s":
            out.append(f'<text x="{_num(t.x)}" y="{_num(t.y)}" text-anchor="middle">{escape(t.text)}</text>')
        else:
            out.append(f'<text x="{_num(t.x)}" y="{_num(t.y + scene.font_size * 0.35)}">{escape(t.text)}</text>')
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def save_svg(draft: Draft, path: str | Path, cell: int = 12) -> None:
    Path(path).write_text(draft_to_svg(draft, cell), encoding="utf-8")
