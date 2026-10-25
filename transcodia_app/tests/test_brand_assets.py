import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image
from PySide6 import QtWidgets
import pytest

from transcodia_app.icons import ASSETS, asset_path, icon
from transcodia_app.views.category_panel import CATEGORIES
from scripts.audit_release_tree import audit


def test_generated_icon_files_match_the_creation_manifest(qapp):
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    assert len(manifest["assets"]) == 24
    assert len(list((ASSETS / "icons").glob("*.png"))) == 23
    for entry in manifest["assets"]:
        path = ASSETS / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        with Image.open(path) as picture:
            assert picture.mode == "RGBA"
            assert picture.getextrema()[3][0] == 0
        assert not icon(path.stem if path.parent.name == "icons" else "app").isNull()


def test_every_tool_and_toolbar_action_loads_a_project_image(qapp):
    names = {asset for _, _, entries in CATEGORIES for _, _, _, asset, _ in entries}
    names.update({"folder", "options", "remove", "clear", "stop", "start", "pause", "home", "confirm", "add_files"})
    for name in names:
        assert asset_path(name).is_file()
        assert asset_path(name).is_relative_to(ASSETS)
        assert not icon(name).pixmap(32, 32).isNull()


def test_toolbar_controls_are_not_vertically_clipped(app_window, qapp):
    app_window.show()
    qapp.processEvents()
    toolbar = app_window.findChild(QtWidgets.QToolBar, "mainToolbar")
    for button in toolbar.findChildren(QtWidgets.QToolButton):
        if button.isVisible() and button.text():
            assert button.height() >= button.minimumSizeHint().height()
    app_window._change_language("en")
    assert "Language" in [action.text() for action in app_window.menuBar().actions()]


@pytest.mark.parametrize("filename,contents,expected", [("app.py", "print('ok')", 0), ("library.dll", "binary", 1), ("transcodia.local.json", "{}", 1), ("app.py", "path = '" + "C:" + "/Users/Example/private'", 1)])
def test_source_publication_checks(tmp_path, filename, contents, expected):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / filename).write_text(contents)
    subprocess.run(["git", "add", filename], cwd=tmp_path, check=True)
    files, issues = audit(tmp_path)
    assert len(files) == 1
    assert len(issues) == expected


def test_publication_audit_reads_the_staged_snapshot(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "app.py"
    source.write_text("print('safe staged content')")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True)
    source.write_text("path = '" + "C:" + "/Users/Example/private'")
    assert audit(tmp_path)[1] == []
