from weavegen.core.draft import Draft
from weavegen.core.history import History


def edit(draft: Draft, history: History, end: int, shaft: int) -> None:
    before = draft.snapshot()
    if draft.set_thread(end, shaft):
        history.record(before)


def test_undo_and_redo_round_trip():
    d, h = Draft(ends=4, shafts=4), History()
    edit(d, h, 0, 2)
    edit(d, h, 1, 3)
    assert d.threading[:2].tolist() == [2, 3]

    assert h.undo(d) and d.threading[:2].tolist() == [2, -1]
    assert h.undo(d) and d.threading[:2].tolist() == [-1, -1]
    assert not h.undo(d)

    assert h.redo(d) and d.threading[:2].tolist() == [2, -1]
    assert h.redo(d) and d.threading[:2].tolist() == [2, 3]
    assert not h.redo(d)


def test_new_edit_discards_redo_history():
    d, h = Draft(ends=4, shafts=4), History()
    edit(d, h, 0, 1)
    h.undo(d)
    assert h.can_redo
    edit(d, h, 2, 2)
    assert not h.can_redo


def test_undo_restores_dimensions_too():
    d, h = Draft.twill_2_2(), History()
    before = d.snapshot()
    d.resize(ends=30, shafts=8)
    h.record(before)
    h.undo(d)
    assert (d.ends, d.shafts) == (16, 4)
    h.redo(d)
    assert (d.ends, d.shafts) == (30, 8)


def test_limit_drops_the_oldest_steps():
    d, h = Draft(ends=8, shafts=4), History(limit=3)
    for end in range(5):
        edit(d, h, end, 0)
    undone = 0
    while h.undo(d):
        undone += 1
    assert undone == 3
    assert d.threading[:2].tolist() == [0, 0]  # the two oldest edits were not undoable
