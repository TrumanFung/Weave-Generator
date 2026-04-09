"""
Weave Generator MVP
==================

An interactive weave pattern (over/under) grid editor.

Requirements:
- Python 3
- Tkinter (bundled with most Python installs on Windows)
- Pillow (PIL) for PNG export:  pip install pillow

Packaging (Windows .exe) with PyInstaller:
    pyinstaller --onefile --windowed weave_generator.py
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, filedialog, messagebox

from PIL import Image, ImageDraw  # type: ignore


@dataclass
class GridSize:
    warp: int  # columns
    weft: int  # rows


class WeaveGeneratorApp:
    """
    Simple Tkinter app:
    - A 2D grid of 0/1 states (under/over)
    - Canvas draws the grid
    - Clicking toggles a cell
    - Two colors control the visual palette
    - Export generates a PNG using Pillow
    """

    DEFAULT_WARP = 16
    DEFAULT_WEFT = 16
    MAX_GRID = 40
    MIN_GRID = 1

    # Reasonable default canvas size; it remains usable when resized.
    DEFAULT_CANVAS_W = 640
    DEFAULT_CANVAS_H = 640

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Weave Generator MVP")
        self.root.minsize(520, 520)

        # ---- State ----
        self.grid_size = GridSize(warp=self.DEFAULT_WARP, weft=self.DEFAULT_WEFT)
        self.grid: list[list[int]] = self._new_grid(self.grid_size.warp, self.grid_size.weft)

        # Two thread colors; these affect rendering and export.
        self.color_over = "#1f2937"   # dark slate
        self.color_under = "#f8fafc"  # near-white

        # Canvas layout metrics (computed on each draw / resize).
        self._cell_size = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0

        # Optional: cache rectangle ids if you want very fast updates.
        # For MVP simplicity we redraw everything each time (still fine up to 40x40).

        self._build_ui()
        self._bind_events()

        # First draw.
        self._redraw()

    # -----------------
    # UI construction
    # -----------------
    def _build_ui(self) -> None:
        # Top: size controls
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(side=tk.TOP, fill=tk.X)

        tk.Label(top, text="Grid size (warp x weft):").pack(side=tk.LEFT)

        self.warp_var = tk.StringVar(value=str(self.DEFAULT_WARP))
        self.weft_var = tk.StringVar(value=str(self.DEFAULT_WEFT))

        warp_entry = tk.Entry(top, textvariable=self.warp_var, width=5)
        warp_entry.pack(side=tk.LEFT, padx=(8, 4))

        tk.Label(top, text="x").pack(side=tk.LEFT)

        weft_entry = tk.Entry(top, textvariable=self.weft_var, width=5)
        weft_entry.pack(side=tk.LEFT, padx=(4, 8))

        tk.Button(top, text="Generate", command=self.on_generate).pack(side=tk.LEFT)

        hint = f" (max {self.MAX_GRID}x{self.MAX_GRID})"
        tk.Label(top, text=hint, fg="#6b7280").pack(side=tk.LEFT, padx=10)

        # Middle: canvas
        middle = tk.Frame(self.root, padx=10, pady=0)
        middle.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            middle,
            width=self.DEFAULT_CANVAS_W,
            height=self.DEFAULT_CANVAS_H,
            bg="white",
            highlightthickness=1,
            highlightbackground="#d1d5db",
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Bottom: colors + download
        bottom = tk.Frame(self.root, padx=10, pady=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(bottom, text="Over color:").pack(side=tk.LEFT)
        self.over_swatch = tk.Label(bottom, width=3, bg=self.color_over, relief=tk.GROOVE)
        self.over_swatch.pack(side=tk.LEFT, padx=(6, 8))
        tk.Button(bottom, text="Pick", command=self.on_pick_over).pack(side=tk.LEFT)

        tk.Label(bottom, text="Under color:").pack(side=tk.LEFT, padx=(16, 0))
        self.under_swatch = tk.Label(bottom, width=3, bg=self.color_under, relief=tk.GROOVE)
        self.under_swatch.pack(side=tk.LEFT, padx=(6, 8))
        tk.Button(bottom, text="Pick", command=self.on_pick_under).pack(side=tk.LEFT)

        tk.Button(bottom, text="Download Pattern", command=self.on_download).pack(
            side=tk.RIGHT
        )

    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        # Redraw when the canvas changes size (window resize).
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    # -----------------
    # Grid helpers
    # -----------------
    def _new_grid(self, warp: int, weft: int) -> list[list[int]]:
        return [[0 for _ in range(warp)] for _ in range(weft)]

    def _clamp_grid_size(self, warp: int, weft: int) -> GridSize:
        warp = max(self.MIN_GRID, min(self.MAX_GRID, warp))
        weft = max(self.MIN_GRID, min(self.MAX_GRID, weft))
        return GridSize(warp=warp, weft=weft)

    # -----------------
    # Event handlers
    # -----------------
    def on_generate(self) -> None:
        try:
            warp = int(self.warp_var.get().strip())
            weft = int(self.weft_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid size", "Please enter whole numbers for warp and weft.")
            return

        size = self._clamp_grid_size(warp, weft)
        if size.warp != warp or size.weft != weft:
            # Keep the UI consistent with what we actually generate.
            self.warp_var.set(str(size.warp))
            self.weft_var.set(str(size.weft))
            messagebox.showinfo(
                "Size adjusted",
                f"Grid size was clamped to {size.warp}x{size.weft} (allowed range: 1..{self.MAX_GRID}).",
            )

        self.grid_size = size
        self.grid = self._new_grid(size.warp, size.weft)
        self._redraw()

    def on_canvas_resize(self, _event: tk.Event) -> None:
        # Just redraw; we'll recompute the layout.
        self._redraw()

    def on_canvas_click(self, event: tk.Event) -> None:
        cell = self._pixel_to_cell(event.x, event.y)
        if cell is None:
            return

        row, col = cell
        self.grid[row][col] = 0 if self.grid[row][col] == 1 else 1
        self._redraw()

    def on_pick_over(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.color_over, title="Pick over color")
        if color and color[1]:
            self.color_over = color[1]
            self.over_swatch.configure(bg=self.color_over)
            self._redraw()

    def on_pick_under(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.color_under, title="Pick under color")
        if color and color[1]:
            self.color_under = color[1]
            self.under_swatch.configure(bg=self.color_under)
            self._redraw()

    def on_download(self) -> None:
        # Ask user where to save.
        path = filedialog.asksaveasfilename(
            title="Save weave pattern as PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile="weave_pattern.png",
        )
        if not path:
            return

        try:
            image = self._render_to_image(
                cell_px=32,  # export resolution per cell
                margin_px=16,
                grid_line_px=1,
            )
            image.save(path, format="PNG")
        except Exception as exc:  # pragma: no cover (MVP)
            messagebox.showerror("Export failed", f"Could not save PNG.\n\n{exc}")
            return

        messagebox.showinfo("Saved", f"Pattern saved to:\n{path}")

    # -----------------
    # Rendering
    # -----------------
    def _compute_layout(self) -> None:
        """
        Compute cell size and offsets to fit the grid in the current canvas size.
        """
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        cols = self.grid_size.warp
        rows = self.grid_size.weft

        # Compute a square cell size that fits both dimensions.
        self._cell_size = max(1.0, min(w / cols, h / rows))

        # Center the grid within the canvas.
        grid_w = self._cell_size * cols
        grid_h = self._cell_size * rows
        self._offset_x = (w - grid_w) / 2.0
        self._offset_y = (h - grid_h) / 2.0

    def _redraw(self) -> None:
        self._compute_layout()

        self.canvas.delete("all")

        cols = self.grid_size.warp
        rows = self.grid_size.weft

        # Draw cells.
        for r in range(rows):
            for c in range(cols):
                x0, y0, x1, y1 = self._cell_rect(r, c)
                fill = self.color_over if self.grid[r][c] == 1 else self.color_under
                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill=fill,
                    outline="#e5e7eb",  # light grid line
                    width=1,
                )

        # Subtle border around the whole grid.
        x0, y0, x1, y1 = self._grid_bounds()
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#9ca3af", width=1)

    def _grid_bounds(self) -> tuple[float, float, float, float]:
        cols = self.grid_size.warp
        rows = self.grid_size.weft
        x0 = self._offset_x
        y0 = self._offset_y
        x1 = self._offset_x + self._cell_size * cols
        y1 = self._offset_y + self._cell_size * rows
        return x0, y0, x1, y1

    def _cell_rect(self, row: int, col: int) -> tuple[float, float, float, float]:
        x0 = self._offset_x + col * self._cell_size
        y0 = self._offset_y + row * self._cell_size
        x1 = x0 + self._cell_size
        y1 = y0 + self._cell_size
        return x0, y0, x1, y1

    def _pixel_to_cell(self, x: float, y: float) -> tuple[int, int] | None:
        x0, y0, x1, y1 = self._grid_bounds()
        if x < x0 or x >= x1 or y < y0 or y >= y1:
            return None

        col = int(math.floor((x - x0) / self._cell_size))
        row = int(math.floor((y - y0) / self._cell_size))

        if 0 <= row < self.grid_size.weft and 0 <= col < self.grid_size.warp:
            return row, col
        return None

    # -----------------
    # Export to PNG (Pillow)
    # -----------------
    def _render_to_image(self, cell_px: int, margin_px: int, grid_line_px: int) -> Image.Image:
        """
        Create a Pillow Image of the pattern.

        We render from the underlying grid state (not from a canvas screenshot), which
        makes the export crisp and independent of window size.
        """
        cols = self.grid_size.warp
        rows = self.grid_size.weft

        width = margin_px * 2 + cols * cell_px
        height = margin_px * 2 + rows * cell_px

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        # Cells
        for r in range(rows):
            for c in range(cols):
                x0 = margin_px + c * cell_px
                y0 = margin_px + r * cell_px
                x1 = x0 + cell_px
                y1 = y0 + cell_px
                fill = self.color_over if self.grid[r][c] == 1 else self.color_under
                draw.rectangle([x0, y0, x1, y1], fill=fill)

        # Grid lines (optional; helps readability)
        if grid_line_px > 0:
            line = "#e5e7eb"
            # Vertical lines
            for c in range(cols + 1):
                x = margin_px + c * cell_px
                draw.line([(x, margin_px), (x, margin_px + rows * cell_px)], fill=line, width=grid_line_px)
            # Horizontal lines
            for r in range(rows + 1):
                y = margin_px + r * cell_px
                draw.line([(margin_px, y), (margin_px + cols * cell_px, y)], fill=line, width=grid_line_px)

        # Border
        border = "#9ca3af"
        draw.rectangle(
            [margin_px, margin_px, margin_px + cols * cell_px, margin_px + rows * cell_px],
            outline=border,
            width=max(1, grid_line_px),
        )

        return img

    # -----------------
    # App lifecycle
    # -----------------
    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = WeaveGeneratorApp()
    app.run()


if __name__ == "__main__":
    main()

