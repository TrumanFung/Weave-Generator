"""Block substitution: the structure text, summer and winter, and expanding a profile draft."""

import numpy as np
import pytest

from weavegen.core import analysis, blocks
from weavegen.core.blocks import BlockStructure, parse_structure, substitute, summer_and_winter
from weavegen.core.draft import MAX_ENDS, Draft


def profile(threading, treadling, *, shafts=None, treadles=None) -> Draft:
    """A profile draft: ``threading`` lists a block (profile shaft) per end, ``treadling`` a block per pick."""
    shafts = shafts or max(threading) + 1
    treadles = treadles or max(treadling) + 1
    d = Draft(ends=len(threading), picks=len(treadling), shafts=shafts, treadles=treadles)
    d.threading[:] = threading
    d.treadling[np.arange(len(treadling)), treadling] = True
    return d


# ---- summer and winter ----

def test_two_block_summer_and_winter_matches_the_published_threading_and_tieup():
    sw = summer_and_winter(2)
    assert (sw.shafts, sw.treadles) == (4, 6)
    assert sw.threading == {0: (0, 2, 1, 2), 1: (0, 3, 1, 3)}          # 1-3-2-3 and 1-4-2-4
    assert sw.tieup[0].nonzero()[0].tolist() == [0, 2]                 # one pattern treadle: shafts 1 and 3 ...
    assert sw.tieup[1].nonzero()[0].tolist() == [1, 2]                 # ... and its twin: shafts 2 and 3
    assert sw.tieup[4].nonzero()[0].tolist() == [0, 1]                 # tabby A: the tie-downs
    assert sw.tieup[5].nonzero()[0].tolist() == [2, 3]                 # tabby B: every pattern shaft
    assert sw.treadling[0] == (0, 4, 1, 5) and sw.treadling[1] == (2, 4, 3, 5)


@pytest.mark.parametrize("n", [1, 2, 4, 6, 15])
def test_summer_and_winter_sizes(n):
    sw = summer_and_winter(n)
    assert (sw.shafts, sw.treadles) == (n + 2, 2 * n + 2)
    sw.check()


def test_summer_and_winter_needs_a_sensible_number_of_blocks():
    for bad in (0, 16, -1):
        with pytest.raises(ValueError, match="1 to 15 blocks"):
            summer_and_winter(bad)


def test_woven_summer_and_winter_has_plain_weave_tabby_picks_and_short_floats():
    n = 4
    prof = profile([0, 1, 2, 3, 2, 1, 0], [0, 1, 2, 3, 2, 1, 0], shafts=n, treadles=n)
    d, notes = substitute(prof, summer_and_winter(n))
    assert notes == [] and (d.ends, d.picks) == (28, 28)
    dd = d.drawdown()
    tabby_a = [dd[p] for p in range(d.picks) if p % 4 == 1]            # each block is pattern, tabby, pattern, tabby
    tabby_b = [dd[p] for p in range(d.picks) if p % 4 == 3]
    for row in tabby_a + tabby_b:
        assert (row[:-1] != row[1:]).all()                               # alternate ends: plain weave
    assert (tabby_a[0] != tabby_b[0]).all()                              # the two tabbies are opposites
    report = analysis.analyse_floats(d, 3)
    assert report.longest[("weft", "face")] <= 3 and report.longest[("weft", "back")] <= 3


def test_a_pattern_pick_floats_over_every_block_except_its_own():
    n = 3
    prof = profile([0, 1, 2], [1], shafts=n, treadles=n)               # one pick of block 2
    d, _ = substitute(prof, summer_and_winter(n))
    first_pick = d.drawdown()[0]                                       # in thread order from end 1
    block = lambda i: first_pick[4 * i:4 * i + 4]
    assert block(1).tolist() == [True, True, False, True]              # its own block: tied down, no long float
    assert block(0).tolist() == [True, False, False, False]            # the others: a float of three
    assert block(2).tolist() == [True, False, False, False]


# ---- the text form ----

def test_the_text_form_round_trips():
    for sw in (summer_and_winter(1), summer_and_winter(5)):
        back = parse_structure(blocks.format_structure(sw))
        assert (back.shafts, back.treadles) == (sw.shafts, sw.treadles)
        assert (back.tieup == sw.tieup).all() and back.threading == sw.threading and back.treadling == sw.treadling


def test_the_text_form_accepts_the_documented_spellings():
    s = parse_structure("""
        # a tiny structure
        shafts = 2
        TREADLES 3          # upper case is fine
        tieup 1 = 1
        tieup 3 = 1, 2
        block 1 threading = 1 2, 1
        block 2 threading = 2
        block 1 treadling = 3 1
    """)
    assert (s.shafts, s.treadles) == (2, 3)
    assert s.tieup.tolist() == [[True, False], [False, False], [True, True]]
    assert s.threading == {0: (0, 1, 0), 1: (1,)} and s.treadling == {0: (2, 0)}


@pytest.mark.parametrize("text,fragment", [
    ("", "how many shafts and treadles"),
    ("shafts 4", "how many shafts and treadles"),
    ("shafts 4\ntreadles", "cannot understand"),
    ("shafts four\ntreadles 2", "not a whole number"),
    ("shafts 0\ntreadles 2", "between 1 and 32"),
    ("shafts 2\ntreadles 33", "between 1 and 32"),
    ("shafts 2\ntreadles 2\nnonsense here", "line 3: cannot understand"),
    ("shafts 2\ntreadles 2\ntieup 3 = 1", "line 3: treadle 3 is outside 1 to 2"),
    ("shafts 2\ntreadles 2\ntieup 1 = 3", "line 3: shaft 3 is outside 1 to 2"),
    ("shafts 2\ntreadles 2\ntieup 0 = 1", "should be a number from 1"),
    ("shafts 2\ntreadles 2\nblock 1 threading = 1 3", "line 3: shaft 3 is outside 1 to 2"),
    ("shafts 2\ntreadles 2\nblock 1 treadling = 5", "line 3: treadle 5 is outside 1 to 2"),
    ("shafts 2\ntreadles 2\nblock 1 threading =", "cannot understand"),
    ("shafts 2\ntreadles 2\nblock 1 threading = 1\nblock 1 threading = 2", "line 4: block 1 is already defined"),
    ("shafts 2\ntreadles 2\nblock x threading = 1", "not a whole number"),
])
def test_bad_structure_text_is_reported_with_its_line(text, fragment):
    with pytest.raises(ValueError, match=fragment):
        parse_structure(text)


def test_check_rejects_inconsistent_structures():
    good = summer_and_winter(1)
    with pytest.raises(ValueError, match="tie-up does not match"):
        BlockStructure(3, 3, good.tieup).check()
    with pytest.raises(ValueError, match="shaft 9"):
        BlockStructure(2, 2, np.zeros((2, 2), dtype=bool), {0: (8,)}).check()
    with pytest.raises(ValueError, match="empty threading unit"):
        BlockStructure(2, 2, np.zeros((2, 2), dtype=bool), {0: ()}).check()


# ---- expanding a profile ----

def test_each_profile_end_and_pick_becomes_its_unit():
    sw = parse_structure("shafts 3\ntreadles 2\ntieup 1 = 1\ntieup 2 = 2, 3\n"
                         "block 1 threading = 1 2\nblock 2 threading = 3\n"
                         "block 1 treadling = 1 2 1\nblock 2 treadling = 2\n")
    d, notes = substitute(profile([0, 1, 0], [1, 0]), sw)
    assert notes == [] and (d.ends, d.picks, d.shafts, d.treadles) == (5, 4, 3, 2)
    assert d.threading.tolist() == [0, 1, 2, 0, 1]
    assert d.treadling.argmax(axis=1).tolist() == [1, 0, 1, 0]
    assert (d.tieup == sw.tieup).all() and d.treadling.sum(axis=1).tolist() == [1, 1, 1, 1]


def test_colours_and_the_shed_carry_over_from_the_profile():
    prof = profile([0, 1], [0, 1], shafts=2, treadles=2)
    prof.add_palette_color("#ff0000")
    prof.warp_colors[:] = [2, 0]
    prof.weft_colors[:] = [0, 2]
    prof.set_rising(False)
    d, _ = substitute(prof, summer_and_winter(2))
    assert d.palette == prof.palette and d.rising is False
    assert d.warp_colors.tolist() == [2] * 4 + [0] * 4
    assert d.weft_colors.tolist() == [0] * 4 + [2] * 4


def test_unthreaded_ends_and_blank_picks_are_left_out_and_reported():
    prof = Draft(ends=3, picks=3, shafts=2, treadles=2)
    prof.threading[:] = [0, -1, 1]
    prof.treadling[0, 0] = True
    prof.treadling[2, 1] = True
    d, notes = substitute(prof, summer_and_winter(2))
    assert (d.ends, d.picks) == (8, 8)
    assert len(notes) == 2 and "unthreaded" in notes[0] and "no treadle" in notes[1]


def test_the_profile_is_not_changed():
    prof = profile([0, 1, 0], [0, 1], shafts=2, treadles=2)
    before = prof.snapshot()
    substitute(prof, summer_and_winter(2))
    assert (prof.threading == before.threading).all() and (prof.treadling == before.treadling).all()
    assert prof.shafts == 2


@pytest.mark.parametrize("make,fragment", [
    (lambda: Draft(ends=2, picks=1, shafts=2, treadles=2), "no threaded ends"),
    (lambda: profile([0, 2], [0], shafts=3, treadles=1), "no threading unit for block 3"),
    (lambda: profile([0], [0, 2], shafts=1, treadles=3), "no treadling unit for block 3"),
])
def test_profiles_that_cannot_be_expanded_say_why(make, fragment):
    with pytest.raises(ValueError, match=fragment):
        substitute(make(), summer_and_winter(2))


def test_a_pick_pressing_two_treadles_is_refused():
    prof = profile([0], [0], shafts=2, treadles=2)
    prof.treadling[0, 1] = True
    with pytest.raises(ValueError, match="profile pick 1 presses several treadles"):
        substitute(prof, summer_and_winter(2))


def test_a_profile_with_nothing_to_weave_is_refused():
    only_ends = Draft(ends=2, picks=2, shafts=2, treadles=2)
    only_ends.threading[:] = [0, 1]
    with pytest.raises(ValueError, match="no picks with a treadle"):
        substitute(only_ends, summer_and_winter(2))


def test_the_result_must_fit_in_a_draft():
    prof = profile([0] * (MAX_ENDS // 4 + 1), [0], shafts=1, treadles=1)
    with pytest.raises(ValueError, match="at most 400"):
        substitute(prof, summer_and_winter(1))
    ok = profile([0] * (MAX_ENDS // 4), [0], shafts=1, treadles=1)
    assert substitute(ok, summer_and_winter(1))[0].ends == MAX_ENDS
