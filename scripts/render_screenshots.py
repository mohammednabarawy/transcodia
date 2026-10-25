"""Capture the actual Transcodia widgets and generated icon set offscreen."""
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6 import QtCore, QtGui, QtWidgets
from transcodia_app.icons import icon, ASSETS
from transcodia_app.views.main_window import MainWindow
from transcodia_app.views.pdf_joiner_dialog import PdfJoinerDialog

app = QtWidgets.QApplication([])
app.setStyle("Fusion")
font_folder = Path(os.environ.get("WINDIR", "")) / "Fonts"
for name in ("segoeui.ttf", "arial.ttf"):
    if (font_folder / name).is_file():
        QtGui.QFontDatabase.addApplicationFont(str(font_folder / name))
app.setFont(QtGui.QFont("Segoe UI", 10))
output = ROOT / "_docs" / "images"
output.mkdir(parents=True, exist_ok=True)
main = MainWindow(probe_hardware=False)
main.resize(1440, 960)
main._change_language("en")
main.txt_bottom_output.setText("Documents/TranscodiaOutput")
main.show()
app.processEvents()
main.grab().save(str(output / "main-window.png"))
main._change_language("ar")
app.processEvents()
main.grab().save(str(output / "main-window-ar.png"))
joiner = PdfJoinerDialog("Documents/TranscodiaOutput", main, language="en")
joiner.resize(1080, 740)
joiner.show()
app.processEvents()
joiner.grab().save(str(output / "pdf-joiner.png"))
joiner.close()
main.close()

sheet = QtWidgets.QWidget()
sheet.setStyleSheet("QWidget { background: #f5f9ff; color: #172d49; font: 12px 'Segoe UI'; } QLabel { background: transparent; }")
grid = QtWidgets.QGridLayout(sheet)
grid.setContentsMargins(24, 24, 24, 24)
grid.setSpacing(14)
for index, path in enumerate(sorted((ASSETS / "icons").glob("*.png"))):
    cell = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(cell)
    picture = QtWidgets.QLabel()
    picture.setPixmap(icon(path.stem).pixmap(72, 72))
    picture.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    caption = QtWidgets.QLabel(path.stem.replace("_", " ").title())
    caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(picture)
    layout.addWidget(caption)
    grid.addWidget(cell, index // 6, index % 6)
sheet.resize(900, 570)
sheet.show()
app.processEvents()
sheet.grab().save(str(output / "ui-icons.png"))
sheet.close()
print("Saved current UI screenshots and 23-icon preview")
