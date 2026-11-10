"""The pieces the Windows build needs are in place (the build itself is run by hand)."""

import re
from pathlib import Path

import weavegen

ROOT = Path(__file__).resolve().parents[1]


def test_the_spec_points_at_files_that_exist():
    spec = (ROOT / "weave_generator.spec").read_text(encoding="utf-8")
    assert (ROOT / "weave_generator.py").is_file()
    for path in re.findall(r'"(weavegen/assets/[^"]+)"', spec):
        assert (ROOT / path).is_file(), path
    assert "console=False" in spec


def test_the_version_looks_like_a_version_number():
    assert re.fullmatch(r"\d+\.\d+\.\d+", weavegen.__version__)


def test_the_icon_files_are_real_images():
    from PIL import Image
    with Image.open(ROOT / "weavegen" / "assets" / "icon.png") as png:
        assert png.size == (256, 256)
    with Image.open(ROOT / "weavegen" / "assets" / "icon.ico") as ico:
        assert ico.format == "ICO" and 256 in {size[0] for size in ico.info.get("sizes", {(256, 256)})}
