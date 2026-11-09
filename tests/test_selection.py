import pytest

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout
from weavegen.core.selection import (
    Rect, display_axis, display_shift_to_matrix, matrix_to_display,
)


def test_spanning_normalises_corner_order():
    assert Rect.spanning((4, 1), (2, 3)) == Rect(2, 4, 1, 3)
    r = Rect.spanning((1, 2), (1, 2))
    assert (r.height, r.width) == (1, 1)


def test_rect_slices_are_inclusive_and_fits_checks_bounds():
    r = Rect(1, 3, 0, 2)
    assert (r.height, r.width) == (3, 3)
    assert r.rows == slice(1, 4) and r.cols == slice(0, 3)
    assert r.fits((4, 3)) and not r.fits((3, 3)) and not r.fits((4, 2))
    assert not Rect(-1, 0, 0, 0).fits((5, 5))


@pytest.mark.parametrize("panel,make", [
    ("threading", lambda: Draft(ends=10, picks=6, shafts=5, treadles=4)),
    ("tieup", lambda: Draft(ends=10, picks=6, shafts=5, treadles=4)),
    ("treadling", lambda: Draft(ends=10, picks=6, shafts=5, treadles=4)),
])
def test_matrix_to_display_agrees_with_layout_hit_testing(panel, make):
    """A single matrix cell must land exactly where a click on that cell is reported."""
    draft = make()
    layout = DraftLayout.build(draft, cell=12)
    rows, cols = draft.matrix(panel).shape
    grid = layout.grid(panel)
    for a in range(rows):
        for b in range(cols):
            r0, c0, r1, c1 = matrix_to_display(draft, panel, Rect(a, a, b, b))
            assert (r0, c0) == (r1, c1)
            x = grid.x + (c0 + 0.5) * grid.cell
            y = grid.y + (r0 + 0.5) * grid.cell
            hit = layout.hit(x, y)
            assert (hit.panel, hit.a, hit.b) == (panel, a, b)


def test_liftplan_matrix_to_display_is_identity_and_agrees_with_hits():
    d = Draft(ends=4, picks=6, shafts=3, treadles=2)
    d.set_liftplan_mode(True)
    layout = DraftLayout.build(d, cell=12)
    assert matrix_to_display(d, "liftplan", Rect(2, 4, 1, 2)) == (2, 1, 4, 2)
    grid = layout.grid("liftplan")
    hit = layout.hit(grid.x + 1.5 * grid.cell, grid.y + 2.5 * grid.cell)
    assert (hit.panel, hit.a, hit.b) == ("liftplan", 2, 1)


def test_multi_cell_threading_rect_maps_to_the_right_display_block():
    d = Draft(ends=10, shafts=5)
    # ends 2..4 (matrix rows), shafts 1..2 (matrix cols)
    # display: cols = 10-1-4 .. 10-1-2 = 5..7 ; rows = 5-1-2 .. 5-1-1 = 2..3
    assert matrix_to_display(d, "threading", Rect(2, 4, 1, 2)) == (2, 5, 3, 7)


def test_display_axis():
    assert display_axis("threading", "h") == "rows" and display_axis("threading", "v") == "cols"
    assert display_axis("tieup", "h") == "rows" and display_axis("tieup", "v") == "cols"
    assert display_axis("treadling", "h") == "cols" and display_axis("treadling", "v") == "rows"
    assert display_axis("liftplan", "h") == "cols"
    with pytest.raises(ValueError):
        display_axis("threading", "x")
    with pytest.raises(ValueError):
        display_axis("drawdown", "h")


def test_display_shift_to_matrix():
    # Threading: ends run right-to-left, so moving content right means fewer-numbered ends.
    assert display_shift_to_matrix("threading", dcol=1, drow=0) == (-1, 0)
    assert display_shift_to_matrix("threading", dcol=0, drow=1) == (0, -1)   # down = lower shaft
    assert display_shift_to_matrix("tieup", dcol=1, drow=1) == (1, -1)
    assert display_shift_to_matrix("treadling", dcol=1, drow=2) == (2, 1)
    assert display_shift_to_matrix("liftplan", dcol=-1, drow=0) == (0, -1)


# ---- colour strips ----

@pytest.mark.parametrize("panel", ["warp", "weft"])
def test_strip_matrix_to_display_agrees_with_layout_hit_testing(panel):
    draft = Draft(ends=9, picks=7, shafts=4, treadles=4)
    layout = DraftLayout.build(draft, cell=12)
    grid = layout.grid(panel)
    for a in range(draft.matrix(panel).shape[0]):
        r0, c0, r1, c1 = matrix_to_display(draft, panel, Rect(a, a, 0, 0))
        assert (r0, c0) == (r1, c1)
        hit = layout.hit(grid.x + (c0 + 0.5) * grid.cell, grid.y + (r0 + 0.5) * grid.cell)
        assert (hit.panel, hit.a, hit.b) == (panel, a, 0)


def test_multi_cell_strip_rects_map_to_the_right_display_block():
    d = Draft(ends=10, picks=8)
    assert matrix_to_display(d, "warp", Rect(2, 4, 0, 0)) == (0, 5, 0, 7)   # ends 3-5, right to left
    assert matrix_to_display(d, "weft", Rect(2, 4, 0, 0)) == (2, 0, 4, 0)   # picks 3-5, top to bottom


def test_strip_axes_and_shifts():
    assert display_axis("warp", "h") == "rows" and display_axis("warp", "v") == "cols"
    assert display_axis("weft", "v") == "rows" and display_axis("weft", "h") == "cols"
    assert display_shift_to_matrix("warp", dcol=1, drow=0) == (-1, 0)
    assert display_shift_to_matrix("weft", dcol=0, drow=2) == (2, 0)
