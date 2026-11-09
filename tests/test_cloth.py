import numpy as np
import pytest

from weavegen.core import cloth
from weavegen.core.cloth import GAP_SHADE, render_cloth
from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import drawdown_colors, render_panels, warp_strip, weft_strip
from weavegen.io.png import render_draft_image

WARP = "#c80000"   # (200, 0, 0)
WEFT = "#0000c8"   # (0, 0, 200)


def two_by_two(warp=WARP, weft=WEFT):
    """Plain weave on 2 ends x 2 picks. Pick 1 lifts end 1 only, pick 2 lifts end 2 only."""
    d = Draft(ends=2, picks=2, shafts=2, treadles=2)
    d.set_thread(0, 0)
    d.set_thread(1, 1)
    d.set_tieup(0, 0, True)
    d.set_tieup(1, 1, True)
    d.set_treadling(0, 0, True)
    d.set_treadling(1, 1, True)
    d.set_palette_color(0, warp)
    d.set_palette_color(1, weft)
    return d


def near(pixel, expected, tolerance=4):
    return all(abs(int(a) - int(b)) <= tolerance for a, b in zip(pixel, expected))


# ---- flat drawdown with per-thread colours ----

def test_flat_drawdown_uses_each_threads_own_colour():
    d = Draft(ends=3, picks=2, shafts=1, treadles=1)
    for e in range(3):
        d.set_thread(e, 0)
    d.set_tieup(0, 0, True)
    d.set_treadling(0, 0, True)                   # pick 1 lifts every end; pick 2 lifts none
    d.add_palette_color("#00ff00")
    d.set_warp_color(1, 2)                        # end 2 is green
    d.set_weft_color(1, 2)                        # pick 2 is green
    rgb = drawdown_colors(d)                      # display order: end 3, end 2, end 1
    assert rgb.shape == (2, 3, 3)
    assert rgb[0].tolist() == [[31, 41, 55], [0, 255, 0], [31, 41, 55]]   # pick 1: warp on top, end 2 green
    assert (rgb[1] == [0, 255, 0]).all()                                   # pick 2: weft on top, green weft


def test_warp_and_weft_strips_show_the_thread_colours_in_display_order():
    d = Draft(ends=3, picks=2)
    d.add_palette_color("#ff0000")
    d.set_warp_color(0, 2)                        # end 1 is red and appears at the right
    d.set_weft_color(0, 2)                        # pick 1 is red and appears at the top
    assert warp_strip(d).shape == (1, 3, 3)
    assert warp_strip(d)[0, 2].tolist() == [255, 0, 0] and warp_strip(d)[0, 0].tolist() == [31, 41, 55]
    assert weft_strip(d).shape == (2, 1, 3)
    assert weft_strip(d)[0, 0].tolist() == [255, 0, 0] and weft_strip(d)[1, 0].tolist() == [248, 250, 252]


def test_render_panels_includes_the_strips_at_the_layout_size():
    d = Draft.twill_2_2(ends=12, picks=9)
    panels = render_panels(d, 10)
    lay = DraftLayout.build(d, 10)
    assert panels["warp"].shape[:2] == (lay.warp.height, lay.warp.width)
    assert panels["weft"].shape[:2] == (lay.weft.height, lay.weft.width)


# ---- cloth ----

@pytest.mark.parametrize("cell,thickness", [(4, 0.85), (9, 0.5), (12, 1.0)])
def test_cloth_has_exactly_the_size_of_the_flat_drawdown(cell, thickness):
    d = Draft.twill_2_2(ends=10, picks=7)
    flat = render_panels(d, cell)["drawdown"]
    assert render_cloth(d, cell, thickness).shape == flat.shape
    assert render_panels(d, cell, cloth_thickness=thickness)["drawdown"].shape == flat.shape


def test_top_thread_shows_in_its_own_colour_at_the_middle_of_the_yarn():
    img = render_cloth(two_by_two(), 12, 0.85)
    # Display order: column 0 is end 2, column 1 is end 1. Pick 1 lifts end 1, pick 2 lifts end 2.
    assert near(img[6, 18], (200, 0, 0))      # pick 1, end 1: warp on top
    assert near(img[6, 6], (0, 0, 200))       # pick 1, end 2: weft on top
    assert near(img[18, 6], (200, 0, 0))      # pick 2, end 2: warp on top
    assert near(img[18, 18], (0, 0, 200))     # pick 2, end 1: weft on top


def test_yarn_is_shaded_darker_toward_its_edges():
    img = render_cloth(two_by_two(), 12, 1.0)
    middle = int(img[6, 18, 0])               # warp yarn, centre of the cell
    edge = int(img[6, 12, 0])                 # warp yarn, its left edge
    assert middle > edge > 0


def test_the_thread_underneath_shows_dimly_beside_the_top_yarn():
    img = render_cloth(two_by_two(), 12, 0.6)
    # Pick 1, end 1: warp (red) on top, 60% of the cell wide. Beside it the weft (blue) passes under.
    beside = img[6, 12 + 1]                   # left of the red yarn, at the weft's middle height
    assert beside[2] > 0 and beside[0] == 0   # it is the blue weft...
    assert beside[2] < 0.6 * 200              # ...in shadow, much darker than the lit weft on top


def test_there_is_a_dark_gap_where_neither_yarn_reaches():
    img = render_cloth(two_by_two(), 12, 0.5)
    corner = img[0, 12]                       # pick 1, end 1: top-left corner of the cell
    assert int(corner.max()) <= 200 * GAP_SHADE + 2


def test_full_thickness_leaves_no_gap():
    img = render_cloth(two_by_two(), 12, 1.0)
    assert (img.max(axis=2) > 200 * 0.5).all()          # every pixel shows yarn


def test_floats_are_continuous_across_cell_boundaries():
    d = Draft(ends=1, picks=2, shafts=1, treadles=1)
    d.set_thread(0, 0)
    d.set_tieup(0, 0, True)
    d.set_treadling(0, 0, True)
    d.set_treadling(1, 0, True)               # the end is up on both picks: one long float
    d.set_palette_color(0, WARP)
    img = render_cloth(d, 10, 0.85)
    assert (img[9] == img[10]).all()          # no seam where the two picks meet


def test_thickness_is_clamped_rather_than_failing():
    d = two_by_two()
    assert (render_cloth(d, 8, 5.0) == render_cloth(d, 8, 1.0)).all()
    assert (render_cloth(d, 8, -1.0) == render_cloth(d, 8, cloth.MIN_THICKNESS)).all()
    with pytest.raises(ValueError):
        render_cloth(d, 0)


def test_chunked_rendering_matches_rendering_in_one_piece(monkeypatch):
    d = Draft.twill_2_2(ends=9, picks=11)
    d.add_palette_color("#33aa77")
    d.set_warp_color(3, 2)
    d.set_weft_color(5, 2)
    whole = render_cloth(d, 7, 0.8)
    monkeypatch.setattr(cloth, "_CHUNK_PIXELS", 1)       # force one pick per chunk
    assert (render_cloth(d, 7, 0.8) == whole).all()


def test_cloth_follows_the_drawdown_when_the_shed_is_flipped():
    d = two_by_two()
    rising = render_cloth(d, 12, 0.85)
    d.set_rising(False)
    sinking = render_cloth(d, 12, 0.85)
    assert near(sinking[6, 18], (0, 0, 200)) and near(rising[6, 18], (200, 0, 0))


def test_png_export_can_show_the_cloth_view():
    d = Draft.twill_2_2(ends=12, picks=12)
    flat = render_draft_image(d, cell=10)
    woven = render_draft_image(d, cell=10, cloth_thickness=0.85)
    assert flat.size == woven.size
    assert len(woven.getcolors(maxcolors=1_000_000)) > len(flat.getcolors(maxcolors=1_000_000))   # shading adds tones


def test_png_export_includes_the_colour_strips():
    d = Draft(ends=4, picks=4)
    d.add_palette_color("#ff00ff")
    d.set_warp_color(0, 2)
    img = render_draft_image(d, cell=10)
    lay = DraftLayout.build(d, 10)
    x = int(lay.warp.x + 3 * 10 + 5)                      # end 1 is the right-most cell of the strip
    y = int(lay.warp.y + 5)
    assert img.getpixel((x, y)) == (255, 0, 255)
