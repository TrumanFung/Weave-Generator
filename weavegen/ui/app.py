"""Tkinter front end. All weaving state, geometry, editing and rendering live in weavegen.core.

The four panels are drawn as images (rendered by core.render) rather than one canvas item
per cell, so drafts of hundreds of ends and picks stay responsive.
"""

from __future__ import annotations

import os
import tempfile
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk  # type: ignore

from weavegen.core import ops, patterns
from weavegen.core.draft import (
    COLOR_PANELS, MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, Draft, DraftState,
)
from weavegen.core.history import History
from weavegen.core.layout import DraftLayout, Hit
from weavegen.core.render import render_panels
from weavegen.core.selection import Rect, display_axis, display_shift_to_matrix, matrix_to_display
from weavegen.io import wif
from weavegen.io.pdf import PAGE_SIZES, save_pdf
from weavegen.io.png import render_draft_image
from weavegen.io.svg import save_svg

TOOLS = (("pencil", "Pencil"), ("line", "Line"), ("select", "Select"))

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


class WeaveGeneratorApp:
    ZOOM_MIN = 4
    ZOOM_MAX = 40
    ZOOM_DEFAULT = 16
    MAX_PIXELS = 6000  # cap on the drawn draft's width/height; the effective zoom shrinks to fit

    LABEL_COLOR = "#b45a5a"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Weave Generator")
        self.root.minsize(760, 600)

        self.draft = Draft.twill_2_2()
        self.history = History()
        self.active_color = 0  # palette index painted into the colour strips
        self._palette_key: tuple | None = None
        self.zoom = self.ZOOM_DEFAULT
        self.file_path: str | None = None  # the WIF file the draft was last opened from or saved to

        self.selection: tuple[str, Rect] | None = None  # (panel, cells in matrix coordinates)
        self.clipboard: ops.Clipboard | None = None
        self.active_panel: str | None = None  # the panel last clicked, target of wrap

        self.layout: DraftLayout = DraftLayout.build(self.draft, self.zoom)
        self._stroke: _Stroke | None = None
        self._photos: dict[str, ImageTk.PhotoImage] = {}  # keep references or Tk drops the images
        self._image_items: dict[str, int] = {}

        self._build_ui()
        self._build_menus()
        self._bind_events()
        self._rebuild()

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

        tk.Button(tool_bar, text="Export PNG", command=self.on_export).pack(side=tk.RIGHT)

        draw_bar = tk.Frame(self.root, padx=10, pady=2)
        draw_bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(draw_bar, text="Tool:").pack(side=tk.LEFT, padx=(0, 6))
        self.tool_var = tk.StringVar(value="pencil")
        for key, label in TOOLS:
            tk.Radiobutton(draw_bar, text=label, value=key, variable=self.tool_var,
                           indicatoron=False, width=8, command=self._on_tool_changed
                           ).pack(side=tk.LEFT, padx=(0, 2))
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
            tk.Radiobutton(colour_bar, text=label, value=key, variable=self.view_var,
                           indicatoron=False, width=9, command=self._refresh_images
                           ).pack(side=tk.LEFT, padx=(0, 2))
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
        file_menu.add_command(label="Open WIF...", accelerator="Ctrl+O", command=self.on_open)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.on_save)
        file_menu.add_command(label="Save as WIF...", command=self.on_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export PNG...", command=self.on_export)
        file_menu.add_command(label="Export SVG...", command=self.on_export_svg)
        file_menu.add_command(label="Export PDF...", command=self.on_export_pdf)
        file_menu.add_command(label="Print...", command=self.on_print)
        self.page_var = tk.StringVar(value="a4")
        pages = tk.Menu(file_menu, tearoff=0)
        for key in PAGE_SIZES:
            pages.add_radiobutton(label={"a4": "A4", "letter": "US Letter"}[key], value=key,
                                  variable=self.page_var)
        file_menu.add_cascade(label="PDF page size", menu=pages)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.destroy)
        bar.add_cascade(label="File", menu=file_menu)

        edit = tk.Menu(bar, tearoff=0)
        edit.add_command(label="Undo", accelerator="Ctrl+Z", command=self.on_undo)
        edit.add_command(label="Redo", accelerator="Ctrl+Y", command=self.on_redo)
        edit.add_separator()
        edit.add_command(label="Cut", accelerator="Ctrl+X", command=self.on_cut)
        edit.add_command(label="Copy", accelerator="Ctrl+C", command=self.on_copy)
        edit.add_command(label="Paste", accelerator="Ctrl+V", command=self.on_paste)
        edit.add_command(label="Delete", accelerator="Del", command=self.on_delete)
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
        bar.add_cascade(label="Draft", menu=draft)

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
        self.root.bind("<Control-o>", lambda _e: self.on_open())
        self.root.bind("<Control-s>", lambda _e: self.on_save())
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
        panels = render_panels(self.draft, self.layout.cell, self._cloth_thickness())
        for name, pixels in panels.items():
            photo = ImageTk.PhotoImage(Image.fromarray(pixels))
            self._photos[name] = photo
            self.canvas.itemconfigure(self._image_items[name], image=photo)

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
            "select": "Drag to select cells, then use the Edit menu (copy, flip, repeat...).",
        }
        self.tool_hint.configure(text=hints[self.tool_var.get()])

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
        # The line tool waits for the drag and release.

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
        if stroke.changed:
            self.history.record(stroke.before)
            self._sync_controls()

    def on_hover(self, event: tk.Event) -> None:
        hit = self.layout.hit(*self._canvas_xy(event))
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
    def _update_title(self) -> None:
        name = Path(self.file_path).name if self.file_path else None
        self.root.title(f"{name} - Weave Generator" if name else "Weave Generator")

    def _default_name(self, extension: str) -> str:
        stem = Path(self.file_path).stem if self.file_path else "weave_draft"
        return stem + extension

    def open_wif(self, path: str) -> bool:
        """Replace the draft with the contents of a WIF file. One undo step brings the old draft back."""
        try:
            result = wif.load(path)
        except (OSError, wif.WifError) as exc:
            self._error(f"Could not open {Path(path).name}.\n\n{exc}")
            return False
        state = result.draft.snapshot()
        self._edit(lambda: self.draft.restore(state) or True, relayout=True)
        self.file_path = str(path)
        self._update_title()
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
        self._update_title()
        self._set_status(f"Saved {Path(path).name}.")
        return True

    def on_open(self) -> None:
        path = filedialog.askopenfilename(title="Open WIF draft", filetypes=WIF_TYPES)
        if path:
            self.open_wif(path)

    def on_save(self) -> None:
        if self.file_path:
            self.save_wif(self.file_path)
        else:
            self.on_save_as()

    def on_save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save draft as WIF", defaultextension=".wif", filetypes=WIF_TYPES,
            initialfile=self._default_name(".wif"))
        if path:
            self.save_wif(path)

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
            filetypes=[("SVG vector image", "*.svg")], initialfile=self._default_name(".svg"))
        if path:
            self.export_svg(path)

    def on_export_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export draft as PDF", defaultextension=".pdf",
            filetypes=[("PDF document", "*.pdf")], initialfile=self._default_name(".pdf"))
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
        path = filedialog.asksaveasfilename(
            title="Save draft as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile=self._default_name(".png"),
        )
        if not path:
            return
        try:
            render_draft_image(self.draft, cloth_thickness=self._cloth_thickness()).save(path, format="PNG")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not save PNG.\n\n{exc}")
            return
        messagebox.showinfo("Saved", f"Draft saved to:\n{path}")

    # -----------------
    # App lifecycle
    # -----------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    WeaveGeneratorApp().run()
