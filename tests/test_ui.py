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
        if "display" not in str(exc).lower():     # only a missing display is a reason to skip
            raise
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


# ---- colours: palette, strips, stripes ----

def swatch_count(app):
    return len(app.swatch_frame.winfo_children())


def test_palette_swatches_follow_the_draft_and_selecting_one_makes_it_active(app):
    assert swatch_count(app) == 2 and app.active_color == 0
    app.select_color(1)
    assert app.active_color == 1 and "Colour 2" in app.status.cget("text")
    app.select_color(7)                                   # no such colour: ignored
    assert app.active_color == 1


def test_pencil_paints_the_selected_colour_into_the_warp_and_weft_strips(app):
    app.add_color("#ff0000")                              # colour 3, selected
    depth = undo_depth(app)
    press(app, "warp", 2, 0)
    drag_to(app, "warp", 3, 0)
    drag_to(app, "warp", 4, 0)
    release(app, "warp", 4, 0)
    assert app.draft.warp_colors[:6].tolist() == [0, 0, 2, 2, 2, 0]
    assert undo_depth(app) == depth + 1                   # the whole drag is one step
    press(app, "weft", 5, 0)
    release(app, "weft", 5, 0)
    assert app.draft.weft_colors[4:7].tolist() == [1, 2, 1]
    app.on_undo()
    app.on_undo()
    assert app.draft.warp_colors.tolist() == [0] * 16 and app.draft.weft_colors.tolist() == [1] * 16


def test_clicking_a_strip_cell_that_already_has_the_colour_does_not_create_an_undo_step(app):
    depth = undo_depth(app)
    app.select_color(0)
    press(app, "warp", 3, 0)                              # already colour 1
    release(app, "warp", 3, 0)
    assert undo_depth(app) == depth


def test_painting_a_strip_changes_the_cloth_colours_but_not_the_structure(app):
    structure = app.draft.drawdown().copy()
    app.add_color("#ff0000")
    stroke(app, "warp", (0, 0), (15, 0))
    assert (app.draft.drawdown() == structure).all()      # colour never changes which thread is on top
    assert (app.draft.warp_colors == 2).all()


def test_line_tool_paints_a_run_of_the_selected_colour_in_a_strip(app):
    app.add_color("#00ff00")
    app.tool_var.set("line")
    stroke(app, "weft", (2, 0), (5, 0))
    assert app.draft.weft_colors[:8].tolist() == [1, 1, 2, 2, 2, 2, 1, 1]


def test_select_and_repeat_build_stripes_in_the_warp_strip(app):
    app.add_color("#ff0000")
    app.tool_var.set("pencil")
    stroke(app, "warp", (0, 0), (1, 0))                   # ends 1-2 red
    select(app, "warp", (0, 0), (3, 0))                   # ends 1-4: red red base base
    app.on_repeat()
    assert app.draft.warp_colors.tolist() == [2, 2, 0, 0] * 4
    assert app.canvas.find_withtag("selection")           # the overlay works on strips too


def test_flip_and_delete_work_on_a_strip(app):
    app.add_color("#ff0000")
    stroke(app, "warp", (0, 0), (0, 0))                   # only end 1 is red
    select(app, "warp", (0, 0), (3, 0))
    app.on_flip("h")                                      # mirror left-right on screen
    assert app.draft.warp_colors[:4].tolist() == [0, 0, 0, 2]
    app.on_delete()                                       # back to the default warp colour
    assert app.draft.warp_colors[:4].tolist() == [0, 0, 0, 0]


def test_deleting_a_weft_selection_restores_the_default_weft_colour_not_colour_one(app):
    app.select_color(0)
    stroke(app, "weft", (0, 0), (3, 0))                   # weft picks 1-4 painted with colour 1
    assert app.draft.weft_colors[:4].tolist() == [0, 0, 0, 0]
    select(app, "weft", (0, 0), (3, 0))
    app.on_delete()
    assert app.draft.weft_colors[:4].tolist() == [1, 1, 1, 1]


def test_rotating_a_strip_selection_is_refused(app):
    select(app, "warp", (0, 0), (0, 0))
    app.on_rotate()
    assert app.errors and "colour strips" in app.errors[-1]


def test_wrap_shifts_the_warp_colours(app):
    app.add_color("#ff0000")
    stroke(app, "warp", (0, 0), (0, 0))                   # end 1 red; the strip is now the active panel
    app.on_wrap(1, 0)                                     # right on screen = to a lower end number, wrapping
    assert app.draft.warp_colors.tolist() == [0] * 15 + [2]


def test_hovering_a_strip_cell_names_its_colour(app):
    app.draft.set_warp_color(2, 1)
    app.on_hover(at(app, "warp", 2, 0))
    assert "end 3" in app.status.cget("text") and "colour 2" in app.status.cget("text")
    app.on_hover(at(app, "weft", 4, 0))
    assert "pick 5" in app.status.cget("text") and "colour 2" in app.status.cget("text")


def test_add_color_selects_it_adds_a_swatch_and_undoes_in_one_step(app):
    depth = undo_depth(app)
    assert app.add_color("#336699")
    assert app.draft.palette[2] == "#336699" and app.active_color == 2
    assert swatch_count(app) == 3 and undo_depth(app) == depth + 1
    app.on_undo()
    assert len(app.draft.palette) == 2 and app.active_color == 1 and swatch_count(app) == 2


def test_add_color_with_a_bad_value_reports_an_error_and_changes_nothing(app):
    assert not app.add_color("blue")
    assert app.errors and len(app.draft.palette) == 2 and undo_depth(app) == 0


def test_edit_color_recolours_every_thread_that_uses_it(app):
    assert app.edit_color(0, "#ff0000")
    assert app.draft.palette[0] == "#ff0000"
    app.edit_color(0, "#ff0000")                          # unchanged: no extra undo step
    assert undo_depth(app) == 1
    app.on_undo()
    assert app.draft.palette[0] == "#1f2937"


def test_remove_color_reassigns_threads_and_the_last_colour_is_protected(app):
    app.add_color("#ff0000")
    app.draft.warp_colors[:4] = 2
    assert app.remove_color(2)
    assert len(app.draft.palette) == 2 and app.draft.warp_colors[:4].tolist() == [0, 0, 0, 0]
    assert app.remove_color(1)
    depth = undo_depth(app)
    assert not app.remove_color(0)                        # the palette must keep one colour
    assert app.errors and len(app.draft.palette) == 1 and undo_depth(app) == depth


def test_the_palette_has_no_practical_limit(app):
    for i in range(40):
        assert app.add_color(f"#{i * 6:02x}{i * 3:02x}{255 - i:02x}")
    assert len(app.draft.palette) == 42 and swatch_count(app) == 42


def test_stripes_logic_applies_validates_and_undoes_in_one_step(app):
    app.add_color("#ff0000")
    depth = undo_depth(app)
    assert app.stripes("warp", "1:3, 3:1")
    assert app.draft.warp_colors.tolist() == [0, 0, 0, 2] * 4
    assert undo_depth(app) == depth + 1
    assert not app.stripes("warp", "9:2")                 # colour 9 does not exist
    assert not app.stripes("weft", "nonsense")
    assert len(app.errors) == 2 and app.draft.warp_colors.tolist() == [0, 0, 0, 2] * 4
    app.on_undo()
    assert app.draft.warp_colors.tolist() == [0] * 16


def test_a_preset_keeps_the_palette_and_thread_colours(app):
    app.add_color("#ff0000")
    app.stripes("warp", "1:2, 3:2")
    stripes_before = app.draft.warp_colors.copy()
    assert app.apply_preset("satin_5")
    assert len(app.draft.palette) == 3
    assert (app.draft.warp_colors == stripes_before).all()
    app.on_undo()
    assert app.draft.shafts == 4 and (app.draft.warp_colors == stripes_before).all()


# ---- cloth view ----

def test_cloth_view_passes_the_yarn_width_to_the_renderer(app, monkeypatch):
    seen = []
    real = app_module.render_panels
    monkeypatch.setattr(app_module, "render_panels",
                        lambda draft, cell, cloth=None: (seen.append(cloth), real(draft, cell, cloth))[1])
    app._refresh_images()
    assert seen[-1] is None                               # the flat drawdown by default
    app.view_var.set("cloth")
    app._refresh_images()
    assert seen[-1] == pytest.approx(0.85)
    app.yarn_var.set("100")
    app._refresh_images()
    assert seen[-1] == pytest.approx(1.0)


@pytest.mark.parametrize("text,expected", [("60", 0.6), ("5", 0.3), ("250", 1.0), ("abc", 0.85), ("", 0.85)])
def test_yarn_width_is_clamped_and_falls_back_when_unreadable(app, text, expected):
    app.view_var.set("cloth")
    app.yarn_var.set(text)
    assert app._cloth_thickness() == pytest.approx(expected)


def test_switching_views_never_changes_the_draft_or_its_history(app):
    before = app.draft.snapshot()
    depth = undo_depth(app)
    for view in ("cloth", "drawdown", "cloth"):
        app.view_var.set(view)
        app._refresh_images()
    assert undo_depth(app) == depth and (app.draft.threading == before.threading).all()


def test_the_cloth_view_still_lets_you_edit(app):
    app.view_var.set("cloth")
    app._refresh_images()
    press(app, "threading", 0, 3)
    release(app, "threading", 0, 3)
    assert app.draft.threading[0] == 3


def test_export_follows_the_current_view(app, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *a, **k: None)
    flat, woven = tmp_path / "flat.png", tmp_path / "woven.png"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(flat))
    app.on_export()
    app.view_var.set("cloth")
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(woven))
    app.on_export()
    from PIL import Image
    a, b = Image.open(flat), Image.open(woven)
    assert a.size == b.size
    assert len(b.getcolors(maxcolors=1_000_000)) > len(a.getcolors(maxcolors=1_000_000))


def test_the_old_two_colour_pickers_are_gone(app):
    assert not hasattr(app, "warp_color") and not hasattr(app, "on_pick_warp")


# ---- pencil drags: Tk reports sparse motion events, so the pencil must fill the gaps ----

def test_a_fast_pencil_drag_leaves_no_gaps_in_a_strip(app):
    app.add_color("#ff0000")
    press(app, "warp", 1, 0)
    drag_to(app, "warp", 9, 0)                            # one motion event, eight cells away
    release(app, "warp", 9, 0)
    assert app.draft.warp_colors[:11].tolist() == [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0]


def test_a_fast_diagonal_pencil_drag_fills_the_run_in_the_tieup(app):
    app.draft.clear()
    press(app, "tieup", 0, 0)
    drag_to(app, "tieup", 3, 3)
    release(app, "tieup", 3, 3)
    assert [bool(app.draft.tieup[i, i]) for i in range(4)] == [True] * 4


def test_leaving_a_panel_mid_drag_does_not_bridge_the_gap_on_return(app):
    app.add_color("#ff0000")
    press(app, "warp", 1, 0)
    drag_to(app, "warp", 2, 0)
    app.on_drag(at(app, "weft", 3, 0))                    # pointer strays into another panel
    drag_to(app, "warp", 8, 0)                            # ...and comes back far away
    release(app, "warp", 8, 0)
    assert app.draft.warp_colors[:10].tolist() == [0, 2, 2, 0, 0, 0, 0, 0, 2, 0]


# ---- files: WIF open/save, SVG/PDF export, print ----

def wif_file(tmp_path, name="sample.wif"):
    """A WIF file holding a recognisably different draft: 6 ends, 3 picks, 2 shafts, 3 colours."""
    from weavegen.core.draft import Draft
    from weavegen.io import wif
    d = Draft(ends=6, picks=3, shafts=2, treadles=2, rising=False)
    d.threading[:] = [0, 1, 0, 1, 0, 1]
    d.tieup[0, 0] = d.tieup[1, 1] = True
    d.treadling[0, 0] = d.treadling[1, 1] = d.treadling[2, 0] = True
    d.add_palette_color("#336699")
    d.warp_colors[:] = [2, 0, 2, 0, 2, 0]
    path = tmp_path / name
    wif.save(d, path)
    return path, d


def test_opening_a_wif_replaces_the_draft_resizes_the_controls_and_names_the_window(app, tmp_path):
    path, expected = wif_file(tmp_path)
    assert app.open_wif(str(path))
    assert app.draft.threading.tolist() == expected.threading.tolist()
    assert app.draft.palette == expected.palette and app.draft.rising is False
    assert (app.draft.ends, app.draft.picks, app.draft.shafts, app.draft.treadles) == (6, 3, 2, 2)
    assert app.size_vars["ends"].get() == "6" and app.size_vars["shafts"].get() == "2"
    assert app.root.title() == "sample.wif - Weave Generator" and app.file_path == str(path)
    assert swatch_count(app) == 3 and "sample.wif" in app.status.cget("text")


def test_opening_a_wif_is_one_undo_step_that_brings_the_old_draft_back(app, tmp_path):
    before = app.draft.snapshot()
    path, _ = wif_file(tmp_path)
    depth = undo_depth(app)
    app.open_wif(str(path))
    assert undo_depth(app) == depth + 1
    app.on_undo()
    assert app.draft.ends == 16 and (app.draft.threading == before.threading).all()
    assert app.draft.palette == list(before.palette) and swatch_count(app) == 2
    app.on_redo()
    assert app.draft.ends == 6


def test_opening_clears_a_selection_that_no_longer_fits(app, tmp_path):
    select(app, "threading", (10, 0), (14, 3))
    assert app.selection is not None
    path, _ = wif_file(tmp_path)
    app.open_wif(str(path))
    assert app.selection is None


def test_opening_a_file_that_is_not_wif_reports_it_and_changes_nothing(app, tmp_path):
    bad = tmp_path / "bad.wif"
    bad.write_text("this is not a draft", encoding="utf-8")
    before, depth = app.draft.snapshot(), undo_depth(app)
    assert not app.open_wif(str(bad))
    assert app.errors and "bad.wif" in app.errors[-1] and "WIF" in app.errors[-1]
    assert (app.draft.threading == before.threading).all() and undo_depth(app) == depth
    assert app.file_path is None and app.root.title() == "Weave Generator"


def test_opening_a_missing_file_reports_it(app, tmp_path):
    assert not app.open_wif(str(tmp_path / "gone.wif"))
    assert app.errors and "gone.wif" in app.errors[-1]


def test_opening_a_file_with_losses_shows_the_warnings(app, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(app_module.messagebox, "showwarning", lambda title, message, **kw: shown.append(message))
    path = tmp_path / "multi.wif"
    path.write_text("[WIF]\n[WEAVING]\nShafts=3\nTreadles=1\n[WARP]\nThreads=2\n[WEFT]\nThreads=1\n"
                    "[THREADING]\n1=1,2\n2=3\n", encoding="ascii")
    assert app.open_wif(str(path))
    assert len(shown) == 1 and "more than one shaft" in shown[0]
    assert app.draft.threading.tolist() == [0, 2]


def test_a_clean_open_shows_no_warning_dialog(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.messagebox, "showwarning",
                        lambda *a, **k: pytest.fail("no warning expected"))
    path, _ = wif_file(tmp_path)
    app.open_wif(str(path))


def test_on_open_uses_the_file_dialog_and_ignores_cancel(app, tmp_path, monkeypatch):
    path, _ = wif_file(tmp_path)
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: "")
    app.on_open()
    assert app.draft.ends == 16
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: str(path))
    app.on_open()
    assert app.draft.ends == 6


def test_save_asks_for_a_name_once_then_overwrites_the_same_file(app, tmp_path, monkeypatch):
    from weavegen.io import wif
    target = tmp_path / "mine.wif"
    asked = []
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename",
                        lambda **k: asked.append(k) or str(target))
    app.on_save()
    assert len(asked) == 1 and asked[0]["initialfile"] == "weave_draft.wif"
    assert target.exists() and app.file_path == str(target)
    assert app.root.title() == "mine.wif - Weave Generator"
    press(app, "threading", 0, 3)
    release(app, "threading", 0, 3)
    app.on_save()                                         # no dialog the second time
    assert len(asked) == 1
    assert wif.load(target).draft.threading[0] == 3


def test_cancelling_save_as_writes_nothing_and_keeps_the_current_file(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: "")
    app.on_save_as()
    assert app.file_path is None and list(tmp_path.iterdir()) == []


def test_save_as_names_the_draft_after_the_open_file(app, tmp_path, monkeypatch):
    path, _ = wif_file(tmp_path, "cloth.wif")
    app.open_wif(str(path))
    seen = {}
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename",
                        lambda **k: seen.update(k) or "")
    app.on_save_as()
    assert seen["initialfile"] == "cloth.wif" and seen["defaultextension"] == ".wif"


def test_a_failed_save_is_reported_and_does_not_change_the_current_file(app, tmp_path):
    assert not app.save_wif(str(tmp_path / "no_such_folder" / "x.wif"))
    assert app.errors and "x.wif" in app.errors[-1] and app.file_path is None


def test_a_saved_draft_opens_identically_after_the_window_has_changed(app, tmp_path):
    app.add_color("#abcdef")
    app.stripes("warp", "1:3, 3:1")
    app.apply_preset("herringbone")
    path = tmp_path / "round.wif"
    assert app.save_wif(str(path))
    expected = app.draft.snapshot()
    app.on_clear()
    app.open_wif(str(path))
    got = app.draft.snapshot()
    assert (got.threading == expected.threading).all() and (got.tieup == expected.tieup).all()
    assert (got.treadling == expected.treadling).all() and got.palette == expected.palette
    assert (got.warp_colors == expected.warp_colors).all()


def test_the_png_export_suggests_the_open_files_name(app, tmp_path, monkeypatch):
    path, _ = wif_file(tmp_path, "cloth.wif")
    app.open_wif(str(path))
    seen = {}
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: seen.update(k) or "")
    app.on_export()
    assert seen["initialfile"] == "cloth.png"


def test_export_svg_writes_a_vector_file(app, tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    target = tmp_path / "out.svg"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(target))
    app.on_export_svg()
    root = ET.parse(target).getroot()
    assert root.tag.endswith("svg") and "out.svg" in app.status.cget("text")


def test_export_pdf_follows_the_page_size_menu(app, tmp_path, monkeypatch):
    import re
    boxes = {}
    for size in ("a4", "letter"):
        target = tmp_path / f"{size}.pdf"
        app.page_var.set(size)
        monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(target))
        app.on_export_pdf()
        data = target.read_bytes()
        assert data.startswith(b"%PDF-")
        boxes[size] = sorted(float(v) for v in re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", data).groups())
    assert boxes["a4"] == pytest.approx([595.28, 841.89]) and boxes["letter"] == [612.0, 792.0]


def test_cancelling_an_export_writes_nothing(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: "")
    app.on_export_svg()
    app.on_export_pdf()
    assert list(tmp_path.iterdir()) == []


def test_a_failed_export_is_reported(app, tmp_path):
    assert not app.export_svg(str(tmp_path / "missing" / "a.svg"))
    assert not app.export_pdf(str(tmp_path / "missing" / "a.pdf"))
    assert len(app.errors) == 2


def test_print_makes_a_pdf_and_opens_it_in_the_viewer_instead_of_printing_directly(app, monkeypatch):
    import os
    opened = []
    monkeypatch.setattr(app_module, "open_in_viewer", opened.append)
    assert app.print_draft()
    try:
        assert len(opened) == 1 and opened[0].endswith(".pdf")
        with open(opened[0], "rb") as handle:
            assert handle.read(5) == b"%PDF-"
        assert "Print command" in app.status.cget("text")
    finally:
        os.remove(opened[0])


def test_print_reports_when_no_viewer_can_be_opened(app, monkeypatch):
    import os
    tried = []

    def refuse(path):
        tried.append(path)
        raise OSError("no PDF viewer")
    monkeypatch.setattr(app_module, "open_in_viewer", refuse)
    assert not app.print_draft()
    assert app.errors and "no PDF viewer" in app.errors[-1] and "Export PDF" in app.errors[-1]
    assert len(tried) == 1 and not os.path.exists(tried[0])   # no temp file left behind


def test_the_file_menu_offers_the_new_commands_and_shortcuts(app):
    menu = app.root.nametowidget(app.root.cget("menu"))
    file_menu = menu.nametowidget(menu.entrycget(0, "menu"))
    labels = [file_menu.entrycget(i, "label") for i in range(file_menu.index("end") + 1)
              if file_menu.type(i) in ("command", "cascade")]
    for wanted in ("Open WIF...", "Save", "Save as WIF...", "Export PNG...", "Export SVG...",
                   "Export PDF...", "Print...", "PDF page size", "Quit"):
        assert wanted in labels
    assert app.root.bind("<Control-o>") and app.root.bind("<Control-s>")
