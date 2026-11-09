import numpy as np
import pytest

from weavegen.core import ops, patterns
from weavegen.core.draft import DEFAULT_PALETTE, Draft
from weavegen.core.history import History
from weavegen.core.selection import Rect


# ---- palette ----

def test_new_draft_starts_with_the_classic_two_colour_look():
    d = Draft(ends=5, picks=4)
    assert tuple(d.palette) == DEFAULT_PALETTE
    assert d.warp_colors.tolist() == [0] * 5      # warp on the first colour
    assert d.weft_colors.tolist() == [1] * 4      # weft on the second


def test_set_palette_color_validates_and_reports_change():
    d = Draft()
    assert d.set_palette_color(0, "#FF8000")
    assert d.palette[0] == "#ff8000"              # normalised to lower case
    assert not d.set_palette_color(0, "#ff8000")
    for bad in ("red", "#fff", "ff8000", "#gg0000", 5):
        with pytest.raises(ValueError):
            d.set_palette_color(0, bad)
    with pytest.raises(IndexError):
        d.set_palette_color(2, "#000000")
    assert d.palette[0] == "#ff8000"


def test_palette_has_no_size_limit():
    d = Draft()
    for i in range(300):
        d.add_palette_color(f"#{i:06x}")
    assert len(d.palette) == 302
    d.set_warp_color(0, 301)
    assert d.warp_colors[0] == 301


def test_add_palette_color_returns_its_index_and_allows_duplicates():
    d = Draft()
    assert d.add_palette_color("#112233") == 2
    assert d.add_palette_color("#112233") == 3
    with pytest.raises(ValueError):
        d.add_palette_color("nope")
    assert len(d.palette) == 4


def test_set_thread_colours_validate_their_indices():
    d = Draft(ends=3, picks=3)
    assert d.set_warp_color(1, 1) and not d.set_warp_color(1, 1)
    assert d.set_weft_color(2, 0) and not d.set_weft_color(2, 0)
    for call in (lambda: d.set_warp_color(3, 0), lambda: d.set_warp_color(-1, 0),
                 lambda: d.set_warp_color(0, 2), lambda: d.set_weft_color(0, -1),
                 lambda: d.set_weft_color(5, 0)):
        with pytest.raises(IndexError):
            call()


def test_remove_palette_color_reassigns_its_threads_and_shifts_later_colours():
    d = Draft(ends=4, picks=4)
    d.add_palette_color("#aa0000")     # 2
    d.add_palette_color("#00aa00")     # 3
    d.warp_colors[:] = [0, 2, 3, 1]
    d.weft_colors[:] = [3, 3, 2, 0]
    d.remove_palette_color(2)
    assert d.palette == [DEFAULT_PALETTE[0], DEFAULT_PALETTE[1], "#00aa00"]
    assert d.warp_colors.tolist() == [0, 0, 2, 1]      # colour 2 threads fell back to colour 1 (index 0)
    assert d.weft_colors.tolist() == [2, 2, 0, 0]      # colour 3 became colour 2 (index 2)


def test_removing_the_first_colour_moves_its_threads_to_what_becomes_first():
    d = Draft(ends=3, picks=2)
    d.add_palette_color("#aa0000")
    d.warp_colors[:] = [0, 1, 2]
    d.remove_palette_color(0)
    assert d.palette == [DEFAULT_PALETTE[1], "#aa0000"]
    assert d.warp_colors.tolist() == [0, 0, 1]


def test_the_last_colour_cannot_be_removed():
    d = Draft()
    d.remove_palette_color(1)
    with pytest.raises(ValueError):
        d.remove_palette_color(0)
    assert len(d.palette) == 1
    assert d.weft_colors.tolist() == [0] * d.picks


# ---- resize, snapshot, structure ----

def test_resize_keeps_thread_colours_and_gives_new_threads_the_defaults():
    d = Draft(ends=4, picks=4)
    d.add_palette_color("#aa0000")
    d.warp_colors[:] = [2, 2, 0, 0]
    d.weft_colors[:] = [2, 0, 2, 0]
    d.resize(ends=6, picks=2)
    assert d.warp_colors.tolist() == [2, 2, 0, 0, 0, 0]
    assert d.weft_colors.tolist() == [2, 0]
    d.resize(picks=4)
    assert d.weft_colors.tolist() == [2, 0, 1, 1]      # new picks start on the default weft colour


def test_snapshot_and_restore_include_the_palette_and_thread_colours():
    d = Draft(ends=3, picks=3)
    state = d.snapshot()
    d.add_palette_color("#aa0000")
    d.set_palette_color(0, "#000001")
    d.set_warp_color(0, 2)
    d.remove_palette_color(1)
    d.restore(state)
    assert tuple(d.palette) == DEFAULT_PALETTE and d.warp_colors.tolist() == [0, 0, 0]
    d.add_palette_color("#bbbbbb")                      # restored data must not alias the snapshot
    assert len(state.palette) == 2


def test_undo_restores_a_palette_edit():
    d, h = Draft(ends=3, picks=3), History()
    before = d.snapshot()
    d.set_palette_color(1, "#123456")
    h.record(before)
    h.undo(d)
    assert d.palette[1] == DEFAULT_PALETTE[1]
    h.redo(d)
    assert d.palette[1] == "#123456"


def test_clear_leaves_the_colours_alone():
    d = Draft.twill_2_2()
    d.add_palette_color("#aa0000")
    d.set_warp_color(3, 2)
    d.clear()
    assert d.warp_colors[3] == 2 and len(d.palette) == 3


def test_replace_structure_keeps_palette_colours_and_shed_and_fits_the_strips():
    d = Draft.twill_2_2(ends=8, picks=8)
    d.add_palette_color("#aa0000")
    d.warp_colors[:] = 2
    d.set_rising(False)
    other = patterns.build_preset("satin_5", ends=10, picks=6)
    d.replace_structure(other)
    assert (d.shafts, d.ends, d.picks) == (5, 10, 6)
    assert d.rising is False and len(d.palette) == 3
    assert d.warp_colors.tolist() == [2] * 8 + [0, 0]          # old ends keep colour; new ones default
    assert d.weft_colors.tolist() == [1] * 6
    assert (d.threading == other.threading).all()


# ---- strips as editable panels ----

def test_strip_matrices_hold_palette_indices():
    d = Draft(ends=4, picks=3)
    d.add_palette_color("#aa0000")
    d.warp_colors[:] = [0, 2, 1, 2]
    assert d.matrix("warp").tolist() == [[0], [2], [1], [2]]
    assert d.matrix("weft").shape == (3, 1)


def test_set_matrix_on_a_strip_validates_indices_and_shape():
    d = Draft(ends=3, picks=3)
    assert d.set_matrix("warp", np.array([[1], [0], [1]]))
    assert d.warp_colors.tolist() == [1, 0, 1]
    assert not d.set_matrix("warp", np.array([[1], [0], [1]]))
    with pytest.raises(ValueError):
        d.set_matrix("warp", np.array([[0], [0], [2]]))          # palette has only 2 colours
    with pytest.raises(ValueError):
        d.set_matrix("warp", np.array([[0], [-1], [0]]))
    with pytest.raises(ValueError):
        d.set_matrix("warp", np.zeros((2, 1), dtype=int))
    assert d.warp_colors.tolist() == [1, 0, 1]                    # rejected writes changed nothing


def test_clear_value_is_the_default_thread_colour():
    d = Draft()
    assert d.clear_value("warp") == 0 and d.clear_value("weft") == 1
    assert d.clear_value("tieup") == 0


# ---- operations on strips ----

def stripes(d, warp):
    d.warp_colors[:] = warp
    return d


def test_copy_paste_a_run_of_warp_colours():
    d = stripes(Draft(ends=8), [1, 1, 0, 0, 0, 0, 0, 0])
    d.add_palette_color("#aa0000")
    clip = ops.copy(d, "warp", Rect(0, 1, 0, 0))
    assert clip.data.tolist() == [[1], [1]]
    assert ops.paste(d, clip, "warp", 4, 0)
    assert d.warp_colors.tolist() == [1, 1, 0, 0, 1, 1, 0, 0]


def test_repeat_tiles_a_stripe_sequence_to_the_end():
    d = stripes(Draft(ends=10), [1, 1, 0, 0] + [0] * 6)
    ops.repeat(d, "warp", Rect(0, 3, 0, 0))
    assert d.warp_colors.tolist() == [1, 1, 0, 0] * 2 + [1, 1]


def test_flip_reverses_the_stripe_order_and_wrap_shifts_it():
    d = stripes(Draft(ends=4), [0, 0, 0, 1])
    ops.flip(d, "warp", Rect(0, 3, 0, 0), "rows")
    assert d.warp_colors.tolist() == [1, 0, 0, 0]
    ops.wrap(d, "warp", 1, 0)
    assert d.warp_colors.tolist() == [0, 1, 0, 0]


def test_clearing_a_strip_restores_the_default_colour_not_colour_one():
    d = Draft(ends=3, picks=3)
    d.add_palette_color("#aa0000")
    d.warp_colors[:] = 2
    d.weft_colors[:] = 2
    ops.clear(d, "warp", Rect(0, 2, 0, 0))
    ops.clear(d, "weft", Rect(0, 1, 0, 0))
    assert d.warp_colors.tolist() == [0, 0, 0]          # default warp colour
    assert d.weft_colors.tolist() == [1, 1, 2]          # default weft colour, last pick untouched


def test_draw_line_paints_a_run_of_the_chosen_colour_in_a_strip():
    d = Draft(ends=8)
    d.add_palette_color("#aa0000")
    assert ops.draw_line(d, "warp", (2, 0), (5, 0), paint=True, value=2)
    assert d.warp_colors.tolist() == [0, 0, 2, 2, 2, 2, 0, 0]
    assert ops.draw_line(d, "warp", (3, 0), (4, 0), paint=False)
    assert d.warp_colors.tolist() == [0, 0, 2, 0, 0, 2, 0, 0]


def test_rotate_and_invert_are_rejected_for_strips():
    d = Draft(ends=4, picks=4)
    with pytest.raises(ValueError):
        ops.rotate(d, "warp", Rect(0, 0, 0, 0))
    with pytest.raises(ValueError):
        ops.invert(d, "weft")


def test_pasting_a_colour_that_no_longer_exists_is_rejected_and_changes_nothing():
    d = Draft(ends=4)
    d.add_palette_color("#aa0000")
    d.warp_colors[0] = 2
    clip = ops.copy(d, "warp", Rect(0, 0, 0, 0))
    d.remove_palette_color(2)
    before = d.warp_colors.copy()
    with pytest.raises(ValueError):
        ops.paste(d, clip, "warp", 1, 0)
    assert (d.warp_colors == before).all()


# ---- stripe generator ----

@pytest.mark.parametrize("text,expected", [
    ("1:4, 2:2", [(0, 4), (1, 2)]),
    ("1x4 2x2", [(0, 4), (1, 2)]),
    ("1:4;2:2", [(0, 4), (1, 2)]),
    ("3*5", [(2, 5)]),
    ("  1 : 4 ,  2 : 2  ", [(0, 4), (1, 2)]),
])
def test_parse_stripes_accepts_common_spellings(text, expected):
    assert patterns.parse_stripes(text, 3) == expected


@pytest.mark.parametrize("text", ["", "   ", "abc", "1:", "4:2", "0:2", "1:0", "1:2:3"])
def test_parse_stripes_rejects_bad_input_with_a_message(text):
    with pytest.raises(ValueError):
        patterns.parse_stripes(text, 3)


def test_apply_stripes_repeats_the_sequence_across_the_warp_and_the_weft():
    d = Draft(ends=11, picks=5)
    d.add_palette_color("#aa0000")
    assert patterns.apply_stripes(d, "warp", [(0, 3), (2, 2)])
    assert d.warp_colors.tolist() == [0, 0, 0, 2, 2, 0, 0, 0, 2, 2, 0]    # last repeat is cut short
    assert patterns.apply_stripes(d, "weft", [(1, 1), (2, 1)])
    assert d.weft_colors.tolist() == [1, 2, 1, 2, 1]
    assert not patterns.apply_stripes(d, "weft", [(1, 1), (2, 1)])        # already applied


def test_apply_stripes_validates_its_arguments():
    d = Draft()
    with pytest.raises(ValueError):
        patterns.apply_stripes(d, "threading", [(0, 1)])
    with pytest.raises(ValueError):
        patterns.apply_stripes(d, "warp", [])
