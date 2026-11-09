"""Float finder: where threads pass over or under many others without interlacing.

A *float* is a run of consecutive crossings where one thread stays on the same side. Long floats
snag and sag, so weavers look for them before weaving. In the drawdown (``True`` where the warp
end is on top), for each thread:

* an end that is up across several picks is a **warp float on the face**; one that is down across
  several picks is a **warp float on the back** (it lies under those picks);
* a pick that passes over several ends (drawdown ``False``) is a **weft float on the face**; one
  that passes under several ends (``True``) is a **weft float on the back**.

The length of a float is the number of threads it crosses. The analysis is of the draft as drawn:
it does not look across the join where the draft repeats. Unthreaded ends are never lifted, so
they show up as full-length floats, which is what they would do in the cloth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from weavegen.core.draft import Draft

SIDES = ("face", "back")
KINDS = ("warp", "weft")


@dataclass(frozen=True)
class Float:
    kind: str     # "warp" (an end) or "weft" (a pick)
    side: str     # "face" or "back"
    thread: int   # the end or pick number, 0-based
    start: int    # first pick (for a warp float) or first end (for a weft float) it crosses, 0-based
    length: int   # how many threads it crosses


@dataclass(frozen=True)
class FloatReport:
    limit: int
    floats: list[Float] = field(default_factory=list)   # those longer than ``limit``, longest first
    longest: dict[tuple[str, str], int] = field(default_factory=dict)  # (kind, side) -> longest, 0 if none;
    # only the sides that were analysed appear


def _check_limit(limit: int) -> None:
    if not isinstance(limit, (int, np.integer)) or limit < 1:
        raise ValueError(f"the float limit must be a whole number of at least 1, got {limit!r}")


def _check_sides(sides: Iterable[str]) -> tuple[str, ...]:
    sides = tuple(sides)
    unknown = [s for s in sides if s not in SIDES]
    if unknown:
        raise ValueError(f"sides must be 'face' and/or 'back', got {unknown[0]!r}")
    return sides


def run_length_map(bits: np.ndarray, axis: int) -> np.ndarray:
    """For every cell, the length of the run of equal values it belongs to along ``axis``.

    ``axis=0`` runs down each column (along the picks, for the drawdown) and ``axis=1`` along each
    row (along the ends).
    """
    if axis not in (0, 1):
        raise ValueError("axis must be 0 or 1")
    lines = bits.T if axis == 0 else bits           # one row per line to scan
    flat = np.ascontiguousarray(lines).reshape(-1)
    start = np.ones(flat.shape, dtype=bool)         # a run begins where the value changes ...
    start[1:] = flat[1:] != flat[:-1]
    start[::lines.shape[1]] = True                   # ... and at the start of every line
    run_id = np.cumsum(start) - 1
    lengths = np.bincount(run_id)[run_id].reshape(lines.shape)
    return lengths.T if axis == 0 else lengths


def float_lengths(draft: Draft) -> tuple[np.ndarray, np.ndarray]:
    """``(warp, weft)`` run length maps, each ``(picks, ends)``: the length of the warp run down
    each cell's end, and of the weft run along each cell's pick."""
    drawdown = draft.drawdown()
    return run_length_map(drawdown, 0), run_length_map(drawdown, 1)


def float_mask(draft: Draft, limit: int, sides: Iterable[str] = SIDES) -> np.ndarray:
    """``(picks, ends)`` bool: the cells that lie on a float longer than ``limit``, on the chosen
    sides ("face", "back" or both)."""
    _check_limit(limit)
    sides = _check_sides(sides)
    up = draft.drawdown()
    warp_run, weft_run = float_lengths(draft)
    long_warp, long_weft = warp_run > limit, weft_run > limit
    mask = np.zeros_like(up)
    if "face" in sides:
        mask |= long_warp & up          # warp up for many picks
        mask |= long_weft & ~up         # weft over many ends
    if "back" in sides:
        mask |= long_warp & ~up         # warp down for many picks
        mask |= long_weft & up          # weft under many ends
    return mask


def _line_runs(line: np.ndarray):
    """``(start, length, value)`` for each run of equal values in a 1-D bool array."""
    change = np.flatnonzero(line[1:] != line[:-1]) + 1
    starts = np.concatenate(([0], change))
    stops = np.concatenate((change, [line.shape[0]]))
    return starts, stops - starts, line[starts]


def analyse_floats(draft: Draft, limit: int, sides: Iterable[str] = SIDES) -> FloatReport:
    """Every float longer than ``limit`` on the chosen sides, plus the longest float of each kind."""
    _check_limit(limit)
    sides = _check_sides(sides)
    up = draft.drawdown()
    found: list[Float] = []
    longest = {(kind, side): 0 for kind in KINDS for side in SIDES if side in sides}

    def scan(kind: str, thread: int, line: np.ndarray) -> None:
        starts, lengths, values = _line_runs(line)
        for start, length, value in zip(starts.tolist(), lengths.tolist(), values.tolist()):
            # Along an end the end is on top when True; along a pick the pick is on top when False.
            on_top = value if kind == "warp" else not value
            side = "face" if on_top else "back"
            if side not in sides:
                continue
            key = (kind, side)
            longest[key] = max(longest[key], length)
            if length > limit:
                found.append(Float(kind, side, thread, start, length))

    for end in range(draft.ends):
        scan("warp", end, up[:, end])
    for pick in range(draft.picks):
        scan("weft", pick, up[pick, :])
    found.sort(key=lambda f: (-f.length, f.kind, f.side, f.thread, f.start))
    return FloatReport(limit, found, longest)


def describe(report: FloatReport) -> str:
    """A plain-language summary of a float report, with ends and picks numbered from 1."""
    lines = []
    total = len(report.floats)
    if total == 0:
        lines.append(f"No floats longer than {report.limit}.")
    else:
        lines.append(f"{total} float{'s' if total != 1 else ''} longer than {report.limit}.")
    lines.append("")
    lines.append("Longest float in each place:")
    for kind in KINDS:
        for side in SIDES:
            if (kind, side) not in report.longest:
                continue
            length = report.longest[(kind, side)]
            lines.append(f"  {kind} on the {side}: {length if length else 'none'}")
    if total:
        lines.append("")
        lines.append("Longest ones:")
        for f in report.floats[:8]:
            where = f"end {f.thread + 1}, picks {f.start + 1}-{f.start + f.length}" if f.kind == "warp" \
                else f"pick {f.thread + 1}, ends {f.start + 1}-{f.start + f.length}"
            lines.append(f"  {f.length} {f.kind} on the {f.side}: {where}")
        if total > 8:
            lines.append(f"  ... and {total - 8} more")
    return "\n".join(lines)
