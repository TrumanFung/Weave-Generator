import numpy as np
import pytest

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.render import display_arrays, hex_to_rgb, panel_rgb, render_panels
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
    assert set(render_panels(d, 6, "#000000", "#ffffff")) == {"threading", "liftplan", "drawdown"}


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
    panels = render_panels(d, 10, "#000000", "#ffffff")
    for name, grid in (("threading", lay.threading), ("tieup", lay.tieup),
                       ("treadling", lay.treadling), ("drawdown", lay.drawdown)):
        assert panels[name].shape[:2] == (grid.height, grid.width), name


def test_drawdown_uses_warp_and_weft_colors():
    d = Draft(ends=2, picks=1, shafts=1, treadles=1)
    d.set_thread(0, 0)
    d.set_tieup(0, 0, True)
    d.set_treadling(0, 0, True)           # end 1 up, end 2 (unthreaded) down
    img = render_panels(d, 6, "#ff0000", "#0000ff")["drawdown"]
    assert tuple(img[3, 9]) == (255, 0, 0)   # end 1 is the right-hand column: warp color
    assert tuple(img[3, 3]) == (0, 0, 255)   # end 2 on the left: weft color


def test_png_export_matches_layout_and_contains_the_drawdown_colors():
    d = Draft.twill_2_2(ends=12, picks=12)
    img = render_draft_image(d, "#ff0000", "#0000ff", cell=10)
    lay = DraftLayout.build(d, 10)
    assert img.size == (int(lay.width), int(lay.height))
    colors = {c for _, c in img.getcolors(maxcolors=100000)}
    assert (255, 0, 0) in colors and (0, 0, 255) in colors
