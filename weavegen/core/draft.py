"""The weaving draft: threading, tie-up, treadling (or liftplan) and the derived drawdown.

Conventions (all indices are 0-based internally; the UI shows them 1-based):

* ``threading[end]`` is the shaft that end is threaded on, or ``UNTHREADED``.
* ``tieup[treadle, shaft]`` is True when that treadle is tied to that shaft.
* ``treadling[pick, treadle]`` is True when that treadle is pressed for that pick,
  so several treadles per pick are allowed.
* ``liftplan[pick, shaft]`` is used instead of treadling + tie-up in liftplan mode.
* ``drawdown()`` returns a ``(picks, ends)`` bool array, True where the warp end is
  on top of the weft.

Rising shed: tied/lifted shafts raise their ends. Sinking shed: tied/lifted shafts
lower their ends, so the result is inverted. An unthreaded end is never moved by a
shaft, so it stays down in a rising shed and up in a sinking shed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_SHAFTS = 32
MAX_TREADLES = 32
MAX_ENDS = 400
MAX_PICKS = 400

UNTHREADED = -1


@dataclass(frozen=True)
class DraftState:
    """An immutable copy of everything a Draft holds, used for undo/redo."""

    threading: np.ndarray
    tieup: np.ndarray
    treadling: np.ndarray
    liftplan: np.ndarray
    rising: bool
    liftplan_mode: bool


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}, got {value}")


def _resized(array: np.ndarray, shape: tuple[int, ...], fill) -> np.ndarray:
    """A new array of ``shape`` holding ``array``'s overlapping region, ``fill`` elsewhere."""
    out = np.full(shape, fill, dtype=array.dtype)
    overlap = tuple(slice(0, min(a, b)) for a, b in zip(array.shape, shape))
    out[overlap] = array[overlap]
    return out


class Draft:
    def __init__(self, ends: int = 16, picks: int = 16, shafts: int = 4, treadles: int = 4,
                 *, rising: bool = True) -> None:
        _check_range("ends", ends, 1, MAX_ENDS)
        _check_range("picks", picks, 1, MAX_PICKS)
        _check_range("shafts", shafts, 1, MAX_SHAFTS)
        _check_range("treadles", treadles, 1, MAX_TREADLES)
        self.threading = np.full(ends, UNTHREADED, dtype=np.int16)
        self.tieup = np.zeros((treadles, shafts), dtype=bool)
        self.treadling = np.zeros((picks, treadles), dtype=bool)
        self.liftplan = np.zeros((picks, shafts), dtype=bool)
        self.rising = rising
        self.liftplan_mode = False

    @classmethod
    def twill_2_2(cls, ends: int = 16, picks: int = 16) -> "Draft":
        """A 4-shaft 2/2 twill on a straight draw, a sensible starting draft."""
        draft = cls(ends=ends, picks=picks, shafts=4, treadles=4)
        for end in range(ends):
            draft.threading[end] = end % 4
        for treadle in range(4):
            draft.tieup[treadle, treadle] = True
            draft.tieup[treadle, (treadle + 1) % 4] = True
        for pick in range(picks):
            draft.treadling[pick, pick % 4] = True
        return draft

    # ---- dimensions ----
    @property
    def ends(self) -> int:
        return int(self.threading.shape[0])

    @property
    def picks(self) -> int:
        return int(self.treadling.shape[0])

    @property
    def shafts(self) -> int:
        return int(self.tieup.shape[1])

    @property
    def treadles(self) -> int:
        return int(self.tieup.shape[0])

    # ---- derived cloth ----
    def lifts(self) -> np.ndarray:
        """``(picks, shafts)`` bool: which shafts move on each pick."""
        if self.liftplan_mode:
            return self.liftplan
        return (self.treadling.astype(np.uint16) @ self.tieup.astype(np.uint16)) > 0

    def drawdown(self) -> np.ndarray:
        """``(picks, ends)`` bool, True where the warp end is on top."""
        moved = self.lifts()
        threaded = self.threading >= 0
        shaft_of_end = np.where(threaded, self.threading, 0)
        hit = moved[:, shaft_of_end] & threaded[None, :]
        return hit if self.rising else ~hit

    # ---- editing; each mutator returns True if it changed the draft ----
    @staticmethod
    def _index(name: str, value: int, size: int) -> None:
        if not 0 <= value < size:
            raise IndexError(f"{name} {value} out of range 0..{size - 1}")

    def set_thread(self, end: int, shaft: int | None) -> bool:
        """Thread ``end`` on ``shaft``; ``None`` leaves the end unthreaded."""
        self._index("end", end, self.ends)
        new = UNTHREADED if shaft is None else shaft
        if shaft is not None:
            self._index("shaft", shaft, self.shafts)
        if self.threading[end] == new:
            return False
        self.threading[end] = new
        return True

    def set_tieup(self, treadle: int, shaft: int, value: bool) -> bool:
        self._index("treadle", treadle, self.treadles)
        self._index("shaft", shaft, self.shafts)
        if self.tieup[treadle, shaft] == value:
            return False
        self.tieup[treadle, shaft] = value
        return True

    def set_treadling(self, pick: int, treadle: int, value: bool) -> bool:
        self._index("pick", pick, self.picks)
        self._index("treadle", treadle, self.treadles)
        if self.treadling[pick, treadle] == value:
            return False
        self.treadling[pick, treadle] = value
        return True

    def set_lift(self, pick: int, shaft: int, value: bool) -> bool:
        self._index("pick", pick, self.picks)
        self._index("shaft", shaft, self.shafts)
        if self.liftplan[pick, shaft] == value:
            return False
        self.liftplan[pick, shaft] = value
        return True

    def set_rising(self, rising: bool) -> bool:
        if self.rising == rising:
            return False
        self.rising = rising
        return True

    def set_liftplan_mode(self, on: bool) -> bool:
        """Switch between treadling + tie-up and a direct liftplan.

        Turning liftplan mode on converts the current treadling into a liftplan, so the
        cloth is unchanged. Turning it off returns to the stored treadling and tie-up.
        """
        if self.liftplan_mode == on:
            return False
        if on:
            self.liftplan = self.lifts().copy()
        self.liftplan_mode = on
        return True

    def resize(self, *, ends: int | None = None, picks: int | None = None,
               shafts: int | None = None, treadles: int | None = None) -> bool:
        """Change dimensions, keeping what still fits. Raises ValueError, changing nothing,
        if any value is out of range. Ends threaded on a removed shaft become unthreaded."""
        new_ends = self.ends if ends is None else ends
        new_picks = self.picks if picks is None else picks
        new_shafts = self.shafts if shafts is None else shafts
        new_treadles = self.treadles if treadles is None else treadles
        _check_range("ends", new_ends, 1, MAX_ENDS)
        _check_range("picks", new_picks, 1, MAX_PICKS)
        _check_range("shafts", new_shafts, 1, MAX_SHAFTS)
        _check_range("treadles", new_treadles, 1, MAX_TREADLES)
        if (new_ends, new_picks, new_shafts, new_treadles) == (
                self.ends, self.picks, self.shafts, self.treadles):
            return False

        threading = _resized(self.threading, (new_ends,), UNTHREADED)
        threading[threading >= new_shafts] = UNTHREADED
        self.threading = threading
        self.tieup = _resized(self.tieup, (new_treadles, new_shafts), False)
        self.treadling = _resized(self.treadling, (new_picks, new_treadles), False)
        self.liftplan = _resized(self.liftplan, (new_picks, new_shafts), False)
        return True

    def clear(self) -> bool:
        """Blank threading, tie-up, treadling and liftplan, keeping dimensions and mode."""
        if not (self.threading >= 0).any() and not self.tieup.any() \
                and not self.treadling.any() and not self.liftplan.any():
            return False
        self.threading[:] = UNTHREADED
        self.tieup[:] = False
        self.treadling[:] = False
        self.liftplan[:] = False
        return True

    # ---- snapshots for undo/redo ----
    def snapshot(self) -> DraftState:
        return DraftState(
            threading=self.threading.copy(),
            tieup=self.tieup.copy(),
            treadling=self.treadling.copy(),
            liftplan=self.liftplan.copy(),
            rising=self.rising,
            liftplan_mode=self.liftplan_mode,
        )

    def restore(self, state: DraftState) -> None:
        self.threading = state.threading.copy()
        self.tieup = state.tieup.copy()
        self.treadling = state.treadling.copy()
        self.liftplan = state.liftplan.copy()
        self.rising = state.rising
        self.liftplan_mode = state.liftplan_mode
