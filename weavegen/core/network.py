"""Network drafting: threadings and treadlings that follow a curve, built on a twill network.

This is the method of Alice Schlein. It starts from an *initial*: the smallest threading that
defines a structure (for 3/1 and 1/3 twills it is the 4 ends 1-2-3-4). Repeating the initial's
twill pattern across all the shafts makes a *network*: end ``e`` (counting from 0) may only be
threaded on the shafts ``s`` where ``s % initial == e % initial``. A *design line* is a curve drawn
over the network; around it a ribbon ``initial`` shafts high (wrapping from the top shaft to the
bottom) always holds exactly one allowed shaft per end, and the end is threaded there. A threading
that falls on the network can be woven with any structure that fits the initial.

The treadling is networked the same way, over the treadles and picks.

A design line is given as *control points*: ribbon heights (shaft numbers from 1, may go beyond the
shaft count and wrap) spread evenly over the ends and joined by straight lines.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from weavegen.core.draft import Draft

KINDS = ("level", "straight", "point", "wave")


def _check(size: int, initial: int, what: str) -> None:
    if isinstance(initial, bool) or not isinstance(initial, (int, np.integer)) or initial < 2:
        raise ValueError(f"the initial must be a whole number of at least 2, got {initial!r}")
    if initial > size:
        raise ValueError(f"the initial ({initial}) cannot be larger than the number of {what} ({size})")
    if size % initial:
        raise ValueError(f"the number of {what} ({size}) must be a multiple of the initial ({initial}) "
                         "so that the network wraps around evenly")


def line_from_points(points: Sequence[float], length: int) -> np.ndarray:
    """A design line of ``length`` values: the control ``points`` spread evenly over positions 0 to
    ``length - 1`` and joined by straight lines. One point gives a level line."""
    if length < 1:
        raise ValueError("the design line needs at least one position")
    points = np.asarray(points, dtype=float)
    if points.ndim != 1 or points.size == 0 or not np.isfinite(points).all():
        raise ValueError("the design line needs at least one finite number")
    if points.size == 1:
        return np.full(length, points[0])
    return np.interp(np.linspace(0, points.size - 1, length), np.arange(points.size), points)


def preset_points(kind: str, size: int, cycles: int = 1) -> list[float]:
    """Control points (ribbon heights, shaft numbers from 1) for a ready-made design line.

    ``level`` is a ribbon that never moves, which threads the initial over and over (the usual
    treadling), ``straight`` climbs through all the shafts once per cycle, ``point`` goes up and back
    down, and ``wave`` is a smooth up-and-down curve, each repeated ``cycles`` times.
    """
    if kind not in KINDS:
        raise ValueError(f"the design line must be one of {', '.join(KINDS)}, got {kind!r}")
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    if kind == "level":
        return [1.0]
    if kind == "straight":
        return [1.0, 1.0 + size * cycles]
    if kind == "point":
        out: list[float] = []
        for _ in range(cycles):
            out += [1.0, float(size)]
        return out + [1.0]
    steps = 8 * cycles
    return [1 + (size - 1) * (0.5 - 0.5 * float(np.cos(2 * np.pi * i / 8))) for i in range(steps + 1)]


def parse_points(text: str) -> list[float]:
    """Read design line control points typed as numbers separated by spaces or commas."""
    points = []
    for part in text.replace(",", " ").split():
        try:
            value = float(part)
        except ValueError:
            raise ValueError(f"design line: {part!r} is not a number") from None
        if not np.isfinite(value):
            raise ValueError(f"design line: {part!r} is not a usable number")
        points.append(value)
    if not points:
        raise ValueError("design line: enter at least one number")
    return points


def format_points(points: Sequence[float]) -> str:
    """Control points as text that ``parse_points`` reads back (up to one decimal place)."""
    return " ".join(f"{p:.1f}".rstrip("0").rstrip(".") for p in points)


def network_sequence(line: np.ndarray, size: int, initial: int) -> np.ndarray:
    """For each position along ``line`` (ribbon bottom, shaft number from 1) the 0-based shaft or
    treadle it is threaded on: the one allowed place inside the ribbon ``initial`` high."""
    _check(size, initial, "shafts or treadles")
    bottoms = (np.floor(np.asarray(line, dtype=float) + 0.5).astype(int) - 1) % size
    position = np.arange(len(bottoms))
    offset = (position % initial - bottoms) % initial       # steps up from the bottom to the allowed place
    return ((bottoms + offset) % size).astype(np.int16)


def apply_network(draft: Draft, initial: int, thread_points: Sequence[float],
                  tread_points: Sequence[float]) -> Draft:
    """A copy of ``draft`` with its threading and treadling replaced by networked ones.

    ``thread_points`` and ``tread_points`` are design lines (see ``line_from_points``) over the ends
    and the picks. The tie-up, colours and shed are kept; the treadling gets one treadle per pick.
    Not available in liftplan mode, where there is no treadling.
    """
    if draft.liftplan_mode:
        raise ValueError("network drafting sets a threading and a treadling; turn off liftplan mode first")
    _check(draft.shafts, initial, "shafts")
    _check(draft.treadles, initial, "treadles")
    out = Draft(ends=draft.ends, picks=draft.picks, shafts=draft.shafts, treadles=draft.treadles,
                rising=draft.rising)
    out.restore(draft.snapshot())
    out.threading[:] = network_sequence(line_from_points(thread_points, draft.ends), draft.shafts, initial)
    out.treadling[:] = False
    treadles = network_sequence(line_from_points(tread_points, draft.picks), draft.treadles, initial)
    out.treadling[np.arange(draft.picks), treadles] = True
    return out
