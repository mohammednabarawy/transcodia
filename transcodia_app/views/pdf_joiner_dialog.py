"""PDF merge workspace with ordered inputs and rendered page previews."""
import os
from pathlib import Path

import io
import pypdfium2 as pdfium
from PySide6 import QtCore, QtGui, QtWidgets

from transcodia_app.icons import icon
from transcodia_app.i18n import tr
from transcodia_app.handlers.doc_handler import read_pdf


class PdfFileTable(QtWidgets.QTableWidget):
    files_dropped = QtCore.Signal(list)

    def __init__(self, language, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels([tr("Preview", language), "Media information"])
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 130)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(112)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setAcceptDrops(True)
        self.setIconSize(QtCore.QSize(80, 100))
        self.empty_button = QtWidgets.QPushButton(tr("Add Files", language), self.viewport())
        self.empty_button.setProperty("sourceText", "Add Files")
        self.empty_button.setIcon(icon("add_files"))
        self.empty_button.setIconSize(QtCore.QSize(56, 56))
        self.empty_button.resize(165, 64)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.empty_button.move((self.viewport().width() - self.empty_button.width()) // 2,
                               (self.viewport().height() - self.empty_button.height()) // 2)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class PdfJoinerDialog(QtWidgets.QDialog):
    def __init__(self, default_output_dir, parent=None, language="ar"):
        super().__init__(parent)
        self.language = language
        self.paths = []
        self.output_dir = default_output_dir
        self._previews = {}
        self.setWindowTitle("Transcodia · PDF Merge")
        self.setWindowIcon(icon("app"))
        self.resize(1350, 820)
        self.setMinimumSize(760, 480)
        self.setAcceptDrops(True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        heading = QtWidgets.QLabel("Build a single PDF")
        heading.setProperty("sourceText", "Build a single PDF")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        description = QtWidgets.QLabel("Add documents, arrange their order, and choose an output folder.")
        description.setProperty("sourceText", "Add documents, arrange their order, and choose an output folder.")
        description.setObjectName("sectionHint")
        layout.addWidget(description)
        self.table = PdfFileTable(language)
        self.table.setStyleSheet("QTableWidget { border: none; }")
        self.table.empty_button.clicked.connect(self._add_files)
        self.table.files_dropped.connect(self.add_paths)
        layout.addWidget(self.table, 1)

        actions = QtWidgets.QHBoxLayout()
        self.btn_order = QtWidgets.QPushButton("↕")
        self.btn_order.setFixedSize(32, 32)
        order_menu = QtWidgets.QMenu(self)
        order_menu.addAction(tr("Move Up", language), lambda: self.move_selected(-1))
        order_menu.addAction(tr("Move Down", language), lambda: self.move_selected(1))
        self.btn_order.setMenu(order_menu)
        actions.addWidget(self.btn_order)
        self.btn_remove = QtWidgets.QPushButton()
        self.btn_remove.setIcon(icon("remove"))
        self.btn_remove.setToolTip(tr("Remove Selected", language))
        self.btn_remove.setFixedSize(32, 32)
        self.btn_remove.clicked.connect(self.remove_selected)
        actions.addWidget(self.btn_remove)
        actions.addStretch()
        self.btn_folder = QtWidgets.QPushButton()
        self.btn_folder.setIcon(icon("folder"))
        self.btn_folder.setToolTip(tr("Add Folder", language))
        self.btn_folder.setFixedSize(42, 32)
        self.btn_folder.clicked.connect(self._add_folder)
        actions.addWidget(self.btn_folder)
        self.btn_add = QtWidgets.QPushButton(tr("Add Files", language))
        self.btn_add.setProperty("sourceText", "Add Files")
        self.btn_add.setIcon(icon("add_files"))
        self.btn_add.setIconSize(QtCore.QSize(28, 28))
        self.btn_add.setFixedSize(140, 32)
        self.btn_add.clicked.connect(self._add_files)
        actions.addWidget(self.btn_add)
        layout.addLayout(actions)

        self.chk_append_name = QtWidgets.QCheckBox(tr("Append setting name", language))
        layout.addWidget(self.chk_append_name)
        bottom = QtWidgets.QHBoxLayout()
        self.txt_output_dir = QtWidgets.QComboBox()
        self.txt_output_dir.setEditable(True)
        self.txt_output_dir.addItem(icon("folder"), default_output_dir)
        self.txt_output_dir.setMinimumWidth(280)
        self.txt_output_dir.setMaximumWidth(360)
        bottom.addWidget(self.txt_output_dir)
        self.btn_destination = QtWidgets.QPushButton()
        self.btn_destination.setIcon(icon("folder"))
        self.btn_destination.setFixedSize(30, 28)
        self.btn_destination.clicked.connect(self._browse_output)
        bottom.addWidget(self.btn_destination)
        bottom.addStretch()
        self.btn_ok = QtWidgets.QPushButton(tr("OK", language))
        self.btn_ok.setIcon(icon("confirm"))
        self.btn_ok.setIconSize(QtCore.QSize(24, 24))
        self.btn_ok.setFixedSize(140, 32)
        self.btn_ok.clicked.connect(self._accept_files)
        bottom.addWidget(self.btn_ok)
        layout.addLayout(bottom)
        self._refresh_actions()

        remove_action = QtGui.QAction(self)
        remove_action.setShortcut(QtGui.QKeySequence.StandardKey.Delete)
        remove_action.triggered.connect(self.remove_selected)
        self.addAction(remove_action)

    def _add_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, tr("Add Files", self.language), "", "PDF (*.pdf)")
        self.add_paths(paths)

    def _add_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Add Folder", self.language))
        if folder:
            self.add_paths([str(p) for p in sorted(Path(folder).iterdir()) if p.suffix.lower() == ".pdf"])

    def add_paths(self, paths):
        errors = []
        known = {os.path.normcase(os.path.abspath(p)) for p in self.paths}
        for path in paths:
            path = os.path.abspath(path)
            key = os.path.normcase(path)
            if key in known:
                continue
            try:
                reader = read_pdf(path)
                with pdfium.PdfDocument(path) as pdf:
                    page = pdf[0]
                    bitmap = page.render(scale=0.18)
                    preview = io.BytesIO()
                    bitmap.to_pil().save(preview, format="PNG")
                    pixmap = QtGui.QPixmap()
                    pixmap.loadFromData(preview.getvalue(), "PNG")
                    bitmap.close()
                    page.close()
                    self._previews[path] = (QtGui.QIcon(pixmap), len(reader.pages))
            except Exception as error:
                errors.append(f"{os.path.basename(path)}: {error}")
                continue
            self.paths.append(path)
            known.add(key)
        self._rebuild_table()
        if errors:
            QtWidgets.QMessageBox.warning(self, "PDF Joiner", "\n".join(errors))

    def _rebuild_table(self):
        self.table.setRowCount(0)
        for row, path in enumerate(self.paths):
            self.table.insertRow(row)
            artwork, pages = self._previews[path]
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(artwork, ""))
            size = os.path.getsize(path) / 1024 if os.path.exists(path) else 0
            info = QtWidgets.QTableWidgetItem(f"{os.path.basename(path)}\n{pages} pages | {size:.1f} KB\n{path}")
            info.setToolTip(path)
            self.table.setItem(row, 1, info)
        self._refresh_actions()

    def _refresh_actions(self):
        self.table.empty_button.setVisible(not self.paths)
        self.btn_order.setEnabled(len(self.paths) > 1)
        self.btn_remove.setEnabled(bool(self.paths))

    def remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self._previews.pop(self.paths.pop(row), None)
        self._rebuild_table()

    def move_selected(self, offset):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows or rows[0] + offset < 0 or rows[-1] + offset >= len(self.paths):
            return
        for row in (rows if offset < 0 else reversed(rows)):
            self.paths[row], self.paths[row + offset] = self.paths[row + offset], self.paths[row]
        self._rebuild_table()
        self.table.clearSelection()
        for row in rows:
            for col in range(2):
                self.table.item(row + offset, col).setSelected(True)

    def _browse_output(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Output Folder", self.language), self.txt_output_dir.currentText())
        if folder:
            self.txt_output_dir.setCurrentText(folder)

    def _accept_files(self):
        if not self.paths:
            QtWidgets.QMessageBox.information(self, "PDF Joiner", tr("Add Files", self.language))
            return
        folder = self.txt_output_dir.currentText().strip()
        if not folder:
            self.txt_output_dir.setFocus()
            return
        if any(not os.path.isfile(path) for path in self.paths):
            QtWidgets.QMessageBox.warning(self, "PDF Joiner", "An input PDF is no longer available. Remove it or add it again.")
            return
        self.output_dir = os.path.abspath(folder)
        self.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()
