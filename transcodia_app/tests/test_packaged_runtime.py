import json
import os
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace

import pytest

from transcodia_app import runtime_check
from scripts.verify_bundle import verify_bundle

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_checks_real_outputs_without_optional_helpers(ffmpeg_bin, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_check, "find_ffmpeg", lambda: ffmpeg_bin)
    report = tmp_path / "runtime.json"
    assert runtime_check.verify_runtime(str(report)) == 0
    data = json.loads(report.read_text())
    assert data["ok"]
    assert data["checks"] == ["project-assets", "image", "pdf-preview", "pdf-txt", "pdf-docx", "pdf-xlsx", "docx-pdf", "media-encode-decode"]


def test_runtime_check_reports_missing_ffmpeg(ffmpeg_bin, tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_check, "find_ffmpeg", lambda: str(tmp_path / "missing-ffmpeg"))
    report = tmp_path / "failed.json"
    assert runtime_check.verify_runtime(str(report)) == 1
    data = json.loads(report.read_text())
    assert not data["ok"] and "error" in data


def test_frozen_check_rejects_an_accidentally_redistributed_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_check.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_check, "app_root", lambda: tmp_path / "bundle")
    monkeypatch.setattr(runtime_check, "find_ffmpeg", lambda: str(tmp_path / "bundle" / "ffmpeg"))
    report = tmp_path / "failed.json"
    assert runtime_check.verify_runtime(str(report)) == 1
    assert "independently installed" in json.loads(report.read_text())["error"]


@pytest.mark.parametrize("returncode,ok,frozen", [(0, True, True), (1, False, True), (0, True, False)])
def test_bundle_verifier_isolates_environment_and_enforces_result(tmp_path, monkeypatch, returncode, ok, frozen):
    executable = tmp_path / "Transcodia.exe"
    executable.touch()
    monkeypatch.setenv("FFMPEG_PATH", "must-not-be-used")
    monkeypatch.setenv("PYTHONPATH", "must-not-be-used")
    def launch(command, **kwargs):
        assert "FFMPEG_PATH" not in kwargs["env"]
        assert "PYTHONPATH" not in kwargs["env"]
        assert kwargs["cwd"] != str(ROOT)
        assert kwargs["env"]["QT_QPA_PLATFORM"] == "offscreen"
        Path(command[-1]).write_text(json.dumps({"ok": ok, "frozen": frozen}))
        return SimpleNamespace(returncode=returncode, stderr=b"")
    monkeypatch.setattr(subprocess, "run", launch)
    report = tmp_path / "result.json"
    if ok and frozen and returncode == 0:
        assert verify_bundle(executable, report)["ok"]
    else:
        with pytest.raises(RuntimeError, match="verification failed"):
            verify_bundle(executable, report)
    assert report.is_file()


def test_bundle_verifier_reports_startup_crash(tmp_path, monkeypatch):
    executable = tmp_path / "Transcodia.exe"
    executable.touch()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr=b"missing Qt plugin"))
    with pytest.raises(RuntimeError, match="missing Qt plugin"):
        verify_bundle(executable, tmp_path / "result.json")


def build_spec(monkeypatch, workspace, bundle_requested=False):
    if bundle_requested:
        monkeypatch.setenv("TRANSCODIA_FFMPEG_DIR", str(workspace))
    else:
        monkeypatch.delenv("TRANSCODIA_FFMPEG_DIR", raising=False)
    (workspace / "transcodia_app").mkdir(exist_ok=True)
    (workspace / "transcodia_app" / "version.py").write_text('APP_VERSION = "0.1.0"')
    notices = workspace / "artifacts" / "dependency-notices"
    notices.mkdir(parents=True, exist_ok=True)
    (notices / "manifest.json").write_text("[]")
    analysis = SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])
    def capture(*args, **kwargs):
        analysis.binaries = kwargs["binaries"]
        # Model dependency scanning finding a same-named, incompatible PATH DLL.
        analysis.binaries.append(("icuuc.dll", "unrelated/icuuc.dll", "BINARY"))
        analysis.datas = kwargs["datas"]
        return analysis
    return runpy.run_path(str(ROOT / "packaging" / "transcodia.spec"), init_globals={
        "SPECPATH": str(workspace / "packaging"), "Analysis": capture,
        "PYZ": lambda *a, **kw: None, "EXE": lambda *a, **kw: None,
        "COLLECT": lambda *a, **kw: None, "BUNDLE": lambda *a, **kw: None})


def test_packaging_rejects_media_engine_redistribution(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="not bundled"):
        build_spec(monkeypatch, tmp_path, bundle_requested=True)


def test_windows_bundle_excludes_foreign_dlls_and_includes_our_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_check.sys, "platform", "win32")
    for name in ("ffmpeg.exe", "ffprobe.exe", "avcodec-test.dll"):
        (tmp_path / name).touch()
    built = build_spec(monkeypatch, tmp_path)
    binaries = built["a"].binaries
    assert not binaries
    assert all(entry[0].lower() != "icuuc.dll" for entry in binaries)
    assert any(target == "transcodia_app/assets" for source, target in built["a"].datas)
