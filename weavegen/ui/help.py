"""The Help menu: the keyboard shortcut list and the About box."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from weavegen import __version__

# (section, [(keys, what it does)]). One list feeds the Help window and the README check.
SHORTCUTS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("File", (
        ("Ctrl+N", "New draft"),
        ("Ctrl+O", "Open a WIF file"),
        ("Ctrl+S", "Save"),
        ("Ctrl+Shift+S", "Save as"),
        ("Ctrl+P", "Print"),
        ("Ctrl+Q", "Quit"),
    )),
    ("Edit", (
        ("Ctrl+Z", "Undo"),
        ("Ctrl+Y or Ctrl+Shift+Z", "Redo"),
        ("Ctrl+C / Ctrl+X / Ctrl+V", "Copy, cut, paste the selected cells (while the draft has focus)"),
        ("Delete", "Clear the selected cells"),
        ("Ctrl+A", "Select the whole panel you last clicked in"),
        ("Esc", "Drop the selection"),
    )),
    ("Tools (while the draft has focus)", (
        ("P", "Pencil"),
        ("L", "Line"),
        ("S", "Select"),
    )),
    ("View", (
        ("Ctrl++ or Ctrl+mouse wheel up", "Zoom in"),
        ("Ctrl+- or Ctrl+mouse wheel down", "Zoom out"),
        ("Ctrl+0", "Back to the standard zoom"),
        ("Ctrl+K", "Switch between the drawdown and the cloth view"),
    )),
    ("Help", (
        ("F1", "This list"),
    )),
)


def shortcuts_text() -> str:
    lines: list[str] = []
    for section, rows in SHORTCUTS:
        lines.append(section)
        lines.extend(f"    {keys:<34}{what}" for keys, what in rows)
        lines.append("")
    return "\n".join(lines).rstrip()


def about_text() -> str:
    return (f"Weave Generator {__version__}\n\n"
            "A weaving draft editor: threading, tie-up, treadling and a live drawdown, with colour, "
            "cloth view, WIF files, PDF/SVG/PNG output, float and yardage analysis, and block, "
            "network and double-weave drafting.\n\n"
            "Released under CC0 1.0 (public domain).")


def asset_path(name: str) -> Path:
    """Where a bundled file lives, both when run from source and inside a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "assets" / name


class ShortcutsWindow:
    def __init__(self, parent: tk.Misc) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title("Keyboard shortcuts")
        self.window.transient(parent)
        self.window.resizable(False, False)
        body = shortcuts_text()
        text = tk.Text(self.window, width=max(len(line) for line in body.splitlines()) + 2,
                       height=body.count("\n") + 2,
                       font=("Consolas", 10), relief=tk.FLAT, padx=12, pady=10, wrap="none")
        text.insert("1.0", body)
        text.configure(state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=(0, 10))
        self.window.bind("<Escape>", lambda _e: self.window.destroy())
        self.window.focus_set()
