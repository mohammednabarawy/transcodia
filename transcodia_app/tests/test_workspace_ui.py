import os
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
import pytest
from PySide6 import QtWidgets

from transcodia_app.handlers.doc_handler import DocumentConverter
from transcodia_app.views.category_panel import FormatTile
from transcodia_app.views.main_window import MainWindow, ConversionRunnerThread
from transcodia_app.views.pdf_joiner_dialog import PdfJoinerDialog
from transcodia_app.views.task_table import TaskTableView
from transcodia_app.views.add_files_dialog import AddFilesDialog


@pytest.fixture
def pdfs(tmp_path):
    paths = []
    for name, content in [("فاتورة أولى.pdf", "FIRST DOCUMENT"), ("فاتورة ثانية.pdf", "SECOND DOCUMENT")]:
        path = tmp_path / name
        document = Canvas(str(path))
        document.drawString(50, 50, content)
        document.save()
        paths.append(str(path))
    return paths


def test_reference_shell_and_language_keep_queue(qapp, tmp_path):
    window = MainWindow(probe_hardware=False)
    assert window.current_skin == "Transcodia Light"
    assert window.category_panel.toolbox.count() == 6
    assert window.category_panel.toolbox.itemText(0) == "الفيديو"
    assert len([c for c in range(window.task_table.columnCount()) if not window.task_table.isColumnHidden(c)]) == 3
    assert window.task_table.horizontalHeader().logicalIndex(0) == TaskTableView.COL_PREVIEW
    window._enqueue_doc_task(str(tmp_path / "ملف.pdf"), "pdf2xlsx", False, str(tmp_path))
    assert window.btn_start.isEnabled()
    window._change_language("en")
    assert window.category_panel.toolbox.itemText(0) == "Video"
    assert window.btn_start.text() == "Start"
    window._change_language("ar")
    assert window.btn_start.text() == "بدء"
    assert len(window.all_tasks) == 1
    window.close()


def test_pdf_joiner_order_dialog_queue_and_real_output(qapp, pdfs, tmp_path):
    window = MainWindow(probe_hardware=False)
    dialog = PdfJoinerDialog(str(tmp_path), window)
    dialog.add_paths(pdfs + [pdfs[0]])
    assert dialog.paths == pdfs
    assert dialog.table.rowCount() == 2
    assert dialog.table.empty_button.isHidden()
    dialog.table.selectRow(1)
    dialog.move_selected(-1)
    assert dialog.paths == list(reversed(pdfs))
    dialog._accept_files()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    window._enqueue_pdf_joiner_task(dialog.paths, False, dialog.output_dir)
    task = next(iter(window.all_tasks.values()))
    assert task["additional_files"] == [pdfs[0]]
    assert task["dst"].endswith(".pdf")
    runner = ConversionRunnerThread([task])
    finished = []
    runner.task_completed.connect(lambda *args: finished.append(args))
    runner.run()
    assert finished[0][1] is True
    joined = PdfReader(task["dst"])
    assert len(joined.pages) == 2
    assert "SECOND DOCUMENT" in joined.pages[0].extract_text()
    assert "FIRST DOCUMENT" in joined.pages[1].extract_text()
    dialog.close()
    window.close()


def test_pdf_merge_rejects_missing_input_and_preserves_files(pdfs, tmp_path):
    converter = DocumentConverter()
    original = Path(pdfs[0]).read_bytes()
    assert not converter.join_pdfs(pdfs, pdfs[0])
    assert Path(pdfs[0]).read_bytes() == original
    target = tmp_path / "existing.pdf"
    target.write_bytes(b"existing output")
    assert not converter.join_pdfs([pdfs[0], str(tmp_path / "missing.pdf")], str(target))
    assert target.read_bytes() == b"existing output"


def test_remove_row_keeps_progress_attached_to_correct_task(qapp):
    table = TaskTableView()
    for number in range(3):
        table.add_task(str(number), f"input{number}.mp4", "mp4", f"out{number}.mp4")
    table.remove_tasks(["0"])
    table.update_task_progress("2", 42, 2, 10)
    assert table._task_row_map == {"1": 0, "2": 1}
    assert table.cellWidget(1, table.COL_PROGRESS).findChild(QtWidgets.QProgressBar).value() == 42
    assert table.cellWidget(0, table.COL_PROGRESS).findChild(QtWidgets.QProgressBar).value() == 0


def test_dropped_paths_are_passed_to_file_dialog(qapp, tmp_path, monkeypatch):
    source = tmp_path / "صورة.png"
    from PIL import Image
    Image.new("RGB", (30, 20)).save(source)
    received = []
    def inspect(dialog):
        received.extend(item["path"] for item in dialog.file_items)
        return QtWidgets.QDialog.DialogCode.Rejected
    monkeypatch.setattr(AddFilesDialog, "exec", inspect)
    window = MainWindow(probe_hardware=False)
    window._on_files_dropped([str(source)])
    assert received == [str(source)]
    window.close()


def test_queued_names_do_not_overwrite_inputs_or_other_jobs(qapp, pdfs, tmp_path):
    window = MainWindow(probe_hardware=False)
    window._enqueue_doc_task(pdfs[0], "pdf2txt", False, str(tmp_path))
    window._enqueue_doc_task(pdfs[0], "pdf2txt", False, str(tmp_path))
    destinations = [t["dst"] for t in window.all_tasks.values()]
    assert len(set(destinations)) == 2
    assert not set(destinations).intersection(pdfs)
    window.close()


@pytest.fixture
def media_sample(tmp_path):
    import subprocess
    from transcodia_engine.runtime_paths import find_ffmpeg
    binary = find_ffmpeg()
    if not (os.path.isfile(binary) or shutil.which(binary)):
        pytest.skip("Local FFmpeg is unavailable")
    sample = str(tmp_path / "source.mp4")
    subprocess.run([binary, "-v", "error", "-f", "lavfi", "-i", "color=blue:s=160x120:d=0.3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", "-c:v", "libx264",
                    "-c:a", "aac", "-y", sample], check=True, capture_output=True, timeout=20)
    return sample, binary


@pytest.mark.parametrize("category,format_name", [("audio", f) for f in ("mp3", "aac", "wav", "flac", "wma", "m4a", "ogg", "m4r", "ac3")] + [("video", f) for f in ("mp4", "webm", "gif", "avi", "wmv", "mpg", "flv")])
def test_format_tiles_produce_real_media(qapp, media_sample, tmp_path, category, format_name):
    import subprocess
    from transcodia_engine.engine import FFMpegEngine
    source, binary = media_sample
    dialog = AddFilesDialog(category, format_name, str(tmp_path / "out"))
    dialog._append_file_item(source)
    task = dialog.get_tasks()[0]
    result = subprocess.run(FFMpegEngine(binary).build_cli_arguments(task), capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[-2500:]
    assert Path(task.dst_file).stat().st_size > 0
    if category == "audio":
        probe = subprocess.run([binary, "-i", task.dst_file], capture_output=True, timeout=10)
        assert b"Video:" not in probe.stderr
    dialog.close()
