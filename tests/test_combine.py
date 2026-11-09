"""Interleaving and double weave."""

import numpy as np
import pytest

from weavegen.core import patterns
from weavegen.core.combine import combine
from weavegen.core.draft import MAX_ENDS, Draft


def pair(rising=True):
    a = patterns.build_preset("plain", 6, 6)
    b = Draft.twill_2_2(ends=6, picks=6)
    a.set_rising(rising)
    b.set_rising(rising)
    return a, b


def quadrants(out: Draft):
    """The drawdown split into the cells where each draft's picks cross each draft's ends."""
    dd = out.drawdown()
    return {"AA": dd[0::2, 0::2], "AB": dd[0::2, 1::2], "BA": dd[1::2, 0::2], "BB": dd[1::2, 1::2]}


@pytest.mark.parametrize("rising", [True, False])
@pytest.mark.parametrize("mode", ["interleave", "double"])
def test_each_draft_keeps_its_own_cloth_where_its_picks_cross_its_ends(mode, rising):
    a, b = pair(rising)
    q = quadrants(combine(a, b, mode))
    assert (q["AA"] == a.drawdown()).all() and (q["BB"] == b.drawdown()).all()


@pytest.mark.parametrize("mode,rising,ab,ba", [
    ("interleave", True, False, False),     # rising: unlifted ends stay down, so the weft passes over them
    ("double", True, False, True),          # top picks pass over the bottom ends; bottom picks pass under the top ends
    ("interleave", False, True, True),      # sinking: unlowered ends stay up
    ("double", False, False, True),
])
def test_the_other_layers_ends_are_held_out_of_the_way_in_a_double_cloth(mode, rising, ab, ba):
    a, b = pair(rising)
    q = quadrants(combine(a, b, mode))
    assert (q["AB"] == ab).all() and (q["BA"] == ba).all()


def test_the_result_has_the_combined_size_and_interleaved_threading():
    a, b = pair()
    out = combine(a, b)
    assert (out.ends, out.picks, out.shafts, out.treadles) == (12, 12, a.shafts + b.shafts, a.treadles + b.treadles)
    assert out.threading[0::2].tolist() == a.threading.tolist()
    assert out.threading[1::2].tolist() == (b.threading + a.shafts).tolist()
    assert not out.liftplan_mode and out.rising


def test_the_tieup_is_two_blocks_and_a_double_cloth_adds_the_layering_lifts():
    a, b = pair()
    plain = combine(a, b, "interleave").tieup
    assert not plain[:a.treadles, a.shafts:].any() and not plain[a.treadles:, :a.shafts].any()
    assert (plain[:a.treadles, :a.shafts] == a.tieup).all() and (plain[a.treadles:, a.shafts:] == b.tieup).all()
    double = combine(a, b, "double").tieup
    assert double[a.treadles:, :a.shafts].all()                      # every bottom treadle lifts the whole top layer
    assert not double[:a.treadles, a.shafts:].any()
    sinking_a, sinking_b = pair(False)
    assert combine(sinking_a, sinking_b, "double").tieup[:a.treadles, a.shafts:].all()


def test_the_shorter_draft_is_repeated_to_match():
    a = patterns.build_preset("plain", 4, 4)
    b = Draft.twill_2_2(ends=8, picks=12)
    out = combine(a, b)
    assert (out.ends, out.picks) == (16, 24)
    assert out.threading[0::2].tolist() == (a.threading[np.arange(8) % 4]).tolist()
    q = quadrants(out)
    assert (q["BB"] == b.drawdown()[np.arange(12) % 12][:, np.arange(8) % 8]).all()
    assert (q["AA"] == a.drawdown()[np.arange(12) % 4][:, np.arange(8) % 4]).all()


def test_unthreaded_ends_stay_unthreaded():
    a, b = pair()
    a.threading[1] = -1
    b.threading[2] = -1
    out = combine(a, b)
    assert out.threading[2] == -1 and out.threading[5] == -1


def test_colours_merge_into_one_palette_and_follow_their_threads():
    a, b = pair()
    b.palette = ["#1f2937", "#00ff00", "#123456"]                    # shares colour 1 with A's default palette
    b.warp_colors[:] = [1, 2] * 3
    b.weft_colors[:] = 2
    a.warp_colors[:] = 1
    out = combine(a, b)
    assert out.palette == ["#1f2937", "#f8fafc", "#00ff00", "#123456"]
    assert out.warp_colors[0::2].tolist() == [1] * 6
    assert out.warp_colors[1::2].tolist() == [2, 3] * 3
    assert out.weft_colors[1::2].tolist() == [3] * 6 and out.weft_colors[0::2].tolist() == a.weft_colors.tolist()


def test_liftplan_drafts_give_a_liftplan_result_with_the_same_cloth():
    a, b = pair()
    a.set_liftplan_mode(True)
    out = combine(a, b, "double")
    assert out.liftplan_mode
    q = quadrants(out)
    assert (q["AA"] == a.drawdown()).all() and (q["BB"] == b.drawdown()).all() and q["BA"].all()


def test_too_many_treadles_falls_back_to_a_liftplan():
    a = Draft.twill_2_2(ends=4, picks=4)
    b = Draft.twill_2_2(ends=4, picks=4)
    a.resize(treadles=20)
    b.resize(treadles=20)
    out = combine(a, b)
    assert out.liftplan_mode and out.treadles == 1
    q = quadrants(out)
    assert (q["AA"] == a.drawdown()).all() and (q["BB"] == b.drawdown()).all()


def test_the_inputs_are_not_changed():
    a, b = pair()
    sa, sb = a.snapshot(), b.snapshot()
    combine(a, b, "double")
    assert (a.tieup == sa.tieup).all() and (b.threading == sb.threading).all() and len(a.palette) == 2


@pytest.mark.parametrize("make,fragment", [
    (lambda: (Draft(shafts=20), Draft(shafts=20), "double"), "needs 40 shafts"),
    (lambda: (Draft(ends=250), Draft(ends=4), "interleave"), "at most 400"),
    (lambda: (Draft(picks=201), Draft(), "interleave"), "at most 400"),
    (lambda: (Draft(), Draft(rising=False), "interleave"), "same shed"),
    (lambda: (Draft(), Draft(), "triple"), "mode must be one of"),
])
def test_combinations_that_cannot_work_are_refused(make, fragment):
    a, b, mode = make()
    with pytest.raises(ValueError, match=fragment):
        combine(a, b, mode)


def test_the_largest_possible_result_is_accepted():
    a = Draft(ends=MAX_ENDS // 2, picks=MAX_ENDS // 2, shafts=16, treadles=16)
    assert combine(a, a).ends == MAX_ENDS
