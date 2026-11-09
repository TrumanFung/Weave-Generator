"""Fabric analysis (drawdown to draft), the image import that feeds it, and network drafting."""

import numpy as np
import pytest
from PIL import Image

from weavegen.core import fabric, network, patterns
from weavegen.core.draft import MAX_ENDS, Draft
from weavegen.io.drawdown_image import ImageImportError, drawdown_from_image


def random_matrix(seed: int, rows=None, cols=None, density=0.5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random((rows or int(rng.integers(1, 25)), cols or int(rng.integers(1, 25)))) < density


# ---- drawdown to draft ----

@pytest.mark.parametrize("rising", [True, False])
@pytest.mark.parametrize("seed", range(25))
def test_the_derived_draft_reproduces_the_drawdown_exactly(seed, rising):
    m = random_matrix(seed, density=[0.2, 0.5, 0.8][seed % 3]) if seed % 4 else random_matrix(seed, 6, 6, 0.5)
    try:
        d = fabric.draft_from_drawdown(m, rising=rising)
    except ValueError:
        pytest.skip("needs more than 32 shafts")
    assert (d.drawdown() == m).all() and d.rising == rising


def test_the_shaft_and_treadle_counts_are_the_numbers_of_different_ends_and_picks():
    m = np.array([[1, 0, 1, 0],
                  [0, 1, 0, 1],
                  [1, 0, 1, 0],
                  [1, 1, 0, 0]], dtype=bool)
    d = fabric.draft_from_drawdown(m)
    assert d.shafts == 4 and d.treadles == 3                 # 4 different columns, 3 different rows (1 and 3 match)
    assert d.threading.tolist() == [0, 1, 2, 3]
    assert d.treadling.argmax(axis=1).tolist() == [0, 1, 0, 2]
    twin = np.array([[1, 0, 1, 0], [0, 1, 0, 1]] * 2, dtype=bool)   # ends 1 and 3 match, so do 2 and 4
    assert fabric.draft_from_drawdown(twin).threading.tolist() == [0, 1, 0, 1]


@pytest.mark.parametrize("preset,shafts,treadles", [
    ("plain", 2, 2), ("twill_2_2", 4, 4), ("twill_2_1", 3, 3), ("satin_5", 5, 5), ("satin_8", 8, 8),
])
def test_known_structures_need_the_expected_loom(preset, shafts, treadles):
    d = patterns.build_preset(preset, 40, 40)
    out = fabric.draft_from_drawdown(d.drawdown())
    assert (out.shafts, out.treadles) == (shafts, treadles)


def test_ends_that_are_never_lifted_are_left_unthreaded_and_empty_picks_press_nothing():
    m = np.array([[1, 0, 0], [0, 0, 0], [1, 0, 1]], dtype=bool)
    d = fabric.draft_from_drawdown(m)
    assert d.threading.tolist()[1] == -1 and d.shafts == 2
    assert not d.treadling[1].any() and d.treadles == 2
    assert (d.drawdown() == m).all()


def test_in_a_sinking_shed_the_cells_that_are_up_are_the_ones_not_lowered():
    m = np.array([[1, 1], [1, 1]], dtype=bool)               # nothing is ever lowered
    d = fabric.draft_from_drawdown(m, rising=False)
    assert d.threading.tolist() == [-1, -1] and (d.drawdown() == m).all()


def test_an_all_empty_or_all_lifted_cloth_still_makes_a_draft():
    none = fabric.draft_from_drawdown(np.zeros((3, 3), dtype=bool))
    assert (none.shafts, none.treadles) == (1, 1) and (none.drawdown() == 0).all()
    full = fabric.draft_from_drawdown(np.ones((3, 3), dtype=bool))
    assert full.shafts == 1 and (full.drawdown()).all()


def test_more_than_32_different_picks_becomes_a_liftplan():
    m = np.array([[bool(i >> b & 1) for b in range(6)] for i in range(1, 41)])   # 40 different rows, 6 ends
    d = fabric.draft_from_drawdown(m)
    assert d.liftplan_mode and d.treadles == 1 and (d.drawdown() == m).all()


def test_more_than_32_different_ends_cannot_be_woven_and_is_refused():
    with pytest.raises(ValueError, match="needs 40 shafts"):
        fabric.draft_from_drawdown(np.eye(40, dtype=bool))


@pytest.mark.parametrize("bad,fragment", [
    (np.zeros((0, 3), dtype=bool), "non-empty"),
    (np.zeros(5, dtype=bool), "non-empty"),
    (np.zeros((2, MAX_ENDS + 1), dtype=bool), "at most 400"),
    (np.zeros((MAX_ENDS + 1, 2), dtype=bool), "at most 400"),
])
def test_unusable_drawdowns_are_refused(bad, fragment):
    with pytest.raises(ValueError, match=fragment):
        fabric.draft_from_drawdown(bad)


def test_minimise_removes_shafts_and_treadles_nobody_needs_and_keeps_the_cloth():
    big = patterns.build_preset("twill_2_2", 32, 32)         # a 4-shaft twill ...
    big.resize(shafts=8, treadles=8)
    for end in range(0, 32, 2):
        big.threading[end] += 4                              # ... spread over 8 shafts: shaft n and n+4 behave alike
    big.tieup[:, 4:] = big.tieup[:, :4]
    big.tieup[4:, :] = big.tieup[:4, :]
    big.treadling[:, :] = False
    for pick in range(32):
        big.treadling[pick, pick % 4 + (4 if pick % 2 else 0)] = True
    assert big.shafts == 8
    small = fabric.minimise(big)
    assert (small.shafts, small.treadles) == (4, 4)
    assert (small.drawdown() == big.drawdown()).all()


def test_minimise_keeps_colours_shed_and_size():
    d = patterns.build_preset("herringbone", 24, 24)
    d.add_palette_color("#ff0000")
    d.warp_colors[:] = np.arange(24) % 3
    d.weft_colors[:] = 2
    d.set_rising(False)
    out = fabric.minimise(d)
    assert out.palette == d.palette and out.rising is False and (out.ends, out.picks) == (24, 24)
    assert (out.warp_colors == d.warp_colors).all() and (out.weft_colors == d.weft_colors).all()
    assert (out.drawdown() == d.drawdown()).all()


def test_minimising_a_minimal_draft_changes_nothing_but_the_numbering():
    d = Draft.twill_2_2()
    out = fabric.minimise(d)
    assert (out.shafts, out.treadles) == (4, 4) and (out.drawdown() == d.drawdown()).all()


# ---- picture to drawdown ----

def save(tmp_path, array, mode="L", name="d.png"):
    path = tmp_path / name
    Image.fromarray(array, mode).save(path)
    return path


def test_dark_pixels_are_warp_on_top_and_the_picture_reads_like_the_screen(tmp_path):
    img = np.full((3, 4), 255, dtype=np.uint8)
    img[0, 0] = 0          # top-left: pick 1, the highest-numbered end
    img[2, 3] = 0          # bottom-right: pick 3, end 1
    m = drawdown_from_image(save(tmp_path, img))
    assert m.shape == (3, 4) and m.sum() == 2
    assert m[0, 3] and m[2, 0]


def test_a_drawdown_drawn_to_a_picture_imports_back_unchanged(tmp_path):
    d = patterns.build_preset("herringbone", 30, 20)
    dd = d.drawdown()
    picture = np.where(dd[:, ::-1], 0, 255).astype(np.uint8)         # as it looks on screen
    assert (drawdown_from_image(save(tmp_path, picture)) == dd).all()


def test_the_threshold_and_colour_images(tmp_path):
    grey = np.array([[0, 100, 127, 128, 200, 255]], dtype=np.uint8)
    path = save(tmp_path, grey)
    assert drawdown_from_image(path)[0, ::-1].tolist() == [True, True, True, False, False, False]
    assert drawdown_from_image(path, threshold=50)[0, ::-1].tolist() == [True, False, False, False, False, False]
    rgb = np.zeros((1, 2, 3), dtype=np.uint8)
    rgb[0, 1] = (255, 255, 0)
    assert drawdown_from_image(save(tmp_path, rgb, "RGB", "c.png"))[0, ::-1].tolist() == [True, False]


def test_transparent_pixels_count_as_white(tmp_path):
    rgba = np.zeros((1, 2, 4), dtype=np.uint8)
    rgba[0, 0] = (0, 0, 0, 255)                 # solid black
    rgba[0, 1] = (0, 0, 0, 0)                   # fully transparent black
    assert drawdown_from_image(save(tmp_path, rgba, "RGBA", "t.png"))[0, ::-1].tolist() == [True, False]


def test_bad_images_are_refused_with_a_reason(tmp_path):
    big = save(tmp_path, np.zeros((10, MAX_ENDS + 1), dtype=np.uint8), name="big.png")
    with pytest.raises(ImageImportError, match="at most 400 x 400"):
        drawdown_from_image(big)
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not an image at all")
    with pytest.raises(ImageImportError, match="junk.png is not an image"):
        drawdown_from_image(junk)
    with pytest.raises(FileNotFoundError):
        drawdown_from_image(tmp_path / "missing.png")
    with pytest.raises(ImageImportError, match="threshold"):
        drawdown_from_image(big, threshold=300)


def test_an_import_error_is_a_value_error():
    assert issubclass(ImageImportError, ValueError)


def test_a_picture_can_be_turned_into_a_draft(tmp_path):
    d = patterns.build_preset("twill_2_2", 16, 16)
    picture = np.where(d.drawdown()[:, ::-1], 0, 255).astype(np.uint8)
    out = fabric.draft_from_drawdown(drawdown_from_image(save(tmp_path, picture)))
    assert (out.shafts, out.treadles) == (4, 4) and (out.drawdown() == d.drawdown()).all()


# ---- network drafting ----

def test_design_lines_interpolate_between_control_points():
    assert network.line_from_points([1, 3], 3).tolist() == [1, 2, 3]
    assert network.line_from_points([5], 4).tolist() == [5] * 4
    assert network.line_from_points([0, 10, 0], 5).tolist() == [0, 5, 10, 5, 0]
    assert network.line_from_points([2, 4], 1).tolist() == [2]


@pytest.mark.parametrize("points", [[], [float("nan")], [[1, 2]], [float("inf"), 1]])
def test_design_lines_need_finite_numbers(points):
    with pytest.raises(ValueError):
        network.line_from_points(points, 5)
    with pytest.raises(ValueError, match="at least one position"):
        network.line_from_points([1], 0)


@pytest.mark.parametrize("seed", range(20))
def test_every_networked_end_sits_on_its_network_inside_the_ribbon(seed):
    rng = np.random.default_rng(seed)
    initial = int(rng.choice([2, 3, 4, 5]))
    size = initial * int(rng.integers(1, 6))
    line = rng.uniform(-20, 40, int(rng.integers(1, 60)))
    seq = network.network_sequence(line, size, initial)
    assert ((seq >= 0) & (seq < size)).all()
    assert (seq % initial == np.arange(len(line)) % initial).all()                   # on the network
    bottoms = (np.floor(line + 0.5).astype(int) - 1) % size
    assert (((seq - bottoms) % size) < initial).all()                                 # inside the ribbon, wrapping


def test_a_networked_threading_on_a_known_line():
    line = network.line_from_points(network.preset_points("point", 8), 16)
    seq = network.network_sequence(line, 8, 4)
    assert (seq + 1).tolist() == [1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 7, 8, 5, 6, 3, 4]


def test_a_level_ribbon_is_a_repeat_of_the_initial():
    assert (network.network_sequence(np.full(8, 1), 8, 4) + 1).tolist() == [1, 2, 3, 4, 1, 2, 3, 4]
    assert (network.network_sequence(np.full(8, 5), 8, 4) + 1).tolist() == [5, 6, 7, 8, 5, 6, 7, 8]


def test_the_ribbon_wraps_from_the_top_shaft_to_the_bottom():
    seq = network.network_sequence(np.full(4, 7), 8, 4)               # ribbon over shafts 7, 8, 1, 2
    assert (seq + 1).tolist() == [1, 2, 7, 8]


@pytest.mark.parametrize("size,initial,fragment", [
    (8, 1, "at least 2"), (8, 3, "multiple of the initial"), (4, 8, "cannot be larger"),
    (8, True, "at least 2"), (8, 2.5, "at least 2"),
])
def test_unworkable_initials_are_refused(size, initial, fragment):
    with pytest.raises(ValueError, match=fragment):
        network.network_sequence(np.zeros(4), size, initial)


def test_preset_design_lines():
    assert network.preset_points("level", 8) == [1.0]
    assert network.preset_points("straight", 8) == [1.0, 9.0]
    assert network.preset_points("straight", 8, 2) == [1.0, 17.0]
    assert network.preset_points("point", 8, 2) == [1.0, 8.0, 1.0, 8.0, 1.0]
    wave = network.preset_points("wave", 8, 2)
    assert len(wave) == 17 and wave[0] == pytest.approx(1) and max(wave) == pytest.approx(8) and wave[4] == pytest.approx(8)
    for bad in ("zigzag",):
        with pytest.raises(ValueError, match="must be one of"):
            network.preset_points(bad, 8)
    with pytest.raises(ValueError, match="cycles"):
        network.preset_points("wave", 8, 0)


def test_apply_network_sets_threading_and_treadling_and_keeps_everything_else():
    d = Draft.twill_2_2(ends=16, picks=12)
    d.resize(shafts=8, treadles=8)
    d.add_palette_color("#ff0000")
    d.warp_colors[:] = 2
    d.set_rising(False)
    before = d.snapshot()
    out = network.apply_network(d, 4, network.preset_points("point", 8), network.preset_points("wave", 8))
    assert (out.threading % 4 == np.arange(16) % 4).all()
    assert out.treadling.sum(axis=1).tolist() == [1] * 12
    assert (out.treadling.argmax(axis=1) % 4 == np.arange(12) % 4).all()
    assert (out.tieup == d.tieup).all() and out.palette == d.palette and out.rising is False
    assert (out.warp_colors == 2).all() and not out.liftplan_mode
    assert (d.threading == before.threading).all() and (d.treadling == before.treadling).all()   # input untouched


def test_a_networked_draft_with_a_repeated_unit_tieup_weaves_the_initials_twill_whatever_the_ribbon():
    """The point of the network: the threading falls on the twill lattice, so the cloth is the
    initial's twill (here 2/2) however the design line curves."""
    d = Draft(ends=24, picks=24, shafts=8, treadles=8)
    unit = Draft.twill_2_2(4, 4).tieup
    d.tieup[:] = np.tile(unit, (2, 2))
    out = network.apply_network(d, 4, [1, 8, 3, 6, 1], [2, 7, 4, 1])
    straight = Draft.twill_2_2(24, 24)
    assert (out.drawdown() == straight.drawdown()).all()


def test_network_drafting_needs_a_compatible_draft():
    d = Draft.twill_2_2()
    with pytest.raises(ValueError, match="multiple of the initial"):
        network.apply_network(d, 3, [1], [1])
    d.resize(shafts=8)
    with pytest.raises(ValueError, match="treadles"):
        network.apply_network(Draft(ends=4, picks=4, shafts=8, treadles=6), 4, [1], [1])
    d.set_liftplan_mode(True)
    with pytest.raises(ValueError, match="liftplan"):
        network.apply_network(d, 4, [1], [1])


def test_typed_control_points_are_parsed_and_formatted():
    assert network.parse_points("1 5, 3.5,  8") == [1.0, 5.0, 3.5, 8.0]
    assert network.format_points([1.0, 5.0, 3.5, 2.25]) == "1 5 3.5 2.2"
    assert network.parse_points(network.format_points([1.0, 4.5, 8.0])) == [1.0, 4.5, 8.0]
    for bad, fragment in (("", "at least one"), ("1 x", "'x' is not a number"), ("1 nan", "usable"), ("inf", "usable")):
        with pytest.raises(ValueError, match=fragment):
            network.parse_points(bad)


def test_minimising_a_liftplan_draft_keeps_it_a_liftplan_draft():
    d = patterns.build_preset("twill_2_2", 12, 12)
    d.set_liftplan_mode(True)
    out = fabric.minimise(d)
    assert out.liftplan_mode and (out.drawdown() == d.drawdown()).all()
