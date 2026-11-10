"""Keep every test away from the real settings folder."""

import pytest

from weavegen import settings as settings_module


@pytest.fixture(autouse=True)
def _private_settings_folder(tmp_path_factory, monkeypatch):
    monkeypatch.setenv(settings_module.CONFIG_DIR_ENV, str(tmp_path_factory.mktemp("settings")))
