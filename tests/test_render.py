import numpy as np
import pytest

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import (
    FLOAT_TINT, display_arrays, hex_to_rgb, panel_rgb, render_panels, tint_cells,
)
from weavegen.io.png import render_draft_image


def test_hex_to_rgb():
    assert hex_to_rgb("#ff8000") == (255, 128, 0)
    with pytest.raises(ValueError):
        hex_to_rgb("#fff")


def test_display_arrays_orientation():
    d = Draft(ends=3, picks=2, shafts=2, treadles=2)
    d.set_thread(0, 0)   # end 1 on shaft 1
    d.set_thread(2, 1)   # end 3 on shaft 2
    d.set_tieup(0, 1, True)  # treadle 1 tied to shaft 2
    arrays = display_arrays(d)
    # Threading: rows are shaft 2 then shaft 1; columns are end 3, 2, 1.
    assert arrays["threading"].tolist() == [[True, False, False], [False, False, True]]
    # Tie-up: rows shaft 2 then shaft 1; columns treadle 1, 2.
    assert arrays["tieup"].tolist() == [[True, False], [False, False]]
    assert set(arrays) == {"threading", "tieup", "treadling", "drawdown"}


def test_liftplan_mode_hides_the_tieup_and_swaps_treadling_for_liftplan():
    d = Draft(ends=3, picks=2, shafts=2, treadles=2)
    d.set_liftplan_mode(True)
    assert set(display_arrays(d)) == {"threading", "liftplan", "drawdown"}
    assert set(render_panels(d, 6)) == {"threading", "liftplan", "drawdown", "warp", "weft"}


def test_drawdown_is_mirrored_so_end_one_is_at_the_right():
    d = Draft(ends=3, picks=1, shafts=1, treadles=1)
    d.set_thread(0, 0)
    d.set_tieup(0, 0, True)
    d.set_treadling(0, 0, True)
    assert d.drawdown().tolist() == [[True, False, False]]
    assert display_arrays(d)["drawdown"].tolist() == [[False, False, True]]


def test_panel_rgb_size_colors_and_grid_lines():
    states = np.array([[True, False]])
    img = panel_rgb(states, cell=8, on=(10, 20, 30), off=(200, 210, 220), line=(1, 2, 3))
    assert img.shape == (8, 16, 3) and img.dtype == np.uint8
    assert tuple(img[4, 4]) == (10, 20, 30)
    assert tuple(img[4, 12]) == (200, 210, 220)
    assert tuple(img[0, 4]) == (1, 2, 3) and tuple(img[4, 8]) == (1, 2, 3)   # cell edges
    assert tuple(img[7, 4]) == (1, 2, 3) and tuple(img[4, 15]) == (1, 2, 3)  # outer border


def test_tiny_cells_skip_grid_lines():
    img = panel_rgb(np.array([[True]]), cell=2, on=(0, 0, 0), off=(255, 255, 255))
    assert (img == 0).all()


def test_render_panels_sizes_match_the_layout():
    d = Draft.twill_2_2(ends=12, picks=9)
    lay = DraftLayout.build(d, cell=10)
    panels = render_panels(d, 10)
    for name, grid in (("threading", lay.threading), ("tieup", lay.tieup),
                       ("treadling", lay.treadling), ("drawdown", lay.drawdown),
                       ("warp", lay.warp), ("weft", lay.weft)):
        assert panels[name].shape[:2] == (grid.height, grid.width), name


def test_drawdown_uses_warp_and_weft_colors():
    d = Draft(ends=2, picks=1, shafts=1, treadles=1)
    d.set_thread(0, 0)
    d.set_tieup(0, 0, True)
    d.set_treadling(0, 0, True)           # end 1 up, end 2 (unthreaded) down
    d.set_palette_color(0, "#ff0000")     # warp colour
    d.set_palette_color(1, "#0000ff")     # weft colour
    img = render_panels(d, 6)["drawdown"]
    assert tuple(img[3, 9]) == (255, 0, 0)   # end 1 is the right-hand column: warp color
    assert tuple(img[3, 3]) == (0, 0, 255)   # end 2 on the left: weft color


def test_png_export_matches_layout_and_contains_the_drawdown_colors():
    d = Draft.twill_2_2(ends=12, picks=12)
    d.set_palette_color(0, "#ff0000")
    d.set_palette_color(1, "#0000ff")
    img = render_draft_image(d, cell=10)
    lay = DraftLayout.build(d, 10)
    assert img.size == (int(lay.width), int(lay.height))
    colors = {c for _, c in img.getcolors(maxcolors=100000)}
    assert (255, 0, 0) in colors and (0, 0, 255) in colors


# ---- float highlight ----

def test_tint_cells_shades_only_the_masked_cells_and_keeps_grid_lines():
    base = np.full((4 * 8, 4 * 8, 3), 200, dtype=np.uint8)
    base[::8, :] = 100                                    # grid lines
    base[:, ::8] = 100
    mask = np.zeros((4, 4), dtype=bool)
    mask[1, 2] = True
    out = tint_cells(base, mask, 8)
    cell = (slice(8, 16), slice(16, 24))
    assert (out[8 + 3, 16 + 3] != 200).any()               # the inside of the masked cell is tinted
    assert tuple(out[8, 16 + 3]) == (100, 100, 100)        # but its top grid line is not
    other = np.ones((32, 32), dtype=bool)
    other[cell] = False
    assert (out[other] == base[other]).all()               # nothing else changed
    assert (base == 200).sum() > 0 and base[8 + 3, 16 + 3, 0] == 200   # the input is not modified


def test_tint_mixes_towards_the_tint_colour():
    base = np.full((8, 8, 3), 255, dtype=np.uint8)
    out = tint_cells(base, np.ones((2, 2), dtype=bool), 4, tint=(0, 0, 0), strength=0.5)
    assert out[1, 1].tolist() == [127, 127, 127]


def test_highlight_shades_the_drawdown_in_display_orientation_and_nothing_else():
    d = Draft.twill_2_2()
    mask = np.zeros((d.picks, d.ends), dtype=bool)
    mask[0, 0] = True                                      # pick 1, end 1: the top-right cell on screen
    plain, marked = render_panels(d, 8), render_panels(d, 8, highlight=mask)
    changed = (plain["drawdown"] != marked["drawdown"]).any(axis=2)
    assert changed[:8, -8:].any() and changed.sum() == changed[:8, -8:].sum()
    for name in ("threading", "tieup", "treadling", "warp", "weft"):
        assert (plain[name] == marked[name]).all()
    before, after = (int(v) for v in plain["drawdown"][3, -4]), [int(v) for v in marked["drawdown"][3, -4]]
    assert after != list(before) and after[0] > after[1]   # shaded, and towards red


def test_highlight_works_over_the_cloth_view_and_none_changes_nothing():
    d = Draft.twill_2_2()
    mask = np.ones((d.picks, d.ends), dtype=bool)
    plain = render_panels(d, 10, cloth_thickness=0.85)
    assert (render_panels(d, 10, cloth_thickness=0.85, highlight=None)["drawdown"] == plain["drawdown"]).all()
    assert (render_panels(d, 10, cloth_thickness=0.85, highlight=mask)["drawdown"] != plain["drawdown"]).any()


def test_a_highlight_of_the_wrong_shape_is_refused():
    d = Draft.twill_2_2()
    with pytest.raises(ValueError, match="highlight must be"):
        render_panels(d, 8, highlight=np.zeros((3, 3), dtype=bool))


def test_the_tint_is_a_strong_red():
    r, g, b = FLOAT_TINT
    assert r > 200 and g < 60


# ---- weave-only PNG ----

def test_weave_image_is_only_the_drawdown_without_grid_lines():
    from weavegen.io.png import render_weave_image
    d = Draft.twill_2_2(ends=12, picks=8)
    d.set_palette_color(0, "#ff0000")
    d.set_palette_color(1, "#0000ff")
    img = render_weave_image(d, cell=10)
    assert img.size == (12 * 10, 8 * 10)                       # exactly ends x picks cells
    assert {c for _, c in img.getcolors(maxcolors=100000)} == {(255, 0, 0), (0, 0, 255)}   # no grid, no ink/paper
    assert render_weave_image(d, cell=10, cloth_thickness=0.85).size == img.size
