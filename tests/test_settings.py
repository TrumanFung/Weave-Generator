import json

import numpy as np

from weavegen import settings as settings_module
from weavegen.core.draft import Draft
from weavegen.settings import MAX_RECENT, Settings


def test_a_missing_file_gives_the_defaults(tmp_path):
    s = Settings.load(tmp_path / "nothing.json")
    assert s.get("zoom") == 16 and s.get("view") == "drawdown" and s.get("recent_files") == []
    assert s.get("page_size") == "a4" and s.get("float_limit") == 3 and s.get("window") == ""


def test_saved_values_come_back(tmp_path):
    path = tmp_path / "s.json"
    s = Settings(path)
    for key, value in (("zoom", 24), ("view", "cloth"), ("yarn_width", 60), ("float_limit", 5),
                       ("float_side", "face"), ("page_size", "letter"), ("window", "1000x700+20+30"),
                       ("last_directory", str(tmp_path)), ("yardage", {"width": "30"})):
        assert s.set(key, value)
    assert s.save() and path.exists()
    again = Settings.load(path)
    assert again.values == s.values


def test_damaged_files_fall_back_to_defaults(tmp_path):
    path = tmp_path / "s.json"
    for text in ("", "{not json", "[1, 2]", "null", '"text"'):
        path.write_text(text, encoding="utf-8")
        assert Settings.load(path).values == Settings(path).values


def test_bad_values_are_ignored_one_by_one(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({
        "zoom": 9999, "view": "sideways", "yarn_width": "wide", "float_limit": True,
        "float_side": 3, "page_size": "a0", "window": "huge", "last_directory": 5,
        "recent_files": "nope", "yardage": {"width": 30}, "unknown": 1,
        "zoom_note": "x",
    }), encoding="utf-8")
    s = Settings.load(path)
    assert s.values == Settings(path).values          # every bad entry fell back to its default


def test_good_values_survive_bad_neighbours(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"zoom": 30, "view": "sideways"}), encoding="utf-8")
    s = Settings.load(path)
    assert s.get("zoom") == 30 and s.get("view") == "drawdown"


def test_set_rejects_bad_values_and_unknown_names(tmp_path):
    s = Settings(tmp_path / "s.json")
    assert not s.set("zoom", 3) and not s.set("zoom", "16") and s.get("zoom") == 16
    assert not s.set("window", "100x100;rm") and s.get("window") == ""
    try:
        s.set("nonsense", 1)
    except KeyError:
        pass
    else:
        raise AssertionError("an unknown setting should be refused")


def test_window_geometry_forms(tmp_path):
    s = Settings(tmp_path / "s.json")
    for ok in ("900x700", "900x700+10+20", "900x700+-8+-8", "900x700-8+20", ""):
        assert s.set("window", ok), ok
    for bad in ("900", "x700", "900x700+a+b", "900x700+1+2+3"):
        assert not s.set("window", bad), bad


def test_recent_files_are_newest_first_without_repeats_and_capped(tmp_path):
    s = Settings(tmp_path / "s.json")
    for i in range(MAX_RECENT + 3):
        s.add_recent(f"f{i}.wif")
    recent = s.get("recent_files")
    assert recent[0] == f"f{MAX_RECENT + 2}.wif" and len(recent) == MAX_RECENT
    s.add_recent("f5.wif")
    assert s.get("recent_files")[0] == "f5.wif" and s.get("recent_files").count("f5.wif") == 1
    s.forget_recent("f5.wif")
    assert "f5.wif" not in s.get("recent_files")
    s.clear_recent()
    assert s.get("recent_files") == []


def test_loading_tidies_a_hand_edited_recent_list(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"recent_files": ["a", "a", 3, "", "b"] + [f"x{i}" for i in range(20)]}),
                    encoding="utf-8")
    recent = Settings.load(path).get("recent_files")
    assert recent[:2] == ["a", "b"] and len(recent) == MAX_RECENT


def test_get_returns_copies(tmp_path):
    s = Settings(tmp_path / "s.json")
    s.add_recent("a.wif")
    s.get("recent_files").append("hack")
    assert s.get("recent_files") == ["a.wif"]


def test_saving_creates_the_folder_and_leaves_no_temporary_files(tmp_path):
    path = tmp_path / "deep" / "er" / "s.json"
    assert Settings(path).save()
    assert [p.name for p in path.parent.iterdir()] == ["s.json"]


def test_an_unwritable_location_is_not_an_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert Settings(blocker / "s.json").save() is False       # a file where the folder should be


def test_the_folder_can_be_chosen_with_an_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv(settings_module.CONFIG_DIR_ENV, str(tmp_path / "mine"))
    assert settings_module.settings_path() == tmp_path / "mine" / "settings.json"
    monkeypatch.delenv(settings_module.CONFIG_DIR_ENV)
    assert settings_module.settings_path().name == "settings.json"


def test_the_fingerprint_changes_exactly_when_the_draft_does():
    d = Draft.twill_2_2()
    start = d.snapshot().fingerprint()
    assert d.snapshot().fingerprint() == start
    d.set_thread(0, 2)
    changed = d.snapshot().fingerprint()
    assert changed != start
    d.set_thread(0, 0)
    assert d.snapshot().fingerprint() == start               # undoing by hand is no change
    d.set_rising(False)
    assert d.snapshot().fingerprint() != start
    d.set_rising(True)
    d.add_palette_color("#123456")
    assert d.snapshot().fingerprint() != start
    other = Draft.twill_2_2()
    other.threading = np.array(other.threading)
    assert other.snapshot().fingerprint() == start
    assert Draft(ends=8).snapshot().fingerprint() != Draft(ends=9).snapshot().fingerprint()
