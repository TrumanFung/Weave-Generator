"""A small hover tip for toolbar widgets."""

from __future__ import annotations

import tkinter as tk


class Tooltip:
    DELAY_MS = 600

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._after: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    @property
    def visible(self) -> bool:
        return self._tip is not None

    def _schedule(self, _event: object = None) -> None:
        self._cancel()
        self._after = self.widget.after(self.DELAY_MS, self.show)

    def _cancel(self) -> None:
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def show(self) -> None:
        self._after = None
        if self._tip is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            tip = tk.Toplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x}+{y}")
            tk.Label(tip, text=self.text, background="#fffbe6", foreground="#222222",
                     relief=tk.SOLID, borderwidth=1, padx=6, pady=2,
                     justify=tk.LEFT).pack()
        except tk.TclError:
            self._tip = None
            return
        self._tip = tip

    def hide(self, _event: object = None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None
