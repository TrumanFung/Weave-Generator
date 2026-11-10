import numpy as np
import pytest

from weavegen.core import ops
from weavegen.core.draft import UNTHREADED, Draft
from weavegen.core.selection import Rect


def threaded(*shafts, n_shafts=4):
    d = Draft(ends=len(shafts), picks=4, shafts=n_shafts, treadles=4)
    for end, shaft in enumerate(shafts):
        d.set_thread(end, None if shaft == UNTHREADED else shaft)
    return d


# ---- copy / clear / paste ----

def test_copy_returns_the_selected_block_and_leaves_the_draft_alone():
    d = Draft.twill_2_2()
    before = d.tieup.copy()
    clip = ops.copy(d, "tieup", Rect(0, 1, 0, 2))
    assert clip.panel == "tieup" and clip.data.shape == (2, 3)
    assert (clip.data == before[0:2, 0:3]).all()
    assert (d.tieup == before).all()


def test_clip_is_independent_of_later_edits():
    d = Draft.twill_2_2()
    clip = ops.copy(d, "tieup", Rect(0, 0, 0, 3))
    d.tieup[:] = False
    assert clip.data.any()


def test_clear_only_touches_the_selection():
    d = Draft.twill_2_2()
    assert ops.clear(d, "tieup", Rect(0, 1, 0, 3))
    assert not d.tieup[0:2].any() and d.tieup[2:].any()
    assert not ops.clear(d, "tieup", Rect(0, 1, 0, 3))  # already empty


def test_paste_replaces_the_block_including_empty_cells():
    d = Draft(ends=2, picks=2, shafts=4, treadles=4)
    d.tieup[:] = True
    clip = ops.Clipboard("tieup", np.array([[True, False], [False, True]]))
    assert ops.paste(d, clip, "tieup", 1, 1)
    assert d.tieup[1:3, 1:3].tolist() == [[True, False], [False, True]]
    assert d.tieup[0].all() and d.tieup[3].all()  # outside rows untouched


def test_paste_is_clipped_at_the_panel_edge():
    d = Draft(ends=2, picks=2, shafts=3, treadles=3)
    clip = ops.Clipboard("tieup", np.ones((3, 3), dtype=bool))
    assert ops.paste(d, clip, "tieup", 2, 2)
    assert d.tieup.sum() == 1 and d.tieup[2, 2]


def test_paste_into_threading_replaces_whole_ends():
    d = threaded(0, 1, 2, 3)
    clip = ops.copy(d, "threading", Rect(0, 1, 0, 3))      # ends 0,1 -> shafts 0,1
    assert ops.paste(d, clip, "threading", 2, 0)
    assert d.threading.tolist() == [0, 1, 0, 1]            # not merged with old shafts 2 and 3


def test_paste_rejects_the_wrong_panel_and_out_of_range_targets():
    d = Draft.twill_2_2()
    clip = ops.copy(d, "tieup", Rect(0, 0, 0, 0))
    with pytest.raises(ValueError):
        ops.paste(d, clip, "treadling", 0, 0)
    with pytest.raises(IndexError):
        ops.paste(d, clip, "tieup", 9, 0)


def test_selection_outside_the_panel_is_rejected_without_changing_anything():
    d = Draft.twill_2_2()
    before = d.snapshot()
    with pytest.raises(ValueError):
        ops.clear(d, "tieup", Rect(0, 9, 0, 0))
    assert (d.tieup == before.tieup).all()


# ---- flip / rotate / invert ----

def test_flip_rows_and_cols_within_the_selection():
    d = Draft(ends=2, picks=2, shafts=3, treadles=3)
    d.tieup[0, 0] = d.tieup[1, 1] = True
    assert ops.flip(d, "tieup", Rect(0, 1, 0, 1), "rows")
    assert d.tieup[:2, :2].tolist() == [[False, True], [True, False]]
    ops.flip(d, "tieup", Rect(0, 1, 0, 1), "rows")   # flipping twice restores
    assert d.tieup[:2, :2].tolist() == [[True, False], [False, True]]
    assert ops.flip(d, "tieup", Rect(0, 0, 0, 2), "cols")
    assert d.tieup[0].tolist() == [False, False, True]


def test_flip_threading_ends_reverses_their_order():
    d = threaded(0, 1, 2, 3)
    ops.flip(d, "threading", Rect(0, 3, 0, 3), "rows")
    assert d.threading.tolist() == [3, 2, 1, 0]


def test_flip_threading_shafts_mirrors_the_shaft_numbers():
    d = threaded(0, 1, 2, 3)
    ops.flip(d, "threading", Rect(0, 3, 0, 3), "cols")
    assert d.threading.tolist() == [3, 2, 1, 0]
    d = threaded(0, 1, 2, 3)
    ops.flip(d, "threading", Rect(0, 3, 1, 2), "cols")   # only shafts 2 and 3 swap places
    assert d.threading.tolist() == [0, 2, 1, 3]


def test_flip_rejects_a_bad_axis():
    with pytest.raises(ValueError):
        ops.flip(Draft(), "tieup", Rect(0, 0, 0, 0), "diag")


def test_rotate_square_selection_and_four_turns_restore():
    d = Draft(ends=2, picks=2, shafts=4, treadles=4)
    d.tieup[0, 0] = d.tieup[0, 1] = True
    original = d.tieup.copy()
    assert ops.rotate(d, "tieup", Rect(0, 1, 0, 1))
    assert not (d.tieup == original).all()
    for _ in range(3):
        ops.rotate(d, "tieup", Rect(0, 1, 0, 1))
    assert (d.tieup == original).all()


def test_rotate_rejects_non_square_selection_and_threading():
    d = Draft.twill_2_2()
    with pytest.raises(ValueError):
        ops.rotate(d, "tieup", Rect(0, 1, 0, 2))
    with pytest.raises(ValueError):
        ops.rotate(d, "threading", Rect(0, 1, 0, 1))


def test_invert_whole_tieup_and_a_selection():
    d = Draft.twill_2_2()
    original = d.tieup.copy()
    assert ops.invert(d, "tieup")
    assert (d.tieup == ~original).all()
    ops.invert(d, "tieup")
    assert (d.tieup == original).all()
    ops.invert(d, "tieup", Rect(0, 0, 0, 3))
    assert (d.tieup[0] == ~original[0]).all() and (d.tieup[1:] == original[1:]).all()


def test_invert_rejects_threading():
    with pytest.raises(ValueError):
        ops.invert(Draft.twill_2_2(), "threading")


# ---- repeat / wrap ----

def test_repeat_tiles_the_selected_ends_toward_the_last_end():
    d = threaded(0, 1, 2, UNTHREADED, UNTHREADED, UNTHREADED, UNTHREADED, UNTHREADED)
    assert ops.repeat(d, "threading", Rect(0, 2, 0, 3))
    assert d.threading.tolist() == [0, 1, 2, 0, 1, 2, 0, 1]   # last block is cut short


def test_repeat_from_a_later_selection_leaves_earlier_rows_alone():
    d = threaded(3, 0, 1, UNTHREADED, UNTHREADED, UNTHREADED)
    ops.repeat(d, "threading", Rect(1, 2, 0, 3))
    assert d.threading.tolist() == [3, 0, 1, 0, 1, 0]


def test_repeat_on_treadling_picks():
    d = Draft(ends=4, picks=6, shafts=4, treadles=4)
    d.treadling[0, 0] = d.treadling[1, 2] = True
    ops.repeat(d, "treadling", Rect(0, 1, 0, 3))
    assert [int(np.argmax(r)) for r in d.treadling] == [0, 2, 0, 2, 0, 2]


def test_wrap_rolls_the_panel_around_the_edges():
    d = threaded(0, 1, 2, 3)
    assert ops.wrap(d, "threading", drow=1, dcol=0)
    assert d.threading.tolist() == [3, 0, 1, 2]
    ops.wrap(d, "threading", drow=0, dcol=1)    # every end moves up one shaft, shaft 4 wraps to 1
    assert d.threading.tolist() == [0, 1, 2, 3]


def test_wrap_by_a_full_cycle_changes_nothing():
    d = Draft.twill_2_2()
    assert not ops.wrap(d, "tieup", drow=4, dcol=4)


# ---- lines ----

def test_line_cells_horizontal_vertical_diagonal_and_reverse():
    assert ops.line_cells((0, 0), (0, 3)) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert ops.line_cells((0, 1), (3, 1)) == [(0, 1), (1, 1), (2, 1), (3, 1)]
    assert ops.line_cells((0, 0), (3, 3)) == [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert ops.line_cells((2, 2), (2, 2)) == [(2, 2)]
    assert ops.line_cells((3, 0), (0, 3)) == [(3, 0), (2, 1), (1, 2), (0, 3)]


@pytest.mark.parametrize("start,end", [((0, 0), (5, 2)), ((4, 7), (1, 0)), ((2, 2), (2, 9)), ((0, 5), (6, 0))])
def test_line_cells_touch_both_ends_and_have_no_gaps(start, end):
    cells = ops.line_cells(start, end)
    assert cells[0] == start and cells[-1] == end
    for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
        assert max(abs(r1 - r0), abs(c1 - c0)) == 1
    assert len(cells) == max(abs(end[0] - start[0]), abs(end[1] - start[1])) + 1


def test_draw_line_paints_and_erases_in_the_tieup():
    d = Draft(ends=2, picks=2, shafts=4, treadles=4)
    assert ops.draw_line(d, "tieup", (0, 0), (3, 3), paint=True)
    assert [d.tieup[i, i] for i in range(4)] == [True] * 4 and d.tieup.sum() == 4
    assert ops.draw_line(d, "tieup", (1, 1), (2, 2), paint=False)
    assert d.tieup.sum() == 2


def test_draw_line_in_threading_threads_one_shaft_per_end():
    d = Draft(ends=8, picks=2, shafts=4, treadles=2)
    assert ops.draw_line(d, "threading", (0, 0), (3, 3), paint=True)
    assert d.threading.tolist()[:4] == [0, 1, 2, 3] and (d.threading[4:] == UNTHREADED).all()


def test_draw_line_in_threading_works_backwards_and_when_steep():
    d = Draft(ends=8, picks=2, shafts=4, treadles=2)
    ops.draw_line(d, "threading", (5, 3), (2, 0), paint=True)
    assert d.threading.tolist()[2:6] == [0, 1, 2, 3]
    # A line within one end threads it on the shaft where the line finishes.
    d2 = Draft(ends=4, picks=2, shafts=4, treadles=2)
    ops.draw_line(d2, "threading", (1, 0), (1, 3), paint=True)
    assert d2.threading.tolist() == [UNTHREADED, 3, UNTHREADED, UNTHREADED]


def test_draw_line_in_threading_erases_ends_it_crosses():
    d = threaded(0, 1, 2, 3)
    assert ops.draw_line(d, "threading", (1, 0), (2, 0), paint=False)
    assert d.threading.tolist() == [0, UNTHREADED, UNTHREADED, 3]


def test_draw_line_rejects_points_outside_the_panel():
    d = Draft(ends=4, shafts=4, treadles=4)
    before = d.snapshot()
    with pytest.raises(IndexError):
        ops.draw_line(d, "tieup", (0, 0), (9, 0), paint=True)
    assert (d.tieup == before.tieup).all()


# ---- curve tool ----
CURVES = [((0, 0), (9, 9), (0, 9)), ((5, 0), (5, 9), (0, 4)), ((9, 0), (0, 0), (4, 6)),
          ((0, 0), (0, 12), (3, 6)), ((3, 3), (3, 4), (8, 3)), ((0, 5), (10, 5), (5, 0))]


@pytest.mark.parametrize("start,end,through", CURVES)
def test_curve_cells_run_from_start_to_end_without_gaps(start, end, through):
    cells = ops.curve_cells(start, end, through)
    assert cells[0] == start and cells[-1] == end
    for (r0, c0), (r1, c1) in zip(cells, cells[1:]):
        assert (r0, c0) != (r1, c1) and max(abs(r1 - r0), abs(c1 - c0)) == 1


@pytest.mark.parametrize("start,end,through", CURVES)
def test_the_curve_passes_through_the_chosen_point(start, end, through):
    cells = ops.curve_cells(start, end, through)
    assert min(max(abs(r - through[0]), abs(c - through[1])) for r, c in cells) <= 1


def test_a_point_on_the_chord_gives_a_straight_line():
    cells = ops.curve_cells((0, 0), (8, 4), (4, 2))
    for r, c in cells:
        assert abs(c - r / 2) <= 1          # within a cell of the straight line c = r / 2
    assert len(cells) >= 9


def test_a_degenerate_curve_is_one_cell():
    assert ops.curve_cells((3, 3), (3, 3), (3, 3)) == [(3, 3)]


def test_the_curve_is_symmetric_about_its_middle():
    cells = ops.curve_cells((0, 0), (0, 10), (6, 5))
    for r, c in cells:        # each cell's mirror image is on the curve, give or take rounding
        assert min(max(abs(r - r2), abs(10 - c - c2)) for r2, c2 in cells) <= 1


def test_curve_cells_bend_toward_the_chosen_point():
    low = ops.curve_cells((0, 0), (0, 10), (2, 5))
    high = ops.curve_cells((0, 0), (0, 10), (6, 5))
    assert max(r for r, _ in high) > max(r for r, _ in low) >= 1


def test_draw_curve_paints_and_erases_in_the_tieup():
    d = Draft(ends=4, picks=4, shafts=10, treadles=10)
    assert ops.draw_curve(d, "tieup", (0, 0), (9, 9), (0, 9), paint=True)
    painted = {(int(r), int(c)) for r, c in zip(*np.nonzero(d.tieup))}
    assert (0, 0) in painted and (9, 9) in painted and len(painted) >= 10
    assert all(0 <= r < 10 and 0 <= c < 10 for r, c in painted)
    assert ops.draw_curve(d, "tieup", (0, 0), (9, 9), (0, 9), paint=False)
    assert not d.tieup.any()


def test_draw_curve_in_threading_threads_one_shaft_per_end():
    d = Draft(ends=12, picks=4, shafts=8, treadles=4)
    assert ops.draw_curve(d, "threading", (0, 0), (11, 0), (5, 7), paint=True)
    assert (d.matrix("threading").sum(axis=1) == 1).all()           # every end threaded exactly once
    shafts = [int(s) for s in d.threading]
    assert shafts[0] == 0 and shafts[-1] == 0 and max(shafts) >= 6   # up and back down
    assert shafts[5] >= 6 or shafts[6] >= 6


def test_draw_curve_in_threading_averages_where_it_doubles_back_over_one_end():
    d = Draft(ends=4, picks=4, shafts=10, treadles=4)
    ops.draw_curve(d, "threading", (1, 0), (1, 9), (1, 4), paint=True)    # straight up one end
    assert d.threading[1] in range(0, 10) and d.matrix("threading")[1].sum() == 1


def test_a_curve_that_swings_out_of_the_panel_is_flattened_against_its_edge():
    d = Draft(ends=4, picks=4, shafts=10, treadles=10)
    assert ops.draw_curve(d, "tieup", (0, 0), (9, 9), (0, 9), paint=True)   # the true curve leaves the panel
    painted = {(int(r), int(c)) for r, c in zip(*np.nonzero(d.tieup))}
    assert {(0, 0), (9, 9), (0, 9)} <= painted
    assert any(r == 0 for r, c in painted if 3 < c < 9)                    # it runs along the top edge
    d2 = Draft(ends=12, picks=4, shafts=10, treadles=4)
    assert ops.draw_curve(d2, "threading", (0, 0), (11, 9), (0, 9), paint=True)
    assert (d2.matrix("threading").sum(axis=1) == 1).all()


def test_draw_curve_rejects_points_outside_the_panel_and_changes_nothing():
    d = Draft(ends=4, picks=4, shafts=4, treadles=4)
    for start, end, through in (((0, 0), (3, 3), (4, 0)), ((0, 0), (9, 3), (1, 1)), ((-1, 0), (3, 3), (1, 1))):
        with pytest.raises(IndexError):
            ops.draw_curve(d, "tieup", start, end, through, paint=True)
    assert not d.tieup.any()


def test_draw_curve_paints_the_chosen_colour_in_a_strip():
    d = Draft(ends=8, picks=4, shafts=4, treadles=4)
    d.add_palette_color("#ff0000")
    assert ops.draw_curve(d, "warp", (1, 0), (6, 0), (3, 0), paint=True, value=2)
    assert list(d.warp_colors[1:7]) == [2] * 6 and d.warp_colors[0] != 2
    assert ops.draw_curve(d, "warp", (1, 0), (6, 0), (3, 0), paint=False)
    assert 2 not in list(d.warp_colors)


def test_a_curve_changes_nothing_when_every_cell_already_matches():
    d = Draft(ends=4, picks=4, shafts=10, treadles=10)
    ops.draw_curve(d, "tieup", (0, 0), (9, 9), (2, 7), paint=True)
    assert ops.draw_curve(d, "tieup", (0, 0), (9, 9), (2, 7), paint=True) is False
