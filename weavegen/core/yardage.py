"""Yardage: how much yarn a project needs, in total and for each colour.

The draft supplies the colour order. Its warp colour strip is repeated across the project's whole
width and its weft colour strip down the project's whole length, so a 16-end stripe repeats as
often as it needs to.

Everything is measured in one length unit, inches or centimetres; the report converts the
totals to yards or metres. The sums, with ``W`` and ``L`` the finished width and length:

* loom width  = W / (1 - width shrinkage)  and  loom length = L / (1 - length shrinkage), because
  finishing shrinks the cloth, so more has to be woven;
* ends = loom width x ends per unit, and picks = loom length x picks per unit;
* each warp end = loom length x (1 + warp take-up) + loom waste (tie-on, fringe and the part of
  the warp that cannot be woven);
* each weft pick = loom width x (1 + weft take-up), the extra being the thread's draw-in and crimp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from weavegen.core.draft import Draft

UNITS = {
    "in": {"name": "inches", "big": "yd", "big_name": "yards", "per_big": 36.0},
    "cm": {"name": "centimetres", "big": "m", "big_name": "metres", "per_big": 100.0},
}
MAX_THREADS = 1_000_000  # a sanity limit: more ends or picks than this is a typing slip


@dataclass(frozen=True)
class Project:
    """What is being woven. Lengths are in ``unit`` (inches or cm), percentages are 0 to 95."""

    width: float                 # finished width
    length: float                # finished length
    epi: float                   # ends per unit of width, as set in the reed
    ppi: float                   # picks per unit of length, as woven on the loom
    waste: float = 0.0           # extra warp length per end
    warp_takeup: float = 0.0     # percent of extra warp length used up by weaving over and under
    weft_takeup: float = 0.0     # percent of extra weft length for draw-in
    width_shrinkage: float = 0.0   # percent the cloth narrows when finished
    length_shrinkage: float = 0.0  # percent the cloth shortens when finished
    unit: str = "in"

    def check(self) -> None:
        """Raise ValueError, naming the field, if anything is unusable."""
        if self.unit not in UNITS:
            raise ValueError(f"unit must be 'in' or 'cm', got {self.unit!r}")
        for name in ("width", "length", "epi", "ppi"):
            value = getattr(self, name)
            if not _finite(value) or value <= 0:
                raise ValueError(f"{name} must be a number greater than 0, got {value!r}")
        if not _finite(self.waste) or self.waste < 0:
            raise ValueError(f"waste must be 0 or more, got {self.waste!r}")
        for name in ("warp_takeup", "weft_takeup"):
            value = getattr(self, name)
            if not _finite(value) or not 0 <= value <= 100:
                raise ValueError(f"{name.replace('_takeup', ' take-up')} must be a percentage from 0 to 100, got {value!r}")
        for name in ("width_shrinkage", "length_shrinkage"):
            value = getattr(self, name)
            if not _finite(value) or not 0 <= value < 95:
                raise ValueError(f"{name.replace('_', ' ')} must be a percentage from 0 to under 95, got {value!r}")


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value)


@dataclass(frozen=True)
class ColorUse:
    index: int            # position in the draft's palette
    color: str            # "#rrggbb"
    ends: int
    picks: int
    warp_length: float    # in the project's unit
    weft_length: float

    @property
    def total(self) -> float:
        return self.warp_length + self.weft_length


@dataclass(frozen=True)
class YardageReport:
    project: Project
    loom_width: float
    loom_length: float
    ends: int
    picks: int
    warp_each: float      # length of one warp end
    weft_each: float      # length of one weft pick
    colors: list[ColorUse]

    @property
    def warp_length(self) -> float:
        return self.ends * self.warp_each

    @property
    def weft_length(self) -> float:
        return self.picks * self.weft_each

    @property
    def total_length(self) -> float:
        return self.warp_length + self.weft_length


def calculate(draft: Draft, project: Project) -> YardageReport:
    """Work out the yarn for ``project``, split by the draft's warp and weft colours."""
    project.check()
    loom_width = project.width / (1 - project.width_shrinkage / 100)
    loom_length = project.length / (1 - project.length_shrinkage / 100)
    ends = max(1, round(loom_width * project.epi))
    picks = max(1, round(loom_length * project.ppi))
    if ends > MAX_THREADS or picks > MAX_THREADS:
        raise ValueError(f"that is {max(ends, picks):,} threads; check the width, length and sett")
    warp_each = loom_length * (1 + project.warp_takeup / 100) + project.waste
    weft_each = loom_width * (1 + project.weft_takeup / 100)

    count = len(draft.palette)
    warp_counts = np.bincount(draft.warp_colors[np.arange(ends) % draft.ends], minlength=count)
    weft_counts = np.bincount(draft.weft_colors[np.arange(picks) % draft.picks], minlength=count)
    colors = [
        ColorUse(i, draft.palette[i], int(warp_counts[i]), int(weft_counts[i]),
                 float(warp_counts[i] * warp_each), float(weft_counts[i] * weft_each))
        for i in range(count) if warp_counts[i] or weft_counts[i]
    ]
    return YardageReport(project, loom_width, loom_length, ends, picks, warp_each, weft_each, colors)


def to_big_unit(length: float, unit: str) -> float:
    """Convert inches to yards, or centimetres to metres."""
    return length / UNITS[unit]["per_big"]


def format_report(report: YardageReport) -> str:
    """The report as plain text for the dialog or the clipboard."""
    unit = report.project.unit
    small, big = unit, UNITS[unit]["big"]

    def amount(length: float) -> str:
        return f"{to_big_unit(length, unit):,.2f} {big}"

    lines = [
        f"Loom setup: {report.loom_width:.1f} {small} wide, {report.loom_length:.1f} {small} woven "
        f"(finished {report.project.width:g} x {report.project.length:g} {small})",
        f"Warp: {report.ends:,} ends of {report.warp_each:.1f} {small} each = {amount(report.warp_length)}",
        f"Weft: {report.picks:,} picks of {report.weft_each:.1f} {small} each = {amount(report.weft_length)}",
        f"Total: {amount(report.total_length)}",
        "",
        f"{'Colour':<14}{'Ends':>8}{'Picks':>8}{'Warp ' + big:>12}{'Weft ' + big:>12}{'Total ' + big:>12}",
    ]
    for use in report.colors:
        lines.append(f"{'#' + str(use.index + 1) + ' ' + use.color:<14}{use.ends:>8,}{use.picks:>8,}"
                     f"{to_big_unit(use.warp_length, unit):>12,.2f}{to_big_unit(use.weft_length, unit):>12,.2f}"
                     f"{to_big_unit(use.total, unit):>12,.2f}")
    return "\n".join(lines)
