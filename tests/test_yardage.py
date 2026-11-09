"""Yardage: the sums, the colour split, units and bad input."""

import math

import numpy as np
import pytest

from weavegen.core import yardage
from weavegen.core.draft import Draft
from weavegen.core.yardage import Project, calculate


def striped_draft() -> Draft:
    d = Draft(ends=16, picks=4)
    d.add_palette_color("#c0392b")            # colour 3
    d.warp_colors[:] = [0] * 12 + [2] * 4     # 12 ends of colour 1, 4 of colour 3
    d.weft_colors[:] = [1, 1, 1, 2]           # 3 picks of colour 2, 1 of colour 3
    return d


BASIC = Project(width=20, length=60, epi=12, ppi=12, waste=24, warp_takeup=10, weft_takeup=5)


def test_the_basic_sums_by_hand():
    r = calculate(striped_draft(), BASIC)
    assert (r.ends, r.picks) == (240, 720)
    assert r.warp_each == pytest.approx(60 * 1.10 + 24)       # 90 in
    assert r.weft_each == pytest.approx(20 * 1.05)            # 21 in
    assert r.warp_length == pytest.approx(240 * 90) and r.weft_length == pytest.approx(720 * 21)
    assert yardage.to_big_unit(r.warp_length, "in") == pytest.approx(600)
    assert yardage.to_big_unit(r.weft_length, "in") == pytest.approx(420)
    assert r.total_length == pytest.approx(r.warp_length + r.weft_length)


def test_the_colour_strips_are_repeated_across_the_whole_project():
    r = calculate(striped_draft(), BASIC)
    by = {u.index: u for u in r.colors}
    assert by[0].ends == 180 and by[2].ends == 60            # 15 repeats of 12 + 4
    assert by[1].picks == 540 and by[2].picks == 180         # 180 repeats of 3 + 1
    assert by[0].warp_length == pytest.approx(180 * 90) and by[1].weft_length == pytest.approx(540 * 21)
    assert sum(u.ends for u in r.colors) == r.ends and sum(u.picks for u in r.colors) == r.picks
    assert sum(u.total for u in r.colors) == pytest.approx(r.total_length)


def test_a_project_that_is_not_a_whole_number_of_repeats_uses_the_start_of_the_next_one():
    p = Project(width=2, length=1, epi=10, ppi=10)            # 20 ends: one repeat of 16 plus 4
    r = calculate(striped_draft(), p)
    by = {u.index: u.ends for u in r.colors if u.ends}
    assert by == {0: 16, 2: 4}                               # 12 + 4 from the first repeat, then 4 more of colour 1


def test_colours_nothing_uses_are_left_out():
    r = calculate(striped_draft(), BASIC)
    assert [u.index for u in r.colors] == [0, 1, 2]
    d = Draft(ends=4, picks=4)
    d.add_palette_color("#00ff00")
    assert [u.index for u in calculate(d, BASIC).colors] == [0, 1]


def test_shrinkage_means_weaving_more_than_the_finished_size():
    r = calculate(Draft(), Project(width=18, length=54, epi=10, ppi=10, width_shrinkage=10, length_shrinkage=10))
    assert r.loom_width == pytest.approx(20) and r.loom_length == pytest.approx(60)
    assert (r.ends, r.picks) == (200, 600)


def test_takeup_and_waste_apply_to_the_warp_and_draw_in_to_the_weft():
    flat = calculate(Draft(), Project(width=10, length=10, epi=10, ppi=10))
    assert flat.warp_each == pytest.approx(10) and flat.weft_each == pytest.approx(10)
    more = calculate(Draft(), Project(width=10, length=10, epi=10, ppi=10, waste=5, warp_takeup=20, weft_takeup=50))
    assert more.warp_each == pytest.approx(17) and more.weft_each == pytest.approx(15)


def test_metric_projects_report_metres():
    p = Project(width=50, length=150, epi=5, ppi=4, waste=60, warp_takeup=10, weft_takeup=0, unit="cm")
    r = calculate(Draft(), p)
    assert (r.ends, r.picks) == (250, 600)
    assert r.warp_each == pytest.approx(150 * 1.1 + 60)
    assert yardage.to_big_unit(r.total_length, "cm") == pytest.approx((250 * 225 + 600 * 50) / 100)
    text = yardage.format_report(r)
    assert " m" in text and "yd" not in text and "cm" in text


def test_the_totals_equal_the_sum_over_colours_for_awkward_numbers():
    d = striped_draft()
    for w, l, epi, ppi in ((7.3, 11.9, 9.5, 13.25), (0.2, 0.2, 5, 5), (33, 2, 3.3, 8)):
        r = calculate(d, Project(width=w, length=l, epi=epi, ppi=ppi, waste=3, warp_takeup=7, weft_takeup=3))
        assert sum(u.total for u in r.colors) == pytest.approx(r.total_length)
        assert r.ends >= 1 and r.picks >= 1


def test_a_tiny_project_still_has_at_least_one_end_and_pick():
    r = calculate(Draft(), Project(width=0.01, length=0.01, epi=1, ppi=1))
    assert (r.ends, r.picks) == (1, 1)


@pytest.mark.parametrize("change,fragment", [
    ({"width": 0}, "width must be a number greater than 0"),
    ({"length": -3}, "length must be a number greater than 0"),
    ({"epi": 0}, "epi must be"),
    ({"ppi": float("nan")}, "ppi must be"),
    ({"width": float("inf")}, "width must be"),
    ({"width": True}, "width must be"),
    ({"width": "20"}, "width must be"),
    ({"waste": -1}, "waste must be 0 or more"),
    ({"warp_takeup": -1}, "warp take-up must be a percentage"),
    ({"weft_takeup": 101}, "weft take-up must be a percentage"),
    ({"width_shrinkage": 95}, "width shrinkage must be a percentage"),
    ({"length_shrinkage": -2}, "length shrinkage must be a percentage"),
    ({"unit": "ft"}, "unit must be"),
])
def test_bad_measurements_are_refused_with_the_field_named(change, fragment):
    values = {"width": 20, "length": 60, "epi": 12, "ppi": 12, **change}
    with pytest.raises(ValueError, match=fragment):
        calculate(Draft(), Project(**values))


def test_an_absurdly_large_project_is_refused():
    with pytest.raises(ValueError, match="threads"):
        calculate(Draft(), Project(width=100000, length=10, epi=100, ppi=1))


def test_the_report_text_has_the_headline_numbers_and_a_row_per_colour():
    text = yardage.format_report(calculate(striped_draft(), BASIC))
    assert "Warp: 240 ends of 90.0 in each = 600.00 yd" in text
    assert "Weft: 720 picks of 21.0 in each = 420.00 yd" in text
    assert "Total: 1,020.00 yd" in text
    rows = [line for line in text.splitlines() if line.startswith("#")]
    assert len(rows) == 3 and rows[0].startswith("#1 #1f2937") and rows[2].startswith("#3 #c0392b")
    assert math.isclose(float(rows[0].split()[-1]), 180 * 90 / 36)
