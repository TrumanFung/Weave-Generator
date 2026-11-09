"""WIF import and export: round trips, hand-written files from other programs, and bad input."""

from datetime import date

import numpy as np
import pytest

from weavegen.core.draft import MAX_ENDS, Draft
from weavegen.io import wif


def same_cloth(a: Draft, b: Draft) -> bool:
    return (a.ends, a.picks, a.shafts, a.treadles) == (b.ends, b.picks, b.shafts, b.treadles) \
        and a.rising == b.rising and a.liftplan_mode == b.liftplan_mode \
        and (a.threading == b.threading).all() and (a.drawdown() == b.drawdown()).all() \
        and a.palette == b.palette \
        and (a.warp_colors == b.warp_colors).all() and (a.weft_colors == b.weft_colors).all()


def random_draft(seed: int) -> Draft:
    rng = np.random.default_rng(seed)
    d = Draft(ends=int(rng.integers(1, 40)), picks=int(rng.integers(1, 40)),
              shafts=int(rng.integers(1, 12)), treadles=int(rng.integers(1, 12)),
              rising=bool(rng.integers(2)))
    d.threading[:] = rng.integers(-1, d.shafts, d.ends)
    d.tieup[:] = rng.random(d.tieup.shape) < 0.4
    d.treadling[:] = rng.random(d.treadling.shape) < 0.3
    d.liftplan[:] = rng.random(d.liftplan.shape) < 0.3
    for _ in range(int(rng.integers(0, 6))):
        d.add_palette_color("#{:06x}".format(int(rng.integers(0, 1 << 24))))
    d.warp_colors[:] = rng.integers(0, len(d.palette), d.ends)
    d.weft_colors[:] = rng.integers(0, len(d.palette), d.picks)
    d.liftplan_mode = bool(rng.integers(2))
    return d


# ---- round trips ----

def test_the_default_twill_survives_a_round_trip():
    original = Draft.twill_2_2()
    result = wif.loads(wif.dumps(original))
    assert result.warnings == [] and same_cloth(original, result.draft)


@pytest.mark.parametrize("seed", range(40))
def test_random_drafts_survive_a_round_trip(seed):
    original = random_draft(seed)
    result = wif.loads(wif.dumps(original))
    assert result.warnings == []
    assert same_cloth(original, result.draft)


def test_a_round_trip_keeps_several_treadles_per_pick_and_unthreaded_ends():
    d = Draft(ends=4, picks=2, shafts=3, treadles=3)
    d.threading[:] = [0, -1, 2, 1]
    d.tieup[0, 0] = d.tieup[1, 1] = d.tieup[2, 2] = True
    d.treadling[0, 0] = d.treadling[0, 2] = True
    out = wif.loads(wif.dumps(d)).draft
    assert out.threading.tolist() == [0, -1, 2, 1]
    assert out.treadling.tolist() == [[True, False, True], [False, False, False]]
    assert out.tieup.tolist() == d.tieup.tolist()


def test_a_draft_with_one_colour_round_trips_with_the_default_colours_in_place():
    d = Draft(ends=2, picks=2)
    d.remove_palette_color(1)
    out = wif.loads(wif.dumps(d)).draft
    assert out.palette == d.palette and out.weft_colors.tolist() == [0, 0]


# ---- what is written ----

def test_dumps_is_deterministic_for_a_given_date_and_uses_one_based_numbers():
    d = Draft.twill_2_2(ends=4, picks=4)
    text = wif.dumps(d, when=date(2026, 3, 7))
    assert text == wif.dumps(d, when=date(2026, 3, 7))
    assert "Date=March 7, 2026" in text
    assert "[THREADING]\n1=1\n2=2\n3=3\n4=4\n" in text
    assert "[TIEUP]\n1=1,2\n2=2,3\n3=3,4\n4=1,4\n" in text
    assert "Rising Shed=true" in text and "Shafts=4" in text and "Treadles=4" in text


def test_a_sinking_shed_is_written_as_false():
    d = Draft(rising=False)
    assert "Rising Shed=false" in wif.dumps(d)
    assert wif.loads(wif.dumps(d)).draft.rising is False


def test_liftplan_mode_writes_the_liftplan_and_not_the_hidden_tieup_and_treadling():
    d = Draft.twill_2_2(ends=4, picks=4)
    d.set_liftplan_mode(True)
    text = wif.dumps(d)
    assert "[LIFTPLAN]" in text and "[TIEUP]" not in text and "[TREADLING]" not in text
    back = wif.loads(text).draft
    assert back.liftplan_mode and (back.drawdown() == d.drawdown()).all()


def test_colours_are_written_as_an_rgb_table():
    d = Draft(ends=1, picks=1)
    d.add_palette_color("#ff8000")
    text = wif.dumps(d)
    assert "[COLOR TABLE]\n1=31,41,55\n2=248,250,252\n3=255,128,0\n" in text
    assert "Entries=3" in text


def test_save_writes_ascii_with_windows_line_endings_and_load_reads_it_back(tmp_path):
    d = random_draft(3)
    path = tmp_path / "draft.wif"
    wif.save(d, path)
    raw = path.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    raw.decode("ascii")
    assert same_cloth(d, wif.load(path).draft)


# ---- files written by other programs ----

HAND_WRITTEN = """﻿; made by some other program
[wif]
Version=1.1
Source Program = SomeWeaver

[Contents]
Weaving=yes
Threading=yes

[WEAVING]
Shafts = 4
Treadles=4
Rising Shed = false

[warp]
Threads=6
Color=1

[WEFT]
Threads=4
Color=2

[COLOR PALETTE]
Entries=3
Form=RGB
Range=0,999

[COLOR TABLE]
1=999,0,0
2=0,500,999
5=0,0,0

[THREADING]
1=1
2=2
3=3
4=4
5=1
; end 6 is left unthreaded

[TIEUP]
1=1,2
2=2,3
3=3,4
4=4,1

[TREADLING]
1=1
2=2
3=3
4=4

[WARP COLORS]
2=5
"""


def test_a_hand_written_file_with_other_programs_conventions_loads():
    result = wif.loads(HAND_WRITTEN.replace("\n", "\r\n"))
    d = result.draft
    assert (d.ends, d.picks, d.shafts, d.treadles) == (6, 4, 4, 4)
    assert d.rising is False
    assert d.threading.tolist() == [0, 1, 2, 3, 0, -1]
    assert d.tieup.tolist() == [[True, True, False, False], [False, True, True, False],
                                [False, False, True, True], [True, False, False, True]]
    assert d.treadling.argmax(axis=1).tolist() == [0, 1, 2, 3]
    assert result.warnings == []


def test_the_colour_range_is_scaled_and_sparse_colour_numbers_are_mapped():
    d = wif.loads(HAND_WRITTEN).draft
    assert d.palette == ["#ff0000", "#0080ff", "#000000"]      # 500 of 999 scales to 127.6, i.e. 0x80
    assert d.warp_colors.tolist() == [0, 2, 0, 0, 0, 0]        # file colour 5 is palette entry 3
    assert d.weft_colors.tolist() == [1, 1, 1, 1]              # default weft colour 2 -> entry 2


def test_a_file_without_a_colour_table_gets_the_default_palette():
    d = wif.loads("[WIF]\n[WEAVING]\nShafts=2\nTreadles=2\n[WARP]\nThreads=2\n[WEFT]\nThreads=2\n").draft
    assert d.palette == ["#1f2937", "#f8fafc"] and d.weft_colors.tolist() == [1, 1]


def test_missing_counts_are_taken_from_what_the_file_uses():
    d = wif.loads("[WIF]\n[THREADING]\n1=1\n2=3\n[TIEUP]\n1=1\n2=2\n3=3\n[TREADLING]\n1=1\n2=2\n3=3\n").draft
    assert (d.ends, d.picks, d.shafts, d.treadles) == (2, 3, 3, 3)


def test_a_liftplan_only_file_opens_in_liftplan_mode():
    text = "[WIF]\n[WEAVING]\nShafts=3\n[WARP]\nThreads=3\n[WEFT]\nThreads=2\n" \
           "[THREADING]\n1=1\n2=2\n3=3\n[LIFTPLAN]\n1=1,2\n2=3\n"
    d = wif.loads(text).draft
    assert d.liftplan_mode and d.liftplan.tolist() == [[True, True, False], [False, False, True]]
    assert d.drawdown()[0].tolist() == [True, True, False]


def test_an_end_threaded_on_several_shafts_keeps_the_lowest_and_warns():
    text = "[WIF]\n[WEAVING]\nShafts=4\nTreadles=1\n[WARP]\nThreads=3\n[WEFT]\nThreads=1\n" \
           "[THREADING]\n1=3,2\n2=4\n3=1\n"
    result = wif.loads(text)
    assert result.draft.threading.tolist() == [1, 3, 0]
    assert len(result.warnings) == 1 and "more than one shaft" in result.warnings[0] and "1" in result.warnings[0]


def test_a_zero_thread_means_unthreaded_and_an_empty_pick_is_allowed():
    text = "[WIF]\n[WEAVING]\nShafts=2\nTreadles=2\n[WARP]\nThreads=2\n[WEFT]\nThreads=2\n" \
           "[THREADING]\n1=0\n2=2\n[TREADLING]\n1=\n2=1,2\n"
    d = wif.loads(text).draft
    assert d.threading.tolist() == [-1, 1] and d.treadling.tolist() == [[False, False], [True, True]]


def test_a_liftplan_that_disagrees_with_the_treadling_warns_and_the_treadling_wins():
    text = "[WIF]\n[WEAVING]\nShafts=2\nTreadles=1\n[WARP]\nThreads=2\n[WEFT]\nThreads=1\n" \
           "[THREADING]\n1=1\n2=2\n[TIEUP]\n1=1\n[TREADLING]\n1=1\n[LIFTPLAN]\n1=2\n"
    result = wif.loads(text)
    assert not result.draft.liftplan_mode and result.draft.drawdown().tolist() == [[True, False]]
    assert any("disagree" in w for w in result.warnings)


def test_threads_with_colours_missing_from_the_table_keep_the_default_and_warn():
    text = "[WIF]\n[WEAVING]\nShafts=1\nTreadles=1\n[WARP]\nThreads=2\n[WEFT]\nThreads=1\n" \
           "[COLOR TABLE]\n1=0,0,0\n[WARP COLORS]\n1=1\n2=9\n"
    result = wif.loads(text)
    assert result.draft.warp_colors.tolist() == [0, 0]
    assert any("9" in w and "colour table" in w for w in result.warnings)


def test_a_colour_form_other_than_rgb_falls_back_to_the_defaults_with_a_warning():
    text = "[WIF]\n[WEAVING]\nShafts=1\nTreadles=1\n[WARP]\nThreads=1\n[WEFT]\nThreads=1\n" \
           "[COLOR PALETTE]\nForm=Ramie\n[COLOR TABLE]\n1=1,2,3\n"
    result = wif.loads(text)
    assert result.draft.palette == ["#1f2937", "#f8fafc"] and result.warnings


def test_windows_text_files_that_are_not_utf8_still_load(tmp_path):
    path = tmp_path / "old.wif"
    path.write_bytes("[WIF]\nDevelopers=Zo\xeb\n[WEAVING]\nShafts=1\nTreadles=1\n"
                     "[WARP]\nThreads=1\n[WEFT]\nThreads=1\n".encode("cp1252"))
    assert wif.load(path).draft.ends == 1


# ---- bad input is reported, never half-loaded ----

@pytest.mark.parametrize("text,fragment", [
    ("hello world", "does not look like a WIF"),
    ("", "does not look like a WIF"),
    ("[WIF]\n[WEAVING\nShafts=4", "unfinished section"),
    ("Shafts=4\n[WIF]", "does not look like a WIF"),
    ("[WIF]\nnonsense line", "expected key=value"),
    ("[WIF]\n[WEAVING]\nShafts=four", "not a whole number"),
    ("[WIF]\n[WEAVING]\nShafts=0", "at least 1"),
    ("[WIF]\n[WEAVING]\nShafts=33", "at most 32"),
    (f"[WIF]\n[WARP]\nThreads={MAX_ENDS + 1}", f"at most {MAX_ENDS}"),
    ("[WIF]\n[WEAVING]\nRising Shed=maybe", "true or false"),
    ("[WIF]\n[THREADING]\n0=1", "start at 1"),
    ("[WIF]\n[WARP]\nThreads=2\n[THREADING]\n3=1", "end 3"),
    ("[WIF]\n[WEAVING]\nShafts=2\n[WARP]\nThreads=1\n[THREADING]\n1=3", "shaft 3"),
    ("[WIF]\n[WEAVING]\nShafts=2\nTreadles=2\n[TIEUP]\n3=1", "treadle 3"),
    ("[WIF]\n[WEAVING]\nShafts=2\nTreadles=1\n[WEFT]\nThreads=1\n[TREADLING]\n1=2", "treadle 2"),
    ("[WIF]\n[WEFT]\nThreads=1\n[TREADLING]\n2=1", "pick 2"),
    ("[WIF]\n[COLOR TABLE]\n1=1,2", "red, green and blue"),
    ("[WIF]\n[COLOR PALETTE]\nRange=5,5\n[COLOR TABLE]\n1=1,2,3", "Range"),
])
def test_bad_files_raise_a_clear_error(text, fragment):
    with pytest.raises(wif.WifError, match=fragment):
        wif.loads(text)


def test_wif_error_is_a_value_error():
    assert issubclass(wif.WifError, ValueError)


def test_loading_a_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        wif.load(tmp_path / "nothing.wif")
