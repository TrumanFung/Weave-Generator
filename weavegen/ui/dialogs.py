"""Windows for the advanced Draft commands: block substitution, combining drafts, network drafting.

Each window shows its options, works out the resulting draft as you change them, and says what it
would be (or what is wrong) before anything is applied. Apply replaces the draft as one undo step.
The windows do not block the main window, and they never change the draft until Apply is pressed.
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog

from weavegen.core import blocks, combine, network, patterns
from weavegen.core.draft import Draft
from weavegen.io import wif


def describe_draft(draft: Draft) -> str:
    side = f"{draft.shafts} shafts" + ("" if draft.liftplan_mode else f", {draft.treadles} treadles")
    return f"{draft.ends} ends x {draft.picks} picks, {side}"


class ToolDialog:
    """Common frame: an options area, a line saying what would result, and Apply / Close."""

    TITLE = ""
    DONE = "Done."

    def __init__(self, app) -> None:
        self.app = app
        self.result: Draft | None = None
        self.notes: list[str] = []
        self._ready = False
        self.window = tk.Toplevel(app.root)
        self.window.title(self.TITLE)
        self.window.transient(app.root)
        self.options = tk.Frame(self.window, padx=12, pady=10)
        self.options.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.message = tk.Label(self.window, anchor="w", justify="left", wraplength=520, padx=12)
        self.message.pack(side=tk.TOP, fill=tk.X)
        bar = tk.Frame(self.window, padx=12, pady=10)
        bar.pack(side=tk.TOP, fill=tk.X)
        self.apply_button = tk.Button(bar, text="Apply", width=10, command=self.apply)
        self.apply_button.pack(side=tk.LEFT)
        tk.Button(bar, text="Close", width=10, command=self.close).pack(side=tk.LEFT, padx=6)
        self.build(self.options)
        self._ready = True
        self.refresh()

    # -- for subclasses --
    def build(self, frame: tk.Frame) -> None:
        raise NotImplementedError

    def compute(self) -> tuple[Draft, list[str]]:
        """The draft Apply would produce and any notes about it. Raise ValueError (or OSError) if not possible."""
        raise NotImplementedError

    # -- shared behaviour --
    def watch(self, *variables: tk.Variable) -> None:
        for variable in variables:
            variable.trace_add("write", self.refresh)

    def refresh(self, *_args) -> None:
        if not self._ready:
            return
        try:
            self.result, self.notes = self.compute()
        except (ValueError, OSError) as exc:
            self.result, self.notes = None, []
            self.message.configure(text=str(exc), fg="#b91c1c")
            self.apply_button.configure(state="disabled")
            return
        text = f"Result: {describe_draft(self.result)}."
        if self.notes:
            text += "\n" + "\n".join(self.notes)
        self.message.configure(text=text, fg="#065f46")
        self.apply_button.configure(state="normal")

    def apply(self) -> bool:
        """Replace the draft with the result (one undo step) and close the window."""
        self.refresh()
        if self.result is None:
            return False
        done = self.app.replace_draft(self.result, f"{self.DONE} {describe_draft(self.result)}.")
        if done:
            self.close()
        return done

    def close(self) -> None:
        self.window.destroy()


# ---------------------------------------------------------------- block substitution

class BlockSubstitutionDialog(ToolDialog):
    TITLE = "Block substitution"
    DONE = "Profile expanded."
    CUSTOM = "Custom (edit the text)"

    def build(self, frame: tk.Frame) -> None:
        draft = self.app.draft
        used = [int(s) for s in draft.threading if s >= 0] + [int(t) for t in draft.treadling.argmax(axis=1)
                                                               if draft.treadling.any()]
        needed = max(used) + 1 if used else 1
        tk.Label(frame, justify="left", anchor="w", wraplength=520, text=(
            "The current draft is the profile: each shaft in the threading and each treadle in the "
            "treadling stands for a block. Every profile end and pick is replaced by that block's unit "
            "below, and the profile's own tie-up is replaced by the structure's.")
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self.names = {label: build for label, build in blocks.STRUCTURES.values()}
        self.family_var = tk.StringVar(value=next(iter(self.names)))
        tk.Label(frame, text="Structure:").grid(row=1, column=0, sticky="w")
        menu = tk.OptionMenu(frame, self.family_var, *self.names, self.CUSTOM, command=lambda _v: self.fill())
        menu.grid(row=1, column=1, sticky="w")
        tk.Label(frame, text="Blocks:").grid(row=1, column=2, sticky="e", padx=(12, 4))
        self.blocks_var = tk.StringVar(value=str(min(15, needed)))
        spin = tk.Spinbox(frame, from_=1, to=15, width=4, textvariable=self.blocks_var, command=self.fill)
        spin.grid(row=1, column=3, sticky="w")
        spin.bind("<Return>", lambda _e: self.fill())
        spin.bind("<FocusOut>", lambda _e: self.fill())

        text_frame = tk.Frame(frame)
        text_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
        self.text = tk.Text(text_frame, width=64, height=16, font=("Consolas", 9), wrap="none", undo=True)
        scroll = tk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.text.bind("<KeyRelease>", self.refresh)
        tk.Label(frame, anchor="w", justify="left", fg="#6b7280", wraplength=520, text=(
            "Numbers start at 1. 'tieup 3 = 1, 4' ties treadle 3 to shafts 1 and 4. "
            "'block 2 threading = 1 4 2 4' replaces each profile end on shaft 2 with those shafts, and "
            "'block 2 treadling = 3 5 4 6' replaces each profile pick on treadle 2 with those treadles, "
            "one pick each.")).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.fill()

    def fill(self, *_args) -> None:
        """Write the chosen structure into the text box (unless it is a custom one)."""
        if self.family_var.get() == self.CUSTOM:
            return
        try:
            count = int(self.blocks_var.get())
            structure = self.names[self.family_var.get()](count)
        except ValueError as exc:
            self.result = None
            self.message.configure(text=str(exc) if "blocks" in str(exc) else "Blocks must be a whole number.",
                                   fg="#b91c1c")
            self.apply_button.configure(state="disabled")
            return
        self.set_text(blocks.format_structure(structure))
        self.refresh()

    def set_text(self, text: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def compute(self) -> tuple[Draft, list[str]]:
        return blocks.substitute(self.app.draft, blocks.parse_structure(self.text.get("1.0", "end")))


# ---------------------------------------------------------------- combining drafts

class CombineDialog(ToolDialog):
    TITLE = "Combine drafts"
    DONE = "Drafts combined."
    SOURCES = (("preset", "A preset:"), ("wif", "A WIF file:"), ("current", "A copy of the current draft"))

    def build(self, frame: tk.Frame) -> None:
        tk.Label(frame, justify="left", anchor="w", wraplength=520, text=(
            "The current draft is draft A. Choose draft B; the two are woven together with their ends and "
            "picks alternating A, B, A, B (the shorter one repeats to match). B's shafts and treadles follow "
            "A's. Both drafts must use the same shed.")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.source_var = tk.StringVar(value="preset")
        self.preset_names = {preset.label: key for key, preset in patterns.PRESETS.items()}
        self.preset_var = tk.StringVar(value=patterns.PRESETS["plain"].label)
        self.path_var = tk.StringVar(value="")
        row = 1
        for value, label in self.SOURCES:
            tk.Radiobutton(frame, text=label, value=value, variable=self.source_var,
                           anchor="w").grid(row=row, column=0, sticky="w")
            if value == "preset":
                tk.OptionMenu(frame, self.preset_var, *self.preset_names).grid(row=row, column=1, sticky="w")
            elif value == "wif":
                tk.Entry(frame, textvariable=self.path_var, width=34).grid(row=row, column=1, sticky="w")
                tk.Button(frame, text="Browse...", command=self.browse).grid(row=row, column=2, padx=(6, 0))
            row += 1

        self.mode_var = tk.StringVar(value="interleave")
        modes = tk.LabelFrame(frame, text="Combine as", padx=8, pady=4)
        modes.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        tk.Radiobutton(modes, value="interleave", variable=self.mode_var, anchor="w", justify="left",
                       text="Interleave: each draft is woven through the other in one plane").pack(fill=tk.X)
        tk.Radiobutton(modes, value="double", variable=self.mode_var, anchor="w", justify="left",
                       text="Double weave: A is the top layer and B the bottom layer").pack(fill=tk.X)
        self.watch(self.source_var, self.preset_var, self.path_var, self.mode_var)

    def browse(self) -> None:
        path = filedialog.askopenfilename(title="Open WIF draft for draft B",
                                          filetypes=[("WIF weaving draft", "*.wif"), ("All files", "*.*")])
        if path:
            self.path_var.set(path)
            self.source_var.set("wif")

    def second_draft(self) -> Draft:
        source = self.source_var.get()
        draft = self.app.draft
        if source == "preset":
            return patterns.build_preset(self.preset_names[self.preset_var.get()], draft.ends, draft.picks)
        if source == "wif":
            if not self.path_var.get().strip():
                raise ValueError("Choose a WIF file for draft B.")
            return wif.load(self.path_var.get().strip()).draft
        copy = Draft(draft.ends, draft.picks, draft.shafts, draft.treadles, rising=draft.rising)
        copy.restore(draft.snapshot())
        return copy

    def compute(self) -> tuple[Draft, list[str]]:
        try:
            other = self.second_draft()
        except wif.WifError as exc:
            raise ValueError(f"Could not read that WIF file: {exc}") from None
        return combine.combine(self.app.draft, other, self.mode_var.get()), []


# ---------------------------------------------------------------- network drafting

@dataclass
class _DesignLine:
    """The controls for one design line: its shape, number of cycles and control points."""

    kind: tk.StringVar
    cycles: tk.StringVar
    points: tk.StringVar
    size: int          # how many shafts (or treadles) the ribbon moves over


class NetworkDialog(ToolDialog):
    TITLE = "Network drafting"
    DONE = "Network applied."
    KIND_NAMES = {"level": "Level (the initial repeated)", "straight": "Straight (climbing)",
                  "point": "Point (up and down)", "wave": "Wave"}

    def build(self, frame: tk.Frame) -> None:
        draft = self.app.draft
        gcd = math.gcd(draft.shafts, draft.treadles)
        divisors = [k for k in range(2, gcd + 1) if gcd % k == 0]
        default = 4 if 4 in divisors else (divisors[0] if divisors else 2)
        tk.Label(frame, justify="left", anchor="w", wraplength=560, text=(
            "Network drafting threads the loom along a curve. The initial (4 for 3/1 and 2/2 twills) fixes "
            "which shafts each end may use: end e can go on shaft s only when s and e leave the same remainder "
            "when divided by the initial. The design line is the height of a ribbon, one initial tall, wandering "
            "over the shafts; each end is threaded where the network falls inside the ribbon. The treadling is "
            "networked over the treadles in the same way, one treadle per pick. The tie-up is left alone: set it "
            "from the Tie-up menu (a twill or satin on all the shafts).")
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 8))
        tk.Label(frame, text="Initial:").grid(row=1, column=0, sticky="w")
        self.initial_var = tk.StringVar(value=str(default))
        tk.Spinbox(frame, from_=2, to=32, width=4, textvariable=self.initial_var,
                   command=self.refresh).grid(row=1, column=1, sticky="w")
        tk.Label(frame, text=f"({draft.shafts} shafts, {draft.treadles} treadles: both must be multiples of it)",
                 fg="#6b7280").grid(row=1, column=2, columnspan=3, sticky="w", padx=(8, 0))

        self.lines: dict[str, _DesignLine] = {}
        for row, (key, label, size, default_kind) in enumerate((
                ("thread", "Threading design line", draft.shafts, "wave"),
                ("tread", "Treadling design line", draft.treadles, "level")), start=2):
            box = tk.LabelFrame(frame, text=f"{label} (ribbon height as a {'shaft' if key == 'thread' else 'treadle'} number)",
                                padx=8, pady=6)
            box.grid(row=row, column=0, columnspan=5, sticky="ew", pady=(8, 0))
            kind = tk.StringVar(value=self.KIND_NAMES[default_kind])
            cycles = tk.StringVar(value="2" if default_kind == "wave" else "1")
            points = tk.StringVar(value="")
            self.lines[key] = _DesignLine(kind, cycles, points, size)
            tk.Label(box, text="Shape:").grid(row=0, column=0, sticky="w")
            tk.OptionMenu(box, kind, *self.KIND_NAMES.values(),
                          command=lambda _v, k=key: self.preset(k)).grid(row=0, column=1, sticky="w")
            tk.Label(box, text="Cycles:").grid(row=0, column=2, padx=(12, 4))
            tk.Spinbox(box, from_=1, to=16, width=4, textvariable=cycles,
                       command=lambda k=key: self.preset(k)).grid(row=0, column=3)
            tk.Label(box, text="Control points:").grid(row=1, column=0, sticky="w", pady=(6, 0))
            tk.Entry(box, textvariable=points, width=58).grid(row=1, column=1, columnspan=4, sticky="w", pady=(6, 0))
            self.preset(key, refresh=False)
        self.watch(self.initial_var, self.lines["thread"].points, self.lines["tread"].points)

    def preset(self, key: str, refresh: bool = True) -> None:
        """Fill a design line's control points from its shape and cycles."""
        line = self.lines[key]
        names = {label: kind for kind, label in self.KIND_NAMES.items()}
        try:
            points = network.preset_points(names[line.kind.get()], line.size, int(line.cycles.get()))
        except ValueError:
            return
        line.points.set(network.format_points(points))
        if refresh:
            self.refresh()

    def compute(self) -> tuple[Draft, list[str]]:
        try:
            initial = int(self.initial_var.get())
        except ValueError:
            raise ValueError("The initial must be a whole number.") from None
        thread = network.parse_points(self.lines["thread"].points.get())
        tread = network.parse_points(self.lines["tread"].points.get())
        return network.apply_network(self.app.draft, initial, thread, tread), []
