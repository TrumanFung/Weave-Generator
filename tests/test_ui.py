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


def submenu(app, label):
    """The drop-down menu with this title in the menu bar."""
    bar = app.root.nametowidget(app.root.cget("menu"))
    for i in range(bar.index("end") + 1):
        if bar.entrycget(i, "label") == label:
            return bar.nametowidget(bar.entrycget(i, "menu"))
    raise AssertionError(f"no {label} menu")


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
    assert labels == ["File", "Edit", "View", "Draft", "Analysis", "Help"]
    edit = submenu(app, "Edit")
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
                        lambda draft, cell, cloth=None, highlight=None: (seen.append(cloth), real(draft, cell, cloth, highlight))[1])
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
    assert app.file_path is None and app.root.title() == "Untitled - Weave Generator"


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
    file_menu = submenu(app, "File")
    labels = [file_menu.entrycget(i, "label") for i in range(file_menu.index("end") + 1)
              if file_menu.type(i) in ("command", "cascade")]
    for wanted in ("Open WIF...", "Save", "Save as WIF...", "Export PNG...", "Export SVG...",
                   "Export PDF...", "Print...", "PDF page size", "Quit"):
        assert wanted in labels
    assert app.root.bind("<Control-o>") and app.root.bind("<Control-s>")


# ---- analysis: float finder and yardage ----

def analysis_labels(app):
    menubar = app.root.nametowidget(app.root.cget("menu"))
    menu = submenu(app, "Analysis")
    return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) != "separator"]


def drawdown_pixels(app):
    return app_module.render_panels(app.draft, app.layout.cell, app._cloth_thickness(),
                                    app._float_highlight())["drawdown"]


def test_the_analysis_menu_lists_its_commands(app):
    assert analysis_labels(app) == ["Highlight long floats", "Float length limit...", "Floats to show",
                                    "Float report...", "Yardage..."]


def test_floats_are_not_highlighted_until_asked(app):
    app.apply_preset("satin_5")
    assert app._float_highlight() is None
    plain = drawdown_pixels(app).copy()
    app.float_var.set(True)
    app.on_toggle_floats()
    mask = app._float_highlight()
    assert mask is not None and mask.any()
    assert (drawdown_pixels(app) != plain).any()


def test_the_highlight_marks_the_cells_the_float_finder_reports(app):
    from weavegen.core import analysis
    app.apply_preset("satin_5")
    app.float_var.set(True)
    app.on_toggle_floats()
    assert (app._float_highlight() == analysis.float_mask(app.draft, 3)).all()
    assert "floats longer than 3" in app.status.cget("text")


def test_a_draft_without_long_floats_says_so(app):
    app.float_var.set(True)
    app.on_toggle_floats()                                # the default 2/2 twill has floats of 2
    assert not app._float_highlight().any() and "No floats longer than 3" in app.status.cget("text")


def test_the_highlight_follows_edits(app):
    app.apply_preset("satin_5")
    app.float_var.set(True)
    assert app._float_highlight().any()
    app.apply_preset("plain")
    assert not app._float_highlight().any()


def test_changing_the_float_limit_updates_the_highlight_and_rejects_bad_values(app):
    app.apply_preset("satin_5")
    app.float_var.set(True)
    assert app.set_float_limit(4)
    assert app.float_limit == 4 and not app._float_highlight().any()    # satin floats are 4, not longer than 4
    assert app.set_float_limit(2) and app._float_highlight().any()
    depth = len(app.errors)
    assert not app.set_float_limit(0)
    assert app.float_limit == 2 and len(app.errors) == depth + 1


def test_the_limit_dialog_sets_the_limit_and_cancel_keeps_it(app, monkeypatch):
    monkeypatch.setattr(app_module.simpledialog, "askinteger", lambda *a, **k: None)
    app.on_float_limit()
    assert app.float_limit == 3
    seen = {}
    monkeypatch.setattr(app_module.simpledialog, "askinteger", lambda *a, **k: seen.update(k) or 5)
    app.on_float_limit()
    assert app.float_limit == 5 and seen["initialvalue"] == 3 and seen["minvalue"] == 1


def test_the_side_choice_limits_which_floats_are_shown(app):
    from weavegen.core import analysis
    app.apply_preset("satin_5")
    app.float_var.set(True)
    both = app._float_highlight().sum()
    app.float_side_var.set("face")
    assert app._float_sides() == ("face",)
    assert (app._float_highlight() == analysis.float_mask(app.draft, 3, ["face"])).all()
    app.float_side_var.set("back")
    assert app._float_sides() == ("back",)
    assert app._float_highlight().sum() <= both and app._float_highlight().any()


def test_highlighting_changes_neither_the_draft_nor_the_undo_history_nor_the_export(app, tmp_path, monkeypatch):
    from PIL import Image
    app.apply_preset("satin_5")
    snapshot, depth = app.draft.snapshot(), undo_depth(app)
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *a, **k: None)
    out = {}
    for flag in (False, True):
        app.float_var.set(flag)
        app.on_toggle_floats()
        out[flag] = tmp_path / f"{flag}.png"
        monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(out[flag]))
        app.on_export()
    assert undo_depth(app) == depth and (app.draft.threading == snapshot.threading).all()
    assert list(Image.open(out[False]).getdata()) == list(Image.open(out[True]).getdata())


def test_the_float_report_dialog_shows_the_summary(app, monkeypatch):
    shown = []
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda title, message, **k: shown.append((title, message)))
    app.apply_preset("satin_5")
    app.on_float_report()
    assert shown[0][0] == "Float report" and "Longest float in each place" in shown[0][1]
    assert "floats longer than 3" in shown[0][1]


def test_the_highlight_works_in_the_cloth_view(app):
    app.apply_preset("satin_5")
    app.view_var.set("cloth")
    plain = drawdown_pixels(app).copy()
    app.float_var.set(True)
    assert (drawdown_pixels(app) != plain).any()


# ---- yardage window ----

def open_yardage(app):
    app.on_yardage()
    return app._yardage_dialog


def test_the_yardage_window_shows_the_default_project_for_the_current_draft(app):
    dialog = open_yardage(app)
    report = dialog.report
    assert (report.ends, report.picks) == (240, 720) and report.warp_each == pytest.approx(90)
    text = dialog.result.get("1.0", "end")
    assert "Warp: 240 ends of 90.0 in each = 600.00 yd" in text and "#1 #1f2937" in text
    assert dialog.message.cget("text") == ""


def test_changing_an_entry_and_calculating_updates_the_result_and_is_remembered(app):
    dialog = open_yardage(app)
    dialog.vars["width"].set("10")
    dialog.vars["epi"].set("20")
    report = dialog.calculate()
    assert report.ends == 200
    assert app.yardage_settings["width"] == "10" and app.yardage_settings["unit"] == "in"
    dialog.close()
    again = open_yardage(app)
    assert again.vars["width"].get() == "10" and again.vars["epi"].get() == "20"


def test_a_mistake_in_a_field_is_shown_beside_the_form_without_a_popup(app):
    dialog = open_yardage(app)
    dialog.vars["epi"].set("twelve")
    assert dialog.calculate() is None and dialog.report is None
    assert "Ends per in" in dialog.message.cget("text") and "'twelve' is not a number" in dialog.message.cget("text")
    assert dialog.result.get("1.0", "end").strip() == "" and app.errors == []
    dialog.vars["epi"].set("")
    dialog.calculate()
    assert "enter a number" in dialog.message.cget("text")
    dialog.vars["epi"].set("0")
    dialog.calculate()
    assert "greater than 0" in dialog.message.cget("text")
    dialog.vars["epi"].set("12")
    assert dialog.calculate() is not None and dialog.message.cget("text") == ""


def test_switching_to_centimetres_relabels_the_fields_and_reports_metres(app):
    dialog = open_yardage(app)
    assert "(in)" in dialog.labels["width"].cget("text")
    dialog.unit_var.set("cm")
    dialog._relabel()
    assert "(cm)" in dialog.labels["width"].cget("text") and "Ends per cm" in dialog.labels["epi"].cget("text")
    dialog.calculate()
    text = dialog.result.get("1.0", "end")
    assert " m" in text and "yd" not in text and app.yardage_settings["unit"] == "cm"


def test_the_yardage_window_uses_the_drafts_colours(app):
    app.add_color("#c0392b")
    app.stripes("warp", "1:3, 3:1")
    report = open_yardage(app).report
    by = {u.index: u.ends for u in report.colors}
    assert by[0] == 180 and by[2] == 60                   # 240 ends in a 3:1 repeat


def test_opening_yardage_again_reuses_the_window_and_refreshes_it(app):
    first = open_yardage(app)
    app.add_color("#00ff00")
    app.stripes("weft", "3:2, 2:2")
    second = open_yardage(app)
    assert second is first
    assert {u.index for u in second.report.colors} >= {1, 2}
    first.close()
    assert open_yardage(app) is not first


def test_copy_puts_the_report_on_the_clipboard(app):
    dialog = open_yardage(app)
    dialog.copy()
    assert "Total: 1,020.00 yd" in app.root.clipboard_get()
    assert "Yardage copied" in app.status.cget("text")


def test_copy_with_nothing_calculated_does_nothing(app):
    dialog = open_yardage(app)
    dialog.vars["width"].set("x")
    dialog.calculate()
    app.root.clipboard_clear()
    app.root.clipboard_append("keep me")
    dialog.copy()
    assert app.root.clipboard_get() == "keep me"


def test_parse_project_names_the_field_and_converts_numbers():
    from weavegen.ui.yardage_dialog import FIELDS, parse_project
    values = {key: default for key, _label, default in FIELDS}
    project = parse_project(values, "cm")
    assert project.unit == "cm" and project.width == 20 and project.warp_takeup == 10
    with pytest.raises(ValueError, match="Finished width: 'abc' is not a number"):
        parse_project({**values, "width": "abc"}, "in")
    with pytest.raises(ValueError, match="Picks per cm: enter a number"):
        parse_project({**values, "ppi": " "}, "cm")


# ---- advanced drafting: block substitution, combining, network drafting, reduce, image import ----

def dialog_text(dialog):
    return dialog.message.cget("text")


def window_open(dialog):
    return bool(dialog.window.winfo_exists())


def test_the_new_commands_are_in_the_menus(app):
    menubar = app.root.nametowidget(app.root.cget("menu"))
    draft_menu = submenu(app, "Draft")
    labels = [draft_menu.entrycget(i, "label") for i in range(draft_menu.index("end") + 1)
              if draft_menu.type(i) != "separator"]
    for wanted in ("Block substitution...", "Combine drafts...", "Network drafting...",
                   "Reduce to fewest shafts and treadles"):
        assert wanted in labels
    file_menu = submenu(app, "File")
    assert "Import drawdown from image..." in [file_menu.entrycget(i, "label")
                                              for i in range(file_menu.index("end") + 1)
                                              if file_menu.type(i) != "separator"]


# -- block substitution --

def test_block_substitution_previews_the_expanded_draft_for_the_current_profile(app):
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    assert dialog.blocks_var.get() == "4"                           # the twill profile uses blocks 1 to 4
    assert dialog_text(dialog).startswith("Result: 64 ends x 64 picks, 6 shafts, 10 treadles")
    assert "block 1 threading = 1 3 2 3" in dialog.text.get("1.0", "end")
    assert str(dialog.apply_button.cget("state")) == "normal"


def test_applying_block_substitution_replaces_the_draft_in_one_undo_step_and_closes(app):
    before = app.draft.snapshot()
    depth = undo_depth(app)
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    assert dialog.apply()
    assert (app.draft.ends, app.draft.picks, app.draft.shafts, app.draft.treadles) == (64, 64, 6, 10)
    assert app.size_vars["ends"].get() == "64" and app.size_vars["shafts"].get() == "6"
    assert undo_depth(app) == depth + 1 and not window_open(dialog)
    assert "Profile expanded" in app.status.cget("text")
    app.on_undo()
    assert app.draft.ends == 16 and (app.draft.threading == before.threading).all()


def test_changing_the_number_of_blocks_rewrites_the_structure_and_bad_profiles_are_explained(app):
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    dialog.blocks_var.set("2")
    dialog.fill()
    assert "shafts 4" in dialog.text.get("1.0", "end")
    assert "no threading unit for block 3" in dialog_text(dialog)        # the profile uses four blocks
    assert str(dialog.apply_button.cget("state")) == "disabled"
    depth = undo_depth(app)
    assert dialog.apply() is False and app.draft.ends == 16 and undo_depth(app) == depth
    dialog.blocks_var.set("99")
    dialog.fill()
    assert "1 to 15 blocks" in dialog_text(dialog)


def test_editing_the_structure_text_updates_the_result_and_reports_mistakes(app):
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    dialog.set_text("shafts 4\ntreadles 4\ntieup 1 = 1\n"
                    + "".join(f"block {b} threading = {b}\nblock {b} treadling = {b}\n" for b in range(1, 5)))
    dialog.refresh()
    assert dialog_text(dialog).startswith("Result: 16 ends x 16 picks, 4 shafts, 4 treadles")
    dialog.set_text("shafts 4\ntreadles 4\nnonsense")
    dialog.refresh()
    assert "line 3: cannot understand" in dialog_text(dialog) and str(dialog.apply_button.cget("state")) == "disabled"


def test_the_custom_choice_keeps_the_text_the_user_wrote(app):
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    dialog.set_text("# mine\nshafts 4\ntreadles 4\n")
    dialog.family_var.set(dialog.CUSTOM)
    dialog.fill()
    assert dialog.text.get("1.0", "end").startswith("# mine")


def test_block_substitution_reports_what_it_left_out(app):
    app.draft.threading[0] = -1
    app.on_block_substitution()
    dialog = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    assert "1 unthreaded profile end(s) were left out" in dialog_text(dialog)


def test_reopening_a_window_brings_the_same_one_forward_with_fresh_results(app):
    app.on_block_substitution()
    first = app._tool_dialogs[app_module.BlockSubstitutionDialog]
    app.draft.threading[0] = -1
    app.on_block_substitution()
    assert app._tool_dialogs[app_module.BlockSubstitutionDialog] is first
    assert "unthreaded" in dialog_text(first)
    first.close()
    app.on_block_substitution()
    assert app._tool_dialogs[app_module.BlockSubstitutionDialog] is not first


# -- combining drafts --

def test_combining_with_a_preset_previews_and_applies(app):
    app.on_combine()
    dialog = app._tool_dialogs[app_module.CombineDialog]
    assert dialog_text(dialog).startswith("Result: 32 ends x 32 picks, 6 shafts, 6 treadles")    # twill + plain
    dialog.mode_var.set("double")
    depth = undo_depth(app)
    assert dialog.apply()
    d = app.draft
    assert (d.ends, d.picks, d.shafts, d.treadles) == (32, 32, 6, 6) and undo_depth(app) == depth + 1
    assert d.drawdown()[1::2, 0::2].all()                        # a double cloth: the top layer is lifted out of the way
    assert "Drafts combined" in app.status.cget("text")


def test_combining_the_draft_with_a_copy_of_itself_doubles_the_loom(app):
    app.on_combine()
    dialog = app._tool_dialogs[app_module.CombineDialog]
    dialog.source_var.set("current")
    assert dialog_text(dialog).startswith("Result: 32 ends x 32 picks, 8 shafts, 8 treadles")


def test_combining_with_a_wif_file_and_its_mistakes(app, tmp_path):
    from weavegen.core.draft import Draft
    from weavegen.io import wif
    app.on_combine()
    dialog = app._tool_dialogs[app_module.CombineDialog]
    dialog.source_var.set("wif")
    assert "Choose a WIF file" in dialog_text(dialog)
    dialog.path_var.set(str(tmp_path / "missing.wif"))
    assert str(dialog.apply_button.cget("state")) == "disabled" and dialog_text(dialog)
    junk = tmp_path / "junk.wif"
    junk.write_text("nothing useful", encoding="utf-8")
    dialog.path_var.set(str(junk))
    assert "Could not read that WIF file" in dialog_text(dialog)
    good = tmp_path / "good.wif"
    wif.save(Draft.twill_2_2(ends=8, picks=8), good)
    dialog.path_var.set(str(good))
    assert dialog_text(dialog).startswith("Result: 32 ends x 32 picks, 8 shafts, 8 treadles")   # B is repeated to 16
    sinking = tmp_path / "sinking.wif"
    wif.save(Draft(rising=False), sinking)
    dialog.path_var.set(str(sinking))
    assert "same shed" in dialog_text(dialog)


def test_the_browse_button_chooses_the_file(app, tmp_path, monkeypatch):
    app.on_combine()
    dialog = app._tool_dialogs[app_module.CombineDialog]
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: "")
    dialog.browse()
    assert dialog.path_var.get() == "" and dialog.source_var.get() == "preset"
    import weavegen.ui.dialogs as dialogs_module
    monkeypatch.setattr(dialogs_module.filedialog, "askopenfilename", lambda **k: str(tmp_path / "x.wif"))
    dialog.browse()
    assert dialog.path_var.get().endswith("x.wif") and dialog.source_var.get() == "wif"


# -- network drafting --

def test_network_drafting_defaults_to_an_initial_of_four_and_previews(app):
    app.draft.resize(shafts=8, treadles=8)
    app.on_network()
    dialog = app._tool_dialogs[app_module.NetworkDialog]
    assert dialog.initial_var.get() == "4"
    assert dialog_text(dialog).startswith("Result: 16 ends x 16 picks, 8 shafts, 8 treadles")
    assert dialog.lines["thread"].points.get() and dialog.lines["tread"].points.get() == "1"     # level treadling


def test_applying_a_network_threads_on_the_network_and_is_one_undo_step(app):
    app.draft.resize(shafts=8, treadles=8)
    before = app.draft.snapshot()
    depth = undo_depth(app)
    app.on_network()
    dialog = app._tool_dialogs[app_module.NetworkDialog]
    assert dialog.apply()
    d = app.draft
    assert (d.threading % 4 == np.arange(16) % 4).all() and d.treadling.sum(axis=1).tolist() == [1] * 16
    assert undo_depth(app) == depth + 1 and "Network applied" in app.status.cget("text")
    app.on_undo()
    assert (app.draft.threading == before.threading).all() and (app.draft.treadling == before.treadling).all()


def test_changing_the_design_line_shape_rewrites_its_control_points(app):
    app.draft.resize(shafts=8, treadles=8)
    app.on_network()
    dialog = app._tool_dialogs[app_module.NetworkDialog]
    line = dialog.lines["thread"]
    line.kind.set(dialog.KIND_NAMES["point"])
    line.cycles.set("2")
    dialog.preset("thread")
    assert line.points.get() == "1 8 1 8 1"
    line.points.set("1 5 3")
    assert dialog_text(dialog).startswith("Result:")                 # typing points is honoured
    line.points.set("1 five")
    assert "'five' is not a number" in dialog_text(dialog) and str(dialog.apply_button.cget("state")) == "disabled"


def test_a_network_needs_shafts_and_treadles_that_fit_the_initial(app):
    app.on_network()                                                # 4 shafts and 4 treadles: fine
    dialog = app._tool_dialogs[app_module.NetworkDialog]
    dialog.initial_var.set("3")
    assert "multiple of the initial" in dialog_text(dialog)
    dialog.initial_var.set("x")
    assert "whole number" in dialog_text(dialog)
    dialog.initial_var.set("4")
    assert dialog_text(dialog).startswith("Result:")


def test_network_drafting_is_refused_in_liftplan_mode(app):
    app.draft.set_liftplan_mode(True)
    app.on_network()
    assert "liftplan" in dialog_text(app._tool_dialogs[app_module.NetworkDialog])


# -- reduce to fewest shafts and treadles --

def test_reduce_removes_shafts_and_treadles_the_cloth_does_not_need(app):
    app.draft.resize(shafts=8, treadles=8)
    cloth = app.draft.drawdown().copy()
    depth = undo_depth(app)
    assert app.reduce_draft()
    assert (app.draft.shafts, app.draft.treadles) == (4, 4) and (app.draft.drawdown() == cloth).all()
    assert undo_depth(app) == depth + 1 and "Reduced to 4 shafts and 4 treadles (was 8 and 8)" in app.status.cget("text")
    assert app.size_vars["shafts"].get() == "4"
    app.on_undo()
    assert app.draft.shafts == 8


def test_reduce_on_a_minimal_draft_changes_nothing(app):
    depth = undo_depth(app)
    before = app.draft.snapshot()
    assert app.reduce_draft()
    assert undo_depth(app) == depth and (app.draft.threading == before.threading).all()
    assert "already uses as few" in app.status.cget("text")


def test_reduce_keeps_a_liftplan_draft_in_liftplan_mode(app):
    app.draft.resize(shafts=8)
    app.draft.set_liftplan_mode(True)
    assert app.reduce_draft()
    assert app.draft.liftplan_mode and app.draft.shafts == 4 and "Reduced to 4 shafts (was 8)" in app.status.cget("text")


# -- importing a picture of a drawdown --

def drawdown_picture(tmp_path, draft, name="cloth.png"):
    from PIL import Image
    picture = np.where(draft.drawdown()[:, ::-1], 0, 255).astype(np.uint8)
    path = tmp_path / name
    Image.fromarray(picture, "L").save(path)
    return path


def test_importing_a_drawdown_picture_makes_the_smallest_draft_for_it(app, tmp_path):
    from weavegen.core import patterns
    target = patterns.build_preset("satin_5", 20, 20)
    path = drawdown_picture(tmp_path, target)
    app.add_color("#336699")
    palette, depth = list(app.draft.palette), undo_depth(app)
    assert app.import_image(str(path))
    d = app.draft
    assert (d.ends, d.picks, d.shafts, d.treadles) == (20, 20, 5, 5) and (d.drawdown() == target.drawdown()).all()
    assert d.palette == palette and undo_depth(app) == depth + 1
    assert "Imported cloth.png" in app.status.cget("text") and app.size_vars["ends"].get() == "20"
    app.on_undo()
    assert app.draft.shafts == 4 and app.draft.ends == 16


def test_importing_keeps_the_current_shed(app, tmp_path):
    app.draft.set_rising(False)
    path = drawdown_picture(tmp_path, app.draft)
    app.import_image(str(path))
    assert app.draft.rising is False


def test_a_picture_that_cannot_be_used_is_reported_and_changes_nothing(app, tmp_path):
    from PIL import Image
    depth = undo_depth(app)
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not an image")
    assert not app.import_image(str(junk)) and "junk.png is not an image" in app.errors[-1]
    huge = tmp_path / "huge.png"
    Image.new("L", (401, 5), 255).save(huge)
    assert not app.import_image(str(huge)) and "at most 400 x 400" in app.errors[-1]
    noisy = tmp_path / "noisy.png"
    Image.fromarray(np.eye(40, dtype=np.uint8) * 255, "L").save(noisy)
    assert not app.import_image(str(noisy)) and "needs" in app.errors[-1] and "shafts" in app.errors[-1]
    assert not app.import_image(str(tmp_path / "gone.png")) and "gone.png" in app.errors[-1]
    assert undo_depth(app) == depth and app.draft.ends == 16


def test_the_import_command_uses_the_file_dialog_and_ignores_cancel(app, tmp_path, monkeypatch):
    path = drawdown_picture(tmp_path, app.draft)
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: "")
    app.on_import_image()
    assert undo_depth(app) == 0
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: str(path))
    app.on_import_image()
    assert undo_depth(app) == 1


# ---- Phase 7: unsaved changes, new, recent files, settings, shortcuts, help ----
def answers(monkeypatch, *replies):
    """Script the Save / Discard / Cancel question; returns the list of questions asked."""
    asked: list[str] = []
    queue = list(replies)

    def ask(title, message, **kw):
        asked.append(message)
        return queue.pop(0)
    monkeypatch.setattr(app_module.messagebox, "askyesnocancel", ask)
    return asked


def key(app, widget, sequence):
    widget.focus_force()
    app.root.update()
    widget.event_generate(sequence)
    app.root.update()


def test_a_fresh_draft_is_unmodified_and_an_edit_marks_it(app):
    assert not app.is_modified() and app.root.title() == "Untitled - Weave Generator"
    press(app, "threading", 0, 2)
    release(app, "threading", 0, 2)
    assert app.is_modified() and app.root.title() == "*Untitled - Weave Generator"


def test_undoing_back_to_the_saved_state_clears_the_marker(app):
    press(app, "threading", 0, 2)
    release(app, "threading", 0, 2)
    app.on_undo()
    assert not app.is_modified() and not app.root.title().startswith("*")
    app.on_redo()
    assert app.is_modified()


def test_saving_clears_the_marker_and_shows_the_file_name(app, tmp_path):
    app.generate("threading", "point")
    assert app.is_modified()
    assert app.save_wif(str(tmp_path / "a.wif"))
    assert not app.is_modified() and app.root.title() == "a.wif - Weave Generator"
    app.generate("threading", "straight")
    assert app.root.title() == "*a.wif - Weave Generator"


def test_opening_a_file_starts_clean(app, tmp_path):
    other = app_module.Draft.twill_2_2()
    other.set_thread(0, 3)
    from weavegen.io import wif
    wif.save(other, str(tmp_path / "o.wif"))
    app.generate("threading", "point")
    assert app.open_wif(str(tmp_path / "o.wif")) and not app.is_modified()


def test_changing_the_view_or_zoom_is_not_an_unsaved_change(app):
    app.on_toggle_view()
    app.change_zoom(4)
    app.set_float_limit(5)
    assert not app.is_modified()


def test_new_replaces_the_draft_and_can_be_undone(app, tmp_path):
    app.save_wif(str(tmp_path / "a.wif"))
    before = app.draft.snapshot()
    app.new_draft()
    assert app.file_path is None and not app.is_modified()
    assert not app.draft.tieup.any() and not app.draft.treadling.any()
    app.on_undo()
    assert (app.draft.threading == before.threading).all() and app.draft.tieup.any()


def test_new_asks_first_when_there_are_unsaved_changes(app, monkeypatch):
    app.generate("threading", "point")
    changed = app.draft.snapshot()
    asked = answers(monkeypatch, None)                 # Cancel
    app.on_new()
    assert len(asked) == 1 and "this draft" in asked[0]
    assert (app.draft.threading == changed.threading).all() and app.is_modified()
    answers(monkeypatch, False)                        # Discard
    app.on_new()
    assert not app.is_modified() and not app.draft.tieup.any()


def test_new_does_not_ask_when_nothing_changed(app, monkeypatch):
    asked = answers(monkeypatch)
    app.on_new()
    assert asked == []


def test_answering_save_saves_then_carries_on(app, tmp_path, monkeypatch):
    target = tmp_path / "saved.wif"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: str(target))
    app.generate("threading", "point")
    answers(monkeypatch, True)                         # Save
    app.on_new()
    assert target.exists() and not app.is_modified() and app.file_path is None


def test_cancelling_the_save_dialog_cancels_the_action(app, monkeypatch):
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: "")
    app.generate("threading", "point")
    answers(monkeypatch, True)
    app.on_new()
    assert app.is_modified() and app.draft.tieup.any()


def test_the_question_names_the_open_file(app, tmp_path, monkeypatch):
    app.save_wif(str(tmp_path / "named.wif"))
    app.generate("threading", "point")
    asked = answers(monkeypatch, False)
    app.confirm_discard("closing")
    assert "named.wif" in asked[0] and "closing" in asked[0]


def test_open_asks_before_replacing_unsaved_work(app, tmp_path, monkeypatch):
    app.generate("threading", "point")
    monkeypatch.setattr(app_module.filedialog, "askopenfilename", lambda **k: str(tmp_path / "x.wif"))
    opened: list[str] = []
    monkeypatch.setattr(app, "open_wif", lambda path: opened.append(path))
    answers(monkeypatch, None)
    app.on_open()
    assert opened == []
    answers(monkeypatch, False)
    app.on_open()
    assert opened == [str(tmp_path / "x.wif")]


def test_quit_asks_and_cancel_keeps_the_window(app, monkeypatch):
    app.generate("threading", "point")
    answers(monkeypatch, None)
    app.on_quit()
    assert app.root.winfo_exists()


def test_quit_writes_the_settings_and_closes():
    application = app_module.WeaveGeneratorApp()
    application.root.withdraw()
    application.change_zoom(6)
    application.view_var.set("cloth")
    application.page_var.set("letter")
    application.set_float_limit(7)
    application.yardage_settings = {"width": "44"}
    application.on_quit()
    saved = app_module.Settings.load()
    assert saved.get("zoom") == 22 and saved.get("view") == "cloth" and saved.get("page_size") == "letter"
    assert saved.get("float_limit") == 7 and saved.get("yardage") == {"width": "44"}


def test_settings_are_applied_on_the_next_start():
    st = app_module.Settings.load()
    st.set("zoom", 24)
    st.set("view", "cloth")
    st.set("yarn_width", 60)
    st.set("float_side", "face")
    st.set("page_size", "letter")
    st.set("float_limit", 9)
    st.set("yardage", {"width": "50"})
    st.save()
    application = app_module.WeaveGeneratorApp()
    try:
        application.root.withdraw()
        assert application.zoom == 24 and application.view_var.get() == "cloth"
        assert application.yarn_var.get() == "60" and application.float_side_var.get() == "face"
        assert application.page_var.get() == "letter" and application.float_limit == 9
        assert application.yardage_settings == {"width": "50"}
        assert application._cloth_thickness() == 0.6
    finally:
        application.root.destroy()


def test_a_saved_window_position_off_screen_keeps_only_the_size(app):
    screen_w, screen_h = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
    assert app._fit_to_screen("900x700+10+20") == "900x700+10+20"
    assert app._fit_to_screen(f"900x700+{screen_w + 500}+20") == "900x700"
    assert app._fit_to_screen("900x700+-3000+20") == "900x700"
    assert app._fit_to_screen("900x700") == "900x700"
    assert app._fit_to_screen(f"{screen_w + 4000}x{screen_h + 4000}+0+0") == f"{screen_w}x{screen_h}+0+0"
    assert app._fit_to_screen("nonsense") == "nonsense"


def test_recent_files_menu_follows_opens_and_saves(app, tmp_path):
    def entries():
        menu = app.recent_menu
        return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1) if menu.type(i) == "command"]
    assert entries() == ["(none yet)"]
    app.save_wif(str(tmp_path / "one.wif"))
    app.generate("threading", "point")
    app.save_wif(str(tmp_path / "two.wif"))
    assert entries()[:2] == ["1  two.wif", "2  one.wif"] and entries()[-1] == "Clear list"
    app.open_wif(str(tmp_path / "one.wif"))
    assert entries()[0] == "1  one.wif"
    app.on_clear_recent()
    assert entries() == ["(none yet)"] and app.settings.get("recent_files") == []


def test_choosing_a_recent_file_opens_it(app, tmp_path):
    app.save_wif(str(tmp_path / "keep.wif"))
    app.generate("threading", "point")
    app.save_wif(str(tmp_path / "later.wif"))
    app.recent_menu.invoke(1)                       # the second entry: keep.wif
    assert app.file_path == str(tmp_path / "keep.wif")


def test_a_recent_file_that_has_gone_is_dropped(app, tmp_path):
    path = tmp_path / "soon_gone.wif"
    app.save_wif(str(path))
    path.unlink()
    app.on_open_recent(str(path))
    assert app.errors and str(path) not in app.settings.get("recent_files")
    assert app.recent_menu.entrycget(0, "label") == "(none yet)"


def test_file_dialogs_start_in_the_last_folder_used(app, tmp_path, monkeypatch):
    assert app._dialog_dir() == {}
    app.save_wif(str(tmp_path / "a.wif"))
    assert app._dialog_dir() == {"initialdir": str(tmp_path)}
    app.new_draft()
    assert app._dialog_dir() == {"initialdir": str(tmp_path)}      # remembered after New
    seen = {}
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **k: seen.update(k) or "")
    app.on_export_pdf()
    assert seen["initialdir"] == str(tmp_path)


def test_a_last_folder_that_no_longer_exists_is_ignored(app, tmp_path):
    app.settings.set("last_directory", str(tmp_path / "vanished"))
    assert app._dialog_dir() == {}


def test_keyboard_shortcuts_reach_their_commands(app, monkeypatch):
    calls: list[str] = []
    names = ("on_new", "on_open", "on_save", "on_save_as", "on_print", "on_quit", "on_toggle_view", "on_shortcuts")
    for name in names:
        monkeypatch.setattr(app, name, lambda n=name: calls.append(n))
    app._bind_events()                  # the bindings look the methods up when they are made
    app.root.deiconify()
    app.root.update()
    for sequence, expected in (("<Control-n>", "on_new"), ("<Control-o>", "on_open"),
                               ("<Control-s>", "on_save"), ("<Control-S>", "on_save_as"),
                               ("<Control-p>", "on_print"), ("<Control-q>", "on_quit"),
                               ("<Control-k>", "on_toggle_view"), ("<F1>", "on_shortcuts")):
        calls.clear()
        key(app, app.root, sequence)
        assert calls == [expected], sequence


def test_zoom_shortcuts(app):
    app.root.deiconify()
    app.root.update()
    key(app, app.root, "<Control-plus>")
    assert app.zoom == 18
    key(app, app.root, "<Control-minus>")
    key(app, app.root, "<Control-minus>")
    assert app.zoom == 14
    key(app, app.root, "<Control-0>")
    assert app.zoom == app.ZOOM_DEFAULT
    app.reset_zoom()
    assert app.zoom == app.ZOOM_DEFAULT


def test_tool_letters_work_on_the_draft_but_not_in_the_number_boxes(app):
    app.root.deiconify()
    app.root.update()
    key(app, app.canvas, "<KeyPress-l>")
    assert app.tool_var.get() == "line"
    key(app, app.canvas, "<KeyPress-s>")
    assert app.tool_var.get() == "select" and "Drag to select" in app.tool_hint.cget("text")
    key(app, app.canvas, "<KeyPress-p>")
    assert app.tool_var.get() == "pencil"
    key(app, app.canvas, "<KeyPress-l>")
    spin = next(w for w in app.root.winfo_children()[0].winfo_children() if w.winfo_class() == "Spinbox")
    key(app, spin, "<KeyPress-p>")
    assert app.tool_var.get() == "line"


def test_select_all_and_escape(app):
    app.root.deiconify()
    app.root.update()
    press(app, "tieup", 0, 0)
    release(app, "tieup", 0, 0)
    key(app, app.canvas, "<Control-a>")
    panel, rect = app.selection
    assert panel == "tieup" and (rect.height, rect.width) == app.draft.tieup.shape
    key(app, app.root, "<Escape>")
    assert app.selection is None


def test_select_all_defaults_to_the_threading_and_skips_the_drawdown(app):
    app.on_select_all()
    assert app.selection[0] == "threading"
    app.active_panel = "drawdown"
    app.on_select_all()
    assert app.selection[0] == "threading"
    app.liftplan_var.set(True)
    app.on_toggle_liftplan()
    app.on_select_all()
    assert app.selection[0] == "threading"


def test_the_view_shortcut_and_menu_switch_between_drawdown_and_cloth(app):
    app.on_toggle_view()
    assert app.view_var.get() == "cloth" and app._cloth_thickness() is not None
    app.on_toggle_view()
    assert app.view_var.get() == "drawdown" and app._cloth_thickness() is None
    view = submenu(app, "View")
    labels = [view.entrycget(i, "label") for i in range(view.index("end") + 1) if view.type(i) != "separator"]
    assert labels == ["Drawdown", "Cloth", "Switch view", "Zoom in", "Zoom out", "Standard zoom"]
    view.invoke(1)
    assert app.view_var.get() == "cloth"


def test_the_menus_show_the_shortcuts(app):
    def accel(menu_name, label):
        menu = submenu(app, menu_name)
        for i in range(menu.index("end") + 1):
            if menu.type(i) != "separator" and menu.entrycget(i, "label").startswith(label):
                return menu.entrycget(i, "accelerator")
    assert accel("File", "New") == "Ctrl+N" and accel("File", "Save as") == "Ctrl+Shift+S"
    assert accel("File", "Print") == "Ctrl+P" and accel("File", "Quit") == "Ctrl+Q"
    assert accel("Edit", "Select all") == "Ctrl+A" and accel("Help", "Keyboard") == "F1"


def test_every_listed_shortcut_has_an_entry_in_the_help_text():
    from weavegen.ui import help as help_module
    text = help_module.shortcuts_text()
    for _section, rows in help_module.SHORTCUTS:
        for keys, what in rows:
            assert keys in text and what in text


def test_the_help_window_opens_once(app):
    app.on_shortcuts()
    first = app._shortcuts_window
    app.on_shortcuts()
    assert app._shortcuts_window is first and first.window.winfo_exists()
    first.window.destroy()
    app.on_shortcuts()
    assert app._shortcuts_window is not first


def test_about_shows_the_version(app, monkeypatch):
    from weavegen import __version__
    shown = []
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda title, message, **k: shown.append((title, message)))
    app.on_about()
    assert shown and __version__ in shown[0][1] and "About" in shown[0][0]


def test_the_window_has_an_icon_and_the_assets_exist(app):
    from weavegen.ui.help import asset_path
    assert asset_path("icon.png").is_file() and asset_path("icon.ico").is_file()
    assert getattr(app, "_icon", None) is not None


def test_tooltips_appear_on_hover_and_vanish_on_leave(app):
    from weavegen.ui.tooltip import Tooltip
    app.root.deiconify()
    app.root.update()
    tip = Tooltip(app.undo_button, "Undo (Ctrl+Z)")
    tip.show()
    assert tip.visible
    tip.hide()
    assert not tip.visible
    app.undo_button.event_generate("<Enter>")
    app.root.update()
    app.undo_button.event_generate("<Leave>")
    app.root.update()
    assert not tip.visible


# ---- curve tool ----
def big_tieup(app):
    app.draft.resize(shafts=10, treadles=10)
    app.draft.clear()                      # an empty draft, so every mark on screen is the curve's
    app._rebuild()
    app.set_tool("curve")


def hover(app, panel, a, b):
    app.on_hover(at(app, panel, a, b))


def test_the_curve_tool_is_offered_with_a_hint_and_a_key(app):
    assert "curve" in dict(app_module.TOOLS)
    app.root.deiconify()
    app.root.update()
    key(app, app.canvas, "<KeyPress-c>")
    assert app.tool_var.get() == "curve" and "bend" in app.tool_hint.cget("text")


def test_tool_keys_ignore_ctrl_combinations(app, monkeypatch):
    app.root.deiconify()
    app.root.update()
    saved = []
    monkeypatch.setattr(app, "on_save", lambda: saved.append(1))
    app._bind_events()
    for sequence in ("<Control-s>", "<Control-c>", "<Control-l>", "<Control-p>"):
        app.set_tool("pencil")
        key(app, app.canvas, sequence)
        assert app.tool_var.get() == "pencil", sequence
    assert saved == [1]


def test_drag_the_ends_then_click_to_place_the_bend(app):
    big_tieup(app)
    press(app, "tieup", 0, 0)
    drag_to(app, "tieup", 9, 9)
    release(app, "tieup", 9, 9)
    assert app._curve is not None
    assert undo_depth(app) == 0 and not app.draft.tieup.any()          # nothing drawn yet
    assert "bend" in app.status.cget("text")
    hover(app, "tieup", 2, 7)
    assert app.canvas.find_withtag("preview")                          # the pointer shows the curve
    press(app, "tieup", 2, 7)
    release(app, "tieup", 2, 7)
    assert app._curve is None and not app.canvas.find_withtag("preview")
    assert app.draft.tieup[0, 0] and app.draft.tieup[9, 9] and app.draft.tieup.sum() > 10
    assert undo_depth(app) == 1
    app.on_undo()
    assert not app.draft.tieup.any()


def test_the_curve_follows_the_pointer_not_the_first_hover(app):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (0, 9))
    hover(app, "tieup", 1, 4)
    hover(app, "tieup", 7, 4)
    press(app, "tieup", 7, 4)
    release(app, "tieup", 7, 4)
    assert max(int(r) for r, c in zip(*app.draft.tieup.nonzero())) >= 6


def test_a_curve_on_set_cells_erases_them(app):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (9, 9))      # pending
    press(app, "tieup", 0, 9)
    release(app, "tieup", 0, 9)
    assert app.draft.tieup.any()
    start_cells = app.draft.tieup.copy()
    stroke(app, "tieup", (0, 0), (9, 9))      # starts on a set cell: erases
    press(app, "tieup", 0, 9)
    release(app, "tieup", 0, 9)
    assert not (app.draft.tieup & start_cells).any() and undo_depth(app) == 2


def test_escape_cancels_a_curve_in_progress(app):
    big_tieup(app)
    app.root.deiconify()
    app.root.update()
    stroke(app, "tieup", (0, 0), (9, 9))
    hover(app, "tieup", 3, 6)
    app.selection = ("tieup", app_module.Rect(0, 1, 0, 1))
    key(app, app.root, "<Escape>")
    assert app._curve is None and not app.canvas.find_withtag("preview")
    assert app.selection is not None                                    # the first Esc only cancelled the curve
    assert "cancelled" in app.status.cget("text") and undo_depth(app) == 0 and not app.draft.tieup.any()
    key(app, app.root, "<Escape>")
    assert app.selection is None


def test_clicking_outside_the_panel_or_in_another_one_cancels(app):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (9, 9))
    press(app, "threading", 0, 0)
    assert app._curve is None and not app.draft.tieup.any() and "cancelled" in app.status.cget("text")
    assert undo_depth(app) == 0 and app.draft.threading[0] == -1          # the click did not also edit
    stroke(app, "tieup", (0, 0), (9, 9))
    app.on_press(types.SimpleNamespace(x=-50, y=-50))
    assert app._curve is None and undo_depth(app) == 0


def test_a_single_click_with_the_curve_tool_starts_nothing(app):
    big_tieup(app)
    stroke(app, "tieup", (2, 2), (2, 2))
    assert app._curve is None and "one end" in app.status.cget("text") and undo_depth(app) == 0


def test_changing_tool_or_size_drops_the_curve_in_progress(app):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (9, 9))
    app.set_tool("pencil")
    assert app._curve is None
    app.set_tool("curve")
    stroke(app, "tieup", (0, 0), (9, 9))
    app.draft.resize(ends=20)
    app._rebuild()
    assert app._curve is None


def test_moving_the_pointer_over_another_panel_keeps_the_last_preview(app):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (9, 9))
    hover(app, "tieup", 2, 7)
    shown = len(app.canvas.find_withtag("preview"))
    hover(app, "threading", 0, 0)
    assert len(app.canvas.find_withtag("preview")) == shown and app._curve is not None


def test_a_curve_in_the_threading_threads_every_end_it_crosses_once(app):
    app.draft.resize(ends=24, shafts=8)
    app.draft.clear()
    app._rebuild()
    app.set_tool("curve")
    stroke(app, "threading", (0, 0), (23, 0))
    press(app, "threading", 11, 7)
    release(app, "threading", 11, 7)
    threading = [int(s) for s in app.draft.threading]
    assert threading[0] == 0 and threading[-1] == 0 and max(threading) >= 6
    assert (app.draft.matrix("threading").sum(axis=1) == 1).all() and undo_depth(app) == 1


def test_a_curve_in_the_warp_strip_paints_the_selected_colour(app):
    app.add_color("#ff0000")
    app.select_color(2)
    app.set_tool("curve")
    stroke(app, "warp", (1, 0), (8, 0))
    press(app, "warp", 4, 0)
    release(app, "warp", 4, 0)
    assert list(app.draft.warp_colors[1:9]) == [2] * 8


def test_a_curve_error_is_reported_and_the_draft_is_untouched(app, monkeypatch):
    big_tieup(app)
    stroke(app, "tieup", (0, 0), (9, 9))

    def boom(*a, **k):
        raise ValueError("no curve today")
    monkeypatch.setattr(app_module.ops, "draw_curve", boom)
    press(app, "tieup", 2, 7)
    assert app.errors and "no curve today" in app.errors[-1]
    assert app._curve is None and undo_depth(app) == 0 and not app.draft.tieup.any()


def test_curve_is_in_the_shortcut_help():
    from weavegen.ui import help as help_module
    assert "Curve" in help_module.shortcuts_text()
