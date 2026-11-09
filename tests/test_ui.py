"""End-to-end checks of the Tkinter app, driven with synthetic mouse events.

These need a display; they skip themselves where Tk cannot open one (e.g. headless CI).
"""

import types

import numpy as np
import pytest

tk = pytest.importorskip("tkinter")

from weavegen.core.layout import Hit  # noqa: E402
from weavegen.ui import app as app_module  # noqa: E402


@pytest.fixture
def app(monkeypatch):
    try:
        application = app_module.WeaveGeneratorApp()
    except tk.TclError as exc:
        pytest.skip(f"no display available: {exc}")
    application.root.withdraw()
    errors: list[str] = []
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda title, message, **kw: errors.append(message))
    application.errors = errors
    application.root.update()
    yield application
    application.root.destroy()


def at(app, panel, a, b):
    x, y = app._cell_center(panel, Hit(panel, a, b))
    return types.SimpleNamespace(x=x, y=y)


def press(app, panel, a, b):
    app.on_press(at(app, panel, a, b))


def drag_to(app, panel, a, b):
    app.on_drag(at(app, panel, a, b))


def release(app, panel, a, b):
    app.on_release(at(app, panel, a, b))


def stroke(app, panel, start, end):
    """Press at one cell, drag to another, release."""
    press(app, panel, *start)
    drag_to(app, panel, *end)
    release(app, panel, *end)


def select(app, panel, start, end):
    app.tool_var.set("select")
    stroke(app, panel, start, end)


def undo_depth(app):
    return len(app.history._undo)


# ---- pencil still works ----

def test_pencil_edit_updates_the_cloth_and_undo_restores(app):
    start = app.draft.drawdown().copy()
    press(app, "threading", 0, 3)
    release(app, "threading", 0, 3)
    assert app.draft.threading[0] == 3
    assert (app.draft.drawdown() != start).any()
    app.on_undo()
    assert app.draft.threading[0] == 0 and (app.draft.drawdown() == start).all()


def test_clicking_the_drawdown_changes_nothing(app):
    grid = app.layout.grid("drawdown")        # not a matrix panel, so click by pixel
    click = types.SimpleNamespace(x=grid.x + 2.5 * grid.cell, y=grid.y + 2.5 * grid.cell)
    assert app.layout.hit(click.x, click.y).panel == "drawdown"
    before = app.draft.snapshot()
    depth = undo_depth(app)
    app.on_press(click)
    app.on_release(click)
    assert undo_depth(app) == depth
    assert (app.draft.threading == before.threading).all() and (app.draft.tieup == before.tieup).all()


# ---- select tool ----

def test_select_tool_selects_a_rectangle_and_draws_an_overlay(app):
    select(app, "tieup", (0, 0), (2, 1))
    panel, rect = app.selection
    assert panel == "tieup" and (rect.r0, rect.r1, rect.c0, rect.c1) == (0, 2, 0, 1)
    assert app.canvas.find_withtag("selection")
    assert undo_depth(app) == 0                       # selecting is not an edit


def test_select_drag_in_either_direction_gives_the_same_rectangle(app):
    select(app, "tieup", (2, 1), (0, 0))
    assert app.selection[1] == app.selection[1].__class__(0, 2, 0, 1)


def test_dragging_out_of_the_panel_keeps_the_last_valid_rectangle(app):
    app.tool_var.set("select")
    press(app, "tieup", 0, 0)
    drag_to(app, "tieup", 1, 1)
    app.on_drag(types.SimpleNamespace(x=-50, y=-50))   # pointer wanders off the draft
    release(app, "tieup", 1, 1)
    assert app.selection[1].r1 == 1 and app.selection[1].c1 == 1


# ---- clipboard ----

def test_copy_and_paste_within_the_tieup(app):
    block = app.draft.tieup[0:2, 0:2].copy()
    select(app, "tieup", (0, 0), (1, 1))
    app.on_copy()
    select(app, "tieup", (0, 2), (0, 2))              # a single cell is the paste target
    before = undo_depth(app)
    app.on_paste()
    assert (app.draft.tieup[0:2, 2:4] == block).all()
    assert undo_depth(app) == before + 1
    assert app.selection[1].height == 2 and app.selection[1].width == 2   # selection follows the paste
    app.on_undo()
    assert not (app.draft.tieup[0:2, 2:4] == block).all()


def test_cut_clears_the_cells_and_paste_brings_them_back(app):
    original = app.draft.tieup.copy()
    select(app, "tieup", (0, 0), (3, 3))
    app.on_cut()
    assert not app.draft.tieup.any()
    app.on_paste()                                    # selection is still the whole tie-up
    assert (app.draft.tieup == original).all()


def test_delete_clears_the_selection_only(app):
    select(app, "tieup", (0, 0), (0, 3))
    app.on_delete()
    assert not app.draft.tieup[0].any() and app.draft.tieup[1:].any()


def test_paste_into_the_wrong_panel_is_refused_without_touching_the_draft(app):
    select(app, "tieup", (0, 0), (1, 1))
    app.on_copy()
    select(app, "treadling", (0, 0), (0, 0))
    before = app.draft.snapshot()
    depth = undo_depth(app)
    app.on_paste()
    assert "tie-up" in app.status.cget("text") or "tieup" in app.status.cget("text")
    assert undo_depth(app) == depth and (app.draft.treadling == before.treadling).all()


def test_clipboard_actions_without_a_selection_explain_what_to_do(app):
    for action in (app.on_copy, app.on_cut, app.on_delete, app.on_rotate, app.on_repeat):
        action()
        assert "Select" in app.status.cget("text")
    app.on_flip("h")
    assert "Select" in app.status.cget("text") and undo_depth(app) == 0
    select(app, "tieup", (0, 0), (0, 0))
    app.clipboard = None
    app.on_paste()
    assert "Nothing to paste" in app.status.cget("text")


# ---- flips, rotate, repeat, wrap ----

def test_flip_horizontal_mirrors_the_ends_on_screen(app):
    app.draft.threading[:4] = [0, 0, 1, 2]
    select(app, "threading", (0, 0), (3, 3))          # ends 1-4, every shaft
    app.on_flip("h")
    assert app.draft.threading[:4].tolist() == [2, 1, 0, 0]


def test_flip_vertical_mirrors_the_shafts_on_screen(app):
    app.draft.threading[:4] = [0, 0, 1, 2]
    select(app, "threading", (0, 0), (3, 3))
    app.on_flip("v")
    assert app.draft.threading[:4].tolist() == [3, 3, 2, 1]


def test_flip_in_the_treadling_uses_screen_axes_too(app):
    app.draft.treadling[:] = False
    app.draft.treadling[0, 0] = True                  # pick 1 on treadle 1
    select(app, "treadling", (0, 0), (1, 3))
    app.on_flip("h")                                  # left-right: treadle 1 becomes treadle 4
    assert app.draft.treadling[0].tolist() == [False, False, False, True]
    app.on_flip("v")                                  # up-down: pick 1 becomes pick 2
    assert app.draft.treadling[1].tolist() == [False, False, False, True]


def test_rotate_a_square_tieup_selection_is_one_undo_step(app):
    before = app.draft.tieup.copy()
    select(app, "tieup", (0, 0), (1, 1))
    depth = undo_depth(app)
    app.on_rotate()
    assert undo_depth(app) == depth + 1
    app.on_undo()
    assert (app.draft.tieup == before).all()


def test_rotate_a_non_square_selection_reports_an_error_and_changes_nothing(app):
    select(app, "tieup", (0, 0), (0, 2))
    depth = undo_depth(app)
    before = app.draft.tieup.copy()
    app.on_rotate()
    assert app.errors and "square" in app.errors[-1]
    assert undo_depth(app) == depth and (app.draft.tieup == before).all()


def test_rotate_threading_is_rejected(app):
    select(app, "threading", (0, 0), (1, 1))
    app.on_rotate()
    assert app.errors and "threading" in app.errors[-1]


def test_repeat_tiles_the_selected_ends_to_the_end_of_the_threading(app):
    app.on_clear()
    for end, shaft in enumerate([0, 2, 1]):
        app.draft.set_thread(end, shaft)
    select(app, "threading", (0, 0), (2, 3))
    app.on_repeat()
    assert app.draft.threading.tolist() == [0, 2, 1] * 5 + [0]


def test_wrap_shifts_the_clicked_panel_around_the_edges(app):
    press(app, "tieup", 0, 0)                          # make the tie-up the active panel (pencil edit)
    release(app, "tieup", 0, 0)
    before = app.draft.tieup.copy()
    app.on_wrap(1, 0)                                  # right on screen = next treadle
    assert (app.draft.tieup == np.roll(before, 1, axis=0)).all()
    app.on_wrap(-1, 0)
    assert (app.draft.tieup == before).all()
    app.on_wrap(0, 1)                                  # down on screen = lower shaft number
    assert (app.draft.tieup == np.roll(before, -1, axis=1)).all()


def test_wrap_without_an_active_panel_explains_itself(app):
    app.on_wrap(1, 0)
    assert "Click in a panel" in app.status.cget("text")


# ---- line tool ----

def test_line_tool_draws_a_diagonal_in_the_tieup_as_one_undo_step(app):
    app.on_clear_tieup()
    app.tool_var.set("line")
    depth = undo_depth(app)
    stroke(app, "tieup", (0, 0), (3, 3))
    assert [bool(app.draft.tieup[i, i]) for i in range(4)] == [True] * 4
    assert app.draft.tieup.sum() == 4
    assert undo_depth(app) == depth + 1
    assert not app.canvas.find_withtag("preview")      # the rubber band is removed on release


def test_line_tool_threads_one_shaft_per_end_and_can_erase(app):
    app.on_clear()
    app.tool_var.set("line")
    stroke(app, "threading", (0, 0), (3, 3))
    assert app.draft.threading[:4].tolist() == [0, 1, 2, 3]
    stroke(app, "threading", (1, 1), (2, 2))           # starts on a set cell, so it erases
    assert app.draft.threading[:4].tolist() == [0, -1, -1, 3]


def test_line_tool_shows_a_preview_while_dragging(app):
    app.tool_var.set("line")
    press(app, "tieup", 0, 0)
    drag_to(app, "tieup", 2, 2)
    assert app.canvas.find_withtag("preview")
    release(app, "tieup", 2, 2)


# ---- generators, tie-ups, presets ----

def test_generate_threading_and_treadling_each_undo_in_one_step(app):
    depth = undo_depth(app)
    assert app.generate("threading", "point")
    assert app.draft.threading[:7].tolist() == [0, 1, 2, 3, 2, 1, 0]
    assert app.generate("treadling", "skip")
    assert [int(np.argmax(r)) for r in app.draft.treadling[:4]] == [0, 2, 1, 3]
    assert undo_depth(app) == depth + 2


def test_generate_advancing_passes_its_parameters(app):
    app.generate("threading", "advancing", run=3, advance=1)
    assert app.draft.threading[:6].tolist() == [0, 1, 2, 1, 2, 3]


def test_generate_with_bad_parameters_reports_an_error(app):
    before = app.draft.threading.copy()
    app.generate("threading", "advancing", run=9, advance=1)
    assert app.errors and (app.draft.threading == before).all()


def test_treadling_generation_is_refused_in_liftplan_mode(app):
    app.liftplan_var.set(True)
    app.on_toggle_liftplan()
    depth = undo_depth(app)
    assert not app.generate("treadling", "straight")
    assert undo_depth(app) == depth


def test_tieup_twill_and_satin_through_the_app(app):
    assert app.tieup_twill(3, 1)
    assert app.draft.tieup.sum(axis=1).tolist() == [3, 3, 3, 3]
    assert not app.tieup_twill(4, 4)                  # needs 8 shafts: reported, not applied
    assert app.errors
    app.on_tieup_plain()
    assert app.draft.tieup[0].tolist() == [True, False, True, False]
    app.on_invert_tieup()
    assert app.draft.tieup[0].tolist() == [False, True, False, True]
    app.on_clear_tieup()
    assert not app.draft.tieup.any()


def test_tieup_actions_are_refused_in_liftplan_mode(app):
    app.liftplan_var.set(True)
    app.on_toggle_liftplan()
    before = app.draft.tieup.copy()
    app.on_tieup_plain()
    app.on_invert_tieup()
    app.on_clear_tieup()
    assert (app.draft.tieup == before).all() and "hidden" in app.status.cget("text")


def test_preset_replaces_the_draft_keeps_the_size_and_the_shed_and_undoes(app):
    app.draft.set_rising(False)
    before = app.draft.snapshot()
    assert app.apply_preset("satin_5")
    d = app.draft
    assert (d.ends, d.picks, d.shafts, d.treadles) == (16, 16, 5, 5)
    assert d.rising is False                           # the user's shed choice survives
    assert app.size_vars["shafts"].get() == "5"
    app.on_undo()
    assert app.draft.shafts == 4 and (app.draft.threading == before.threading).all()
    assert app.draft.rising is False


# ---- selection housekeeping ----

def test_selection_is_dropped_when_it_no_longer_fits(app):
    select(app, "threading", (10, 0), (15, 3))
    app.size_vars["ends"].set("8")
    app.on_apply_size()
    assert app.selection is None
    assert not app.canvas.find_withtag("selection")


def test_selection_in_a_hidden_panel_is_dropped_when_liftplan_mode_toggles(app):
    select(app, "tieup", (0, 0), (1, 1))
    app.liftplan_var.set(True)
    app.on_toggle_liftplan()
    assert app.selection is None
    app.on_wrap(1, 0)                                  # the active panel (tie-up) is hidden too
    assert "Click in a panel" in app.status.cget("text")


def test_selection_survives_a_non_structural_edit(app):
    select(app, "tieup", (0, 0), (1, 1))
    app.generate("threading", "straight")
    assert app.selection is not None


# ---- menus ----

def test_menus_expose_the_new_commands(app):
    menubar = app.root.nametowidget(app.root.cget("menu"))
    labels = [menubar.entrycget(i, "label") for i in range(menubar.index("end") + 1)]
    assert labels == ["File", "Edit", "Draft"]
    edit = app.root.nametowidget(menubar.entrycget(1, "menu"))
    edit_labels = [edit.entrycget(i, "label") for i in range(edit.index("end") + 1)
                   if edit.type(i) != "separator"]
    for expected in ("Cut", "Copy", "Paste", "Flip horizontal", "Flip vertical",
                     "Rotate 90 degrees", "Repeat selection to the end", "Wrap panel"):
        assert expected in edit_labels
