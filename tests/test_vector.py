"""SVG and PDF export, checked against the same renderer the screen uses."""

import re
import xml.etree.ElementTree as ET
import zlib

import numpy as np
import pytest

from weavegen.core import patterns
from weavegen.core.draft import MAX_ENDS, MAX_PICKS, Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import display_arrays, drawdown_colors, warp_strip, weft_strip
from weavegen.io import pdf, svg
from weavegen.io.scene import DEFAULT_CELL, build_scene


def coloured_draft() -> Draft:
    d = patterns.build_preset("diamond", 12, 10)
    d.add_palette_color("#c0392b")
    d.add_palette_color("#f1c40f")
    patterns.apply_stripes(d, "warp", patterns.parse_stripes("1:3, 3:2, 4:1", 4))
    patterns.apply_stripes(d, "weft", patterns.parse_stripes("2:2, 3:1", 4))
    return d


def colour_at(rects, x, y):
    """The fill colour covering a point (white when nothing does)."""
    for color, boxes in rects.items():
        for bx, by, bw, bh in boxes:
            if bx <= x < bx + bw and by <= y < by + bh:
                return color
    return (255, 255, 255)


def expected_panels(draft):
    out = {name: np.where(a[..., None], 0, 255).astype(np.uint8).repeat(3, axis=2)
           for name, a in display_arrays(draft).items() if name != "drawdown"}
    out["drawdown"], out["warp"], out["weft"] = drawdown_colors(draft), warp_strip(draft), weft_strip(draft)
    return out


# ---- the scene both formats draw from ----

@pytest.mark.parametrize("liftplan", [False, True])
def test_every_cell_of_every_panel_has_the_colour_the_screen_renderer_gives_it(liftplan):
    d = coloured_draft()
    d.set_liftplan_mode(liftplan)
    scene = build_scene(d)
    layout = DraftLayout.build(d, DEFAULT_CELL)
    for name, small in expected_panels(d).items():
        grid = layout.grid(name)
        for r in range(grid.rows):
            for c in range(grid.cols):
                x, y = grid.x + (c + 0.5) * DEFAULT_CELL, grid.y + (r + 0.5) * DEFAULT_CELL
                assert colour_at(scene.rects, x, y) == tuple(int(v) for v in small[r, c]), (name, r, c)


def test_the_scene_is_the_size_of_the_screen_layout_and_white_is_not_drawn():
    d = coloured_draft()
    scene = build_scene(d, cell=10)
    layout = DraftLayout.build(d, 10)
    assert (scene.width, scene.height) == (layout.width, layout.height)
    assert (255, 255, 255) not in scene.rects


def test_adjacent_cells_of_one_colour_are_merged_into_one_rectangle():
    d = Draft(ends=8, picks=1)
    scene = build_scene(d)
    warp = [r for r in scene.rects[(31, 41, 55)] if r[1] < 20]   # the warp strip: 8 ends, one colour
    assert warp == [(6, 4, 8 * DEFAULT_CELL, DEFAULT_CELL)]


def test_labels_match_the_layout():
    d = coloured_draft()
    scene = build_scene(d)
    layout = DraftLayout.build(d, DEFAULT_CELL)
    assert [(t.text, t.anchor) for t in scene.texts] == [(l.text, l.anchor) for l in layout.labels()]


def test_the_tieup_is_absent_in_liftplan_mode():
    d = Draft.twill_2_2()
    flat = build_scene(d)
    d.set_liftplan_mode(True)
    assert len(build_scene(d).lines) != len(flat.lines)
    assert "one" not in build_scene(d).caption and "treadles" not in build_scene(d).caption


def test_the_caption_describes_the_draft():
    assert build_scene(Draft.twill_2_2()).caption == "16 ends x 16 picks, 4 shafts, 4 treadles, rising shed"
    assert build_scene(Draft(rising=False)).caption.endswith("sinking shed")


# ---- SVG ----

SVG_NS = {"s": "http://www.w3.org/2000/svg"}


def test_the_svg_is_well_formed_and_sized_like_the_layout():
    d = coloured_draft()
    root = ET.fromstring(svg.draft_to_svg(d))
    layout = DraftLayout.build(d, DEFAULT_CELL)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert float(root.get("width")) == layout.width and float(root.get("height")) == layout.height
    assert root.get("viewBox") == f"0 0 {layout.width:g} {layout.height:g}"
    assert root.find("s:title", SVG_NS).text == build_scene(d).caption


def test_the_svg_uses_every_thread_colour_and_one_label_per_number():
    d = coloured_draft()
    root = ET.fromstring(svg.draft_to_svg(d))
    fills = {p.get("fill") for p in root.findall("s:path", SVG_NS)}
    assert {"#c0392b", "#f1c40f", "#1f2937", "#000000"} <= fills
    assert len(root.findall(".//s:text", SVG_NS)) == len(DraftLayout.build(d, DEFAULT_CELL).labels())


def test_svg_rectangles_reproduce_the_scene():
    d = coloured_draft()
    root = ET.fromstring(svg.draft_to_svg(d))
    rects = {}
    for p in root.findall("s:path", SVG_NS):
        if p.get("stroke"):
            continue
        color = tuple(int(p.get("fill")[i:i + 2], 16) for i in (1, 3, 5))
        for m in re.finditer(r"M([\d.]+) ([\d.]+)h([\d.]+)v([\d.]+)", p.get("d")):
            x, y, w, h = map(float, m.groups())
            rects.setdefault(color, []).append((x, y, w, h))
    scene = build_scene(d)
    assert {k: sorted(v) for k, v in rects.items()} == {k: sorted(v) for k, v in scene.rects.items()}


def test_save_svg_writes_a_utf8_file(tmp_path):
    path = tmp_path / "draft.svg"
    svg.save_svg(Draft.twill_2_2(), path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<?xml") and text.rstrip().endswith("</svg>")


def test_the_largest_draft_exports_to_a_reasonable_svg():
    d = Draft.twill_2_2(ends=MAX_ENDS, picks=MAX_PICKS)
    text = svg.draft_to_svg(d)
    ET.fromstring(text)
    assert len(text) < 5_000_000


# ---- PDF ----

def parse_pdf(data: bytes):
    """Check the file's structure and return (media_box, content_stream_text)."""
    assert data.startswith(b"%PDF-1.4\n") and data.rstrip().endswith(b"%%EOF")
    startxref = int(re.search(rb"startxref\n(\d+)\n%%EOF", data).group(1))
    assert data[startxref:startxref + 4] == b"xref"
    count = int(re.match(rb"xref\n0 (\d+)\n", data[startxref:]).group(1))
    entries = data[startxref:].split(b"\n")[2:2 + count]
    assert entries[0] == b"0000000000 65535 f " and all(len(e) == 19 for e in entries)  # + "\n" = 20 bytes
    for number, entry in enumerate(entries[1:], start=1):
        offset = int(entry[:10])
        assert data[offset:].startswith(b"%d 0 obj\n" % number), f"object {number} is not at its offset"
    assert b"/Size %d" % count in data and b"/Root 1 0 R" in data
    box = [float(v) for v in re.search(rb"/MediaBox \[([^\]]+)\]", data).group(1).split()]
    length = int(re.search(rb"/Length (\d+)", data).group(1))
    start = data.index(b"stream\n") + len(b"stream\n")
    assert data[start + length:start + length + 10].startswith(b"\nendstream")
    return box, zlib.decompress(data[start:start + length]).decode("ascii")


def pdf_rects(content: str):
    """Filled rectangles by colour, ignoring everything else in the content stream."""
    rects, color = {}, None
    for line in content.splitlines():
        if line.endswith(" rg") and not line.startswith("BT"):
            color = tuple(round(float(v) * 255) for v in line.split()[:3])
        elif line.endswith(" re"):
            rects.setdefault(color, []).append(tuple(float(v) for v in line.split()[:4]))
    return rects


def test_the_pdf_has_valid_structure_and_a_standard_page():
    box, content = parse_pdf(pdf.draft_to_pdf(Draft.twill_2_2(picks=60), "a4"))
    assert box[:2] == [0, 0] and (box[2], box[3]) == pytest.approx((595.28, 841.89))
    assert "Helvetica" in pdf.draft_to_pdf(Draft.twill_2_2()).decode("latin-1")
    assert "(16 ends x 60 picks, 4 shafts, 4 treadles, rising shed) Tj" in content


def test_letter_paper_is_supported_and_unknown_paper_is_refused():
    box, _ = parse_pdf(pdf.draft_to_pdf(Draft.twill_2_2(picks=60), "Letter"))
    assert box[2:] == [612, 792]
    with pytest.raises(ValueError, match="page must be one of"):
        pdf.draft_to_pdf(Draft.twill_2_2(), "tabloid")


def test_the_page_is_turned_whichever_way_lets_the_draft_print_larger():
    wide = parse_pdf(pdf.draft_to_pdf(Draft.twill_2_2(ends=200, picks=20), "a4"))[0]
    tall = parse_pdf(pdf.draft_to_pdf(Draft.twill_2_2(ends=20, picks=200), "a4"))[0]
    assert wide[2] > wide[3] and tall[2] < tall[3]


def test_the_pdf_draws_the_same_colours_in_the_same_places_as_the_scene():
    d = coloured_draft()
    box, content = parse_pdf(pdf.draft_to_pdf(d, "a4"))
    scene = build_scene(d)
    page_w, page_h, scale, left, top = pdf.placement(scene, "a4")
    assert (page_w, page_h) == (box[2], box[3])
    drawn = pdf_rects(content)
    for color, boxes in scene.rects.items():
        expected = sorted((round(left + x * scale, 2), round(page_h - (top + (y + h) * scale), 2),
                           round(w * scale, 2), round(h * scale, 2)) for x, y, w, h in boxes)
        assert sorted(drawn[color]) == pytest.approx(expected, abs=0.011), color


@pytest.mark.parametrize("size", [(1, 1), (16, 16), (400, 20), (20, 400), (400, 400)])
@pytest.mark.parametrize("paper", ["a4", "letter"])
def test_the_drawing_stays_inside_the_margins_and_is_never_stretched(size, paper):
    d = Draft.twill_2_2(ends=size[0], picks=size[1])
    scene = build_scene(d)
    page_w, page_h, scale, left, top = pdf.placement(scene, paper)
    assert scale <= pdf.MAX_SCALE
    assert left >= pdf.MARGIN - 1e-6 and left + scene.width * scale <= page_w - pdf.MARGIN + 1e-6
    assert top + scene.height * scale <= page_h - pdf.MARGIN + 1e-6
    _, content = parse_pdf(pdf.draft_to_pdf(d, paper))
    for rects in pdf_rects(content).values():
        for x, y, w, h in rects:
            assert -1e-6 <= x and x + w <= page_w + 1e-6 and -1e-6 <= y and y + h <= page_h + 1e-6


def test_a_small_draft_is_not_blown_up_beyond_the_scale_cap():
    assert pdf.placement(build_scene(Draft(ends=1, picks=1)), "a4")[2] == pdf.MAX_SCALE


def test_the_pdf_of_the_largest_draft_is_compact():
    data = pdf.draft_to_pdf(Draft.twill_2_2(ends=MAX_ENDS, picks=MAX_PICKS))
    parse_pdf(data)
    assert len(data) < 3_000_000


def test_save_pdf_writes_the_file(tmp_path):
    path = tmp_path / "draft.pdf"
    pdf.save_pdf(coloured_draft(), path, "letter")
    parse_pdf(path.read_bytes())
