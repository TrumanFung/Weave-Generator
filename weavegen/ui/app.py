"""Tkinter front end. All weaving state, geometry and rendering live in weavegen.core.

The four panels are drawn as images (rendered by core.render) rather than one canvas item
per cell, so drafts of hundreds of ends and picks stay responsive.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk  # type: ignore

from weavegen.core.draft import MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, Draft, DraftState
from weavegen.core.history import History
from weavegen.core.layout import DraftLayout
from weavegen.core.render import render_panels
from weavegen.io.png import render_draft_image


@dataclass
class _Stroke:
    """One mouse press-drag-release, undone as a single step."""

    before: DraftState
    panel: str
    paint: bool  # True sets cells (or threads the shaft); False clears them
    changed: bool = False


class WeaveGeneratorApp:
    ZOOM_MIN = 4
    ZOOM_MAX = 40
    ZOOM_DEFAULT = 16
    MAX_PIXELS = 6000  # cap on the drawn draft's width/height; the effective zoom shrinks to fit

    LABEL_COLOR = "#b45a5a"

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Weave Generator")
        self.root.minsize(760, 560)

        self.draft = Draft.twill_2_2()
        self.history = History()
        self.warp_color = "#1f2937"  # warp thread on top
        self.weft_color = "#f8fafc"  # weft thread on top
        self.zoom = self.ZOOM_DEFAULT

        self.layout: DraftLayout = DraftLayout.build(self.draft, self.zoom)
        self._stroke: _Stroke | None = None
        self._photos: dict[str, ImageTk.PhotoImage] = {}  # keep references or Tk drops the images
        self._image_items: dict[str, int] = {}

        self._build_ui()
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

        tk.Label(tool_bar, text="Warp:").pack(side=tk.LEFT, padx=(20, 0))
        self.warp_swatch = tk.Label(tool_bar, width=3, bg=self.warp_color, relief=tk.GROOVE)
        self.warp_swatch.pack(side=tk.LEFT, padx=(4, 4))
        tk.Button(tool_bar, text="Pick", command=self.on_pick_warp).pack(side=tk.LEFT)

        tk.Label(tool_bar, text="Weft:").pack(side=tk.LEFT, padx=(12, 0))
        self.weft_swatch = tk.Label(tool_bar, width=3, bg=self.weft_color, relief=tk.GROOVE)
        self.weft_swatch.pack(side=tk.LEFT, padx=(4, 4))
        tk.Button(tool_bar, text="Pick", command=self.on_pick_weft).pack(side=tk.LEFT)

        tk.Button(tool_bar, text="Export PNG", command=self.on_export).pack(side=tk.RIGHT)

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

    # -----------------
    # Drawing
    # -----------------
    def _effective_cell(self) -> int:
        d = self.draft
        cols = d.ends + max(d.shafts, d.treadles) + 4
        rows = d.picks + d.shafts + 3
        limit = max(2, self.MAX_PIXELS // max(cols, rows))
        return max(2, min(self.zoom, limit))

    def _rebuild(self) -> None:
        """Re-lay-out and redraw everything. Needed when dimensions, mode or zoom change."""
        self.layout = DraftLayout.build(self.draft, self._effective_cell())
        c = self.canvas
        c.delete("all")
        self._image_items.clear()

        grids = {
            "threading": self.layout.threading,
            "tieup": self.layout.tieup,
            "treadling": self.layout.treadling,
            "liftplan": self.layout.treadling,
            "drawdown": self.layout.drawdown,
        }
        shown = ["threading", "drawdown", "liftplan" if self.draft.liftplan_mode else "treadling"]
        if not self.draft.liftplan_mode:
            shown.append("tieup")
        for name in shown:
            grid = grids[name]
            self._image_items[name] = c.create_image(grid.x, grid.y, anchor="nw")

        for label in self.layout.labels():
            c.create_text(label.x, label.y, text=label.text, anchor=label.anchor,
                          fill=self.LABEL_COLOR, font=("Segoe UI", 8))

        c.configure(scrollregion=(0, 0, self.layout.width, self.layout.height))
        self._refresh_images()
        self._sync_controls()

    def _refresh_images(self) -> None:
        """Re-render the panel pixels only; the layout is unchanged."""
        panels = render_panels(self.draft, self.layout.cell, self.warp_color, self.weft_color)
        for name, pixels in panels.items():
            photo = ImageTk.PhotoImage(Image.fromarray(pixels))
            self._photos[name] = photo
            self.canvas.itemconfigure(self._image_items[name], image=photo)

    def _sync_controls(self) -> None:
        d = self.draft
        for key, value in (("ends", d.ends), ("picks", d.picks),
                           ("shafts", d.shafts), ("treadles", d.treadles)):
            self.size_vars[key].set(str(value))
        self.rising_var.set(d.rising)
        self.liftplan_var.set(d.liftplan_mode)
        self.undo_button.configure(state=tk.NORMAL if self.history.can_undo else tk.DISABLED)
        self.redo_button.configure(state=tk.NORMAL if self.history.can_redo else tk.DISABLED)
        shown = self.layout.cell
        note = "" if shown == self.zoom else f" (shown at {shown}px)"
        self.zoom_label.configure(text=f"{self.zoom}px")
        self._set_status(note.strip())

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    # -----------------
    # Editing the draft
    # -----------------
    def _canvas_xy(self, event: tk.Event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def _paint_for(self, panel: str, a: int, b: int) -> bool:
        """What a press on this cell should do: set it (True) or clear it (False)."""
        d = self.draft
        if panel == "threading":
            return int(d.threading[a]) != b
        if panel == "tieup":
            return not d.tieup[a, b]
        if panel == "treadling":
            return not d.treadling[a, b]
        return not d.liftplan[a, b]

    def _apply(self, panel: str, a: int, b: int, paint: bool) -> bool:
        d = self.draft
        if panel == "threading":
            return d.set_thread(a, b if paint else None)
        if panel == "tieup":
            return d.set_tieup(a, b, paint)
        if panel == "treadling":
            return d.set_treadling(a, b, paint)
        return d.set_lift(a, b, paint)

    def on_press(self, event: tk.Event) -> None:
        hit = self.layout.hit(*self._canvas_xy(event))
        if hit is None or hit.panel == "drawdown":  # the drawdown is derived, not edited
            return
        stroke = _Stroke(self.draft.snapshot(), hit.panel, self._paint_for(*hit))
        self._stroke = stroke
        if self._apply(hit.panel, hit.a, hit.b, stroke.paint):
            stroke.changed = True
            self._refresh_images()

    def on_drag(self, event: tk.Event) -> None:
        stroke = self._stroke
        if stroke is None:
            return
        hit = self.layout.hit(*self._canvas_xy(event))
        if hit is None or hit.panel != stroke.panel:
            return
        if self._apply(hit.panel, hit.a, hit.b, stroke.paint):
            stroke.changed = True
            self._refresh_images()

    def on_release(self, _event: tk.Event) -> None:
        stroke, self._stroke = self._stroke, None
        if stroke is not None and stroke.changed:
            self.history.record(stroke.before)
            self._sync_controls()

    def on_hover(self, event: tk.Event) -> None:
        hit = self.layout.hit(*self._canvas_xy(event))
        if hit is None:
            self._set_status("")
            return
        text = {
            "threading": f"Threading: end {hit.a + 1}, shaft {hit.b + 1}",
            "tieup": f"Tie-up: treadle {hit.a + 1}, shaft {hit.b + 1}",
            "treadling": f"Treadling: pick {hit.a + 1}, treadle {hit.b + 1}",
            "liftplan": f"Liftplan: pick {hit.a + 1}, shaft {hit.b + 1}",
            "drawdown": f"Drawdown: pick {hit.a + 1}, end {hit.b + 1} "
                        "(computed; edit the threading, tie-up or treadling)",
        }[hit.panel]
        self._set_status(text)

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

    # -----------------
    # Toolbar handlers
    # -----------------
    def on_apply_size(self) -> None:
        try:
            sizes = {key: int(var.get().strip()) for key, var in self.size_vars.items()}
        except ValueError:
            messagebox.showerror("Invalid size", "Please enter whole numbers.")
            self._sync_controls()
            return
        try:
            self._edit(lambda: self.draft.resize(**sizes), relayout=True)
        except ValueError as exc:
            messagebox.showerror("Invalid size", str(exc))
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

    def on_pick_warp(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.warp_color, title="Pick warp color")
        if color and color[1]:
            self.warp_color = color[1]
            self.warp_swatch.configure(bg=self.warp_color)
            self._refresh_images()

    def on_pick_weft(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.weft_color, title="Pick weft color")
        if color and color[1]:
            self.weft_color = color[1]
            self.weft_swatch.configure(bg=self.weft_color)
            self._refresh_images()

    def on_export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save draft as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile="weave_draft.png",
        )
        if not path:
            return
        try:
            render_draft_image(self.draft, self.warp_color, self.weft_color).save(path, format="PNG")
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
