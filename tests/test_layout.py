import pytest

from weavegen.core.draft import Draft
from weavegen.core.layout import DraftLayout, Grid, Hit, ruler_step


def centre(grid: Grid, row: int, col: int) -> tuple[float, float]:
    x0 = grid.x + col * grid.cell
    y0 = grid.y + row * grid.cell
    return x0 + grid.cell / 2, y0 + grid.cell / 2


def test_grid_pixel_to_cell_edges():
    g = Grid(x=10, y=20, cell=10, cols=3, rows=2)
    assert g.pixel_to_cell(10, 20) == (0, 0)
    assert g.pixel_to_cell(39.9, 39.9) == (1, 2)
    assert g.pixel_to_cell(40, 30) is None
    assert g.pixel_to_cell(9.9, 30) is None
    assert g.pixel_to_cell(20, 40) is None


def test_panels_are_arranged_like_a_standard_draft():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    assert lay.tieup.y == lay.threading.y                  # tie-up level with threading
    assert lay.treadling.y == lay.drawdown.y               # treadling level with drawdown
    assert lay.drawdown.x == lay.threading.x               # drawdown under threading
    assert lay.treadling.x == lay.tieup.x                  # treadling under tie-up
    assert lay.tieup.x > lay.threading.right               # tie-up right of threading
    assert lay.drawdown.y > lay.threading.bottom           # drawdown below threading
    assert (lay.threading.cols, lay.threading.rows) == (10, 4)
    assert (lay.tieup.cols, lay.tieup.rows) == (6, 4)
    assert (lay.treadling.cols, lay.treadling.rows) == (6, 8)
    assert (lay.drawdown.cols, lay.drawdown.rows) == (10, 8)
    assert lay.width > lay.treadling.right and lay.height > lay.drawdown.bottom


def test_threading_hits_number_ends_right_to_left_and_shafts_bottom_to_top():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    g = lay.threading
    assert lay.hit(*centre(g, row=0, col=0)) == Hit("threading", 9, 3)   # top-left: last end, top shaft
    assert lay.hit(*centre(g, row=3, col=9)) == Hit("threading", 0, 0)   # bottom-right: end 1, shaft 1


def test_tieup_treadling_and_drawdown_hits():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    assert lay.hit(*centre(lay.tieup, 3, 0)) == Hit("tieup", 0, 0)        # treadle 1, shaft 1
    assert lay.hit(*centre(lay.tieup, 0, 5)) == Hit("tieup", 5, 3)
    assert lay.hit(*centre(lay.treadling, 0, 0)) == Hit("treadling", 0, 0)  # pick 1, treadle 1
    assert lay.hit(*centre(lay.treadling, 7, 5)) == Hit("treadling", 7, 5)
    assert lay.hit(*centre(lay.drawdown, 0, 9)) == Hit("drawdown", 0, 0)    # pick 1, end 1 (right edge)
    assert lay.hit(*centre(lay.drawdown, 7, 0)) == Hit("drawdown", 7, 9)


def test_gaps_and_margins_hit_nothing():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    gap_x = (lay.threading.right + lay.tieup.x) / 2
    assert lay.hit(gap_x, lay.threading.y + 5) is None
    gap_y = (lay.threading.bottom + lay.drawdown.y) / 2
    assert lay.hit(lay.threading.x + 5, gap_y) is None
    assert lay.hit(0, 0) is None


def test_liftplan_mode_hides_the_tieup_and_uses_shaft_columns():
    d = Draft(ends=10, picks=8, shafts=4, treadles=6)
    d.set_liftplan_mode(True)
    lay = DraftLayout.build(d, cell=10)
    assert lay.treadling.cols == 4
    assert lay.hit(*centre(lay.tieup, 0, 0)) is None
    assert lay.hit(*centre(lay.treadling, 2, 3)) == Hit("liftplan", 2, 3)


@pytest.mark.parametrize("cell", [4, 9, 16, 31])
def test_every_cell_centre_round_trips_through_hit(cell):
    d = Draft(ends=7, picks=5, shafts=3, treadles=4)
    lay = DraftLayout.build(d, cell)
    for end in range(7):
        for shaft in range(3):
            row, col = 3 - 1 - shaft, 7 - 1 - end
            assert lay.hit(*centre(lay.threading, row, col)) == Hit("threading", end, shaft)
    for pick in range(5):
        for end in range(7):
            assert lay.hit(*centre(lay.drawdown, pick, 7 - 1 - end)) == Hit("drawdown", pick, end)


def test_ruler_step_widens_as_cells_shrink():
    steps = (4, 8, 16, 32, 64)
    assert ruler_step(16, steps, 36) == 4
    assert ruler_step(8, steps, 36) == 8
    assert ruler_step(4, steps, 36) == 16
    assert ruler_step(0.1, steps, 36) == 64  # falls back to the sparsest


def test_labels_are_one_based_and_end_numbers_run_right_to_left():
    d = Draft(ends=16, picks=16, shafts=4, treadles=4)
    lay = DraftLayout.build(d, cell=16)
    ends = {lab.text: lab for lab in lay.labels() if lab.anchor == "s" and lab.y < lay.threading.y}
    # Above the threading: 4, 8, 12, 16, with 16 at the far left and 4 nearest the right.
    thr_labels = sorted((lab for lab in lay.labels()
                         if lab.anchor == "s" and lab.x < lay.threading.right), key=lambda lab: lab.x)
    assert [lab.text for lab in thr_labels] == ["16", "12", "8", "4"]
    assert ends  # sanity: labels exist above the grids
    picks = [lab.text for lab in lay.labels() if lab.anchor == "w" and lab.x > lay.treadling.right]
    assert picks == ["4", "8", "12", "16"]
    shafts = [lab.text for lab in lay.labels() if lab.anchor == "w" and lab.x < lay.tieup.x]
    assert shafts == ["4", "3", "2", "1"]  # top to bottom


# ---- colour strips ----

def test_warp_strip_sits_above_the_threading_and_weft_strip_right_of_the_pick_numbers():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    assert (lay.warp.cols, lay.warp.rows) == (10, 1)
    assert (lay.weft.cols, lay.weft.rows) == (1, 8)
    assert lay.warp.x == lay.threading.x and lay.warp.bottom < lay.threading.y   # room for end numbers between
    assert lay.weft.y == lay.drawdown.y and lay.weft.x > lay.treadling.right     # room for pick numbers between
    assert lay.width > lay.weft.right and lay.height > lay.drawdown.bottom


def test_no_panel_overlaps_another():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    grids = [lay.warp, lay.weft, lay.threading, lay.tieup, lay.treadling, lay.drawdown]
    for i, a in enumerate(grids):
        for b in grids[i + 1:]:
            apart = a.right <= b.x or b.right <= a.x or a.bottom <= b.y or b.bottom <= a.y
            assert apart, (a, b)


def test_warp_strip_hits_number_ends_right_to_left_and_weft_strip_picks_top_to_bottom():
    lay = DraftLayout.build(Draft(ends=10, picks=8, shafts=4, treadles=6), cell=10)
    assert lay.hit(*centre(lay.warp, 0, 9)) == Hit("warp", 0, 0)    # right-hand cell is end 1
    assert lay.hit(*centre(lay.warp, 0, 0)) == Hit("warp", 9, 0)
    assert lay.hit(*centre(lay.weft, 0, 0)) == Hit("weft", 0, 0)    # top cell is pick 1
    assert lay.hit(*centre(lay.weft, 7, 0)) == Hit("weft", 7, 0)


def test_strips_remain_in_liftplan_mode():
    d = Draft(ends=10, picks=8, shafts=4, treadles=6)
    d.set_liftplan_mode(True)
    lay = DraftLayout.build(d, cell=10)
    assert lay.hit(*centre(lay.warp, 0, 3)) == Hit("warp", 6, 0)
    assert lay.hit(*centre(lay.weft, 2, 0)) == Hit("weft", 2, 0)
    assert lay.grid("warp") is lay.warp and lay.grid("weft") is lay.weft
