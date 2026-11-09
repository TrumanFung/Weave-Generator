"""Read and write WIF (Weaving Information File), the interchange format of weaving software.

A WIF file is INI-like text: ``[SECTION]`` headings followed by ``key=value`` lines. Section and
key names are case-insensitive and ``;`` starts a comment. Numbers in the file are 1-based, as
they are in the on-screen draft, so end 1 in the file is end 1 here.

What is kept: shafts, treadles, ends, picks, rising/sinking shed, threading, tie-up, treadling
or liftplan, the colour table and the warp and weft colours. Anything else in a file (notes,
units, spacing, private sections) is ignored. What does not fit this program's model is reported
as a warning rather than dropped silently: an end threaded on several shafts keeps only its
lowest shaft.

``loads`` and ``dumps`` work on text; ``load`` and ``save`` on files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from weavegen.core.draft import (
    DEFAULT_PALETTE, MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, UNTHREADED, Draft,
)

_TRUE = {"true", "on", "yes", "1"}
_FALSE = {"false", "off", "no", "0"}


class WifError(ValueError):
    """The text is not a WIF file this program can open. The message says why."""


@dataclass
class WifResult:
    draft: Draft
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- reading

def _sections(text: str) -> dict[str, dict[str, str]]:
    """Split WIF text into ``{SECTION: {key: value}}`` (names upper/lower-cased, comments gone)."""
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for number, raw in enumerate(text.lstrip("﻿").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if current is None and not line.startswith("["):
            raise WifError("this does not look like a WIF file (it should start with a [WIF] section)")
        if line.startswith("["):
            if not line.endswith("]"):
                raise WifError(f"line {number}: unfinished section heading {line!r}")
            current = sections.setdefault(line[1:-1].strip().upper(), {})
        elif "=" in line:
            key, _, value = line.partition("=")
            current[key.strip().lower()] = value.strip()
        else:
            raise WifError(f"line {number}: expected key=value, got {line!r}")
    return sections


def _flag(section: dict[str, str], key: str, default: bool) -> bool:
    value = section.get(key)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise WifError(f"{key!r} should be true or false, got {value!r}")


def _int(value: str, what: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        raise WifError(f"{what}: {value!r} is not a whole number") from None


def _numbers(value: str, what: str) -> list[int]:
    """A comma-separated list such as ``1,3,4`` (empty means no numbers)."""
    return [_int(part, what) for part in value.split(",") if part.strip()]


def _indexed(section: dict[str, str], name: str, limit: int | None = None) -> dict[int, str]:
    """A section's ``n=value`` lines as ``{n: value}``, with ``n`` checked to be at least 1."""
    out: dict[int, str] = {}
    for key, value in section.items():
        index = _int(key, f"[{name}] line {key!r}")
        if index < 1:
            raise WifError(f"[{name}] numbers start at 1, found {index}")
        if limit is not None and index > limit:
            raise WifError(f"[{name}] refers to {index} but there are only {limit}")
        out[index] = value
    return out


def _count(declared: str | None, what: str, used: int, maximum: int) -> int:
    """A dimension: the declared count when the file has one, otherwise the highest number used."""
    if declared is not None and declared.strip():
        count = _int(declared, what)
        if count < 1:
            raise WifError(f"{what} must be at least 1, got {count}")
    else:
        count = max(used, 1)
    if count > maximum:
        raise WifError(f"{what}: this program handles at most {maximum}, the file has {count}")
    return count


def _palette(sections: dict[str, dict[str, str]], warnings: list[str]) -> tuple[list[str], dict[int, int]]:
    """The colour table as hex strings plus a map from the file's colour numbers to palette indices."""
    table = sections.get("COLOR TABLE", {})
    if not table:
        return list(DEFAULT_PALETTE), {}
    info = sections.get("COLOR PALETTE", {})
    form = info.get("form", "RGB").strip().upper()
    if form != "RGB":
        warnings.append(f"The colour table uses the {info.get('form')!r} form, which is not supported; "
                        "default colours were used.")
        return list(DEFAULT_PALETTE), {}
    low, high = 0, 255
    if "range" in info:
        bounds = _numbers(info["range"], "[COLOR PALETTE] Range")
        if len(bounds) != 2 or bounds[1] <= bounds[0]:
            raise WifError(f"[COLOR PALETTE] Range should be two increasing numbers, got {info['range']!r}")
        low, high = bounds

    colors: list[str] = []
    index_of: dict[int, int] = {}
    for number, value in sorted(_indexed(table, "COLOR TABLE").items()):
        parts = _numbers(value, f"[COLOR TABLE] colour {number}")
        if len(parts) != 3:
            raise WifError(f"[COLOR TABLE] colour {number} needs red, green and blue, got {value!r}")
        channels = [min(255, max(0, round((p - low) * 255 / (high - low)))) for p in parts]
        index_of[number] = len(colors)
        colors.append("#{:02x}{:02x}{:02x}".format(*channels))
    return colors, index_of


def loads(text: str) -> WifResult:
    """Parse WIF text into a draft. Raises ``WifError`` when it cannot be used."""
    sections = _sections(text)
    if "WIF" not in sections and not any(name in sections for name in ("THREADING", "WEAVING", "TIEUP")):
        raise WifError("this does not look like a WIF file (no [WIF] or [WEAVING] section)")
    warnings: list[str] = []
    weaving, warp, weft = (sections.get(name, {}) for name in ("WEAVING", "WARP", "WEFT"))

    # Threading, with the first shaft of any multi-shaft end.
    threading_lines = _indexed(sections.get("THREADING", {}), "THREADING")
    tieup_lines = _indexed(sections.get("TIEUP", {}), "TIEUP")
    treadling_lines = _indexed(sections.get("TREADLING", {}), "TREADLING")
    liftplan_lines = _indexed(sections.get("LIFTPLAN", {}), "LIFTPLAN")

    def highest(lines: dict[int, str], what: str) -> int:
        return max((n for value in lines.values() for n in _numbers(value, what)), default=0)

    shaft_use = max(highest(threading_lines, "[THREADING]"), highest(tieup_lines, "[TIEUP]"),
                    highest(liftplan_lines, "[LIFTPLAN]"))
    treadle_use = max(highest(treadling_lines, "[TREADLING]"), max(tieup_lines, default=0))
    warp_color_lines = _indexed(sections.get("WARP COLORS", {}), "WARP COLORS")
    weft_color_lines = _indexed(sections.get("WEFT COLORS", {}), "WEFT COLORS")
    ends = _count(warp.get("threads"), "[WARP] Threads",
                  max(threading_lines.keys() | warp_color_lines.keys(), default=0), MAX_ENDS)
    picks = _count(weft.get("threads"), "[WEFT] Threads",
                   max(treadling_lines.keys() | liftplan_lines.keys() | weft_color_lines.keys(), default=0),
                   MAX_PICKS)
    shafts = _count(weaving.get("shafts"), "[WEAVING] Shafts", shaft_use, MAX_SHAFTS)
    treadles = _count(weaving.get("treadles"), "[WEAVING] Treadles", treadle_use, MAX_TREADLES)
    if weaving.get("shafts") is None and "WEAVING" in sections:
        warnings.append("The file does not say how many shafts it has; the highest one used was assumed.")

    draft = Draft(ends=ends, picks=picks, shafts=shafts, treadles=treadles,
                  rising=_flag(weaving, "rising shed", True))

    def check(number: int, limit: int, what: str, where: str) -> int:
        if not 1 <= number <= limit:
            raise WifError(f"{where} uses {what} {number}, but the draft has {limit}")
        return number - 1

    multi = []
    for end, value in threading_lines.items():
        if end > ends:
            raise WifError(f"[THREADING] refers to end {end} but the warp has {ends} threads")
        shafts_used = [s for s in _numbers(value, f"[THREADING] end {end}") if s != 0]
        if shafts_used:
            if len(shafts_used) > 1:
                multi.append(end)
            draft.threading[end - 1] = check(min(shafts_used), shafts, "shaft", "[THREADING]")
    if multi:
        shown = ", ".join(str(e) for e in multi[:8]) + (" ..." if len(multi) > 8 else "")
        warnings.append(f"{len(multi)} end(s) are threaded on more than one shaft (ends {shown}); "
                        "only the lowest shaft of each was kept.")

    for treadle, value in tieup_lines.items():
        for shaft in _numbers(value, f"[TIEUP] treadle {treadle}"):
            draft.tieup[check(treadle, treadles, "treadle", "[TIEUP]"),
                        check(shaft, shafts, "shaft", "[TIEUP]")] = True
    for pick, value in treadling_lines.items():
        if pick > picks:
            raise WifError(f"[TREADLING] refers to pick {pick} but the weft has {picks} threads")
        for treadle in _numbers(value, f"[TREADLING] pick {pick}"):
            if treadle != 0:
                draft.treadling[pick - 1, check(treadle, treadles, "treadle", "[TREADLING]")] = True
    for pick, value in liftplan_lines.items():
        if pick > picks:
            raise WifError(f"[LIFTPLAN] refers to pick {pick} but the weft has {picks} threads")
        for shaft in _numbers(value, f"[LIFTPLAN] pick {pick}"):
            if shaft != 0:
                draft.liftplan[pick - 1, check(shaft, shafts, "shaft", "[LIFTPLAN]")] = True

    if liftplan_lines and not treadling_lines:
        draft.liftplan_mode = True
    elif liftplan_lines and not np.array_equal(draft.lifts(), draft.liftplan):
        warnings.append("The file has both a liftplan and a treadling that disagree; the treadling "
                        "and tie-up were used.")

    _apply_colors(draft, sections, warp, weft, warnings)
    return WifResult(draft, warnings)


def _apply_colors(draft: Draft, sections: dict[str, dict[str, str]], warp: dict[str, str],
                  weft: dict[str, str], warnings: list[str]) -> None:
    palette, index_of = _palette(sections, warnings)
    draft.palette = palette
    draft.warp_colors = np.zeros(draft.ends, dtype=np.int32)
    draft.weft_colors = np.full(draft.picks, draft.default_weft_color(), dtype=np.int32)
    if not index_of:
        return

    missing: set[int] = set()

    def resolve(number: int) -> int | None:
        if number in index_of:
            return index_of[number]
        missing.add(number)
        return None

    for section, key, target in ((warp, "color", draft.warp_colors), (weft, "color", draft.weft_colors)):
        if key in section:
            default = resolve(_int(section[key].split(",")[0], "default thread colour"))
            if default is not None:
                target[:] = default
    for name, target, limit in (("WARP COLORS", draft.warp_colors, draft.ends),
                                ("WEFT COLORS", draft.weft_colors, draft.picks)):
        for thread, value in _indexed(sections.get(name, {}), name).items():
            if thread > limit:
                raise WifError(f"[{name}] refers to thread {thread} but there are only {limit}")
            found = resolve(_int(value.split(",")[0], f"[{name}] thread {thread}"))
            if found is not None:
                target[thread - 1] = found
    if missing:
        warnings.append("Some threads use colours missing from the colour table "
                        f"({', '.join(str(n) for n in sorted(missing))}); they kept the default colour.")


def load(path: str | Path) -> WifResult:
    """Read a WIF file (UTF-8 or Windows text) from disk."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return loads(text)


# ---------------------------------------------------------------- writing

def _join(numbers) -> str:
    return ",".join(str(int(n)) for n in numbers)


def dumps(draft: Draft, *, when: date | None = None) -> str:
    """The draft as WIF text. In liftplan mode the liftplan is written instead of the tie-up and
    treadling, which are hidden in that mode."""
    when = when or date.today()
    lines = [
        "[WIF]", "Version=1.1", f"Date={when.strftime('%B')} {when.day}, {when.year}",
        "Developers=", "Source Program=Weave Generator", "Source Version=4",
        "",
        "[CONTENTS]", "COLOR PALETTE=true", "WEAVING=true", "WARP=true", "WEFT=true",
        "COLOR TABLE=true", "THREADING=true", "WARP COLORS=true", "WEFT COLORS=true",
    ]
    lines += ["LIFTPLAN=true"] if draft.liftplan_mode else ["TIEUP=true", "TREADLING=true"]
    lines += [
        "",
        "[COLOR PALETTE]", f"Entries={len(draft.palette)}", "Form=RGB", "Range=0,255",
        "",
        "[WEAVING]", f"Shafts={draft.shafts}", f"Treadles={draft.treadles}",
        f"Rising Shed={'true' if draft.rising else 'false'}",
        "",
        "[WARP]", f"Threads={draft.ends}", "Color=1",
        "",
        "[WEFT]", f"Threads={draft.picks}", f"Color={draft.default_weft_color() + 1}",
        "",
        "[COLOR TABLE]",
    ]
    for number, color in enumerate(draft.palette, start=1):
        lines.append(f"{number}={int(color[1:3], 16)},{int(color[3:5], 16)},{int(color[5:7], 16)}")

    lines += ["", "[THREADING]"]
    for end, shaft in enumerate(draft.threading, start=1):
        if shaft != UNTHREADED:
            lines.append(f"{end}={int(shaft) + 1}")
    if draft.liftplan_mode:
        lines += ["", "[LIFTPLAN]"]
        for pick in range(draft.picks):
            lines.append(f"{pick + 1}={_join(np.flatnonzero(draft.liftplan[pick]) + 1)}")
    else:
        lines += ["", "[TIEUP]"]
        for treadle in range(draft.treadles):
            lines.append(f"{treadle + 1}={_join(np.flatnonzero(draft.tieup[treadle]) + 1)}")
        lines += ["", "[TREADLING]"]
        for pick in range(draft.picks):
            lines.append(f"{pick + 1}={_join(np.flatnonzero(draft.treadling[pick]) + 1)}")
    lines += ["", "[WARP COLORS]"]
    lines += [f"{end}={int(c) + 1}" for end, c in enumerate(draft.warp_colors, start=1)]
    lines += ["", "[WEFT COLORS]"]
    lines += [f"{pick}={int(c) + 1}" for pick, c in enumerate(draft.weft_colors, start=1)]
    return "\n".join(lines) + "\n"


def save(draft: Draft, path: str | Path) -> None:
    """Write the draft to ``path`` as a WIF file (Windows line endings, as most programs expect)."""
    with open(path, "w", encoding="ascii", newline="\r\n") as handle:
        handle.write(dumps(draft))
