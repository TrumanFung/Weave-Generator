import numpy as np
import pytest

from weavegen.core.draft import UNTHREADED, Draft


def test_matrix_shapes_per_panel():
    d = Draft(ends=7, picks=5, shafts=3, treadles=4)
    assert d.matrix("threading").shape == (7, 3)
    assert d.matrix("tieup").shape == (4, 3)
    assert d.matrix("treadling").shape == (5, 4)
    assert d.matrix("liftplan").shape == (5, 3)


def test_threading_matrix_marks_each_ends_shaft():
    d = Draft(ends=3, shafts=3)
    d.set_thread(0, 2)
    d.set_thread(2, 0)
    assert d.matrix("threading").tolist() == [
        [False, False, True],
        [False, False, False],  # unthreaded
        [True, False, False],
    ]


def test_matrix_is_a_copy():
    d = Draft.twill_2_2()
    m = d.matrix("tieup")
    m[:] = False
    assert d.tieup.any()


def test_set_matrix_round_trips_every_panel():
    d = Draft.twill_2_2()
    before = d.snapshot()
    for panel in ("threading", "tieup", "treadling", "liftplan"):
        assert d.set_matrix(panel, d.matrix(panel)) is False
    assert (d.threading == before.threading).all() and (d.tieup == before.tieup).all()


def test_set_matrix_reports_change_and_applies_it():
    d = Draft(ends=2, picks=2, shafts=2, treadles=2)
    m = d.matrix("tieup")
    m[1, 0] = True
    assert d.set_matrix("tieup", m)
    assert d.tieup[1, 0]


def test_threading_matrix_with_several_cells_keeps_the_lowest_shaft():
    d = Draft(ends=2, shafts=4)
    m = np.zeros((2, 4), dtype=bool)
    m[0, 3] = m[0, 1] = True   # two shafts on end 0
    assert d.set_matrix("threading", m)
    assert d.threading.tolist() == [1, UNTHREADED]


def test_set_matrix_rejects_wrong_shape_and_unknown_panel():
    d = Draft(ends=3, shafts=2)
    with pytest.raises(ValueError):
        d.set_matrix("threading", np.zeros((2, 2), dtype=bool))
    with pytest.raises(ValueError):
        d.matrix("drawdown")
