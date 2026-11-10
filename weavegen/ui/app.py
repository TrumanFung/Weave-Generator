"""Tkinter front end. All weaving state, geometry, editing and rendering live in weavegen.core.

The four panels are drawn as images (rendered by core.render) rather than one canvas item
per cell, so drafts of hundreds of ends and picks stay responsive.
"""

from __future__ import annotations

import os
import re
import tempfile
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk  # type: ignore

from weavegen import __version__
from weavegen.core import analysis, fabric, ops, patterns
from weavegen.core.draft import (
    COLOR_PANELS, MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, Draft, DraftState,
)
from weavegen.core.history import History
from weavegen.core.layout import DraftLayout, Hit
from weavegen.core.render import render_panels
from weavegen.core.selection import Rect, display_axis, display_shift_to_matrix, matrix_to_display
from weavegen.io import wif
from weavegen.io.drawdown_image import drawdown_from_image
from weavegen.io.pdf import PAGE_SIZES, save_pdf
from weavegen.io.png import render_draft_image, render_weave_image
from weavegen.settings import Settings
from weavegen.io.svg import save_svg
from weavegen.ui.dialogs import BlockSubstitutionDialog, CombineDialog, NetworkDialog, ToolDialog
from weavegen.ui.help import ShortcutsWindow, about_text, asset_path
from weavegen.ui.tooltip import Tooltip
from weavegen.ui.yardage_dialog import YardageDialog

TOOLS = (("pencil", "Pencil"), ("line", "Line"), ("curve", "Curve"), ("select", "Select"))

# Tk event-state bits for Control and Alt (Mod1 on most systems, 0x20000 on Windows).
CONTROL_ALT_MASK = 0x4 | 0x8 | 0x20000

SEQUENCE_LABELS = (
    ("straight", "Straight draw"),
    ("point", "Point"),
    ("point_repeat", "Point, repeated ends"),
    ("advancing", "Advancing..."),
    ("skip", "Skip"),
)

HIGHLIGHT = "#e11d48"

WIF_TYPES = [("WIF weaving draft", "*.wif"), ("All files", "*.*")]


def open_in_viewer(path: str) -> None:
    """Open a file with the program the system uses for it (a PDF viewer, for a PDF)."""
    if hasattr(os, "startfile"):
        os.startfile(path)  # type: ignore[attr-defined]  # Windows only
    elif not webbrowser.open(Path(path).resolve().as_uri()):
        raise OSError("no program was found to open the file")


@dataclass
class _Stroke:
    """One mouse press-drag-release, undone as a single step."""

    tool: str
    before: DraftState
    panel: str
    paint: bool  # True sets cells (or threads the shaft); False clears them
    start: Hit
    end: Hit
    changed: bool = False
    last: Hit | None = None  # the previous cell of a pencil drag, so fast drags leave no gaps


@dataclass
class _Curve:
    """A curve whose two ends are chosen and whose bend is still being placed."""

    panel: str
    start: Hit
    end: Hit
    paint: bool


class WeaveGeneratorApp:
    ZOOM_MIN = 4
    ZOOM_MAX = 40
    ZOOM_DEFAULT = 16
    MAX_PIXELS = 6000  # cap on the drawn draft's width/height; the effective zoom shrinks to fit

    LABEL_COLOR = "#b45a5a"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else Settings.load()
        self.root = tk.Tk()
        self.root.title("Weave Generator")
        self.root.minsize(760, 600)
        self._set_icon()

        self.draft = Draft.twill_2_2()
        self.history = History()
        self.active_color = 0  # palette index painted into the colour strips
        self._palette_key: tuple | None = None
        self.zoom = self.ZOOM_DEFAULT
        self.file_path: str | None = None  # the WIF file the draft was last opened from or saved to
        self.float_limit = 3  # floats longer than this many threads are highlighted
        self.yardage_settings: dict[str, str] = {}  # the yardage window's entries, kept for the session
        self._yardage_dialog: YardageDialog | None = None
        self._tool_dialogs: dict[type, ToolDialog] = {}  # the open block / combine / network windows

        self.selection: tuple[str, Rect] | None = None  # (panel, cells in matrix coordinates)
        self.clipboard: ops.Clipboard | None = None
        self.active_panel: str | None = None  # the panel last clicked, target of wrap

        self.layout: DraftLayout = DraftLayout.build(self.draft, self.zoom)
        self._stroke: _Stroke | None = None
        self._curve: _Curve | None = None  # a curve waiting for its bend to be placed
        self._photos: dict[str, ImageTk.PhotoImage] = {}  # keep references or Tk drops the images
        self._image_items: dict[str, int] = {}

        self._build_ui()
        self._build_menus()
        self._bind_events()
        self._clean = self.draft.snapshot().fingerprint()  # what "no unsaved changes" looks like
        self._apply_settings()
        self._rebuild()
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

    def _set_icon(self) -> None:
        try:
            self._icon = tk.PhotoImage(file=str(asset_path("icon.png")))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass  # a missing icon is not worth stopping for

    # -----------------
    # UI construction
    # -----------------
    def _build_ui(self) -> None:
        size_bar = tk.Frame(self.root, padx=10, pady=6)
        size_bar.pack(side=tk.TOP, fill=tk.X)

        self.size_vars: dict[str, tk.StringVar] = {}
        for key, label, high in (
            ("ends", "Ends", MAX_ENDS),
            ("picks", "Picks", MAX_PICKS),
            ("shafts", "Shafts", MAX_SHAFTS),
            ("treadles", "Treadles", MAX_TREADLES),
        ):
            tk.Label(size_bar, text=label).pack(side=tk.LEFT, padx=(0, 4))
            var = tk.StringVar()
            self.size_vars[key] = var
            spin = tk.Spinbox(size_bar, from_=1, to=high, width=5, textvariable=var)
            spin.pack(side=tk.LEFT, padx=(0, 12))
            spin.bind("<Return>", lambda _e: self.on_apply_size())
        tk.Button(size_bar, text="Apply", command=self.on_apply_size).pack(side=tk.LEFT)

        self.rising_var = tk.BooleanVar(value=self.draft.rising)
        tk.Checkbutton(size_bar, text="Rising shed", variable=self.rising_var,
                       command=self.on_toggle_rising).pack(side=tk.LEFT, padx=(20, 0))
        self.liftplan_var = tk.BooleanVar(value=self.draft.liftplan_mode)
        tk.Checkbutton(size_bar, text="Liftplan", variable=self.liftplan_var,
                       command=self.on_toggle_liftplan).pack(side=tk.LEFT, padx=(8, 0))

        tool_bar = tk.Frame(self.root, padx=10, pady=2)
        tool_bar.pack(side=tk.TOP, fill=tk.X)

        self.undo_button = tk.Button(tool_bar, text="Undo", command=self.on_undo)
        self.undo_button.pack(side=tk.LEFT)
        self.redo_button = tk.Button(tool_bar, text="Redo", command=self.on_redo)
        self.redo_button.pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(tool_bar, text="Clear", command=self.on_clear).pack(side=tk.LEFT, padx=(12, 0))

        tk.Label(tool_bar, text="Zoom").pack(side=tk.LEFT, padx=(20, 4))
        tk.Button(tool_bar, text="-", width=2, command=lambda: self.change_zoom(-2)).pack(side=tk.LEFT)
        self.zoom_label = tk.Label(tool_bar, width=5)
        self.zoom_label.pack(side=tk.LEFT)
        tk.Button(tool_bar, text="+", width=2, command=lambda: self.change_zoom(2)).pack(side=tk.LEFT)

        export_button = tk.Button(tool_bar, text="Export PNG", command=self.on_export)
        export_button.pack(side=tk.RIGHT)
        Tooltip(export_button, "Save just the woven cloth as a PNG picture "
                               "(the File menu also has the full draft, SVG and PDF)")
        Tooltip(self.undo_button, "Undo (Ctrl+Z)")
        Tooltip(self.redo_button, "Redo (Ctrl+Y)")

        draw_bar = tk.Frame(self.root, padx=10, pady=2)
        draw_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(draw_bar, text="Tool:").pack(side=tk.LEFT, padx=(0, 6))
        self.tool_var = tk.StringVar(value="pencil")
        for key, label in TOOLS:
            button = tk.Radiobutton(draw_bar, text=label, value=key, variable=self.tool_var,
                                    indicatoron=False, width=8, command=self._on_tool_changed)
            button.pack(side=tk.LEFT, padx=(0, 2))
            Tooltip(button, f"{label} tool (press {label[0]} while the draft has focus)")
        self.tool_hint = tk.Label(draw_bar, fg="#6b7280", anchor="w")
        self.tool_hint.pack(side=tk.LEFT, padx=12)

        colour_bar = tk.Frame(self.root, padx=10, pady=2)
        colour_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(colour_bar, text="Colours:").pack(side=tk.LEFT, padx=(0, 6))
        self.swatch_frame = tk.Frame(colour_bar)
        self.swatch_frame.pack(side=tk.LEFT)
        tk.Button(colour_bar, text="Add", command=self.on_add_color).pack(side=tk.LEFT, padx=(8, 2))
        tk.Button(colour_bar, text="Edit", command=self.on_edit_color).pack(side=tk.LEFT, padx=2)
        tk.Button(colour_bar, text="Remove", command=self.on_remove_color).pack(side=tk.LEFT, padx=2)

        tk.Label(colour_bar, text="View:").pack(side=tk.LEFT, padx=(24, 6))
        self.view_var = tk.StringVar(value="drawdown")
        for key, label in (("drawdown", "Drawdown"), ("cloth", "Cloth")):
            button = tk.Radiobutton(colour_bar, text=label, value=key, variable=self.view_var,
                                    indicatoron=False, width=9, command=self._refresh_images)
            button.pack(side=tk.LEFT, padx=(0, 2))
            Tooltip(button, "Flat colour drawdown" if key == "drawdown" else "Shaded woven-cloth picture (Ctrl+K switches)")
        tk.Label(colour_bar, text="Yarn width %").pack(side=tk.LEFT, padx=(10, 4))
        self.yarn_var = tk.StringVar(value="85")
        yarn = tk.Spinbox(colour_bar, from_=30, to=100, increment=5, width=4,
                          textvariable=self.yarn_var, command=self._refresh_images)
        yarn.pack(side=tk.LEFT)
        yarn.bind("<Return>", lambda _e: self._refresh_images())

        self.status = tk.Label(self.root, anchor="w", fg="#6b7280", padx=10)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(self.root, padx=10, pady=4)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg="white", highlightthickness=1,
                                highlightbackground="#d1d5db")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        xbar = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=self.canvas.xview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self._on_tool_changed()

    def _build_menus(self) -> None:
        bar = tk.Menu(self.root, tearoff=0)

        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.on_new)
        file_menu.add_command(label="Open WIF...", accelerator="Ctrl+O", command=self.on_open)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open recent", menu=self.recent_menu)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.on_save)
        file_menu.add_command(label="Save as WIF...", accelerator="Ctrl+Shift+S", command=self.on_save_as)
        file_menu.add_command(label="Import drawdown from image...", command=self.on_import_image)
        file_menu.add_separator()
        file_menu.add_command(label="Export PNG (weave only)...", command=self.on_export)
        file_menu.add_command(label="Export PNG (full draft)...", command=self.on_export_full)
        file_menu.add_command(label="Export SVG...", command=self.on_export_svg)
        file_menu.add_command(label="Export PDF...", command=self.on_export_pdf)
        file_menu.add_command(label="Print...", accelerator="Ctrl+P", command=self.on_print)
        self.page_var = tk.StringVar(value="a4")
        pages = tk.Menu(file_menu, tearoff=0)
        for key in PAGE_SIZES:
            pages.add_radiobutton(label={"a4": "A4", "letter": "US Letter"}[key], value=key,
                                  variable=self.page_var)
        file_menu.add_cascade(label="PDF page size", menu=pages)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator="Ctrl+Q", command=self.on_quit)
        bar.add_cascade(label="File", menu=file_menu)
        self._rebuild_recent_menu()

        edit = tk.Menu(bar, tearoff=0)
        edit.add_command(label="Undo", accelerator="Ctrl+Z", command=self.on_undo)
        edit.add_command(label="Redo", accelerator="Ctrl+Y", command=self.on_redo)
        edit.add_separator()
        edit.add_command(label="Cut", accelerator="Ctrl+X", command=self.on_cut)
        edit.add_command(label="Copy", accelerator="Ctrl+C", command=self.on_copy)
        edit.add_command(label="Paste", accelerator="Ctrl+V", command=self.on_paste)
        edit.add_command(label="Delete", accelerator="Del", command=self.on_delete)
        edit.add_command(label="Select all", accelerator="Ctrl+A", command=self.on_select_all)
        edit.add_separator()
        edit.add_command(label="Flip horizontal", command=lambda: self.on_flip("h"))
        edit.add_command(label="Flip vertical", command=lambda: self.on_flip("v"))
        edit.add_command(label="Rotate 90 degrees", command=self.on_rotate)
        edit.add_command(label="Repeat selection to the end", command=self.on_repeat)
        wrap = tk.Menu(edit, tearoff=0)
        for label, dcol, drow in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            wrap.add_command(label=label, command=lambda c=dcol, r=drow: self.on_wrap(c, r))
        edit.add_cascade(label="Wrap panel", menu=wrap)
        bar.add_cascade(label="Edit", menu=edit)

        view = tk.Menu(bar, tearoff=0)
        view.add_radiobutton(label="Drawdown", value="drawdown", variable=self.view_var,
                             command=self._refresh_images)
        view.add_radiobutton(label="Cloth", value="cloth", variable=self.view_var,
                             command=self._refresh_images)
        view.add_command(label="Switch view", accelerator="Ctrl+K", command=self.on_toggle_view)
        view.add_separator()
        view.add_command(label="Zoom in", accelerator="Ctrl++", command=lambda: self.change_zoom(2))
        view.add_command(label="Zoom out", accelerator="Ctrl+-", command=lambda: self.change_zoom(-2))
        view.add_command(label="Standard zoom", accelerator="Ctrl+0", command=self.reset_zoom)
        bar.add_cascade(label="View", menu=view)

        draft = tk.Menu(bar, tearoff=0)
        for target, label in (("threading", "Threading"), ("treadling", "Treadling")):
            sub = tk.Menu(draft, tearoff=0)
            for kind, text in SEQUENCE_LABELS:
                sub.add_command(label=text, command=lambda t=target, k=kind: self.on_generate(t, k))
            draft.add_cascade(label=f"Generate {label.lower()}", menu=sub)
        tie = tk.Menu(draft, tearoff=0)
        tie.add_command(label="Plain weave", command=self.on_tieup_plain)
        tie.add_command(label="Twill...", command=self.on_tieup_twill)
        tie.add_command(label="Satin...", command=self.on_tieup_satin)
        tie.add_separator()
        tie.add_command(label="Invert tie-up", command=self.on_invert_tieup)
        tie.add_command(label="Clear tie-up", command=self.on_clear_tieup)
        draft.add_cascade(label="Tie-up", menu=tie)
        stripes = tk.Menu(draft, tearoff=0)
        stripes.add_command(label="Warp stripes...", command=lambda: self.on_stripes("warp"))
        stripes.add_command(label="Weft stripes...", command=lambda: self.on_stripes("weft"))
        draft.add_cascade(label="Colour stripes", menu=stripes)
        draft.add_separator()
        presets = tk.Menu(draft, tearoff=0)
        for key, preset in patterns.PRESETS.items():
            presets.add_command(label=preset.label, command=lambda k=key: self.apply_preset(k))
        draft.add_cascade(label="Replace with preset", menu=presets)
        draft.add_separator()
        draft.add_command(label="Block substitution...", command=self.on_block_substitution)
        draft.add_command(label="Combine drafts...", command=self.on_combine)
        draft.add_command(label="Network drafting...", command=self.on_network)
        draft.add_command(label="Reduce to fewest shafts and treadles", command=self.on_reduce)
        bar.add_cascade(label="Draft", menu=draft)

        analysis_menu = tk.Menu(bar, tearoff=0)
        self.float_var = tk.BooleanVar(value=False)
        self.float_side_var = tk.StringVar(value="both")
        analysis_menu.add_checkbutton(label="Highlight long floats", variable=self.float_var,
                                      command=self.on_toggle_floats)
        analysis_menu.add_command(label="Float length limit...", command=self.on_float_limit)
        sides = tk.Menu(analysis_menu, tearoff=0)
        for value, label in (("both", "Face and back"), ("face", "Face only"), ("back", "Back only")):
            sides.add_radiobutton(label=label, value=value, variable=self.float_side_var,
                                  command=self._refresh_images)
        analysis_menu.add_cascade(label="Floats to show", menu=sides)
        analysis_menu.add_command(label="Float report...", command=self.on_float_report)
        analysis_menu.add_separator()
        analysis_menu.add_command(label="Yardage...", command=self.on_yardage)
        bar.add_cascade(label="Analysis", menu=analysis_menu)

        help_menu = tk.Menu(bar, tearoff=0)
        help_menu.add_command(label="Keyboard shortcuts", accelerator="F1", command=self.on_shortcuts)
        help_menu.add_command(label="About Weave Generator", command=self.on_about)
        bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=bar)

    def _bind_events(self) -> None:
        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Motion>", self.on_hover)
        c.bind("<Leave>", lambda _e: self._set_status(""))
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Control-MouseWheel>", lambda e: self.change_zoom(2 if e.delta > 0 else -2))
        self.root.bind("<Control-z>", lambda _e: self.on_undo())
        self.root.bind("<Control-y>", lambda _e: self.on_redo())
        self.root.bind("<Control-Z>", lambda _e: self.on_redo())
        self.root.bind("<Control-n>", lambda _e: self.on_new())
        self.root.bind("<Control-o>", lambda _e: self.on_open())
        self.root.bind("<Control-s>", lambda _e: self.on_save())
        self.root.bind("<Control-S>", lambda _e: self.on_save_as())
        self.root.bind("<Control-p>", lambda _e: self.on_print())
        self.root.bind("<Control-q>", lambda _e: self.on_quit())
        self.root.bind("<Control-k>", lambda _e: self.on_toggle_view())
        self.root.bind("<F1>", lambda _e: self.on_shortcuts())
        self.root.bind("<Escape>", lambda _e: self.on_escape())
        for sequence in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.root.bind(sequence, lambda _e: self.change_zoom(2))
        for sequence in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.root.bind(sequence, lambda _e: self.change_zoom(-2))
        self.root.bind("<Control-0>", lambda _e: self.reset_zoom())
        # Letters and Ctrl+A only act while the draft has focus, so the number boxes still take typing.
        # (Ctrl+S and friends also reach the draft, so a key with Control or Alt held is not a tool key.)
        for key, tool in (("p", "pencil"), ("l", "line"), ("c", "curve"), ("s", "select")):
            c.bind(f"<KeyPress-{key}>",
                   lambda e, t=tool: None if e.state & CONTROL_ALT_MASK else self.set_tool(t))
        c.bind("<Control-a>", lambda _e: self.on_select_all())
        # Clipboard keys only act while the draft has focus, so text fields keep their own copy/paste.
        for sequence, handler in (("<Control-c>", self.on_copy), ("<Control-x>", self.on_cut),
                                  ("<Control-v>", self.on_paste), ("<Delete>", self.on_delete)):
            self.root.bind(sequence, lambda _e, h=handler: h() if self.root.focus_get() is self.canvas else None)

    # -----------------
    # Drawing
    # -----------------
    def _effective_cell(self) -> int:
        d = self.draft
        cols = d.ends + max(d.shafts, d.treadles) + 6
        rows = d.picks + d.shafts + 5
        limit = max(2, self.MAX_PIXELS // max(cols, rows))
        return max(2, min(self.zoom, limit))

    def _rebuild(self) -> None:
        """Re-lay-out and redraw everything. Needed when dimensions, mode or zoom change."""
        self.layout = DraftLayout.build(self.draft, self._effective_cell())
        c = self.canvas
        c.delete("all")
        self._image_items.clear()
        self._curve = None  # a curve in progress belongs to the layout it was started in

        shown = ["threading", "drawdown", "warp", "weft",
                 "liftplan" if self.draft.liftplan_mode else "treadling"]
        if not self.draft.liftplan_mode:
            shown.append("tieup")
        for name in shown:
            grid = self.layout.grid(name)
            self._image_items[name] = c.create_image(grid.x, grid.y, anchor="nw")

        for label in self.layout.labels():
            c.create_text(label.x, label.y, text=label.text, anchor=label.anchor,
                          fill=self.LABEL_COLOR, font=("Segoe UI", 8))

        c.configure(scrollregion=(0, 0, self.layout.width, self.layout.height))
        self._drop_stale_selection()
        self._refresh_images()
        self._draw_selection()
        self._sync_controls()

    def _refresh_images(self) -> None:
        """Re-render the panel pixels only; the layout is unchanged."""
        panels = render_panels(self.draft, self.layout.cell, self._cloth_thickness(),
                               self._float_highlight())
        for name, pixels in panels.items():
            photo = ImageTk.PhotoImage(Image.fromarray(pixels))
            self._photos[name] = photo
            self.canvas.itemconfigure(self._image_items[name], image=photo)

    # ---- analysis ----
    def _float_sides(self) -> tuple[str, ...]:
        side = self.float_side_var.get()
        return analysis.SIDES if side == "both" else (side,)

    def _float_highlight(self):
        """The cells to shade as long floats, or None while the highlight is off."""
        if not self.float_var.get():
            return None
        return analysis.float_mask(self.draft, self.float_limit, self._float_sides())

    def on_toggle_floats(self) -> None:
        self._refresh_images()
        if self.float_var.get():
            report = analysis.analyse_floats(self.draft, self.float_limit, self._float_sides())
            count = len(report.floats)
            self._set_status(f"{count} float{'s' if count != 1 else ''} longer than {self.float_limit} "
                             "shown in red on the drawdown." if count else
                             f"No floats longer than {self.float_limit}.")

    def set_float_limit(self, limit: int) -> bool:
        """Choose how many threads a float may cross before it is highlighted (1 to 400)."""
        try:
            analysis.float_mask(self.draft, limit)  # validates the number
        except ValueError as exc:
            self._error(str(exc))
            return False
        self.float_limit = int(limit)
        self._refresh_images()
        return True

    def on_float_limit(self) -> None:
        limit = simpledialog.askinteger(
            "Float length limit", "Highlight floats longer than this many threads:",
            parent=self.root, initialvalue=self.float_limit, minvalue=1, maxvalue=MAX_ENDS)
        if limit is not None:
            self.set_float_limit(limit)

    def float_report(self) -> analysis.FloatReport:
        return analysis.analyse_floats(self.draft, self.float_limit, self._float_sides())

    def on_float_report(self) -> None:
        messagebox.showinfo("Float report", analysis.describe(self.float_report()))

    def on_yardage(self) -> None:
        if self._yardage_dialog is not None and self._yardage_dialog.window.winfo_exists():
            self._yardage_dialog.window.lift()
            self._yardage_dialog.calculate()  # the draft's colours may have changed
            return
        self._yardage_dialog = YardageDialog(self)

    def _cloth_thickness(self) -> float | None:
        """The yarn width (0 to 1) when the cloth view is on, or None for the flat drawdown."""
        if self.view_var.get() != "cloth":
            return None
        try:
            percent = float(self.yarn_var.get())
        except ValueError:
            percent = 85.0
        return max(30.0, min(100.0, percent)) / 100.0

    def _sync_palette(self) -> None:
        """Redraw the colour swatches when the palette or the selected colour changed."""
        palette = tuple(self.draft.palette)
        self.active_color = max(0, min(self.active_color, len(palette) - 1))
        key = (palette, self.active_color)
        if key == self._palette_key:
            return
        self._palette_key = key
        for child in self.swatch_frame.winfo_children():
            child.destroy()
        for index, color in enumerate(palette):
            active = index == self.active_color
            red, green, blue = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            dark = (0.299 * red + 0.587 * green + 0.114 * blue) < 140
            swatch = tk.Label(self.swatch_frame, text=str(index + 1), width=3, bg=color,
                              fg="white" if dark else "black", cursor="hand2",
                              relief=tk.SUNKEN if active else tk.RAISED, bd=4 if active else 2)
            swatch.grid(row=index // 12, column=index % 12, padx=1, pady=1)
            swatch.bind("<Button-1>", lambda _e, i=index: self.select_color(i))

    def _sync_controls(self) -> None:
        d = self.draft
        for key, value in (("ends", d.ends), ("picks", d.picks),
                           ("shafts", d.shafts), ("treadles", d.treadles)):
            self.size_vars[key].set(str(value))
        self.rising_var.set(d.rising)
        self.liftplan_var.set(d.liftplan_mode)
        self._sync_palette()
        self._update_title()
        self.undo_button.configure(state=tk.NORMAL if self.history.can_undo else tk.DISABLED)
        self.redo_button.configure(state=tk.NORMAL if self.history.can_redo else tk.DISABLED)
        shown = self.layout.cell
        note = "" if shown == self.zoom else f"(shown at {shown}px)"
        self.zoom_label.configure(text=f"{self.zoom}px")
        self._set_status(note)

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _error(self, message: str) -> None:
        messagebox.showerror("Can't do that", message)

    # -----------------
    # Selection overlay
    # -----------------
    def _drop_stale_selection(self) -> None:
        """Forget a selection or active panel that no longer exists (resized, mode switched)."""
        if self.selection is not None:
            panel, rect = self.selection
            if panel not in self._image_items or not rect.fits(self.draft.matrix(panel).shape):
                self.selection = None
        if self.active_panel not in self._image_items:
            self.active_panel = None

    def _draw_selection(self) -> None:
        self.canvas.delete("selection")
        if self.selection is None:
            return
        panel, rect = self.selection
        r0, c0, r1, c1 = matrix_to_display(self.draft, panel, rect)
        grid = self.layout.grid(panel)
        cell = grid.cell
        self.canvas.create_rectangle(
            grid.x + c0 * cell, grid.y + r0 * cell,
            grid.x + (c1 + 1) * cell, grid.y + (r1 + 1) * cell,
            outline=HIGHLIGHT, width=2, dash=(4, 3), tags="selection",
        )

    def _cell_center(self, panel: str, hit: Hit) -> tuple[float, float]:
        r, c, _, _ = matrix_to_display(self.draft, panel, Rect(hit.a, hit.a, hit.b, hit.b))
        grid = self.layout.grid(panel)
        return grid.x + (c + 0.5) * grid.cell, grid.y + (r + 0.5) * grid.cell

    def _draw_preview(self, stroke: _Stroke) -> None:
        self.canvas.delete("preview")
        x0, y0 = self._cell_center(stroke.panel, stroke.start)
        x1, y1 = self._cell_center(stroke.panel, stroke.end)
        self.canvas.create_line(x0, y0, x1, y1, fill=HIGHLIGHT, width=2, tags="preview")

    def _on_tool_changed(self) -> None:
        hints = {
            "pencil": "Click or drag to set or clear cells; in the colour strips it paints the selected colour.",
            "line": "Drag to draw a straight line.",
            "curve": "Drag from one end of the curve to the other, then move the pointer to bend it and click.",
            "select": "Drag to select cells, then use the Edit menu (copy, flip, repeat...).",
        }
        self._cancel_curve()
        self.tool_hint.configure(text=hints[self.tool_var.get()])

    def set_tool(self, tool: str) -> None:
        if tool in dict(TOOLS):
            self.tool_var.set(tool)
            self._on_tool_changed()

    # ---- the curve tool: drag the two ends, then place the bend ----
    def _begin_curve(self, stroke: _Stroke) -> None:
        if (stroke.start.a, stroke.start.b) == (stroke.end.a, stroke.end.b):
            self._set_status("Drag from one end of the curve to the other.")
            return
        self._curve = _Curve(stroke.panel, stroke.start, stroke.end, stroke.paint)
        self._set_status("Now move the pointer to bend the curve and click to place it. Esc cancels.")

    def _draw_curve_preview(self, curve: _Curve, through: Hit) -> None:
        self.canvas.delete("preview")
        points: list[float] = []
        for a, b in ops.curve_cells((curve.start.a, curve.start.b), (curve.end.a, curve.end.b),
                                    (through.a, through.b)):
            x, y = self._cell_center(curve.panel, Hit(curve.panel, a, b))
            points += [x, y]
        if len(points) >= 4:
            self.canvas.create_line(*points, fill=HIGHLIGHT, width=2, tags="preview")
        x, y = self._cell_center(curve.panel, through)
        self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=HIGHLIGHT, width=2, tags="preview")

    def _cancel_curve(self, message: str | None = None) -> None:
        if self._curve is not None:
            self._curve = None
            self.canvas.delete("preview")
            if message:
                self._set_status(message)

    def _finish_curve(self, hit: Hit | None) -> None:
        """The click that places the bend: draw the curve through it as one undo step."""
        curve = self._curve
        if curve is None:
            return
        if hit is None or hit.panel != curve.panel:
            self._cancel_curve(f"Curve cancelled: click inside the {curve.panel} to place the bend.")
            return
        before = self.draft.snapshot()
        try:
            changed = ops.draw_curve(
                self.draft, curve.panel, (curve.start.a, curve.start.b), (curve.end.a, curve.end.b),
                (hit.a, hit.b), curve.paint,
                value=self.active_color if curve.panel in COLOR_PANELS else 1)
        except (ValueError, IndexError) as exc:
            self._cancel_curve()
            self._error(str(exc))
            return
        self._cancel_curve()
        if changed:
            self.history.record(before)
            self._refresh_images()
            self._sync_controls()

    def on_escape(self) -> None:
        if self._curve is not None:
            self._cancel_curve("Curve cancelled.")
        else:
            self.clear_selection()

    def clear_selection(self) -> None:
        if self.selection is not None:
            self.selection = None
            self._draw_selection()

    def on_select_all(self) -> str:
        """Select every cell of the panel last clicked in (the threading if none was)."""
        panel = self.active_panel if self.active_panel not in (None, "drawdown") else "threading"
        if panel not in self._image_items:
            return "break"
        rows, cols = self.draft.matrix(panel).shape
        self.active_panel = panel
        self.selection = (panel, Rect(0, rows - 1, 0, cols - 1))
        self._draw_selection()
        self._set_status(f"Selected the whole {panel}.")
        return "break"

    def on_toggle_view(self) -> None:
        self.view_var.set("drawdown" if self.view_var.get() == "cloth" else "cloth")
        self._refresh_images()

    def reset_zoom(self) -> None:
        self.change_zoom(self.ZOOM_DEFAULT - self.zoom)

    # -----------------
    # Mouse editing
    # -----------------
    def _canvas_xy(self, event: tk.Event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _paint_for(self, panel: str, a: int, b: int) -> bool:
        """What a press on this cell should do: set it (True) or clear it (False)."""
        d = self.draft
        if panel in COLOR_PANELS:
            return True  # colour strips always paint the selected colour
        if panel == "threading":
            return int(d.threading[a]) != b
        if panel == "tieup":
            return not d.tieup[a, b]
        if panel == "treadling":
            return not d.treadling[a, b]
        return not d.liftplan[a, b]

    def _apply(self, panel: str, a: int, b: int, paint: bool) -> bool:
        d = self.draft
        if panel == "warp":
            return d.set_warp_color(a, self.active_color)
        if panel == "weft":
            return d.set_weft_color(a, self.active_color)
        if panel == "threading":
            return d.set_thread(a, b if paint else None)
        if panel == "tieup":
            return d.set_tieup(a, b, paint)
        if panel == "treadling":
            return d.set_treadling(a, b, paint)
        return d.set_lift(a, b, paint)

    def on_press(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        hit = self.layout.hit(*self._canvas_xy(event))
        if self._curve is not None:       # this click places the bend of the curve being drawn
            self._finish_curve(hit)
            return
        if hit is None or hit.panel == "drawdown":  # the drawdown is derived, not edited
            return
        self.active_panel = hit.panel
        tool = self.tool_var.get()
        stroke = _Stroke(tool, self.draft.snapshot(), hit.panel, self._paint_for(*hit), hit, hit)
        self._stroke = stroke
        if tool == "pencil":
            stroke.last = hit
            if self._apply(hit.panel, hit.a, hit.b, stroke.paint):
                stroke.changed = True
                self._refresh_images()
        elif tool == "select":
            self.selection = (hit.panel, Rect.spanning((hit.a, hit.b), (hit.a, hit.b)))
            self._draw_selection()
        # The line and curve tools wait for the drag and release.

    def on_drag(self, event: tk.Event) -> None:
        stroke = self._stroke
        if stroke is None:
            return
        hit = self.layout.hit(*self._canvas_xy(event))
        if hit is None or hit.panel != stroke.panel:
            stroke.last = None  # leaving the panel breaks the stroke; coming back starts afresh
            return
        if stroke.tool == "pencil":
            # Tk only reports where the pointer happens to be, so a fast drag can skip cells:
            # fill the straight run between the previous cell and this one.
            previous = stroke.last if stroke.last is not None else hit
            changed = False
            for a, b in ops.line_cells((previous.a, previous.b), (hit.a, hit.b)):
                changed |= self._apply(hit.panel, a, b, stroke.paint)
            stroke.last = hit
            if changed:
                stroke.changed = True
                self._refresh_images()
            return
        stroke.end = hit
        if stroke.tool == "select":
            self.selection = (stroke.panel, Rect.spanning((stroke.start.a, stroke.start.b),
                                                          (hit.a, hit.b)))
            self._draw_selection()
        else:
            self._draw_preview(stroke)

    def on_release(self, _event: tk.Event) -> None:
        stroke, self._stroke = self._stroke, None
        self.canvas.delete("preview")
        if stroke is None:
            return
        if stroke.tool == "line":
            try:
                if ops.draw_line(self.draft, stroke.panel, (stroke.start.a, stroke.start.b),
                                 (stroke.end.a, stroke.end.b), stroke.paint,
                                 value=self.active_color if stroke.panel in COLOR_PANELS else 1):
                    stroke.changed = True
                    self._refresh_images()
            except (ValueError, IndexError) as exc:
                self._error(str(exc))
                return
        if stroke.tool == "curve":
            self._begin_curve(stroke)
            return
        if stroke.changed:
            self.history.record(stroke.before)
            self._sync_controls()

    def on_hover(self, event: tk.Event) -> None:
        hit = self.layout.hit(*self._canvas_xy(event))
        curve = self._curve
        if curve is not None:             # while a curve waits for its bend, the pointer shapes it
            if hit is not None and hit.panel == curve.panel:
                self._draw_curve_preview(curve, hit)
            self._set_status("Move the pointer to bend the curve, then click to place it. Esc cancels.")
            return
        if hit is None:
            self._set_status("")
            return
        text = {
            "warp": f"Warp colour: end {hit.a + 1} (colour {int(self.draft.warp_colors[hit.a]) + 1})",
            "weft": f"Weft colour: pick {hit.a + 1} (colour {int(self.draft.weft_colors[hit.a]) + 1})",
            "threading": f"Threading: end {hit.a + 1}, shaft {hit.b + 1}",
            "tieup": f"Tie-up: treadle {hit.a + 1}, shaft {hit.b + 1}",
            "treadling": f"Treadling: pick {hit.a + 1}, treadle {hit.b + 1}",
            "liftplan": f"Liftplan: pick {hit.a + 1}, shaft {hit.b + 1}",
            "drawdown": f"Drawdown: pick {hit.a + 1}, end {hit.b + 1} "
                        "(computed; edit the threading, tie-up or treadling)",
        }[hit.panel]
        self._set_status(text)

    # -----------------
    # Whole-draft edits
    # -----------------
    def _edit(self, change, *, relayout: bool = False) -> None:
        """Run a whole-draft change as one undo step."""
        before = self.draft.snapshot()
        if change():
            self.history.record(before)
        if relayout:
            self._rebuild()
        else:
            self._refresh_images()
            self._sync_controls()

    def _try_edit(self, change, *, relayout: bool = False) -> bool:
        """Like _edit, but reports ValueError/IndexError from the core to the user."""
        try:
            self._edit(change, relayout=relayout)
        except (ValueError, IndexError) as exc:
            self._error(str(exc))
            return False
        return True

    def _need_selection(self) -> tuple[str, Rect] | None:
        if self.selection is None:
            self._set_status("Choose the Select tool and drag over some cells first.")
            return None
        return self.selection

    def _tieup_visible(self) -> bool:
        if self.draft.liftplan_mode:
            self._set_status("The tie-up is hidden in liftplan mode.")
            return False
        return True

    # ---- clipboard and selection operations ----
    def on_copy(self) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        try:
            self.clipboard = ops.copy(self.draft, panel, rect)
        except ValueError as exc:
            self._error(str(exc))
            return
        self._set_status(f"Copied {rect.height} x {rect.width} cells from the {panel}.")

    def on_cut(self) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        self.on_copy()
        self._try_edit(lambda: ops.clear(self.draft, panel, rect))

    def on_delete(self) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        self._try_edit(lambda: ops.clear(self.draft, panel, rect))

    def on_paste(self) -> None:
        clip = self.clipboard
        if clip is None:
            self._set_status("Nothing to paste yet: select cells and copy them first.")
            return
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        if panel != clip.panel:
            self._set_status(f"Those cells came from the {clip.panel}; select a cell in the "
                             f"{clip.panel} to paste into.")
            return
        if self._try_edit(lambda: ops.paste(self.draft, clip, panel, rect.r0, rect.c0)):
            rows, cols = self.draft.matrix(panel).shape
            h = min(clip.data.shape[0], rows - rect.r0)
            w = min(clip.data.shape[1], cols - rect.c0)
            self.selection = (panel, Rect(rect.r0, rect.r0 + h - 1, rect.c0, rect.c0 + w - 1))
            self._draw_selection()

    def on_flip(self, direction: str) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        axis = display_axis(panel, direction)
        self._try_edit(lambda: ops.flip(self.draft, panel, rect, axis))

    def on_rotate(self) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        self._try_edit(lambda: ops.rotate(self.draft, panel, rect))

    def on_repeat(self) -> None:
        sel = self._need_selection()
        if sel is None:
            return
        panel, rect = sel
        self._try_edit(lambda: ops.repeat(self.draft, panel, rect))

    def on_wrap(self, dcol: int, drow: int) -> None:
        panel = self.active_panel
        if panel is None:
            self._set_status("Click in a panel first, then wrap it.")
            return
        row_shift, col_shift = display_shift_to_matrix(panel, dcol, drow)
        self._try_edit(lambda: ops.wrap(self.draft, panel, row_shift, col_shift))

    # ---- generators and presets ----
    def generate(self, target: str, kind: str, **params: int) -> bool:
        """Fill the threading or treadling with a generated sequence."""
        if target == "treadling" and self.draft.liftplan_mode:
            self._set_status("The treadling is hidden in liftplan mode.")
            return False
        return self._try_edit(lambda: patterns.apply_sequence(self.draft, target, kind, **params))

    def on_generate(self, target: str, kind: str) -> None:
        params: dict[str, int] = {}
        if kind == "advancing":
            count = self.draft.shafts if target == "threading" else self.draft.treadles
            run = simpledialog.askinteger("Advancing", "Threads in each run:", parent=self.root,
                                          initialvalue=min(3, count), minvalue=1, maxvalue=count)
            if run is None:
                return
            advance = simpledialog.askinteger("Advancing", "Shafts to advance after each run:",
                                              parent=self.root, initialvalue=1, minvalue=1,
                                              maxvalue=max(1, count))
            if advance is None:
                return
            params = {"run": run, "advance": advance}
        self.generate(target, kind, **params)

    def on_tieup_plain(self) -> None:
        if self._tieup_visible():
            self._try_edit(lambda: patterns.tieup_plain(self.draft))

    def tieup_twill(self, up: int, down: int) -> bool:
        return self._tieup_visible() and self._try_edit(lambda: patterns.tieup_twill(self.draft, up, down))

    def on_tieup_twill(self) -> None:
        if not self._tieup_visible():
            return
        up = simpledialog.askinteger("Twill", "Shafts up:", parent=self.root,
                                     initialvalue=2, minvalue=1, maxvalue=MAX_SHAFTS)
        if up is None:
            return
        down = simpledialog.askinteger("Twill", "Shafts down:", parent=self.root,
                                       initialvalue=2, minvalue=1, maxvalue=MAX_SHAFTS)
        if down is None:
            return
        self.tieup_twill(up, down)

    def tieup_satin(self, move: int) -> bool:
        return self._tieup_visible() and self._try_edit(lambda: patterns.tieup_satin(self.draft, move))

    def on_tieup_satin(self) -> None:
        if not self._tieup_visible():
            return
        move = simpledialog.askinteger("Satin", f"Move over {self.draft.shafts} shafts:",
                                       parent=self.root, initialvalue=2, minvalue=2,
                                       maxvalue=max(2, self.draft.shafts - 2))
        if move is not None:
            self.tieup_satin(move)

    def on_invert_tieup(self) -> None:
        if self._tieup_visible():
            self._try_edit(lambda: ops.invert(self.draft, "tieup"))

    def on_clear_tieup(self) -> None:
        if self._tieup_visible():
            full = Rect(0, self.draft.treadles - 1, 0, self.draft.shafts - 1)
            self._try_edit(lambda: ops.clear(self.draft, "tieup", full))

    def _replace_with(self, other: Draft) -> bool:
        """Swap in another draft's structure and size, keeping the user's rising/sinking choice,
        palette and thread colours."""
        self.draft.replace_structure(other)
        return True

    def replace_draft(self, new: Draft, status: str) -> bool:
        """Swap in a whole new draft (any size) as one undo step."""
        state = new.snapshot()
        self._edit(lambda: self.draft.restore(state) or True, relayout=True)
        self._set_status(status)
        return True

    def _open_dialog(self, kind: type) -> ToolDialog:
        """Open one of the Draft-menu windows, or bring the open one forward with fresh results."""
        existing = self._tool_dialogs.get(kind)
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            existing.refresh()
            return existing
        dialog = kind(self)
        self._tool_dialogs[kind] = dialog
        return dialog

    def on_block_substitution(self) -> None:
        self._open_dialog(BlockSubstitutionDialog)

    def on_combine(self) -> None:
        self._open_dialog(CombineDialog)

    def on_network(self) -> None:
        self._open_dialog(NetworkDialog)

    def reduce_draft(self) -> bool:
        """Renumber the shafts and treadles so the draft uses as few as its cloth needs."""
        d = self.draft
        try:
            smaller = fabric.minimise(d)
        except ValueError as exc:
            self._error(str(exc))
            return False
        fewer_treadles = smaller.treadles < d.treadles and not d.liftplan_mode
        if smaller.shafts >= d.shafts and not fewer_treadles:
            self._set_status("The draft already uses as few shafts and treadles as its cloth needs.")
            return True
        if d.liftplan_mode:
            note = f"Reduced to {smaller.shafts} shafts (was {d.shafts})."
        else:
            note = (f"Reduced to {smaller.shafts} shafts and {smaller.treadles} treadles "
                    f"(was {d.shafts} and {d.treadles}).")
        return self.replace_draft(smaller, note)

    def on_reduce(self) -> None:
        self.reduce_draft()

    def import_image(self, path: str) -> bool:
        """Replace the draft with one worked out from a picture of the drawdown (one pixel per cell)."""
        try:
            new = fabric.draft_from_drawdown(drawdown_from_image(path), rising=self.draft.rising)
        except (ValueError, OSError) as exc:
            self._error(f"Could not import {Path(path).name}.\n\n{exc}")
            return False
        new.palette = list(self.draft.palette)
        new.weft_colors[:] = new.default_weft_color()
        return self.replace_draft(
            new, f"Imported {Path(path).name}: {new.ends} ends x {new.picks} picks needing "
                 f"{new.shafts} shafts" + ("." if new.liftplan_mode else f" and {new.treadles} treadles."))

    def on_import_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Import drawdown from image",
            filetypes=[("Images", "*.png *.bmp *.gif *.jpg *.jpeg *.tif *.tiff"), ("All files", "*.*")],
            **self._dialog_dir())
        if path:
            self.import_image(path)

    def apply_preset(self, key: str) -> bool:
        """Replace the draft with a preset at the current number of ends and picks."""
        new = patterns.build_preset(key, self.draft.ends, self.draft.picks)
        return self._try_edit(lambda: self._replace_with(new), relayout=True)

    # ---- colours ----
    def select_color(self, index: int) -> None:
        """Choose the palette colour that the colour strips and line tool paint with."""
        if 0 <= index < len(self.draft.palette):
            self.active_color = index
            self._sync_palette()
            self._set_status(f"Colour {index + 1} selected: click or drag in the warp or weft strip to paint it.")

    def add_color(self, color: str) -> bool:
        """Add a colour to the palette and select it."""
        if not self._try_edit(lambda: self.draft.add_palette_color(color) >= 0):
            return False
        self.active_color = len(self.draft.palette) - 1
        self._sync_palette()
        return True

    def edit_color(self, index: int, color: str) -> bool:
        """Change a palette colour everywhere it is used."""
        return self._try_edit(lambda: self.draft.set_palette_color(index, color))

    def remove_color(self, index: int) -> bool:
        """Remove a palette colour; threads using it fall back to a neighbouring colour."""
        return self._try_edit(lambda: self.draft.remove_palette_color(index) is None)

    def on_add_color(self) -> None:
        _rgb, color = colorchooser.askcolor(title="New colour")
        if color:
            self.add_color(color)

    def on_edit_color(self) -> None:
        index = self.active_color
        _rgb, color = colorchooser.askcolor(initialcolor=self.draft.palette[index],
                                            title=f"Change colour {index + 1}")
        if color:
            self.edit_color(index, color)

    def on_remove_color(self) -> None:
        self.remove_color(self.active_color)

    def stripes(self, target: str, text: str) -> bool:
        """Colour every warp end or weft pick with a repeating stripe sequence like "1:4, 2:2"."""
        try:
            spec = patterns.parse_stripes(text, len(self.draft.palette))
        except ValueError as exc:
            self._error(str(exc))
            return False
        return self._try_edit(lambda: patterns.apply_stripes(self.draft, target, spec))

    def on_stripes(self, target: str) -> None:
        text = simpledialog.askstring(
            f"{target.title()} stripes",
            f"Colour:threads, repeated across the whole {target}.\n"
            "For example 1:4, 2:2 is four threads of colour 1 then two of colour 2.\n"
            "Colours are numbered on the swatches.",
            parent=self.root)
        if text is not None:
            self.stripes(target, text)

    # -----------------
    # Toolbar handlers
    # -----------------
    def on_apply_size(self) -> None:
        try:
            sizes = {key: int(var.get().strip()) for key, var in self.size_vars.items()}
        except ValueError:
            self._error("Please enter whole numbers.")
            self._sync_controls()
            return
        if not self._try_edit(lambda: self.draft.resize(**sizes), relayout=True):
            self._sync_controls()

    def on_toggle_rising(self) -> None:
        self._edit(lambda: self.draft.set_rising(self.rising_var.get()))

    def on_toggle_liftplan(self) -> None:
        self._edit(lambda: self.draft.set_liftplan_mode(self.liftplan_var.get()), relayout=True)

    def on_clear(self) -> None:
        self._edit(self.draft.clear)

    def on_undo(self) -> None:
        if self.history.undo(self.draft):
            self._rebuild()

    def on_redo(self) -> None:
        if self.history.redo(self.draft):
            self._rebuild()

    def change_zoom(self, delta: int) -> None:
        zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom + delta))
        if zoom != self.zoom:
            self.zoom = zoom
            self._rebuild()

    # ---- files ----
    def is_modified(self) -> bool:
        """True when the draft differs from what was last opened, saved or started fresh."""
        return self.draft.snapshot().fingerprint() != self._clean

    def _mark_clean(self) -> None:
        self._clean = self.draft.snapshot().fingerprint()
        self._update_title()

    def _update_title(self) -> None:
        name = Path(self.file_path).name if self.file_path else "Untitled"
        self.root.title(f"{'*' if self.is_modified() else ''}{name} - Weave Generator")

    def _default_name(self, extension: str) -> str:
        stem = Path(self.file_path).stem if self.file_path else "weave_draft"
        return stem + extension

    def open_wif(self, path: str) -> bool:
        """Replace the draft with the contents of a WIF file. One undo step brings the old draft back."""
        try:
            result = wif.load(path)
        except (OSError, wif.WifError) as exc:
            self._error(f"Could not open {Path(path).name}.\n\n{exc}")
            if isinstance(exc, OSError):
                self.settings.forget_recent(path)  # gone or unreadable: stop offering it
                self._rebuild_recent_menu()
            return False
        state = result.draft.snapshot()
        self._edit(lambda: self.draft.restore(state) or True, relayout=True)
        self.file_path = str(path)
        self._mark_clean()
        self._remember_file(path)
        self._set_status(f"Opened {Path(path).name}.")
        if result.warnings:
            messagebox.showwarning("Opened with notes", "\n\n".join(result.warnings))
        return True

    def save_wif(self, path: str) -> bool:
        """Write the draft to a WIF file and remember it as the current file."""
        try:
            wif.save(self.draft, path)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save {Path(path).name}.\n\n{exc}")
            return False
        self.file_path = str(path)
        self._mark_clean()
        self._remember_file(path)
        self._set_status(f"Saved {Path(path).name}.")
        return True

    def on_open(self) -> None:
        if not self.confirm_discard("opening another file"):
            return
        path = filedialog.askopenfilename(title="Open WIF draft", filetypes=WIF_TYPES, **self._dialog_dir())
        if path:
            self.open_wif(path)

    def on_open_recent(self, path: str) -> None:
        if self.confirm_discard("opening another file"):
            self.open_wif(path)

    def on_save(self) -> bool:
        if self.file_path:
            return self.save_wif(self.file_path)
        return self.on_save_as()

    def on_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save draft as WIF", defaultextension=".wif", filetypes=WIF_TYPES,
            initialfile=self._default_name(".wif"), **self._dialog_dir())
        return bool(path) and self.save_wif(path)

    # ---- new, unsaved changes, recent files, quitting ----
    def new_draft(self) -> bool:
        """Start an empty draft. Like opening a file, one undo step brings the old draft back."""
        self.replace_draft(Draft(), "New draft.")
        self.file_path = None
        self._mark_clean()
        return True

    def on_new(self) -> None:
        if self.confirm_discard("starting a new draft"):
            self.new_draft()

    def confirm_discard(self, action: str) -> bool:
        """True when it is fine to go on: nothing is unsaved, or the user saved or chose to discard."""
        if not self.is_modified():
            return True
        name = Path(self.file_path).name if self.file_path else "this draft"
        answer = messagebox.askyesnocancel(
            "Unsaved changes", f"Save changes to {name} before {action}?", parent=self.root)
        if answer is None:
            return False
        return self.on_save() if answer else True

    def on_quit(self) -> None:
        if not self.confirm_discard("closing"):
            return
        self._store_settings()
        self.root.destroy()

    def _remember_file(self, path: str | Path) -> None:
        self.settings.add_recent(path)
        self.settings.set("last_directory", str(Path(path).resolve().parent))
        self.settings.save()
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        menu = self.recent_menu
        menu.delete(0, "end")
        recent = self.settings.get("recent_files")
        for index, path in enumerate(recent, start=1):
            menu.add_command(label=f"{index}  {Path(path).name}",
                             command=lambda p=path: self.on_open_recent(p))
        if recent:
            menu.add_separator()
            menu.add_command(label="Clear list", command=self.on_clear_recent)
        else:
            menu.add_command(label="(none yet)", state=tk.DISABLED)

    def on_clear_recent(self) -> None:
        self.settings.clear_recent()
        self.settings.save()
        self._rebuild_recent_menu()

    def _dialog_dir(self) -> dict[str, str]:
        """initialdir for a file dialog: the folder of the open file, else the last one used."""
        folder = str(Path(self.file_path).parent) if self.file_path else self.settings.get("last_directory")
        return {"initialdir": folder} if folder and Path(folder).is_dir() else {}

    # ---- remembered preferences ----
    def _apply_settings(self) -> None:
        st = self.settings
        self.zoom = st.get("zoom")
        self.view_var.set(st.get("view"))
        self.yarn_var.set(str(st.get("yarn_width")))
        self.float_limit = st.get("float_limit")
        self.float_side_var.set(st.get("float_side"))
        self.page_var.set(st.get("page_size"))
        self.yardage_settings = st.get("yardage")
        geometry = st.get("window")
        if geometry:
            self.root.geometry(self._fit_to_screen(geometry))
        else:  # first run: a comfortable size, but never bigger than the screen
            width = min(1100, self.root.winfo_screenwidth() - 80)
            height = min(780, self.root.winfo_screenheight() - 120)
            self.root.geometry(f"{max(760, width)}x{max(600, height)}")

    def _fit_to_screen(self, geometry: str) -> str:
        """The saved window position, unless it would leave the window off the screen (a monitor
        that is no longer plugged in), in which case only the size is kept."""
        match = re.match(r"^([0-9]+)x([0-9]+)(?:([+-]-?[0-9]+)([+-]-?[0-9]+))?$", geometry)
        if match is None:
            return geometry
        width, height = int(match[1]), int(match[2])
        if match[3] is None:
            return f"{width}x{height}"
        x, y = int(match[3].lstrip("+")), int(match[4].lstrip("+"))
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(width, screen_w), min(height, screen_h)
        if not (0 <= x <= screen_w - 100 and 0 <= y <= screen_h - 100):
            return f"{width}x{height}"
        return f"{width}x{height}+{x}+{y}"

    def _store_settings(self) -> None:
        st = self.settings
        st.set("zoom", self.zoom)
        st.set("view", self.view_var.get())
        try:
            st.set("yarn_width", int(float(self.yarn_var.get())))
        except ValueError:
            pass
        st.set("float_limit", self.float_limit)
        st.set("float_side", self.float_side_var.get())
        st.set("page_size", self.page_var.get())
        st.set("yardage", self.yardage_settings)
        if self.root.state() == "normal":
            st.set("window", self.root.geometry())
        st.save()

    # ---- help ----
    def on_shortcuts(self) -> None:
        existing = getattr(self, "_shortcuts_window", None)
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            return
        self._shortcuts_window = ShortcutsWindow(self.root)

    def on_about(self) -> None:
        messagebox.showinfo("About Weave Generator", about_text(), parent=self.root)

    def export_svg(self, path: str) -> bool:
        try:
            save_svg(self.draft, path)
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not save SVG.\n\n{exc}")
            return False
        self._set_status(f"Exported {Path(path).name}.")
        return True

    def export_pdf(self, path: str) -> bool:
        try:
            save_pdf(self.draft, path, self.page_var.get())
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not save PDF.\n\n{exc}")
            return False
        self._set_status(f"Exported {Path(path).name}.")
        return True

    def on_export_svg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export draft as SVG", defaultextension=".svg",
            filetypes=[("SVG vector image", "*.svg")], initialfile=self._default_name(".svg"), **self._dialog_dir())
        if path:
            self.export_svg(path)

    def on_export_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export draft as PDF", defaultextension=".pdf",
            filetypes=[("PDF document", "*.pdf")], initialfile=self._default_name(".pdf"), **self._dialog_dir())
        if path:
            self.export_pdf(path)

    def print_draft(self) -> bool:
        """Make a printable PDF and open it in the system's PDF viewer, which has the Print command
        (and the choice of printer), so nothing is sent to a printer behind the user's back."""
        handle, path = tempfile.mkstemp(prefix="weave_draft_", suffix=".pdf")
        os.close(handle)
        try:
            save_pdf(self.draft, path, self.page_var.get())
            open_in_viewer(path)
        except OSError as exc:
            try:
                os.remove(path)  # nothing will open it, so do not leave it behind
            except OSError:
                pass
            messagebox.showerror("Print failed", f"Could not open a printable PDF.\n\n{exc}\n\n"
                                 "Use File > Export PDF, then print that file.")
            return False
        self._set_status("Opened a printable PDF in your PDF viewer: use its Print command.")
        return True

    def on_print(self) -> None:
        self.print_draft()

    def on_export(self) -> None:
        """Save only the woven cloth (as shown by the current view), without the editing panels."""
        self._export_png("Save weave as PNG", self._default_name(".png"), render_weave_image, "Weave")

    def on_export_full(self) -> None:
        """Save the whole draft: threading, tie-up, treadling, colour strips and drawdown."""
        stem = Path(self._default_name(".png")).stem
        self._export_png("Save full draft as PNG", f"{stem}_full.png", render_draft_image, "Full draft")

    def _export_png(self, title: str, initial: str, render, what: str) -> None:
        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile=initial,
            **self._dialog_dir(),
        )
        if not path:
            return
        try:
            render(self.draft, cloth_thickness=self._cloth_thickness()).save(path, format="PNG")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not save PNG.\n\n{exc}")
            return
        messagebox.showinfo("Saved", f"{what} saved to:\n{path}")

    # -----------------
    # App lifecycle
    # -----------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    WeaveGeneratorApp().run()
