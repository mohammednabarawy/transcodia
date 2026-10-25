"""Shared regression fixtures. All test inputs/outputs live in pytest temp folders."""
import os
import shutil
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from reportlab.pdfgen.canvas import Canvas
import pytest
from PIL import Image
from PySide6 import QtGui, QtWidgets


@pytest.fixture(scope="session", autouse=True)
def isolated_test_home(tmp_path_factory):
    home = str(tmp_path_factory.mktemp("application-home"))
    environment = pytest.MonkeyPatch()
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME"):
        environment.setenv(name, home)
    yield
    environment.undo()


@pytest.fixture(scope="session", autouse=True)
def offscreen_fonts(qapp):
    if not QtGui.QFontDatabase.families():
        for name in ("segoeui.ttf", "arial.ttf"):
            path = Path("C:/Windows/Fonts") / name
            if path.is_file():
                QtGui.QFontDatabase.addApplicationFont(str(path))


@pytest.fixture(scope="session")
def ffmpeg_bin():
    from transcodia_engine.runtime_paths import find_ffmpeg
    candidate = find_ffmpeg()
    binary = candidate if Path(candidate).is_file() else shutil.which("ffmpeg")
    if not binary:
        pytest.skip("Real FFmpeg integration requires a local FFmpeg executable")
    return binary


@pytest.fixture(scope="session")
def media_files(ffmpeg_bin, tmp_path_factory):
    root = tmp_path_factory.mktemp("media-fixtures")
    video = root / "اختبار media.mp4"
    silent = root / "silent.mp4"
    audio = root / "replacement.wav"
    for output, inputs in [
        (video, ["-f", "lavfi", "-i", "testsrc2=size=160x120:rate=12:duration=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-g", "6", "-c:a", "aac"]),
        (silent, ["-f", "lavfi", "-i", "color=red:size=160x120:rate=12:duration=1", "-c:v", "libx264", "-an"]),
        (audio, ["-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-c:a", "pcm_s16le"]),
    ]:
        subprocess.run([ffmpeg_bin, "-v", "error", "-y", *inputs, str(output)], capture_output=True, check=True, timeout=25)
    subtitle = root / "captions.srt"
    subtitle.write_text("1\n00:00:00,100 --> 00:00:01,500\nRegression caption\n", encoding="utf-8")
    return {"video": str(video), "silent": str(silent), "audio": str(audio), "subtitle": str(subtitle)}


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "فاتورة sample.pdf"
    document = Canvas(str(path), pagesize=(300, 200))
    for text in ("First page: Invoice 123", "Second page: Total 456"):
        document.drawString(20, 160, text)
        document.showPage()
    document.save()
    return str(path)


@pytest.fixture
def sample_image(tmp_path):
    path = tmp_path / "صورة sample.png"
    image = Image.new("RGBA", (80, 40), (255, 0, 0, 255))
    image.paste((0, 0, 255, 255), (40, 0, 80, 40))
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(path)
    return str(path)


@pytest.fixture
def messages(monkeypatch):
    calls = []
    for method in ("information", "warning", "critical", "about", "question"):
        def record(*args, _method=method, **kwargs):
            calls.append((_method, args[1:]))
            return QtWidgets.QMessageBox.StandardButton.No if _method == "question" else QtWidgets.QMessageBox.StandardButton.Ok
        monkeypatch.setattr(QtWidgets.QMessageBox, method, record)
    monkeypatch.setattr(QtWidgets.QApplication, "beep", lambda: None)
    return calls


@pytest.fixture
def app_window(qapp, qtbot, tmp_path, monkeypatch, messages):
    from transcodia_app.views.main_window import MainWindow
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    window = MainWindow(probe_hardware=False)
    window.output_dir = str(tmp_path / "outputs")
    Path(window.output_dir).mkdir()
    window.txt_bottom_output.setText(window.output_dir)
    window.play_sound = False
    window.chk_notify.setChecked(False)
    qtbot.addWidget(window)
    yield window
    if window.runner_thread and window.runner_thread.isRunning():
        window.runner_thread.stop()
        assert window.runner_thread.wait(10000), "Test runner failed to stop"
    window.close()
