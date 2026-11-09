import numpy as np
import pytest

from weavegen.core import patterns
from weavegen.core.draft import UNTHREADED, Draft


# ---- sequences ----

def test_straight():
    assert patterns.straight(4, 10) == [0, 1, 2, 3, 0, 1, 2, 3, 0, 1]


def test_point_and_point_with_repeated_ends():
    assert patterns.point(4, 12) == [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1]
    assert patterns.point(4, 10, repeat_ends=True) == [0, 1, 2, 3, 3, 2, 1, 0, 0, 1]
    assert patterns.point(2, 5) == [0, 1, 0, 1, 0]
    assert patterns.point(1, 3) == [0, 0, 0]


def test_advancing_moves_each_run_along_by_the_advance():
    assert patterns.advancing(4, 12, run=3, advance=1) == [0, 1, 2, 1, 2, 3, 2, 3, 0, 3, 0, 1]
    assert patterns.advancing(4, 7, run=2, advance=2) == [0, 1, 2, 3, 0, 1, 2]
    assert len(patterns.advancing(5, 11, run=3)) == 11
    for bad in (0, 5):
        with pytest.raises(ValueError):
            patterns.advancing(4, 8, run=bad)


def test_skip_is_odd_shafts_then_even_shafts():
    assert patterns.skip(4, 8) == [0, 2, 1, 3, 0, 2, 1, 3]
    assert patterns.skip(8, 8) == [0, 2, 4, 6, 1, 3, 5, 7]
    assert patterns.skip(5, 5) == [0, 2, 4, 1, 3]


@pytest.mark.parametrize("kind", ["straight", "point", "point_repeat", "skip"])
def test_every_sequence_stays_within_the_shaft_count_and_has_the_right_length(kind):
    for count in (1, 2, 3, 8):
        seq = patterns.SEQUENCES[kind](count, 37)
        assert len(seq) == 37 and min(seq) >= 0 and max(seq) < count


# ---- applying sequences ----

def test_apply_sequence_to_threading_uses_shafts_and_ends():
    d = Draft(ends=6, picks=3, shafts=3, treadles=2)
    assert patterns.apply_sequence(d, "threading", "point")
    assert d.threading.tolist() == [0, 1, 2, 1, 0, 1]
    assert not patterns.apply_sequence(d, "threading", "point")      # already applied


def test_apply_sequence_to_treadling_uses_treadles_and_picks_one_per_pick():
    d = Draft(ends=3, picks=6, shafts=4, treadles=3)
    d.treadling[:] = True
    assert patterns.apply_sequence(d, "treadling", "straight")
    assert d.treadling.sum(axis=1).tolist() == [1] * 6
    assert [int(np.argmax(r)) for r in d.treadling] == [0, 1, 2, 0, 1, 2]


def test_apply_sequence_passes_parameters_and_validates():
    d = Draft(ends=6, shafts=4)
    patterns.apply_sequence(d, "threading", "advancing", run=3, advance=1)
    assert d.threading.tolist() == [0, 1, 2, 1, 2, 3]
    with pytest.raises(ValueError):
        patterns.apply_sequence(d, "threading", "nonsense")
    with pytest.raises(ValueError):
        patterns.apply_sequence(d, "tieup", "straight")


# ---- tie-ups ----

def test_plain_tieup_and_plain_weave_cloth():
    d = Draft(ends=8, picks=8, shafts=2, treadles=2)
    patterns.apply_sequence(d, "threading", "straight")
    patterns.apply_sequence(d, "treadling", "straight")
    patterns.tieup_plain(d)
    assert d.tieup.tolist() == [[True, False], [False, True]]
    expected = np.array([[(e + p) % 2 == 0 for e in range(8)] for p in range(8)])
    assert (d.drawdown() == expected).all()


def test_plain_tieup_on_more_shafts_lifts_odds_and_evens():
    d = Draft(shafts=6, treadles=3)
    patterns.tieup_plain(d)
    assert d.tieup[0].tolist() == [True, False, True, False, True, False]
    assert d.tieup[1].tolist() == [False, True, False, True, False, True]
    assert not d.tieup[2].any()


def test_twill_tieup_lifts_up_shafts_per_treadle_and_cloth_has_the_right_float():
    d = Draft(ends=12, picks=12, shafts=4, treadles=4)
    patterns.apply_sequence(d, "threading", "straight")
    patterns.apply_sequence(d, "treadling", "straight")
    patterns.tieup_twill(d, 2, 1)             # 2/1 twill on 3 of the 4 shafts
    assert d.tieup.sum(axis=1).tolist() == [2, 2, 2, 0]
    patterns.tieup_twill(d, 3, 1)
    assert d.tieup.sum(axis=1).tolist() == [3, 3, 3, 3]
    # On a 3/1 twill every pick has 3 of every 4 warp ends up.
    assert (d.drawdown().sum(axis=1) == 9).all()


def test_twill_tieup_clears_whatever_was_there_before():
    d = Draft(shafts=4, treadles=4)
    d.tieup[:] = True
    patterns.tieup_twill(d, 1, 1)   # a 1/1 twill (plain weave) on 2 shafts and 2 treadles
    assert d.tieup.tolist() == [
        [True, False, False, False],
        [False, True, False, False],
        [False, False, False, False],   # the old all-True tie-up is gone, not merged
        [False, False, False, False],
    ]


def test_twill_tieup_validates_before_changing_anything():
    d = Draft(shafts=4, treadles=4)
    d.tieup[:] = True
    for up, down in ((0, 2), (2, 0), (3, 3)):
        with pytest.raises(ValueError):
            patterns.tieup_twill(d, up, down)
    assert d.tieup.all()


def test_satin_lifts_one_shaft_per_treadle_with_no_neighbouring_interlacements():
    d = Draft(ends=10, picks=10, shafts=5, treadles=5)
    patterns.apply_sequence(d, "threading", "straight")
    patterns.apply_sequence(d, "treadling", "straight")
    patterns.tieup_satin(d, 2)
    assert d.tieup.sum(axis=1).tolist() == [1] * 5
    assert d.tieup.sum(axis=0).tolist() == [1] * 5            # every shaft used exactly once
    dd = d.drawdown()
    assert (dd.sum(axis=1) == 2).all()                        # one warp end in five is up
    for p in range(9):                                       # the up-ends of adjacent picks never touch
        up_now = set(np.flatnonzero(dd[p]))
        up_next = set(np.flatnonzero(dd[p + 1]))
        assert all(abs(a - b) > 1 for a in up_now for b in up_next)


@pytest.mark.parametrize("shafts,move,ok", [
    (5, 2, True), (5, 3, True), (8, 3, True), (8, 5, True),
    (5, 1, False), (5, 4, False), (8, 2, False), (8, 4, False), (4, 2, False),
])
def test_satin_move_validation(shafts, move, ok):
    d = Draft(shafts=shafts, treadles=shafts)
    if ok:
        patterns.tieup_satin(d, move)
    else:
        with pytest.raises(ValueError):
            patterns.tieup_satin(d, move)


def test_satin_needs_enough_treadles():
    with pytest.raises(ValueError):
        patterns.tieup_satin(Draft(shafts=5, treadles=3), 2)


# ---- presets ----

@pytest.mark.parametrize("key", list(patterns.PRESETS))
def test_every_preset_builds_a_valid_draft_of_the_requested_size(key):
    d = patterns.build_preset(key, ends=30, picks=20)
    assert (d.ends, d.picks) == (30, 20)
    assert (d.threading >= 0).all() and (d.threading < d.shafts).all()
    assert d.tieup.any() and d.treadling.any()
    assert d.drawdown().any() and not d.drawdown().all()      # has both warp and weft on top


def test_twill_2_2_preset_matches_the_builtin_starter_draft():
    built = patterns.build_preset("twill_2_2", ends=16, picks=16)
    starter = Draft.twill_2_2(ends=16, picks=16)
    assert (built.drawdown() == starter.drawdown()).all()


def test_herringbone_reverses_direction_and_diamond_is_symmetrical():
    herring = patterns.build_preset("herringbone", ends=12, picks=12)
    assert herring.threading.tolist() == [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1]
    diamond = patterns.build_preset("diamond", ends=7, picks=7)
    dd = diamond.drawdown()
    assert (dd == dd[::-1, :]).all() or (dd == dd[:, ::-1]).all()


def test_unknown_preset_is_rejected():
    with pytest.raises(ValueError):
        patterns.build_preset("nope")
