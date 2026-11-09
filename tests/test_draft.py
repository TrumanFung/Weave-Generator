import numpy as np
import pytest

from weavegen.core.draft import UNTHREADED, Draft


def test_new_draft_is_blank_with_expected_shapes():
    d = Draft(ends=6, picks=5, shafts=3, treadles=2)
    assert (d.ends, d.picks, d.shafts, d.treadles) == (6, 5, 3, 2)
    assert d.threading.shape == (6,) and (d.threading == UNTHREADED).all()
    assert d.tieup.shape == (2, 3)
    assert d.treadling.shape == (5, 2)
    assert d.liftplan.shape == (5, 3)
    assert d.drawdown().shape == (5, 6)
    assert not d.drawdown().any()  # rising shed, nothing threaded or lifted


@pytest.mark.parametrize("kwargs", [
    dict(ends=0), dict(picks=0), dict(shafts=0), dict(treadles=0),
    dict(shafts=33), dict(treadles=33), dict(ends=401), dict(picks=401),
])
def test_constructor_rejects_out_of_range(kwargs):
    with pytest.raises(ValueError):
        Draft(**kwargs)


def test_twill_2_2_drawdown_matches_the_known_structure():
    d = Draft.twill_2_2(ends=8, picks=8)
    # Pick p presses treadle p%4, tied to shafts p%4 and (p+1)%4; end e sits on shaft e%4.
    expected = np.array([[(e - p) % 4 in (0, 1) for e in range(8)] for p in range(8)])
    assert (d.drawdown() == expected).all()
    # Every pick lifts exactly half the ends: a balanced 2/2 twill.
    assert (d.drawdown().sum(axis=1) == 4).all()


def test_plain_weave_on_two_shafts():
    d = Draft(ends=4, picks=4, shafts=2, treadles=2)
    for e in range(4):
        d.set_thread(e, e % 2)
    d.set_tieup(0, 0, True)
    d.set_tieup(1, 1, True)
    for p in range(4):
        d.set_treadling(p, p % 2, True)
    expected = np.array([[(e + p) % 2 == 0 for e in range(4)] for p in range(4)])
    assert (d.drawdown() == expected).all()


def test_sinking_shed_inverts_the_cloth():
    d = Draft.twill_2_2(ends=8, picks=8)
    rising = d.drawdown()
    assert d.set_rising(False)
    assert (d.drawdown() == ~rising).all()
    assert not d.set_rising(False)


def test_unthreaded_ends_stay_down_when_rising_and_up_when_sinking():
    d = Draft(ends=3, picks=1, shafts=2, treadles=1)
    d.set_thread(0, 0)
    d.set_thread(2, 1)  # end 1 left unthreaded
    d.set_tieup(0, 0, True)
    d.set_tieup(0, 1, True)
    d.set_treadling(0, 0, True)
    assert d.drawdown().tolist() == [[True, False, True]]
    d.set_rising(False)
    assert d.drawdown().tolist() == [[False, True, False]]


def test_several_treadles_on_one_pick_combine_their_lifts():
    d = Draft(ends=4, picks=1, shafts=4, treadles=2)
    for e in range(4):
        d.set_thread(e, e)
    d.set_tieup(0, 0, True)
    d.set_tieup(1, 2, True)
    d.set_treadling(0, 0, True)
    d.set_treadling(0, 1, True)
    assert d.drawdown().tolist() == [[True, False, True, False]]


def test_liftplan_mode_ignores_tieup_and_treadling():
    d = Draft(ends=3, picks=2, shafts=3, treadles=1)
    for e in range(3):
        d.set_thread(e, e)
    d.set_liftplan_mode(True)
    d.set_lift(0, 1, True)
    d.set_lift(1, 2, True)
    assert d.drawdown().tolist() == [[False, True, False], [False, False, True]]


def test_entering_liftplan_mode_preserves_the_cloth():
    d = Draft.twill_2_2(ends=8, picks=8)
    before = d.drawdown().copy()
    assert d.set_liftplan_mode(True)
    assert (d.drawdown() == before).all()
    assert d.liftplan.tolist() == d.lifts().tolist()
    assert d.set_liftplan_mode(False)
    assert (d.drawdown() == before).all()
    assert not d.set_liftplan_mode(False)


def test_mutators_report_whether_anything_changed():
    d = Draft(ends=3, picks=3, shafts=3, treadles=3)
    assert d.set_thread(0, 2) and not d.set_thread(0, 2)
    assert d.set_thread(0, None) and not d.set_thread(0, None)
    assert d.set_tieup(1, 1, True) and not d.set_tieup(1, 1, True)
    assert d.set_treadling(2, 0, True) and not d.set_treadling(2, 0, True)
    assert d.set_lift(0, 2, True) and not d.set_lift(0, 2, True)


@pytest.mark.parametrize("call", [
    lambda d: d.set_thread(-1, 0),   # negative must not wrap around
    lambda d: d.set_thread(3, 0),
    lambda d: d.set_thread(0, 3),
    lambda d: d.set_tieup(3, 0, True),
    lambda d: d.set_treadling(0, 3, True),
    lambda d: d.set_lift(3, 0, True),
])
def test_out_of_range_indices_raise(call):
    with pytest.raises(IndexError):
        call(Draft(ends=3, picks=3, shafts=3, treadles=3))


def test_resize_grows_and_keeps_existing_content():
    d = Draft.twill_2_2(ends=8, picks=8)
    old = d.drawdown().copy()
    assert d.resize(ends=12, picks=10)
    assert (d.ends, d.picks) == (12, 10)
    assert (d.drawdown()[:8, :8] == old).all()
    assert (d.threading[8:] == UNTHREADED).all()
    assert not d.treadling[8:].any()


def test_removing_shafts_unthreads_ends_that_used_them():
    d = Draft.twill_2_2(ends=8, picks=8)
    assert d.resize(shafts=2)
    assert d.shafts == 2 and d.tieup.shape == (4, 2) and d.liftplan.shape == (8, 2)
    assert d.threading.tolist() == [0, 1, -1, -1, 0, 1, -1, -1]


def test_failed_resize_changes_nothing():
    d = Draft.twill_2_2()
    before = d.snapshot()
    with pytest.raises(ValueError):
        d.resize(ends=10, shafts=99)
    assert d.ends == 16 and d.shafts == 4
    assert (d.threading == before.threading).all()


def test_resize_to_same_dimensions_is_a_noop():
    assert not Draft.twill_2_2().resize(ends=16, picks=16, shafts=4, treadles=4)


def test_clear_blanks_everything_and_keeps_dimensions():
    d = Draft.twill_2_2()
    assert d.clear()
    assert (d.ends, d.picks, d.shafts, d.treadles) == (16, 16, 4, 4)
    assert not d.drawdown().any()
    assert not d.clear()


def test_snapshot_is_independent_of_later_edits_and_restores():
    d = Draft.twill_2_2()
    state = d.snapshot()
    d.set_thread(0, 3)
    d.resize(ends=20)
    d.set_rising(False)
    assert state.threading[0] == 0 and state.threading.shape == (16,)
    d.restore(state)
    assert d.ends == 16 and d.threading[0] == 0 and d.rising
    d.set_thread(1, 3)  # restoring must not alias the stored state
    assert state.threading[1] == 1
