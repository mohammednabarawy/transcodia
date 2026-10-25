# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Transcodia. Build with:  python -m PyInstaller packaging/transcodia.spec
#
# Media engines are installed independently and are not redistributed in this bundle.
import os
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
version = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "transcodia_app" / "version.py").read_text(encoding="utf-8")).group(1)

datas = [(str(ROOT / "transcodia_app" / "assets"), "transcodia_app/assets"),
         (str(ROOT / "LICENSE"), "."), (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
         (str(ROOT / "LICENSES"), "LICENSES")]
notice_folder = ROOT / "artifacts" / "dependency-notices"
if not (notice_folder / "manifest.json").is_file():
    raise SystemExit("Run python scripts/collect_notices.py before packaging.")
datas.append((str(notice_folder), "THIRD_PARTY_LICENSES"))

binaries = []
ffmpeg_dir = os.environ.get("TRANSCODIA_FFMPEG_DIR")
if ffmpeg_dir:
    raise SystemExit("Media engines are not bundled. Unset TRANSCODIA_FFMPEG_DIR and install FFmpeg independently.")

icon = None
for name in ("transcodia.ico" if sys.platform == "win32" else "transcodia.icns",):
    candidate = ROOT / "packaging" / name
    if candidate.is_file():
        icon = str(candidate)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pypdf", "pdfplumber", "pypdfium2", "reportlab", "openpyxl", "docx", "psutil", "PIL"],
    excludes=["tkinter", "pytest", "coverage", "fitz", "pymupdf"],
    noarchive=False,
)
if sys.platform == "win32":
    # Qt uses Windows' ICU API. A different ICU found on PATH can shadow it.
    a.binaries = [entry for entry in a.binaries if entry[0].lower() != "icuuc.dll"]
# This unused optional decorative font is not part of the product's font set.
a.datas = [entry for entry in a.datas if "darkgarden" not in entry[0].lower()]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Transcodia",
    console=False,
    icon=icon,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Transcodia")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Transcodia.app",
        icon=icon,
        bundle_identifier="app.transcodia.desktop",
        version=version,
        info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": version},
    )
