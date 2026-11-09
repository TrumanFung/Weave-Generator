"""Selection rectangles and the mapping between panel matrices and the screen.

A selection lives in *matrix* coordinates (see ``Draft.matrix``): rows then columns, the same
numbers as ``Hit.a`` / ``Hit.b``. The screen shows ends right-to-left and shafts bottom-to-top,
so a few helpers translate between matrix axes and what the user sees.
"""

from __future__ import annotations

from dataclasses import dataclass

from weavegen.core.draft import Draft


@dataclass(frozen=True)
class Rect:
    """An inclusive rectangle of matrix cells."""

    r0: int
    r1: int
    c0: int
    c1: int

    @classmethod
    def spanning(cls, a: tuple[int, int], b: tuple[int, int]) -> "Rect":
        """The smallest rectangle containing two (row, col) cells, in either order."""
        return cls(min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]))

    @property
    def rows(self) -> slice:
        return slice(self.r0, self.r1 + 1)

    @property
    def cols(self) -> slice:
        return slice(self.c0, self.c1 + 1)

    @property
    def height(self) -> int:
        return self.r1 - self.r0 + 1

    @property
    def width(self) -> int:
        return self.c1 - self.c0 + 1

    def fits(self, shape: tuple[int, int]) -> bool:
        return 0 <= self.r0 <= self.r1 < shape[0] and 0 <= self.c0 <= self.c1 < shape[1]


def matrix_to_display(draft: Draft, panel: str, rect: Rect) -> tuple[int, int, int, int]:
    """Display (row0, col0, row1, col1), inclusive, of a matrix rectangle within its panel grid."""
    if panel == "threading":
        # matrix (end, shaft) -> display row = shafts-1-shaft, col = ends-1-end
        return (draft.shafts - 1 - rect.c1, draft.ends - 1 - rect.r1,
                draft.shafts - 1 - rect.c0, draft.ends - 1 - rect.r0)
    if panel == "tieup":
        # matrix (treadle, shaft) -> display row = shafts-1-shaft, col = treadle
        return (draft.shafts - 1 - rect.c1, rect.r0, draft.shafts - 1 - rect.c0, rect.r1)
    if panel in ("treadling", "liftplan"):
        return (rect.r0, rect.c0, rect.r1, rect.c1)
    raise ValueError(f"unknown panel {panel!r}")


def display_axis(panel: str, direction: str) -> str:
    """Which matrix axis ("rows" or "cols") runs horizontally ("h") or vertically ("v") on screen."""
    if direction not in ("h", "v"):
        raise ValueError("direction must be 'h' or 'v'")
    horizontal_is_rows = panel in ("threading", "tieup")  # ends / treadles run across the screen
    if panel not in ("threading", "tieup", "treadling", "liftplan"):
        raise ValueError(f"unknown panel {panel!r}")
    if direction == "h":
        return "rows" if horizontal_is_rows else "cols"
    return "cols" if horizontal_is_rows else "rows"


def display_shift_to_matrix(panel: str, dcol: int, drow: int) -> tuple[int, int]:
    """Convert an on-screen shift (+dcol = right, +drow = down) to (row shift, col shift) in the matrix."""
    if panel == "threading":
        return -dcol, -drow      # ends run right-to-left, shafts bottom-to-top
    if panel == "tieup":
        return dcol, -drow       # treadles run left-to-right, shafts bottom-to-top
    if panel in ("treadling", "liftplan"):
        return drow, dcol
    raise ValueError(f"unknown panel {panel!r}")
