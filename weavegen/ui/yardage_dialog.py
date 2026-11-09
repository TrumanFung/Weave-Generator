"""The yardage calculator window: project measurements in, yarn needed per colour out."""

from __future__ import annotations

import tkinter as tk

from weavegen.core import yardage
from weavegen.core.yardage import Project

# key, label, default. The labels that mention a unit are filled in for inches or centimetres.
FIELDS = (
    ("width", "Finished width ({u})", "20"),
    ("length", "Finished length ({u})", "60"),
    ("epi", "Ends per {u} (sett)", "12"),
    ("ppi", "Picks per {u}", "12"),
    ("waste", "Loom waste per end ({u})", "24"),
    ("warp_takeup", "Warp take-up (%)", "10"),
    ("weft_takeup", "Weft draw-in (%)", "5"),
    ("width_shrinkage", "Width shrinkage (%)", "0"),
    ("length_shrinkage", "Length shrinkage (%)", "0"),
)
NUMBER_KEYS = tuple(key for key, _label, _default in FIELDS)


def parse_project(values: dict[str, str], unit: str) -> Project:
    """Turn the text typed into the fields into a Project. Raises ValueError naming the field."""
    numbers = {}
    for key, label, _default in FIELDS:
        text = values.get(key, "").strip()
        name = label.split(" (")[0].format(u=unit)
        if not text:
            raise ValueError(f"{name}: enter a number")
        try:
            numbers[key] = float(text)
        except ValueError:
            raise ValueError(f"{name}: {text!r} is not a number") from None
    return Project(unit=unit, **numbers)


class YardageDialog:
    """A window that remembers its entries on the app for the rest of the session."""

    def __init__(self, app) -> None:
        self.app = app
        saved = getattr(app, "yardage_settings", None) or {}
        self.window = tk.Toplevel(app.root)
        self.window.title("Yardage")
        self.window.transient(app.root)
        self.window.resizable(False, False)

        self.unit_var = tk.StringVar(value=saved.get("unit", "in"))
        self.vars = {key: tk.StringVar(value=saved.get(key, default)) for key, _l, default in FIELDS}
        self.labels: dict[str, tk.Label] = {}

        form = tk.Frame(self.window, padx=12, pady=10)
        form.grid(row=0, column=0, sticky="n")
        units = tk.Frame(form)
        units.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(units, text="Measure in:").pack(side=tk.LEFT)
        for value, text in (("in", "inches"), ("cm", "centimetres")):
            tk.Radiobutton(units, text=text, value=value, variable=self.unit_var,
                           command=self._relabel).pack(side=tk.LEFT, padx=(8, 0))
        self.entries: dict[str, tk.Entry] = {}
        for row, (key, label, _default) in enumerate(FIELDS, start=1):
            self.labels[key] = tk.Label(form, anchor="w")
            self.labels[key].grid(row=row, column=0, sticky="w", pady=1)
            entry = tk.Entry(form, textvariable=self.vars[key], width=9, justify="right")
            entry.grid(row=row, column=1, padx=(10, 0), pady=1)
            entry.bind("<Return>", lambda _e: self.calculate())
            self.entries[key] = entry
        self._relabel()

        buttons = tk.Frame(form)
        buttons.grid(row=len(FIELDS) + 1, column=0, columnspan=2, pady=(10, 0), sticky="w")
        tk.Button(buttons, text="Calculate", command=self.calculate).pack(side=tk.LEFT)
        tk.Button(buttons, text="Copy", command=self.copy).pack(side=tk.LEFT, padx=6)
        tk.Button(buttons, text="Close", command=self.close).pack(side=tk.LEFT)

        output = tk.Frame(self.window, padx=0, pady=10)
        output.grid(row=0, column=1, sticky="n", padx=(0, 12))
        self.message = tk.Label(output, anchor="w", justify="left", fg="#b91c1c")
        self.message.pack(fill=tk.X)
        self.result = tk.Text(output, width=70, height=16, font=("Consolas", 9), wrap="none",
                              state="disabled", background="#f9fafb")
        self.result.pack()
        tk.Label(output, anchor="w", justify="left", fg="#6b7280",
                 text="The warp and weft colour strips are repeated to fill the project.").pack(fill=tk.X)
        self.report: yardage.YardageReport | None = None
        self.calculate()

    def _relabel(self) -> None:
        unit = self.unit_var.get()
        for key, label, _default in FIELDS:
            self.labels[key].configure(text=label.format(u=unit))

    def values(self) -> dict[str, str]:
        return {key: var.get() for key, var in self.vars.items()}

    def calculate(self) -> yardage.YardageReport | None:
        """Work out and show the yardage; mistakes in the fields are shown beside the form."""
        unit = self.unit_var.get()
        self.app.yardage_settings = {**self.values(), "unit": unit}
        try:
            report = yardage.calculate(self.app.draft, parse_project(self.values(), unit))
        except ValueError as exc:
            self.report = None
            self.message.configure(text=str(exc))
            self._show("")
            return None
        self.report = report
        self.message.configure(text="")
        self._show(yardage.format_report(report))
        return report

    def _show(self, text: str) -> None:
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", text)
        self.result.configure(state="disabled")

    def copy(self) -> None:
        if self.report is None:
            return
        self.window.clipboard_clear()
        self.window.clipboard_append(yardage.format_report(self.report))
        self.message.configure(text="")
        self.app._set_status("Yardage copied to the clipboard.")

    def close(self) -> None:
        self.window.destroy()
