"""Float finder: run lengths, which cells count, and the report."""

import numpy as np
import pytest

from weavegen.core import analysis, patterns
from weavegen.core.analysis import Float
from weavegen.core.draft import Draft


def brute_runs(bits: np.ndarray, axis: int) -> np.ndarray:
    """Run length of every cell along ``axis``, the slow obvious way."""
    out = np.zeros(bits.shape, dtype=int)
    lines = bits.shape[1] if axis == 0 else bits.shape[0]
    for k in range(lines):
        line = bits[:, k] if axis == 0 else bits[k, :]
        i = 0
        while i < len(line):
            j = i
            while j < len(line) and line[j] == line[i]:
                j += 1
            for m in range(i, j):
                if axis == 0:
                    out[m, k] = j - i
                else:
                    out[k, m] = j - i
            i = j
    return out


def random_draft(seed: int) -> Draft:
    rng = np.random.default_rng(seed)
    d = Draft(ends=int(rng.integers(1, 30)), picks=int(rng.integers(1, 30)),
              shafts=int(rng.integers(1, 9)), treadles=int(rng.integers(1, 9)), rising=bool(rng.integers(2)))
    d.threading[:] = rng.integers(-1, d.shafts, d.ends)
    d.tieup[:] = rng.random(d.tieup.shape) < 0.4
    d.treadling[:] = rng.random(d.treadling.shape) < 0.3
    return d


# ---- run lengths ----

def test_run_lengths_on_a_small_example():
    bits = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0]], dtype=bool)
    assert analysis.run_length_map(bits, 0).tolist() == [[2, 1, 3], [2, 2, 3], [1, 2, 3]]
    assert analysis.run_length_map(bits, 1).tolist() == [[2, 2, 1], [1, 2, 2], [3, 3, 3]]


def test_a_run_never_continues_from_the_end_of_one_line_into_the_next():
    ones = np.ones((3, 2), dtype=bool)
    assert (analysis.run_length_map(ones, 0) == 3).all()      # not 6
    assert (analysis.run_length_map(ones, 1) == 2).all()      # not 6


def test_run_lengths_need_a_valid_axis():
    with pytest.raises(ValueError):
        analysis.run_length_map(np.zeros((2, 2), dtype=bool), 2)


@pytest.mark.parametrize("seed", range(25))
def test_run_lengths_match_a_slow_reference(seed):
    rng = np.random.default_rng(seed)
    bits = rng.random((int(rng.integers(1, 20)), int(rng.integers(1, 20)))) < 0.5
    assert (analysis.run_length_map(bits, 0) == brute_runs(bits, 0)).all()
    assert (analysis.run_length_map(bits, 1) == brute_runs(bits, 1)).all()


# ---- known cloths ----

def test_plain_weave_has_no_float_longer_than_one():
    d = patterns.build_preset("plain", 12, 12)
    report = analysis.analyse_floats(d, 1)
    assert report.floats == [] and set(report.longest.values()) == {1}
    assert not analysis.float_mask(d, 1).any()


def test_a_2_2_twill_floats_over_and_under_two_everywhere():
    d = Draft.twill_2_2()
    assert set(analysis.analyse_floats(d, 2).longest.values()) == {2}
    assert not analysis.float_mask(d, 2).any()
    assert analysis.float_mask(d, 1)[1:-1, 1:-1].all()    # inside the draft every cell is on a float of two
    # (the edge threads are cut short by the edge of the draft)


def test_a_five_shaft_satin_floats_four_on_one_side_and_one_on_the_other():
    d = patterns.build_preset("satin_5", 10, 10)
    longest = analysis.analyse_floats(d, 3).longest
    assert longest == {("warp", "face"): 1, ("warp", "back"): 4, ("weft", "face"): 4, ("weft", "back"): 1}


def test_a_sinking_shed_swaps_face_and_back():
    d = patterns.build_preset("satin_5", 10, 10)
    d.set_rising(False)
    longest = analysis.analyse_floats(d, 3).longest
    assert longest[("warp", "face")] == 4 and longest[("weft", "back")] == 4
    assert longest[("warp", "back")] == 1 and longest[("weft", "face")] == 1


def test_floats_are_reported_with_their_position_numbered_from_zero():
    d = patterns.build_preset("satin_5", 10, 10)
    floats = analysis.analyse_floats(d, 3).floats
    assert Float("warp", "back", 0, 1, 4) in floats       # end 1 lies under picks 2 to 5
    assert Float("warp", "back", 3, 0, 4) in floats       # end 4: picks 1 to 4
    assert all(f.length == 4 for f in floats)


def test_unthreaded_ends_are_full_length_floats():
    d = Draft(ends=5, picks=6)           # nothing threaded, rising shed: every end stays down
    report = analysis.analyse_floats(d, 1)
    assert report.longest[("warp", "back")] == 6 and report.longest[("weft", "face")] == 5
    assert analysis.float_mask(d, 5).all()


def test_the_limit_means_longer_than_and_must_be_a_positive_whole_number():
    d = patterns.build_preset("satin_5", 10, 10)
    assert analysis.analyse_floats(d, 3).floats and not analysis.analyse_floats(d, 4).floats
    for bad in (0, -1, 2.5, "3", None):
        with pytest.raises(ValueError, match="float limit"):
            analysis.float_mask(d, bad)
        with pytest.raises(ValueError, match="float limit"):
            analysis.analyse_floats(d, bad)


def test_sides_can_be_chosen_and_unknown_sides_are_refused():
    d = patterns.build_preset("satin_5", 10, 10)
    face, back = analysis.analyse_floats(d, 3, ["face"]), analysis.analyse_floats(d, 3, ["back"])
    assert face.longest == {("warp", "face"): 1, ("weft", "face"): 4}
    assert back.longest == {("warp", "back"): 4, ("weft", "back"): 1}
    assert all(f.side == "face" for f in face.floats) and all(f.side == "back" for f in back.floats)
    weft_face = analysis.float_mask(d, 3, ["face"])
    assert weft_face.any() and not (weft_face & d.drawdown()).any()     # face floats of this satin are weft: warp is down
    with pytest.raises(ValueError, match="sides"):
        analysis.float_mask(d, 3, ["top"])


# ---- agreement between the two interfaces and a reference ----

def reference_mask(d: Draft, limit: int, sides) -> np.ndarray:
    up = d.drawdown()
    warp, weft = brute_runs(up, 0), brute_runs(up, 1)
    mask = np.zeros_like(up)
    for r in range(up.shape[0]):
        for c in range(up.shape[1]):
            if "face" in sides and ((up[r, c] and warp[r, c] > limit) or (not up[r, c] and weft[r, c] > limit)):
                mask[r, c] = True
            if "back" in sides and ((not up[r, c] and warp[r, c] > limit) or (up[r, c] and weft[r, c] > limit)):
                mask[r, c] = True
    return mask


@pytest.mark.parametrize("seed", range(30))
def test_the_mask_and_the_report_agree_with_a_slow_reference(seed):
    d = random_draft(seed)
    for limit in (1, 2, 4):
        for sides in (("face", "back"), ("face",), ("back",)):
            assert (analysis.float_mask(d, limit, sides) == reference_mask(d, limit, sides)).all()
            # every float the report lists lies inside the mask, and together they cover it
            covered = np.zeros(d.drawdown().shape, dtype=bool)
            for f in analysis.analyse_floats(d, limit, sides).floats:
                if f.kind == "warp":
                    covered[f.start:f.start + f.length, f.thread] = True
                else:
                    covered[f.thread, f.start:f.start + f.length] = True
            assert (covered == analysis.float_mask(d, limit, sides)).all()


def test_floats_are_listed_longest_first():
    d = random_draft(7)
    lengths = [f.length for f in analysis.analyse_floats(d, 1).floats]
    assert lengths == sorted(lengths, reverse=True)


# ---- the text report ----

def test_describe_with_no_floats():
    text = analysis.describe(analysis.analyse_floats(Draft.twill_2_2(), 2))
    assert text.startswith("No floats longer than 2.") and "warp on the face: 2" in text


def test_describe_lists_the_longest_and_counts_the_rest():
    d = patterns.build_preset("satin_5", 10, 10)
    text = analysis.describe(analysis.analyse_floats(d, 3))
    assert text.startswith("28 floats longer than 3.")
    assert "4 warp on the back: end 1, picks 2-5" in text and "... and 20 more" in text
    assert "weft on the face: 4" in text


def test_describe_uses_the_singular_and_only_the_analysed_sides():
    d = Draft(ends=1, picks=4)           # one unthreaded end: a single warp float on the back
    text = analysis.describe(analysis.analyse_floats(d, 3, ["back"]))
    assert text.startswith("1 float longer than 3.") and "on the face" not in text
