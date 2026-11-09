"""Block substitution: expand a profile draft into a full thread-by-thread draft.

A *profile draft* shows a block weave in shorthand. Each shaft stands for a block of threads and
each treadle for a block of picks, so a 4-shaft profile can describe a pattern of four blocks.
*Substituting* replaces every profile end with that block's threading unit, and every profile pick
with that block's treadling unit, and ties the new shafts and treadles up as the structure says.

A :class:`BlockStructure` holds those units and the tie-up. It can be written as plain text, which
is what the block substitution window shows and edits::

    # comments start with a hash
    shafts 6
    treadles 10
    tieup 1 = 1, 3            treadle 1 is tied to shafts 1 and 3
    block 1 threading = 1 3 2 3
    block 1 treadling = 1 9 2 10   one treadle per pick

Numbers in the text are 1-based, as on screen. Blocks are numbered like the profile's shafts
(for the threading) and treadles (for the treadling).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from weavegen.core.draft import (
    MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, UNTHREADED, Draft,
)


@dataclass
class BlockStructure:
    """The unit weave that profile blocks are replaced with. All numbers here are 0-based."""

    shafts: int
    treadles: int
    tieup: np.ndarray                                        # (treadles, shafts) bool
    threading: dict[int, tuple[int, ...]] = field(default_factory=dict)   # block -> shafts, one per end
    treadling: dict[int, tuple[int, ...]] = field(default_factory=dict)   # block -> treadles, one per pick

    def check(self) -> None:
        """Raise ValueError if the structure cannot be used."""
        if not 1 <= self.shafts <= MAX_SHAFTS:
            raise ValueError(f"shafts must be between 1 and {MAX_SHAFTS}, got {self.shafts}")
        if not 1 <= self.treadles <= MAX_TREADLES:
            raise ValueError(f"treadles must be between 1 and {MAX_TREADLES}, got {self.treadles}")
        if self.tieup.shape != (self.treadles, self.shafts):
            raise ValueError("the tie-up does not match the number of shafts and treadles")
        for block, unit in self.threading.items():
            if not unit:
                raise ValueError(f"block {block + 1} has an empty threading unit")
            for shaft in unit:
                if not 0 <= shaft < self.shafts:
                    raise ValueError(f"block {block + 1} threading uses shaft {shaft + 1}, "
                                     f"but there are {self.shafts} shafts")
        for block, unit in self.treadling.items():
            if not unit:
                raise ValueError(f"block {block + 1} has an empty treadling unit")
            for treadle in unit:
                if not 0 <= treadle < self.treadles:
                    raise ValueError(f"block {block + 1} treadling uses treadle {treadle + 1}, "
                                     f"but there are {self.treadles} treadles")


# ---------------------------------------------------------------- the text form

_NUMBERS = re.compile(r"[\s,]+")


def _numbers(text: str, where: str) -> list[int]:
    out = []
    for part in _NUMBERS.split(text.strip()):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            raise ValueError(f"{where}: {part!r} is not a whole number") from None
    return out


def parse_structure(text: str) -> BlockStructure:
    """Read a structure from its text form. Raises ValueError naming the line at fault."""
    shafts = treadles = None
    tie_lines: list[tuple[int, int, list[int]]] = []
    thread_lines: list[tuple[int, int, list[int]]] = []
    tread_lines: list[tuple[int, int, list[int]]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        where = f"line {number}"
        head, _, body = line.partition("=")
        words = head.lower().split()
        if words and words[0] in ("shafts", "treadles") and len(words) + bool(body.strip()) == 2:
            value = _count(body if body.strip() else words[1], where, words[0])
            if words[0] == "shafts":
                shafts = value
            else:
                treadles = value
        elif len(words) == 2 and words[0] == "tieup" and body:
            tie_lines.append((number, _one(words[1], where)[0], _numbers(body, where)))
        elif len(words) == 3 and words[0] == "block" and words[2] in ("threading", "treadling") and body:
            block = _one(words[1], where)[0]
            target = thread_lines if words[2] == "threading" else tread_lines
            target.append((number, block, _numbers(body, where)))
        else:
            raise ValueError(f"{where}: cannot understand {line!r}")
    if shafts is None or treadles is None:
        raise ValueError("the structure must say how many shafts and treadles it has")
    if not 1 <= shafts <= MAX_SHAFTS:
        raise ValueError(f"shafts must be between 1 and {MAX_SHAFTS}, got {shafts}")
    if not 1 <= treadles <= MAX_TREADLES:
        raise ValueError(f"treadles must be between 1 and {MAX_TREADLES}, got {treadles}")

    structure = BlockStructure(shafts, treadles, np.zeros((treadles, shafts), dtype=bool))
    for number, treadle, shaft_list in tie_lines:
        if not 1 <= treadle <= treadles:
            raise ValueError(f"line {number}: treadle {treadle} is outside 1 to {treadles}")
        for shaft in shaft_list:
            if not 1 <= shaft <= shafts:
                raise ValueError(f"line {number}: shaft {shaft} is outside 1 to {shafts}")
            structure.tieup[treadle - 1, shaft - 1] = True
    for lines, store, limit, noun in ((thread_lines, structure.threading, shafts, "shaft"),
                                      (tread_lines, structure.treadling, treadles, "treadle")):
        for number, block, values in lines:
            if block in {b + 1 for b in store}:
                raise ValueError(f"line {number}: block {block} is already defined")
            if not values:
                raise ValueError(f"line {number}: block {block} needs at least one {noun}")
            for value in values:
                if not 1 <= value <= limit:
                    raise ValueError(f"line {number}: {noun} {value} is outside 1 to {limit}")
            store[block - 1] = tuple(v - 1 for v in values)
    return structure


def _count(text: str, where: str, what: str) -> int:
    values = _numbers(text, where)
    if len(values) != 1:
        raise ValueError(f"{where}: {what} needs one number")
    return values[0]


def _one(word: str, where: str) -> list[int]:
    values = _numbers(word, where)
    if len(values) != 1 or values[0] < 1:
        raise ValueError(f"{where}: {word!r} should be a number from 1")
    return values


def format_structure(structure: BlockStructure) -> str:
    """The text form of a structure (the inverse of ``parse_structure``)."""
    lines = [f"shafts {structure.shafts}", f"treadles {structure.treadles}", ""]
    for treadle in range(structure.treadles):
        shafts = np.flatnonzero(structure.tieup[treadle]) + 1
        if len(shafts):
            lines.append(f"tieup {treadle + 1} = {', '.join(str(s) for s in shafts)}")
    lines.append("")
    for block in sorted(structure.threading):
        lines.append(f"block {block + 1} threading = {' '.join(str(s + 1) for s in structure.threading[block])}")
    lines.append("")
    for block in sorted(structure.treadling):
        lines.append(f"block {block + 1} treadling = {' '.join(str(t + 1) for t in structure.treadling[block])}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- ready-made structures

def summer_and_winter(blocks: int) -> BlockStructure:
    """Summer and winter on ``blocks`` pattern blocks, using shafts 1 and 2 as tie-downs.

    Each block is threaded tie-down 1, pattern, tie-down 2, pattern. Each block has two pattern
    treadles (one for each tie-down) and the structure has two plain-weave "tabby" treadles. A block
    is woven pattern pick, tabby, pattern pick with the other tie-down, the other tabby.
    """
    if not 1 <= blocks <= 15:   # n + 2 shafts and 2n + 2 treadles must fit in 32
        raise ValueError(f"summer and winter needs 1 to 15 blocks here, got {blocks}")
    shafts, treadles = 2 + blocks, 2 * blocks + 2
    tabby_a, tabby_b = 2 * blocks, 2 * blocks + 1
    structure = BlockStructure(shafts, treadles, np.zeros((treadles, shafts), dtype=bool))
    for b in range(blocks):
        pattern = 2 + b
        structure.tieup[2 * b, [0, pattern]] = True        # pattern treadle with tie-down 1
        structure.tieup[2 * b + 1, [1, pattern]] = True    # pattern treadle with tie-down 2
        structure.threading[b] = (0, pattern, 1, pattern)
        structure.treadling[b] = (2 * b, tabby_a, 2 * b + 1, tabby_b)
    structure.tieup[tabby_a, [0, 1]] = True                # tabby A lifts the tie-downs
    structure.tieup[tabby_b, 2:] = True                    # tabby B lifts every pattern shaft
    return structure


STRUCTURES = {"summer_winter": ("Summer and winter", summer_and_winter)}


# ---------------------------------------------------------------- substitution

def substitute(profile: Draft, structure: BlockStructure) -> tuple[Draft, list[str]]:
    """Expand ``profile`` using ``structure``. Returns the new draft and notes about anything skipped.

    Profile shaft ``n`` (threading) and profile treadle ``n`` (treadling) both mean block ``n``.
    Unthreaded profile ends and picks with no treadle are left out. A profile pick may press only
    one treadle. Thread and weft colours carry over from the profile end or pick each came from.
    The profile's own tie-up is not used.
    """
    structure.check()
    shafts: list[int] = []
    ends_from: list[int] = []
    unthreaded = 0
    for end in range(profile.ends):
        shaft = int(profile.threading[end])
        if shaft == UNTHREADED:
            unthreaded += 1
            continue
        if shaft not in structure.threading:
            raise ValueError(f"the structure has no threading unit for block {shaft + 1}")
        unit = structure.threading[shaft]
        shafts.extend(unit)
        ends_from.extend([end] * len(unit))

    treadles: list[int] = []
    picks_from: list[int] = []
    blank = 0
    for pick in range(profile.picks):
        pressed = np.flatnonzero(profile.treadling[pick])
        if len(pressed) == 0:
            blank += 1
            continue
        if len(pressed) > 1:
            raise ValueError(f"profile pick {pick + 1} presses several treadles; "
                             "a profile pick must press one treadle (one block)")
        block = int(pressed[0])
        if block not in structure.treadling:
            raise ValueError(f"the structure has no treadling unit for block {block + 1}")
        unit = structure.treadling[block]
        treadles.extend(unit)
        picks_from.extend([pick] * len(unit))

    if not shafts:
        raise ValueError("the profile has no threaded ends to expand")
    if not treadles:
        raise ValueError("the profile has no picks with a treadle to expand")
    if len(shafts) > MAX_ENDS or len(treadles) > MAX_PICKS:
        raise ValueError(f"the result would have {len(shafts)} ends and {len(treadles)} picks; "
                         f"a draft here can have at most {MAX_ENDS} and {MAX_PICKS}")

    out = Draft(ends=len(shafts), picks=len(treadles), shafts=structure.shafts,
                treadles=structure.treadles, rising=profile.rising)
    out.threading[:] = shafts
    out.treadling[np.arange(len(treadles)), treadles] = True
    out.tieup[:] = structure.tieup
    out.palette = list(profile.palette)
    out.warp_colors = profile.warp_colors[ends_from].astype(np.int32)
    out.weft_colors = profile.weft_colors[picks_from].astype(np.int32)

    notes = []
    if unthreaded:
        notes.append(f"{unthreaded} unthreaded profile end(s) were left out.")
    if blank:
        notes.append(f"{blank} profile pick(s) with no treadle were left out.")
    return out, notes
