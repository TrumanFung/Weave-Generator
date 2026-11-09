"""Generators for threading/treadling sequences, tie-ups, and a library of starter drafts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from weavegen.core.draft import Draft

# ---- sequences: lists of 0-based shaft (or treadle) numbers ----


def straight(count: int, n: int) -> list[int]:
    """1 2 3 ... count, repeating."""
    return [i % count for i in range(n)]


def point(count: int, n: int, repeat_ends: bool = False) -> list[int]:
    """1 2 3 4 3 2 1 2 3 4 ... A point (zigzag) draw. With ``repeat_ends`` the turning
    points are doubled: 1 2 3 4 4 3 2 1 1 2 ..."""
    if count == 1:
        return [0] * n
    up = list(range(count))
    down = list(range(count - 1, -1, -1)) if repeat_ends else list(range(count - 2, 0, -1))
    cycle = up + down
    return [cycle[i % len(cycle)] for i in range(n)]


def advancing(count: int, n: int, run: int, advance: int = 1) -> list[int]:
    """Runs of ``run`` consecutive shafts, each run starting ``advance`` shafts further along
    than the last (wrapping): with 4 shafts, run 3, advance 1 -> 123 234 341 412 ..."""
    if not 1 <= run <= count:
        raise ValueError(f"run must be between 1 and {count}")
    out: list[int] = []
    start = 0
    while len(out) < n:
        out.extend((start + j) % count for j in range(run))
        start = (start + advance) % count
    return out[:n]


def skip(count: int, n: int) -> list[int]:
    """Odd shafts then even shafts: 1 3 5 ... 2 4 6 ..., repeating (4 shafts: 1 3 2 4)."""
    order = list(range(0, count, 2)) + list(range(1, count, 2))
    return [order[i % count] for i in range(n)]


SEQUENCES: dict[str, Callable[..., list[int]]] = {
    "straight": straight,
    "point": point,
    "point_repeat": lambda count, n: point(count, n, repeat_ends=True),
    "advancing": advancing,
    "skip": skip,
}


def apply_sequence(draft: Draft, target: str, kind: str, **params: int) -> bool:
    """Fill the whole threading or treadling with a generated sequence.

    The threading uses the draft's shafts and ends; the treadling uses its treadles and picks,
    with one treadle per pick. Returns True if the draft changed.
    """
    if kind not in SEQUENCES:
        raise ValueError(f"unknown sequence {kind!r}")
    if target == "threading":
        sequence = SEQUENCES[kind](draft.shafts, draft.ends, **params)
        before = draft.matrix("threading")
        after = before.copy()
        after[:] = False
        for end, shaft in enumerate(sequence):
            after[end, shaft] = True
        return draft.set_matrix("threading", after)
    if target == "treadling":
        sequence = SEQUENCES[kind](draft.treadles, draft.picks, **params)
        after = draft.matrix("treadling")
        after[:] = False
        for pick, treadle in enumerate(sequence):
            after[pick, treadle] = True
        return draft.set_matrix("treadling", after)
    raise ValueError("target must be 'threading' or 'treadling'")


# ---- tie-ups ----


def _fresh_tieup(draft: Draft):
    matrix = draft.matrix("tieup")
    matrix[:] = False
    return matrix


def tieup_plain(draft: Draft) -> bool:
    """Treadle 1 lifts the odd shafts and treadle 2 the even shafts."""
    if draft.shafts < 2 or draft.treadles < 2:
        raise ValueError("plain weave needs at least 2 shafts and 2 treadles")
    matrix = _fresh_tieup(draft)
    matrix[0, 0::2] = True
    matrix[1, 1::2] = True
    return draft.set_matrix("tieup", matrix)


def tieup_twill(draft: Draft, up: int, down: int) -> bool:
    """An ``up``/``down`` twill: each treadle lifts ``up`` consecutive shafts, advancing one
    shaft per treadle, over ``up + down`` shafts and treadles."""
    if up < 1 or down < 1:
        raise ValueError("a twill needs at least 1 shaft up and 1 down")
    span = up + down
    if draft.shafts < span or draft.treadles < span:
        raise ValueError(f"a {up}/{down} twill needs at least {span} shafts and {span} treadles")
    matrix = _fresh_tieup(draft)
    for treadle in range(span):
        for k in range(up):
            matrix[treadle, (treadle + k) % span] = True
    return draft.set_matrix("tieup", matrix)


def tieup_satin(draft: Draft, move: int) -> bool:
    """A satin over all the draft's shafts: each treadle lifts a single shaft, ``move`` shafts
    further along than the last treadle. ``move`` must share no factor with the shaft count
    and be neither 1 nor shafts-1 (that would just be a twill)."""
    size = draft.shafts
    if size < 5:
        raise ValueError("satin needs at least 5 shafts")
    if not 2 <= move <= size - 2 or math.gcd(move, size) != 1:
        raise ValueError(f"move must be between 2 and {size - 2} with no common factor with {size}")
    if draft.treadles < size:
        raise ValueError(f"a {size}-shaft satin needs at least {size} treadles")
    matrix = _fresh_tieup(draft)
    for treadle in range(size):
        matrix[treadle, (treadle * move) % size] = True
    return draft.set_matrix("tieup", matrix)


# ---- starter drafts ----


@dataclass(frozen=True)
class Preset:
    label: str
    build: Callable[[int, int], Draft]  # (ends, picks) -> Draft


def _make(shafts: int, treadles: int, ends: int, picks: int,
          thread: str, tread: str, tieup: Callable[[Draft], bool]) -> Draft:
    draft = Draft(ends=ends, picks=picks, shafts=shafts, treadles=treadles)
    apply_sequence(draft, "threading", thread)
    apply_sequence(draft, "treadling", tread)
    tieup(draft)
    return draft


def _twill(up: int, down: int) -> Callable[[int, int], Draft]:
    return lambda e, p: _make(up + down, up + down, e, p, "straight", "straight",
                              lambda d: tieup_twill(d, up, down))


PRESETS: dict[str, Preset] = {
    "plain": Preset("Plain weave", lambda e, p: _make(2, 2, e, p, "straight", "straight", tieup_plain)),
    "twill_2_1": Preset("2/1 twill", _twill(2, 1)),
    "twill_1_2": Preset("1/2 twill", _twill(1, 2)),
    "twill_2_2": Preset("2/2 twill", _twill(2, 2)),
    "twill_3_1": Preset("3/1 twill", _twill(3, 1)),
    "twill_1_3": Preset("1/3 twill", _twill(1, 3)),
    "herringbone": Preset("2/2 herringbone", lambda e, p: _make(
        4, 4, e, p, "point", "straight", lambda d: tieup_twill(d, 2, 2))),
    "diamond": Preset("2/2 diamond", lambda e, p: _make(
        4, 4, e, p, "point", "point", lambda d: tieup_twill(d, 2, 2))),
    "satin_5": Preset("5-shaft satin", lambda e, p: _make(
        5, 5, e, p, "straight", "straight", lambda d: tieup_satin(d, 2))),
    "satin_8": Preset("8-shaft satin", lambda e, p: _make(
        8, 8, e, p, "straight", "straight", lambda d: tieup_satin(d, 3))),
}


def build_preset(key: str, ends: int = 24, picks: int = 24) -> Draft:
    if key not in PRESETS:
        raise ValueError(f"unknown preset {key!r}")
    return PRESETS[key].build(ends, picks)
