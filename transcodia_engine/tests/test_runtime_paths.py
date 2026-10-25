import json
from pathlib import Path

import pytest

from transcodia_engine import runtime_paths as paths
from transcodia_engine.engine import FFMpegEngine

REAL_APP_ROOT = paths.app_root

@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path / "bundle")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    paths.local_settings.cache_clear()
    yield tmp_path
    paths.local_settings.cache_clear()


def executable(folder):
    path = folder / ("ffmpeg" + paths.EXECUTABLE_SUFFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return str(path)


def test_ffmpeg_priority_and_engine_default(runtime, monkeypatch):
    explicit = executable(runtime / "explicit")
    bundled = executable(runtime / "bundle" / "ffmpeg")
    external = executable(runtime / "configured")
    monkeypatch.setenv("FFMPEG_PATH", explicit)
    (runtime / paths.LOCAL_SETTINGS_NAME).write_text(json.dumps({"ffmpeg_path": external}))
    monkeypatch.setattr(paths.shutil, "which", lambda name: "path-ffmpeg")
    assert paths.find_ffmpeg() == explicit
    assert FFMpegEngine().ffmpeg_path == explicit
    monkeypatch.delenv("FFMPEG_PATH")
    assert paths.find_ffmpeg() == bundled
    Path(bundled).unlink()
    assert paths.find_ffmpeg() == external
    Path(external).unlink()
    assert paths.find_ffmpeg() == "path-ffmpeg"
    monkeypatch.setattr(paths.shutil, "which", lambda name: None)
    assert paths.find_ffmpeg() == "ffmpeg"


@pytest.mark.parametrize("contents", ["{bad json", "[]", '"text"'])
def test_invalid_settings_do_not_prevent_startup(runtime, contents):
    (runtime / paths.LOCAL_SETTINGS_NAME).write_text(contents)
    assert paths.local_settings() == {}


def test_local_configuration_can_select_an_independent_ffmpeg(runtime):
    external = runtime / "configured"
    binary = executable(external)
    (runtime / paths.LOCAL_SETTINGS_NAME).write_text(json.dumps({
        "ffmpeg_path": binary}))
    assert paths.find_ffmpeg() == binary


def test_frozen_resource_root_and_adjacent_configuration(runtime, monkeypatch):
    monkeypatch.setattr(paths, "app_root", REAL_APP_ROOT)
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(runtime / "internal"), raising=False)
    launcher = runtime / "launcher"
    launcher.mkdir()
    monkeypatch.setattr(paths.sys, "executable", str(launcher / "Transcodia.exe"))
    monkeypatch.chdir(runtime)
    (launcher / paths.LOCAL_SETTINGS_NAME).write_text('{"ffmpeg_path":"custom"}')
    paths.local_settings.cache_clear()
    assert paths.app_root() == runtime / "internal"
    assert paths.local_settings()["ffmpeg_path"] == "custom"
