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


def verify_runtime(report_path: str) -> int:
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
        if report["frozen"] and report["engine_bundled"]:
            raise RuntimeError("This package uses an independently installed media engine.")
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
        report["ok"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
