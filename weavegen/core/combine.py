"""Combine two drafts into one: interleaving, and double weave.

Both take draft A and draft B and weave them side by side in one cloth. Ends alternate A, B, A, B
and picks alternate A, B, A, B. B's shafts sit above A's (so shaft 1 of B becomes shaft
``A.shafts + 1``) and B's treadles follow A's. The shorter draft is repeated to match the longer.
Both drafts must use the same shed (both rising or both sinking). Thread colours carry over, with
B's colours added to the palette after A's.

* **Interleave**: A's picks lift only A's shafts and B's picks lift only B's. Each weave is woven
  by its own ends and picks, and passes over the other's ends, so the result is the two cloths
  woven through each other in one plane.
* **Double weave**: the same, but A is the *top layer* and B the *bottom layer*. While a bottom-layer
  pick is woven the top-layer ends are held out of the way (raised in a rising shed), and while a
  top-layer pick is woven the bottom-layer ends stay below it. The result is two separate cloths,
  one on top of the other. The drawdown shows the shed (which ends are lifted), not which layer
  you see on the face.
"""

from __future__ import annotations

import numpy as np

from weavegen.core.draft import (
    MAX_ENDS, MAX_PICKS, MAX_SHAFTS, MAX_TREADLES, UNTHREADED, Draft,
)

MODES = ("interleave", "double")


def _merged_palette(a: Draft, b: Draft) -> tuple[list[str], np.ndarray]:
    """A's palette followed by any of B's colours it lacks, and the map from B's indices to it."""
    palette = list(a.palette)
    remap = np.zeros(len(b.palette), dtype=np.int32)
    for index, color in enumerate(b.palette):
        if color not in palette:
            palette.append(color)
        remap[index] = palette.index(color)
    return palette, remap


def combine(a: Draft, b: Draft, mode: str = "interleave") -> Draft:
    """Interleave ``a`` and ``b`` or weave them as a double cloth with ``a`` on top.

    Returns a new draft and leaves both arguments alone. Raises ValueError if the drafts cannot be
    combined (different sheds, too many shafts or treadles, or too many ends or picks).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, got {mode!r}")
    if a.rising != b.rising:
        raise ValueError("both drafts must use the same shed: both rising or both sinking")
    layered = mode == "double"
    sh_a, sh_b = a.shafts, b.shafts
    shafts = sh_a + sh_b
    if shafts > MAX_SHAFTS:
        raise ValueError(f"the result needs {shafts} shafts ({sh_a} + {sh_b}); at most {MAX_SHAFTS} are supported")
    pairs_e = max(a.ends, b.ends)
    pairs_p = max(a.picks, b.picks)
    if 2 * pairs_e > MAX_ENDS or 2 * pairs_p > MAX_PICKS:
        raise ValueError(f"the result would have {2 * pairs_e} ends and {2 * pairs_p} picks; "
                         f"at most {MAX_ENDS} and {MAX_PICKS} are supported")
    use_treadles = not a.liftplan_mode and not b.liftplan_mode
    if use_treadles and a.treadles + b.treadles > MAX_TREADLES:
        use_treadles = False  # too many treadles to tie up: fall back to a liftplan

    out = Draft(ends=2 * pairs_e, picks=2 * pairs_p, shafts=shafts,
                treadles=min(MAX_TREADLES, a.treadles + b.treadles) if use_treadles else 1,
                rising=a.rising)

    # Threading: A's ends in the even positions, B's (on the upper shafts) in the odd ones.
    ends_a = np.arange(pairs_e) % a.ends
    ends_b = np.arange(pairs_e) % b.ends
    thr_a = a.threading[ends_a].astype(np.int16)
    thr_b = np.where(b.threading[ends_b] == UNTHREADED, UNTHREADED, b.threading[ends_b] + sh_a).astype(np.int16)
    out.threading[0::2], out.threading[1::2] = thr_a, thr_b

    # Lifts: which shafts move on each pick.
    picks_a = np.arange(pairs_p) % a.picks
    picks_b = np.arange(pairs_p) % b.picks
    if use_treadles:
        out.tieup[:a.treadles, :sh_a] = a.tieup
        out.tieup[a.treadles:, sh_a:] = b.tieup
        out.treadling[0::2, :a.treadles] = a.treadling[picks_a]
        out.treadling[1::2, a.treadles:] = b.treadling[picks_b]
        if layered:
            if a.rising:
                out.tieup[a.treadles:, :sh_a] = True    # bottom picks lift all the top layer's shafts
            else:
                out.tieup[:a.treadles, sh_a:] = True    # top picks lower all the bottom layer's shafts
    else:
        lifts = np.zeros((out.picks, shafts), dtype=bool)
        lifts[0::2, :sh_a] = a.lifts()[picks_a]
        lifts[1::2, sh_a:] = b.lifts()[picks_b]
        if layered:
            if a.rising:
                lifts[1::2, :sh_a] = True
            else:
                lifts[0::2, sh_a:] = True
        out.liftplan = lifts
        out.liftplan_mode = True

    # Colours: A's palette first, then B's extra colours.
    palette, remap_b = _merged_palette(a, b)
    out.palette = palette
    out.warp_colors[0::2] = a.warp_colors[ends_a]
    out.warp_colors[1::2] = remap_b[b.warp_colors[ends_b]]
    out.weft_colors[0::2] = a.weft_colors[picks_a]
    out.weft_colors[1::2] = remap_b[b.weft_colors[picks_b]]
    return out
