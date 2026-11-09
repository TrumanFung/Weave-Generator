"""PDF export: the draft as vector graphics on a single page, ready to print.

The file is written directly (no extra library): one page, one content stream, the standard
Helvetica font for the numbers. The page is A4 or US Letter, turned to landscape when that lets the
draft print larger, and the draft is scaled to fill the margins without being stretched.
"""

from __future__ import annotations

import zlib
from pathlib import Path

from weavegen.core.draft import Draft
from weavegen.io.scene import LABEL_RGB, LINE, Color, Scene, build_scene

PAGE_SIZES = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}  # portrait, in points
MARGIN = 36.0            # half an inch
CAPTION_SIZE = 10.0
MAX_SCALE = 2.0          # small drafts are not blown up beyond 2 points per layout pixel
_DIGIT_WIDTH = 0.556     # every Helvetica digit is 556/1000 em wide


def _num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _rgb(color: Color) -> str:
    """Colour components as 0-1 numbers; three decimals keep every 8-bit value distinct."""
    return " ".join(f"{c / 255:.3f}".rstrip("0").rstrip(".") or "0" for c in color)


def _text(value: str) -> str:
    """Escape a string for a PDF literal; the standard font only covers plain ASCII reliably."""
    ascii_only = value.encode("ascii", "replace").decode("ascii")
    return ascii_only.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_size(page: str, landscape: bool) -> tuple[float, float]:
    key = page.lower()
    if key not in PAGE_SIZES:
        raise ValueError(f"page must be one of {', '.join(sorted(PAGE_SIZES))}, got {page!r}")
    width, height = PAGE_SIZES[key]
    return (height, width) if landscape else (width, height)


def placement(scene: Scene, page: str) -> tuple[float, float, float, float, float]:
    """``(page_width, page_height, scale, left, top)``: the page in points, the points per scene unit,
    and where the scene's top-left corner lands (``top`` counted down from the top of the page)."""
    top = MARGIN + CAPTION_SIZE + 10
    best = None
    for landscape in (False, True):  # whichever turn of the page lets the draft be larger; portrait on a tie
        page_w, page_h = page_size(page, landscape)
        scale = min((page_w - 2 * MARGIN) / scene.width, (page_h - top - MARGIN) / scene.height, MAX_SCALE)
        if best is None or scale > best[2] + 1e-9:
            best = (page_w, page_h, scale)
    page_w, page_h, scale = best
    return page_w, page_h, scale, (page_w - scene.width * scale) / 2, top


def draft_to_pdf(draft: Draft, page: str = "a4") -> bytes:
    """The draft as a one-page PDF document."""
    scene = build_scene(draft)
    page_w, page_h, scale, left, top = placement(scene, page)

    def px(x: float) -> str:
        return _num(left + x * scale)

    def py(y: float) -> str:
        return _num(page_h - (top + y * scale))

    ops = [f"BT /F1 {_num(CAPTION_SIZE)} Tf 0 0 0 rg {_num(MARGIN)} {_num(page_h - MARGIN - CAPTION_SIZE)} Td "
           f"({_text(scene.caption)}) Tj ET"]
    for color, rects in scene.rects.items():
        ops.append(f"{_rgb(color)} rg")
        ops.extend(f"{px(x)} {_num(page_h - (top + (y + h) * scale))} {_num(w * scale)} {_num(h * scale)} re"
                   for x, y, w, h in rects)
        ops.append("f")
    ops.append(f"{_rgb(LINE)} RG 0.4 w")
    ops.extend(f"{px(a)} {py(b)} m {px(c)} {py(d)} l" for a, b, c, d in scene.lines)
    ops.append("S")

    size = scene.font_size * scale
    ops.append(f"{_rgb(LABEL_RGB)} rg")
    for t in scene.texts:
        if t.anchor == "s":
            x = left + t.x * scale - _DIGIT_WIDTH * size * len(t.text) / 2
            y = page_h - (top + t.y * scale)
        else:
            x = left + t.x * scale
            y = page_h - (top + t.y * scale) - size * 0.35
        ops.append(f"BT /F1 {_num(size)} Tf {_num(x)} {_num(y)} Td ({_text(t.text)}) Tj ET")

    stream = zlib.compress("\n".join(ops).encode("ascii"))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_num(page_w)} {_num(page_h)}] /Contents 4 0 R "
         "/Resources << /Font << /F1 5 0 R >> >> >>").encode("ascii"),
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        f"<< /Title ({_text(scene.caption)}) /Producer (Weave Generator) >>".encode("ascii"),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref))
    return bytes(out)


def save_pdf(draft: Draft, path: str | Path, page: str = "a4") -> None:
    Path(path).write_bytes(draft_to_pdf(draft, page))
