"""
Task Table View.
Task list with live progress delegates,
separate Elapsed Time and Speed columns, drag-and-drop, and task state tracking.
"""

import os
import re
from typing import Dict, Optional
from PySide6 import QtCore, QtGui, QtWidgets
from transcodia_app.icons import icon
from transcodia_app.i18n import tr


class TaskTableView(QtWidgets.QTableWidget):
    """Main task queue table with live progress bars and state columns."""

    files_dropped = QtCore.Signal(list)  # list of file paths dropped
    task_double_clicked = QtCore.Signal(str)  # task_id

    COL_SOURCE = 0
    COL_FORMAT = 1
    COL_SIZE = 2
    COL_PROGRESS = 3
    COL_ELAPSED = 4
    COL_SPEED = 5
    COL_DESTINATION = 6
    COL_PREVIEW = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.language = "ar"
        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "Source File",
            "Output Format",
            "Output Size",
            "Convert State",
            "Elapsed Time",
            "Speed",
            "Output File Path",
            "Preview",
        ])

        header = self.horizontalHeader()
        header.setSectionsMovable(False)
        header.moveSection(header.visualIndex(self.COL_PREVIEW), 0)
        header.setSectionResizeMode(self.COL_PREVIEW, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(self.COL_PREVIEW, 130)
        header.setSectionResizeMode(self.COL_SOURCE, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_PROGRESS, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column in (self.COL_FORMAT, self.COL_SIZE, self.COL_ELAPSED, self.COL_SPEED, self.COL_DESTINATION):
            self.setColumnHidden(column, True)
        self.verticalHeader().setDefaultSectionSize(100)
        self.setIconSize(QtCore.QSize(64, 64))
        self.setShowGrid(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setAcceptDrops(True)
        self.verticalHeader().setVisible(False)

        self._task_row_map: Dict[str, int] = {}
        self._progress_bars: Dict[str, QtWidgets.QProgressBar] = {}
        self._last_pct_str: Dict[str, str] = {}

        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.empty_state = QtWidgets.QFrame(self.viewport())
        empty_layout = QtWidgets.QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        mark = QtWidgets.QLabel()
        mark.setPixmap(icon("app").pixmap(76, 76))
        mark.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(mark)
        self.empty_title = QtWidgets.QLabel()
        self.empty_title.setObjectName("sectionTitle")
        self.empty_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        self.model().rowsInserted.connect(self._refresh_empty_state)
        self.model().rowsRemoved.connect(self._refresh_empty_state)
        self.set_language(self.language)

    def _refresh_empty_state(self, *args):
        self.empty_state.setVisible(self.rowCount() == 0)
        self.empty_state.setGeometry((self.viewport().width() - 320) // 2,
                                     max(0, (self.viewport().height() - 170) // 2), 320, 170)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "empty_state"):
            self._refresh_empty_state()

    def _on_item_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        row = item.row()
        inv_map = {r: tid for tid, r in self._task_row_map.items()}
        tid = inv_map.get(row)
        if tid:
            self.task_double_clicked.emit(tid)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def add_task(self, task_id: str, src_path: str, format_name: str, dst_path: str) -> int:
        row = self.rowCount()
        self.insertRow(row)

        src_name = os.path.basename(src_path)
        src_item = QtWidgets.QTableWidgetItem(f"{src_name}\n{os.path.dirname(src_path)}")
        src_item.setToolTip(src_path)
        self.setItem(row, self.COL_SOURCE, src_item)
        extension = os.path.splitext(src_path)[1].lstrip(".").lower()
        preview_item = QtWidgets.QTableWidgetItem(icon(extension if extension != "pdf" else "pdf_joiner"), "")
        self.setItem(row, self.COL_PREVIEW, preview_item)

        fmt_item = QtWidgets.QTableWidgetItem(format_name.upper())
        fmt_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_FORMAT, fmt_item)

        size_item = QtWidgets.QTableWidgetItem("--")
        size_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_SIZE, size_item)

        # Embedded QProgressBar
        pbar = QtWidgets.QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setFormat(tr("Pending", self.language))
        output_cell = QtWidgets.QWidget()
        output_cell.setAutoFillBackground(False)
        output_layout = QtWidgets.QVBoxLayout(output_cell)
        output_layout.setContentsMargins(8, 7, 8, 7)
        output_layout.setSpacing(4)
        filename = QtWidgets.QLabel(os.path.basename(dst_path))
        filename.setObjectName("taskDestination")
        filename.setToolTip(dst_path)
        filename.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        output_layout.addWidget(filename)
        output_layout.addWidget(pbar)
        detail = QtWidgets.QLabel(format_name.upper())
        detail.setObjectName("taskDetails")
        detail.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        output_layout.addWidget(detail)
        self.setCellWidget(row, self.COL_PROGRESS, output_cell)
        self._progress_bars[task_id] = pbar

        elapsed_item = QtWidgets.QTableWidgetItem("00:00:00")
        elapsed_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_ELAPSED, elapsed_item)

        speed_item = QtWidgets.QTableWidgetItem("--")
        speed_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, self.COL_SPEED, speed_item)

        dst_name = os.path.basename(dst_path)
        dst_item = QtWidgets.QTableWidgetItem(dst_name)
        dst_item.setToolTip(dst_path)
        self.setItem(row, self.COL_DESTINATION, dst_item)

        self._task_row_map[task_id] = row
        parent = self.window()
        if hasattr(parent, "_update_status_summary"):
            parent._update_status_summary()
        return row

    def set_task_started(self, task_id: str):
        row = self._task_row_map.get(task_id)
        if row is None:
            return
        pbar = self._progress_bars.get(task_id)
        if pbar:
            pbar.setValue(0)
            pbar.setFormat(tr("Converting...", self.language))
            pbar.setStyleSheet("")
        detail = self.cellWidget(row, self.COL_PROGRESS).findChild(QtWidgets.QLabel, "taskDetails")
        if detail:
            detail.setText(tr("Converting...", self.language))

    def update_task_progress(self, task_id: str, pct: Optional[float], speed: Optional[float], current_time: float):
        row = self._task_row_map.get(task_id)
        if row is None:
            return

        pbar = self._progress_bars.get(task_id)
        if pbar:
            if pct is not None and pct >= 0:
                pbar.setValue(int(pct))
                fmt_str = f"{pct:.1f}%"
                self._last_pct_str[task_id] = fmt_str
                pbar.setFormat(fmt_str)
            else:
                pbar.setFormat(tr("Converting...", self.language))

        # Update elapsed
        hrs = int(current_time // 3600)
        mins = int((current_time % 3600) // 60)
        secs = int(current_time % 60)
        self.setItem(row, self.COL_ELAPSED, QtWidgets.QTableWidgetItem(f"{hrs:02d}:{mins:02d}:{secs:02d}"))

        # Update speed
        spd_str = f"{speed:g}x" if speed else "--"
        self.setItem(row, self.COL_SPEED, QtWidgets.QTableWidgetItem(spd_str))
        detail = self.cellWidget(row, self.COL_PROGRESS).findChild(QtWidgets.QLabel, "taskDetails")
        detail.setText(f"{hrs:02d}:{mins:02d}:{secs:02d} | {spd_str}")

    def set_task_paused(self, task_id: str):
        pbar = self._progress_bars.get(task_id)
        if pbar:
            pbar.setFormat(f"Paused ({pbar.value()}%)")

    def set_task_cancelled(self, task_id):
        pbar = self._progress_bars.get(task_id)
        if pbar:
            pbar.setFormat(tr("Cancelled", self.language))
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #e3b04b; }")

    def set_task_resumed(self, task_id: str):
        pbar = self._progress_bars.get(task_id)
        if pbar:
            last = self._last_pct_str.get(task_id, f"{pbar.value()}%")
            pbar.setFormat(last)

    def set_task_completed(self, task_id: str, success: bool, output_bytes: Optional[int] = None, error_msg: Optional[str] = None):
        row = self._task_row_map.get(task_id)
        if row is None:
            return

        pbar = self._progress_bars.get(task_id)
        if pbar:
            if success:
                pbar.setValue(100)
                pbar.setFormat(tr("Completed", self.language))
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #10b981; }")
            else:
                pbar.setValue(100)
                pbar.setFormat(tr("Failed", self.language))
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")

        output_cell = self.cellWidget(row, self.COL_PROGRESS)
        if error_msg:
            output_cell.setToolTip(error_msg)
            detail = output_cell.findChild(QtWidgets.QLabel, "taskDetails")
            lines = error_msg.splitlines()
            cause = next((line for line in lines if re.search(
                r"no space|permission denied|not found|could not|cannot|invalid|error|not supported",
                line, re.IGNORECASE)), lines[-1])
            detail.setText(cause)
            detail.setToolTip(error_msg)

        if output_bytes is not None and output_bytes > 0:
            if output_bytes >= 1024 * 1024:
                size_str = f"{output_bytes / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{output_bytes / 1024:.1f} KB"
            self.setItem(row, self.COL_SIZE, QtWidgets.QTableWidgetItem(size_str))
        elif error_msg:
            err_item = QtWidgets.QTableWidgetItem("Error")
            err_item.setToolTip(error_msg)
            self.setItem(row, self.COL_SIZE, err_item)

    def reset_task(self, task_id: str):
        row = self._task_row_map.get(task_id)
        if row is None:
            return
        pbar = self._progress_bars.get(task_id)
        if pbar:
            pbar.setValue(0)
            pbar.setFormat(tr("Pending", self.language))
            pbar.setStyleSheet("")
        self.cellWidget(row, self.COL_PROGRESS).setToolTip("")
        self.setItem(row, self.COL_SIZE, QtWidgets.QTableWidgetItem("--"))
        self.setItem(row, self.COL_ELAPSED, QtWidgets.QTableWidgetItem("00:00:00"))
        self.setItem(row, self.COL_SPEED, QtWidgets.QTableWidgetItem("--"))

    def get_selected_task_ids(self) -> list:
        rows = set(index.row() for index in self.selectedIndexes())
        inv_map = {r: tid for tid, r in self._task_row_map.items()}
        return [inv_map[r] for r in rows if r in inv_map]

    def clear_tasks(self):
        self.setRowCount(0)
        self._task_row_map.clear()
        self._progress_bars.clear()
        self._last_pct_str.clear()

    def set_language(self, language):
        previous = self.language
        self.language = language
        self.empty_title.setText(tr("Ready for your next conversion", language))
        self._refresh_empty_state()
        for column, label in [(self.COL_PREVIEW, "Preview"), (self.COL_SOURCE, "Source"), (self.COL_PROGRESS, "Output / Convert State")]:
            self.horizontalHeaderItem(column).setText(tr(label, language))
        for pbar in self._progress_bars.values():
            for label in ("Pending", "Completed", "Failed", "Converting...", "Cancelled"):
                if pbar.format() == tr(label, previous):
                    pbar.setFormat(tr(label, language))
                    break

    def remove_tasks(self, task_ids):
        for task_id in sorted(task_ids, key=lambda tid: self._task_row_map.get(tid, -1), reverse=True):
            row = self._task_row_map.pop(task_id, None)
            if row is None:
                continue
            self._progress_bars.pop(task_id, None)
            self._last_pct_str.pop(task_id, None)
            self.removeRow(row)
            for remaining_id, remaining_row in self._task_row_map.items():
                if remaining_row > row:
                    self._task_row_map[remaining_id] = remaining_row - 1

    def set_task_destination(self, task_id, path):
        row = self._task_row_map[task_id]
        item = self.item(row, self.COL_DESTINATION)
        item.setText(os.path.basename(path))
        item.setToolTip(path)
        label = self.cellWidget(row, self.COL_PROGRESS).findChild(QtWidgets.QLabel, "taskDestination")
        label.setText(os.path.basename(path))
        label.setToolTip(path)
