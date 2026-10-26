"""Exercise shipped dependencies and conversion outputs without user documents."""
import asyncio
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from transcodia_app.version import APP_NAME, APP_VERSION
from transcodia_engine.runtime_paths import app_root, find_ffmpeg
from transcodia_app.icons import ASSETS


def verify_runtime(report_path: str, media_source=None) -> int:
    report = {"app": APP_NAME, "version": APP_VERSION,
              "frozen": bool(getattr(sys, "frozen", False)), "checks": [], "ok": False}
    try:
        assets = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
        for entry in assets["assets"]:
            if hashlib.sha256((ASSETS / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError("Project artwork failed its integrity check.")
        report["checks"].append("project-assets")
        ffmpeg = Path(find_ffmpeg()).resolve()
        report["ffmpeg"] = str(ffmpeg)
        report["engine_bundled"] = ffmpeg.is_relative_to(app_root().resolve())
        with tempfile.TemporaryDirectory(prefix="transcodia-check-") as folder:
            root = Path(folder)
            from PIL import Image
            from transcodia_app.handlers.image_handler import ImageConverter
            picture = root / "صورة.png"
            Image.new("RGB", (32, 24), "red").save(picture)
            jpeg = root / "picture.jpg"
            if not ImageConverter.convert_image(str(picture), str(jpeg)):
                raise RuntimeError("Image conversion failed.")
            with Image.open(jpeg) as image:
                if image.size != (32, 24):
                    raise RuntimeError("Incorrect converted image dimensions.")
            report["checks"].append("image")

            from reportlab.pdfgen.canvas import Canvas
            import openpyxl
            from transcodia_app.handlers.doc_handler import DocumentConverter
            pdf = root / "مستند.pdf"
            document = Canvas(str(pdf))
            document.drawString(30, 40, "Transcodia runtime check")
            document.save()
            import pypdfium2 as pdfium
            with pdfium.PdfDocument(str(pdf)) as preview:
                page = preview[0]
                bitmap = page.render(scale=0.2)
                if bitmap.width < 1 or bitmap.height < 1:
                    raise RuntimeError("PDF preview rendering failed.")
                bitmap.close()
                page.close()
            report["checks"].append("pdf-preview")
            # Verify our shipped libraries, never optional tools on the build machine.
            converter = DocumentConverter()
            for method, suffix in (("convert_pdf_to_txt", "txt"),
                                   ("convert_pdf_to_docx", "docx"),
                                   ("convert_pdf_to_xlsx", "xlsx")):
                destination = root / ("document." + suffix)
                if not getattr(converter, method)(str(pdf), str(destination)):
                    raise RuntimeError(f"PDF to {suffix} failed.")
                if suffix == "txt":
                    text = destination.read_text(encoding="utf-8")
                elif suffix == "docx":
                    with zipfile.ZipFile(destination) as archive:
                        text = archive.read("word/document.xml").decode("utf-8")
                else:
                    workbook = openpyxl.load_workbook(destination)
                    try:
                        text = str(workbook.active["A1"].value)
                    finally:
                        workbook.close()
                if "Transcodia runtime check" not in text:
                    raise RuntimeError(f"PDF to {suffix} lost document text.")
                report["checks"].append("pdf-" + suffix)

            from pypdf import PdfReader
            rendered = root / "rendered.pdf"
            if not converter.convert_docx_to_pdf(str(root / "document.docx"), str(rendered)):
                raise RuntimeError("DOCX text rendering failed.")
            if "Transcodia runtime check" not in "".join(page.extract_text() for page in PdfReader(rendered).pages):
                raise RuntimeError("DOCX rendering lost document text.")
            report["checks"].append("docx-pdf")

            from transcodia_engine import (BatchConversionWorker, ConvertTaskItem,
                                           FFMpegEngine, VideoConfig, AudioConfig, TaskStatus)
            movie = root / "فيديو.mp4"
            worker = BatchConversionWorker(FFMpegEngine(str(ffmpeg)), max_concurrency=1)
            worker.add_task(ConvertTaskItem(
                src_file="color=c=blue:s=160x120:d=0.4", dst_file=str(movie),
                custom_input_prefix="-f lavfi",
                video_config=VideoConfig(preset="ultrafast"),
                audio_config=AudioConfig(disable_audio=True)), task_id="runtime")
            result = asyncio.run(worker.run_all())["runtime"]
            if result.status != TaskStatus.COMPLETED:
                raise RuntimeError(result.error_message or "Media conversion failed.")
            decoded = subprocess.run(
                [str(ffmpeg), "-v", "error", "-i", str(movie), "-frames:v", "1",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                capture_output=True, timeout=30, check=True)
            if len(decoded.stdout) != 160 * 120 * 3:
                raise RuntimeError("Converted media could not be decoded.")
            report["checks"].append("media-encode-decode")
            if media_source:
                from transcodia_engine.models import MediaAdditionalConfig
                from transcodia_app.handlers.probe_handler import MediaProbe
                source = Path(media_source).resolve(strict=True)
                before = source.stat()
                converted = root / "source-check.mp4"
                task = ConvertTaskItem(
                    src_file=str(source), dst_file=str(converted),
                    video_config=VideoConfig(), audio_config=AudioConfig(),
                    additional_config=MediaAdditionalConfig(start_time=0, end_time=5))
                from PySide6 import QtCore, QtWidgets
                from transcodia_app.views.main_window import MainWindow
                from transcodia_engine.hardware_prober import HardwareProber
                app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
                window = MainWindow(probe_hardware=False)
                window.play_sound = False
                window.chk_notify.setChecked(False)
                caps = HardwareProber(str(ffmpeg)).probe()
                window._on_hardware_probed({"nvenc": caps.nvenc_h264, "qsv": caps.qsv_h264,
                                            "amf": caps.amf_h264, "mf": caps.mf_h264,
                                            "nvenc_hevc": caps.nvenc_hevc, "qsv_hevc": caps.qsv_hevc,
                                            "amf_hevc": caps.amf_hevc, "mf_hevc": caps.mf_hevc})
                window._enqueue_media_task("video", "mp4", task)
                window._start_conversion()
                loop = QtCore.QEventLoop()
                timer = QtCore.QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                window.runner_thread.finished.connect(loop.quit)
                timer.start(120000)
                loop.exec()
                timer.stop()
                try:
                    if window.runner_thread.isRunning():
                        window.runner_thread.stop()
                        window.runner_thread.wait(10000)
                        raise RuntimeError("GUI conversion timed out.")
                    app.processEvents()
                    actual = next(iter(window.all_tasks.values()))
                    if actual["status"] != "completed":
                        raise RuntimeError(actual.get("error_message") or "GUI source clip conversion failed.")
                    report["gui_encoder"] = task.video_config.hw_accel.value
                    report["checks"].append("gui-conversion-thread")
                finally:
                    window.close()
                subprocess.run([str(ffmpeg), "-v", "error", "-i", str(converted), "-f", "null", "-"],
                               capture_output=True, timeout=30, check=True)
                info = MediaProbe(str(ffmpeg)).probe(str(converted))
                after = source.stat()
                if not 0 < info.duration_seconds <= 5.2 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError("Clip verification failed or source was modified.")
                report["source_clip"] = {"duration": info.duration_seconds, "width": info.width,
                                         "height": info.height, "bytes": converted.stat().st_size}
                report["checks"].append("source-video-clip")
        report["ok"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
