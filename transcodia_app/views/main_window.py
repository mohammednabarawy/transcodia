"""
Main Application Window.
Transcodia main window:
- Top Menu Bar: Task, Theme, Language, Settings, Help
- Toolbar: Start, Pause, Stop, Remove, Clear List, Output Folder, Option, GPU Acceleration Badge
- Central Splitter: CategoryPanel (Video, Audio, Picture, Document, ROM Device) + TaskTableView
- Bottom Bar: Output Folder selector, Change/Open buttons, Post-conversion action selector, Status metrics
- Context Menu: Play Output File, Open Containing Folder, View MediaDetails, Fast Clip / Set Range, Reset Task State
- Task List Persistence: Save Task List (.json/.tctask), Load Task List
"""

import os
import sys
import json
import subprocess
import asyncio
from copy import deepcopy
from typing import Dict, List, Optional, Any

from PySide6 import QtCore, QtGui, QtWidgets

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from transcodia_engine.models import ConvertTaskItem, HardwareAccel, VideoCodec, MediaAdditionalConfig
from transcodia_engine.worker import BatchConversionWorker, TaskProgress, TaskResult, TaskStatus
from transcodia_engine.engine import FFMpegEngine
from transcodia_engine.hardware_prober import HardwareProber, HardwareCapabilities

from transcodia_app.theme_manager import ThemeManager
from transcodia_app.icons import icon
from transcodia_engine.runtime_paths import find_ffmpeg
from transcodia_app.i18n import tr, apply_language
from transcodia_app.version import APP_NAME, APP_VERSION
from transcodia_app.views.pdf_joiner_dialog import PdfJoinerDialog
from transcodia_app.paths import available_output
from transcodia_app.views.category_panel import CategoryPanel
from transcodia_app.views.task_table import TaskTableView
from transcodia_app.views.add_files_dialog import AddFilesDialog
from transcodia_app.views.output_settings_dialog import OutputSettingsDialog
from transcodia_app.views.options_dialog import OptionsDialog
from transcodia_app.views.clip_dialog import ClipDialog
from transcodia_app.views.delogo_dialog import DelogoDialog
from transcodia_app.views.mux_dialog import MuxDialog
from transcodia_app.views.media_details_dialog import MediaDetailsDialog
from transcodia_app.handlers.image_handler import ImageConverter, ImageConfig
from transcodia_app.handlers.doc_handler import DocumentConverter
from transcodia_app.handlers.probe_handler import MediaProbe


class ConversionRunnerThread(QtCore.QThread):
    """Background worker thread running media, image, and document conversions."""

    task_started = QtCore.Signal(str)  # task_id
    task_progress = QtCore.Signal(str, float, float, float)  # task_id, pct, speed, current_time
    task_completed = QtCore.Signal(str, bool, object, str)  # Python integer preserves sizes above 2 GiB.
    task_cancelled = QtCore.Signal(str)
    batch_finished = QtCore.Signal()

    def __init__(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrency: int = 2,
        ffmpeg_path: Optional[str] = None,
        parent: Optional[QtCore.QObject] = None,
    ):
        super().__init__(parent)
        self.tasks = tasks
        self.max_concurrency = max_concurrency
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg()
        self._is_stopped = False
        self._is_paused = False
        self._async_worker: Optional[BatchConversionWorker] = None

    def stop(self):
        self._is_stopped = True
        if self._async_worker:
            self._async_worker.cancel_all()

    def pause(self):
        self._is_paused = True
        if self._async_worker:
            self._async_worker.pause()

    def resume(self):
        self._is_paused = False
        if self._async_worker:
            self._async_worker.resume()

    def is_paused(self) -> bool:
        return self._is_paused

    def run(self):
        try:
            self._run_tasks()
        finally:
            self.batch_finished.emit()

    def _run_tasks(self):
        # Separate tasks into Media (FFmpeg), Picture, and Document
        media_tasks: List[Dict[str, Any]] = []
        pic_tasks: List[Dict[str, Any]] = []
        doc_tasks: List[Dict[str, Any]] = []

        for t in self.tasks:
            cat = t.get("category", "video")
            if cat in ("video", "audio", "tool", "rom"):
                media_tasks.append(t)
            elif cat == "picture":
                pic_tasks.append(t)
            elif cat == "doc":
                doc_tasks.append(t)

        # 1. Run Picture Tasks
        for pt in pic_tasks:
            while self._is_paused and not self._is_stopped:
                self.msleep(25)
            if self._is_stopped:
                break
            t_id = pt["id"]
            self.task_started.emit(t_id)
            src = pt["src"]
            dst = pt["dst"]
            img_cfg = pt.get("img_config") or ImageConfig()
            error = ""
            try:
                os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
                success = ImageConverter.convert_image(src, dst, img_cfg)
                out_bytes = os.path.getsize(dst) if success and os.path.exists(dst) else 0
            except Exception as exc:
                success, out_bytes, error = False, 0, str(exc)
            self.task_progress.emit(t_id, 100.0, 1.0, 0.1)
            self.task_completed.emit(t_id, success, out_bytes, "" if success else (error or "Image conversion failed"))

        # 2. Run Document Tasks
        doc_conv = DocumentConverter()
        for dt in doc_tasks:
            while self._is_paused and not self._is_stopped:
                self.msleep(25)
            if self._is_stopped:
                break
            t_id = dt["id"]
            self.task_started.emit(t_id)
            src = dt["src"]
            dst = dt["dst"]
            fmt = dt["format"]
            success = False
            err_msg = ""
            try:
                os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
                if fmt == "pdf2docx":
                    success = doc_conv.convert_pdf_to_docx(src, dst)
                elif fmt == "docx2pdf":
                    success = doc_conv.convert_docx_to_pdf(src, dst)
                elif fmt == "pdf2xlsx":
                    success = doc_conv.convert_pdf_to_xlsx(src, dst)
                elif fmt == "pdf2txt":
                    success = doc_conv.convert_pdf_to_txt(src, dst)
                elif fmt == "pdf2html":
                    success = doc_conv.convert_pdf_to_html(src, dst)
                elif fmt == "markitdown":
                    success = doc_conv.convert_to_markdown(src, dst)
                elif fmt == "pdf_joiner":
                    all_pdfs = [src] + dt.get("additional_files", [])
                    success = doc_conv.join_pdfs(all_pdfs, dst)
            except Exception as e:
                success = False
                err_msg = str(e)

            out_bytes = os.path.getsize(dst) if success and os.path.exists(dst) else 0
            self.task_progress.emit(t_id, 100.0, 1.0, 0.1)
            self.task_completed.emit(
                t_id,
                success,
                out_bytes,
                "" if success else (err_msg or "Document conversion failed")
            )

        # 3. Run Media Batch (FFmpeg)
        if media_tasks and not self._is_stopped:
            asyncio.run(self._run_media_batch(media_tasks))

    async def _run_media_batch(self, tasks: List[Dict[str, Any]]):
        engine = FFMpegEngine(ffmpeg_path=self.ffmpeg_path)
        self._async_worker = BatchConversionWorker(
            engine=engine,
            max_concurrency=self.max_concurrency,
            on_progress=self._on_worker_progress,
            on_start=self._on_worker_start,
            on_complete=self._on_worker_complete,
        )

        for t in tasks:
            t_id = t["id"]
            convert_item: ConvertTaskItem = t["task_item"]
            duration = t.get("duration", 0.0)
            self._async_worker.add_task(convert_item, total_duration_seconds=duration, task_id=t_id)

        if self._is_paused:
            self._async_worker.pause()
        await self._async_worker.run_all()

    def _on_worker_start(self, task_id: str, task: ConvertTaskItem):
        self.task_started.emit(task_id)

    def _on_worker_progress(self, task_id: str, p: TaskProgress):
        pct = p.progress_percent if p.progress_percent is not None else -1.0
        spd = p.speed if p.speed is not None else 0.0
        self.task_progress.emit(task_id, pct, spd, p.current_seconds)

    def _on_worker_complete(self, task_id: str, res: TaskResult):
        if res.status == TaskStatus.CANCELLED:
            self.task_cancelled.emit(task_id)
            return
        success = (res.status == TaskStatus.COMPLETED)
        out_bytes = res.output_size_bytes or 0
        err_msg = res.error_message or res.warning_message or ""
        self.task_completed.emit(task_id, success, out_bytes, err_msg)


class MainWindow(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self, probe_hardware: bool = True):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1570, 880)
        self.setMinimumSize(1000, 620)
        self.setWindowIcon(icon("app"))
        self.language = "ar"

        # Settings
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "TranscodiaOutput")
        os.makedirs(self.output_dir, exist_ok=True)
        self.max_concurrency = 2
        self.preferred_hw = "auto"
        self.play_sound = True
        self.current_skin = "Transcodia Light"

        # Resolved Executables: FFMPEG_PATH, bundled copy, configured resources folder, then PATH.
        self.ffmpeg_path = find_ffmpeg()

        # State tracking
        self.all_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_counter = 0
        self.runner_thread: Optional[ConversionRunnerThread] = None
        self._probe_thread: Optional[QtCore.QThread] = None

        self._hardware_caps_dict: Dict[str, bool] = {}

        self._setup_ui()
        self._change_language(self.language)
        ThemeManager.apply_theme(self.current_skin, self)

        if probe_hardware:
            self._probe_hardware_in_background()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Safely cleans up any running threads on exit."""
        running_threads = []
        if self._probe_thread and self._probe_thread.isRunning():
            running_threads.append(self._probe_thread)
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.stop()
            running_threads.append(self.runner_thread)
        if running_threads:
            event.ignore()
            for thread in running_threads:
                try:
                    thread.finished.connect(self.close, QtCore.Qt.ConnectionType.UniqueConnection)
                except RuntimeError:
                    pass
            return
        self._elapsed_timer.stop()
        super().closeEvent(event)

    def _setup_ui(self):
        # 1. Menu Bar
        self._create_menu_bar()

        # 2. Main Toolbar
        self._create_toolbar()

        # 3. Central Splitter Area
        central_widget = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        brand = QtWidgets.QFrame()
        brand.setObjectName("brandHeader")
        brand_layout = QtWidgets.QHBoxLayout(brand)
        brand_layout.setContentsMargins(26, 18, 26, 18)
        mark = QtWidgets.QLabel()
        mark.setPixmap(icon("app").pixmap(56, 56))
        brand_layout.addWidget(mark)
        titles = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        titles.addWidget(title)
        subtitle = QtWidgets.QLabel("Your media. Your next format.")
        subtitle.setProperty("sourceText", "Your media. Your next format.")
        subtitle.setObjectName("brandSubtitle")
        titles.addWidget(subtitle)
        brand_layout.addLayout(titles)
        brand_layout.addStretch()
        version = QtWidgets.QLabel(f"v{APP_VERSION}  ·  Desktop workspace")
        version.setObjectName("sectionHint")
        brand_layout.addWidget(version)
        central_layout.addWidget(brand)

        workspace = QtWidgets.QWidget()
        workspace_layout = QtWidgets.QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(20, 22, 24, 20)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Left: Category Sidebar
        self.category_panel = CategoryPanel(self, language=self.language)
        self.category_panel.format_selected.connect(self._on_format_tile_clicked)
        self.splitter.addWidget(self.category_panel)

        # Right: Task Table View
        self.task_table = TaskTableView(self)
        self.task_table.files_dropped.connect(self._on_files_dropped)
        self.task_table.task_double_clicked.connect(self._on_task_double_clicked)
        self.task_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(self._show_table_context_menu)
        queue = QtWidgets.QFrame()
        queue.setObjectName("queueSurface")
        queue_layout = QtWidgets.QVBoxLayout(queue)
        queue_layout.setContentsMargins(20, 18, 20, 14)
        queue_title = QtWidgets.QLabel("Conversion queue")
        queue_title.setProperty("sourceText", "Conversion queue")
        queue_title.setObjectName("sectionTitle")
        queue_layout.addWidget(queue_title)
        queue_hint = QtWidgets.QLabel("Drop files here or choose a tool to begin.")
        queue_hint.setProperty("sourceText", "Drop files here or choose a tool to begin.")
        queue_hint.setObjectName("sectionHint")
        queue_layout.addWidget(queue_hint)
        queue_layout.addWidget(self.task_table, 1)
        self.splitter.addWidget(queue)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([390, 1000])
        self.splitter.setHandleWidth(18)

        workspace_layout.addWidget(self.splitter)
        central_layout.addWidget(workspace, stretch=1)

        # 4. Bottom Controls Bar
        bottom_bar = self._create_bottom_bar()
        central_layout.addWidget(bottom_bar)
        queue_layout.addWidget(self.lbl_status_summary)
        self.lbl_status_summary.show()

        self.setCentralWidget(central_widget)
        self._change_language(self.language)
        self._update_status_summary()

    def _create_menu_bar(self):
        mb = self.menuBar()

        # Task Menu
        menu_task = mb.addMenu("&Task")
        self.act_start = QtGui.QAction("▶ &Start", self)
        self.act_start.setShortcut(QtGui.QKeySequence("F5"))
        self.act_start.triggered.connect(self._start_conversion)
        menu_task.addAction(self.act_start)

        self.act_pause = QtGui.QAction("⏸ &Pause", self)
        self.act_pause.setShortcut(QtGui.QKeySequence("F6"))
        self.act_pause.setEnabled(False)
        self.act_pause.triggered.connect(self._pause_conversion)
        menu_task.addAction(self.act_pause)

        self.act_stop = QtGui.QAction("⏹ S&top", self)
        self.act_stop.setShortcut(QtGui.QKeySequence("Shift+F5"))
        self.act_stop.setEnabled(False)
        self.act_stop.triggered.connect(self._stop_conversion)
        menu_task.addAction(self.act_stop)

        menu_task.addSeparator()

        act_del = QtGui.QAction("🗑 &Remove Selected Task", self)
        act_del.setShortcut(QtGui.QKeySequence("Delete"))
        act_del.triggered.connect(self._delete_selected_tasks)
        menu_task.addAction(act_del)

        act_clear = QtGui.QAction("🧹 &Clear Task List", self)
        act_clear.setShortcut(QtGui.QKeySequence("Ctrl+L"))
        act_clear.triggered.connect(self._clear_all_tasks)
        menu_task.addAction(act_clear)

        act_reset = QtGui.QAction("🔄 Reset &Task State", self)
        act_reset.triggered.connect(self._reset_selected_tasks)
        menu_task.addAction(act_reset)

        menu_task.addSeparator()

        act_save_list = QtGui.QAction("💾 &Save Task List...", self)
        act_save_list.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        act_save_list.triggered.connect(self._save_task_list)
        menu_task.addAction(act_save_list)

        act_load_list = QtGui.QAction("📂 &Load Task List...", self)
        act_load_list.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        act_load_list.triggered.connect(self._load_task_list)
        menu_task.addAction(act_load_list)

        menu_task.addSeparator()

        act_open_out = QtGui.QAction("📁 Open &Output Folder", self)
        act_open_out.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        act_open_out.triggered.connect(self._open_output_folder)
        menu_task.addAction(act_open_out)

        menu_task.addSeparator()

        act_exit = QtGui.QAction("E&xit", self)
        act_exit.setShortcut(QtGui.QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.close)
        menu_task.addAction(act_exit)

        # Skin Menu
        menu_skin = mb.addMenu("&Appearance")
        skin_group = QtGui.QActionGroup(self)
        skin_group.setExclusive(True)

        for skin_name in ThemeManager.THEMES:
            act_skin = QtGui.QAction(skin_name, self, checkable=True)
            if skin_name == self.current_skin:
                act_skin.setChecked(True)
            act_skin.triggered.connect(lambda ch=False, name=skin_name: self._change_skin(name))
            skin_group.addAction(act_skin)
            menu_skin.addAction(act_skin)

        menu_language = mb.addMenu("Language")
        self.language_group = QtGui.QActionGroup(self)
        self.language_group.setExclusive(True)
        for name, code in [("العربية", "ar"), ("English", "en")]:
            action = menu_language.addAction(name)
            action.setCheckable(True)
            action.setChecked(code == self.language)
            action.setData(code)
            self.language_group.addAction(action)
            action.triggered.connect(lambda checked=False, lang=code: self._change_language(lang))

        # Settings Menu
        menu_settings = mb.addMenu("&Settings")
        act_options = QtGui.QAction("⚙ &Option...", self)
        act_options.setShortcut(QtGui.QKeySequence("Ctrl+P"))
        act_options.triggered.connect(self._open_options)
        menu_settings.addAction(act_options)

        # Help Menu
        menu_help = mb.addMenu("&Help")
        act_about = QtGui.QAction("&About Transcodia", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    def _create_toolbar(self):
        tb = self.addToolBar("Main Operations")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QtCore.QSize(32, 32))
        tb.setMinimumHeight(68)

        def button(label, artwork, handler):
            btn = QtWidgets.QToolButton()
            btn.setText(label)
            btn.setProperty("sourceText", label)
            btn.setIcon(icon(artwork))
            btn.setIconSize(QtCore.QSize(32, 32))
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            tb.addWidget(btn)
            return btn

        button("Output Folder", "folder", self._open_output_folder)
        button("Option", "options", self._open_options)
        tb.addSeparator()
        self.btn_remove = button("Remove", "remove", self._delete_selected_tasks)
        self.btn_clear = button("Clear List", "clear", self._clear_all_tasks)
        tb.addSeparator()
        self.btn_stop = button("Stop", "stop", self._stop_conversion)
        self.btn_stop.setEnabled(False)
        self.btn_start = button("Start", "start", self._start_conversion)
        self.btn_start.setObjectName("startConversion")
        self.btn_pause = button("Pause", "pause", self._pause_conversion)
        self.btn_pause.setEnabled(False)
        tb.addSeparator()
        button("Home Page", "home", self._show_home)
        # Hardware preferences are configured through Options.
        self.btn_gpu_badge = QtWidgets.QPushButton(self)
        self.btn_gpu_badge.hide()

    def _create_bottom_bar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QFrame()
        bar.setObjectName("workspaceFooter")
        bar.setMinimumHeight(58)
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(22, 10, 22, 10)
        layout.setSpacing(7)
        folder = QtWidgets.QLabel()
        folder.setPixmap(icon("folder").pixmap(16, 16))
        layout.addWidget(folder)
        self.txt_bottom_output = QtWidgets.QLineEdit(self.output_dir)
        self.txt_bottom_output.setReadOnly(True)
        self.txt_bottom_output.setMaximumWidth(240)
        self.txt_bottom_output.setMinimumWidth(90)
        self.txt_bottom_output.setToolTip(self.output_dir)
        layout.addWidget(self.txt_bottom_output)
        self.chk_multithread = QtWidgets.QCheckBox("Use Multi-Threads")
        self.chk_multithread.setChecked(True)
        layout.addWidget(self.chk_multithread)
        layout.addStretch()
        self.lbl_elapsed = QtWidgets.QLabel()
        layout.addWidget(self.lbl_elapsed)
        self.chk_shutdown = QtWidgets.QCheckBox("After Converting: Shut down computer")
        self.chk_shutdown.setToolTip("Available after explicit confirmation when a batch finishes")
        layout.addWidget(self.chk_shutdown)
        self.chk_notify = QtWidgets.QCheckBox("Completion notification")
        self.chk_notify.setChecked(self.play_sound)
        self.chk_notify.toggled.connect(lambda checked: setattr(self, "play_sound", checked))
        layout.addWidget(self.chk_notify)
        self.lbl_status_summary = QtWidgets.QLabel(self)
        self.lbl_status_summary.hide()
        self.combo_after_done = QtWidgets.QComboBox(self)
        self.combo_after_done.addItems(["Do nothing", "Open output folder", "Play alert sound"])
        self.combo_after_done.hide()
        self._elapsed_clock = QtCore.QElapsedTimer()
        self._elapsed_timer = QtCore.QTimer(self)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._update_elapsed()
        return bar

    def _update_elapsed(self):
        seconds = self._elapsed_clock.elapsed() // 1000 if self._elapsed_clock.isValid() else 0
        self.lbl_elapsed.setText(f'{tr("Elapsed Time", self.language)} : {seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}')

    def _show_home(self):
        self.category_panel.toolbox.setCurrentIndex(0)

    def _change_language(self, language):
        self.language = language
        self.setWindowTitle(f"ترانسكوديا {APP_VERSION}" if language == "ar" else f"{APP_NAME} {APP_VERSION}")
        apply_language(self, language)
        for action in self.menuBar().actions():
            source = (action.property("sourceText") or action.property("menuSource") or action.text()).replace("&", "")
            action.setProperty("menuSource", source)
            action.setText(tr(source, language))
        if hasattr(self, "language_group"):
            for action in self.language_group.actions():
                action.setChecked(action.data() == language)
        self.category_panel.set_language(language)
        self.task_table.set_language(language)
        self._update_elapsed()

    def _change_skin(self, skin_name: str):
        self.current_skin = skin_name
        ThemeManager.apply_theme(skin_name, self)

    def _probe_hardware_in_background(self):
        """Asynchronously probes hardware capabilities to prevent blocking the GUI thread."""
        class ProbeWorker(QtCore.QThread):
            probed = QtCore.Signal(dict)

            def __init__(self, ffmpeg_path: str):
                super().__init__()
                self.ffmpeg_path = ffmpeg_path

            def run(self):
                prober = HardwareProber(ffmpeg_path=self.ffmpeg_path)
                caps = prober.probe(test_runtime=True)
                info = {
                    "nvenc": caps.nvenc_h264,
                    "qsv": caps.qsv_h264,
                    "amf": caps.amf_h264,
                    "mf": caps.mf_h264,
                    "nvenc_hevc": caps.nvenc_hevc,
                    "qsv_hevc": caps.qsv_hevc,
                    "amf_hevc": caps.amf_hevc,
                    "mf_hevc": caps.mf_hevc,
                }
                self.probed.emit(info)

        self._probe_thread = ProbeWorker(self.ffmpeg_path)
        self._probe_thread.probed.connect(self._on_hardware_probed)
        self._probe_thread.start()

    def _on_hardware_probed(self, info: dict):
        self._hardware_caps_dict = info
        if info.get("nvenc"):
            text = "⚡ GPU: NVIDIA NVENC (CUDA)"
            bg = "#e8f5e9"
            fg = "#2e7d32"
        elif info.get("qsv"):
            text = "⚡ GPU: Intel QuickSync (QSV)"
            bg = "#e3f2fd"
            fg = "#1565c0"
        elif info.get("amf"):
            text = "⚡ GPU: AMD AMF (DirectX)"
            bg = "#fff3e0"
            fg = "#e65100"
        elif info.get("mf"):
            text = "⚡ GPU: Windows Media Foundation"
            bg = "#ede7f6"
            fg = "#512da8"
        else:
            text = "💻 CPU Software Encoding"
            bg = "#f5f5f5"
            fg = "#616161"

        self.btn_gpu_badge.setText(text)
        self.btn_gpu_badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid #b0bec5; "
            f"border-radius: 12px; padding: 4px 12px; font-weight: 600; font-size: 11px;"
        )

    def _on_format_tile_clicked(self, category: str, format_name: str, initial_paths=None):
        if category == "rom":
            QtWidgets.QMessageBox.information(self, "DVD / CD / ISO", "This tool requires an optical-disc/ISO backend, which is not available yet.")
            return
        if format_name == "batch_resize":
            self._on_format_tile_clicked("picture", "png", initial_paths=initial_paths)
            return
        if format_name == "pdf_joiner":
            dlg = PdfJoinerDialog(self.output_dir, self, language=self.language)
            if dlg.exec():
                self._enqueue_pdf_joiner_task(dlg.paths, False, dlg.output_dir, dlg.chk_append_name.isChecked())
                self._update_status_summary()
            return
        if format_name == "other_video":
            fmt, ok = QtWidgets.QInputDialog.getItem(self, "Video", "Output format", ["AVI", "FLV", "MOV", "3GP", "WMV", "MPG", "VOB"], 0, False)
            if ok:
                self._on_format_tile_clicked("video", fmt.lower())
            return
        if format_name == "info":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Media information")
            if path:
                MediaDetailsDialog(path, ffmpeg_path=self.ffmpeg_path, parent=self).exec()
            return
        if category == "external":
            self._open_external_tool(format_name)
            return
        if format_name in ("split", "frames"):
            self._open_media_utility(format_name)
            return
        # 1. Specialized Tool: Clip
        if format_name == "clip":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select Video to Clip", "", "Media Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm *.mp3 *.wav);;All Files (*.*)"
            )
            if path:
                clip_dlg = ClipDialog(path, parent=self)
                if clip_dlg.exec():
                    start_s, end_s = clip_dlg.get_range()
                    base = os.path.splitext(os.path.basename(path))[0]
                    dst = os.path.join(self.output_dir, f"{base}_Clip.mp4")
                    task_item = ConvertTaskItem(
                        src_file=path,
                        dst_file=dst,
                        additional_config=MediaAdditionalConfig(start_time=start_s, end_time=end_s)
                    )
                    self._enqueue_media_task("video", "mp4", task_item)
            return
        if format_name == "delogo":
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select Video for Delogo", "", "Media Files (*.mp4 *.mkv *.avi *.mov *.flv *.webm);;All Files (*.*)"
            )
            if path:
                delogo_dlg = DelogoDialog(path, default_output_dir=self.output_dir, parent=self)
                if delogo_dlg.exec():
                    task = delogo_dlg.get_task()
                    self._enqueue_media_task("tool", "delogo", task)
            return

        # 2. Specialized Tool: Mux
        if format_name == "video_joiner":
            # Offer user: Concat Joiner or Stream Muxer
            choice = QtWidgets.QMessageBox.question(
                self,
                "Video Joiner & Mux",
                "Would you like to combine separate video and audio streams (Mux),\n"
                "or concatenate multiple video clips sequentially (Joiner)?\n\n"
                "Click 'Yes' for Mux, 'No' for Concat Joiner.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel
            )
            if choice == QtWidgets.QMessageBox.StandardButton.Yes:
                mux_dlg = MuxDialog(default_output_dir=self.output_dir, parent=self)
                if mux_dlg.exec():
                    task = mux_dlg.get_mux_task()
                    self._enqueue_media_task("tool", "mux", task)
                return
            elif choice == QtWidgets.QMessageBox.StandardButton.Cancel:
                return

        # 3. Standard Category Selection Dialog (AddFilesDialog)
        dlg = AddFilesDialog(
            category=category,
            target_format=format_name,
            default_output_dir=self.output_dir,
            parent=self,
        )
        for path in initial_paths or []:
            dlg._append_file_item(path)
        if dlg.exec():
            if category in ("video", "audio", "tool", "rom"):
                tasks = dlg.get_tasks()
                for task_item in tasks:
                    self._enqueue_media_task(category, format_name, task_item)
            elif category == "picture":
                for item in dlg.file_items:
                    self._enqueue_picture_task(item["path"], format_name, dlg.image_config, dlg.chk_save_source.isChecked(), dlg.txt_output_dir.text().strip())
            elif category == "doc":
                if format_name == "pdf_joiner":
                    all_paths = [item["path"] for item in dlg.file_items]
                    if all_paths:
                        self._enqueue_pdf_joiner_task(all_paths, dlg.chk_save_source.isChecked(), dlg.txt_output_dir.text().strip())
                else:
                    for item in dlg.file_items:
                        self._enqueue_doc_task(item["path"], format_name, dlg.chk_save_source.isChecked(), dlg.txt_output_dir.text().strip())

            self._update_status_summary()

    def _on_files_dropped(self, paths: List[str]):
        if not paths:
            return
        ext = os.path.splitext(paths[0])[1].lower()
        if ext in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".wmv"):
            self._on_format_tile_clicked("video", "mp4", initial_paths=paths)

        elif ext in (".mp3", ".aac", ".wav", ".flac", ".wma", ".ogg", ".m4a"):
            self._on_format_tile_clicked("audio", "mp3", initial_paths=paths)
        elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".ico"):
            self._on_format_tile_clicked("picture", "jpg", initial_paths=paths)
        elif ext in (".pdf", ".docx", ".txt", ".md"):
            self._on_format_tile_clicked("doc", "pdf2docx", initial_paths=paths)
        else:
            self._on_format_tile_clicked("video", "mp4", initial_paths=paths)

    def _open_external_tool(self, name):
        if name == "download":
            QtWidgets.QMessageBox.information(self, "Video Downloader", "The downloader is not available yet.")
        else:
            QtWidgets.QMessageBox.information(self, APP_NAME, "This tool is not available yet.")

    def _open_media_utility(self, name):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Video", "", "Video (*.mp4 *.mkv *.mov *.avi *.webm *.ts)")
        if not path:
            return
        if name == "frames":
            fps, ok = QtWidgets.QInputDialog.getDouble(self, "Export Frames", "Frames per second", 1, 0.01, 60, 2)
            if not ok:
                return
            folder = available_output(os.path.join(self.output_dir, os.path.splitext(os.path.basename(path))[0] + "_frames"))
            os.makedirs(folder, exist_ok=True)
            task = ConvertTaskItem(path, os.path.join(folder, "frame_%06d.png"),
                output_arguments=["-an", "-c:v", "png", "-vf", f"fps={fps:g}"])
            self._enqueue_media_task("tool", "frames", task)
        elif name == "split":
            seconds, ok = QtWidgets.QInputDialog.getInt(self, "Splitter", "Seconds per segment", 60, 1, 86400)
            if not ok:
                return
            from transcodia_engine.models import VideoConfig, AudioConfig, VideoCodec, AudioCodec
            folder = available_output(os.path.join(self.output_dir, os.path.splitext(os.path.basename(path))[0] + "_parts"))
            os.makedirs(folder, exist_ok=True)
            task = ConvertTaskItem(path, os.path.join(folder, "part_%04d.mkv"),
                video_config=VideoConfig(codec=VideoCodec.COPY), audio_config=AudioConfig(codec=AudioCodec.COPY),
                output_arguments=["-f", "segment", "-segment_time", str(seconds), "-reset_timestamps", "1"])
            self._enqueue_media_task("tool", "split", task)
        self._update_status_summary()
    def _on_task_double_clicked(self, task_id: str):
        task_data = self.all_tasks.get(task_id)
        if not task_data:
            return

        if task_data["status"] == "failed" and task_data.get("error_message"):
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle(APP_NAME)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            dialog.setText(tr("Failed", self.language))
            row = self.task_table._task_row_map[task_id]
            cell = self.task_table.cellWidget(row, self.task_table.COL_PROGRESS)
            dialog.setInformativeText(cell.findChild(QtWidgets.QLabel, "taskDetails").text())
            dialog.setDetailedText(task_data["error_message"])
            dialog.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            dialog.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            dialog.exec()
            return

        dst = task_data["dst"]
        if task_data["status"] == "completed":
            target = dst if os.path.exists(dst) else (os.path.dirname(dst) if "%" in dst and os.path.isdir(os.path.dirname(dst)) else None)
            if target:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(target))
                return

        # Show media information
        src = task_data["src"]
        if os.path.exists(src):
            dlg = MediaDetailsDialog(src, ffmpeg_path=self.ffmpeg_path, parent=self)
            dlg.exec()

    def _enqueue_media_task(self, category: str, format_name: str, task_item: ConvertTaskItem, apply_preferences=True):
        task_item.dst_file = available_output(task_item.dst_file, [t["dst"] for t in self.all_tasks.values()])

        # Apply GPU acceleration preference if not manually customized
        if apply_preferences and task_item.video_config and task_item.video_config.codec in (VideoCodec.H264, VideoCodec.HEVC):
            if task_item.video_config.hw_accel == HardwareAccel.NONE:
                hw_pref = (self.preferred_hw or "auto").lower()
                if hw_pref == "nvenc":
                    task_item.video_config.hw_accel = HardwareAccel.NVENC
                elif hw_pref == "qsv":
                    task_item.video_config.hw_accel = HardwareAccel.QSV
                elif hw_pref == "amf":
                    task_item.video_config.hw_accel = HardwareAccel.AMF
                elif hw_pref == "mf":
                    task_item.video_config.hw_accel = HardwareAccel.MEDIA_FOUNDATION
                elif hw_pref == "auto" and hasattr(self, "_hardware_caps_dict"):
                    caps = self._hardware_caps_dict
                    suffix = "_hevc" if task_item.video_config.codec == VideoCodec.HEVC else ""
                    if caps.get("nvenc" + suffix):
                        task_item.video_config.hw_accel = HardwareAccel.NVENC
                    elif caps.get("qsv" + suffix):
                        task_item.video_config.hw_accel = HardwareAccel.QSV
                    elif caps.get("amf" + suffix):
                        task_item.video_config.hw_accel = HardwareAccel.AMF
                    elif caps.get("mf" + suffix):
                        task_item.video_config.hw_accel = HardwareAccel.MEDIA_FOUNDATION

        self.task_counter += 1
        t_id = f"task_{self.task_counter:04d}"

        probe = MediaProbe(self.ffmpeg_path)
        info = probe.probe(task_item.src_file)

        self.all_tasks[t_id] = {
            "id": t_id,
            "category": category,
            "format": format_name,
            "src": task_item.src_file,
            "dst": task_item.dst_file,
            "task_item": task_item,
            "duration": info.duration_seconds,
            "status": "pending",
        }

        self.task_table.add_task(t_id, task_item.src_file, format_name, task_item.dst_file)

    def _enqueue_picture_task(self, src_path: str, format_name: str, img_config: ImageConfig, save_source: bool, out_dir: str):
        self.task_counter += 1
        t_id = f"task_{self.task_counter:04d}"

        base = os.path.splitext(os.path.basename(src_path))[0]
        folder = os.path.dirname(src_path) if save_source else out_dir
        dst_path = os.path.join(folder, f"{base}.{format_name}")
        dst_path = available_output(dst_path, [t["dst"] for t in self.all_tasks.values()])

        self.all_tasks[t_id] = {
            "id": t_id,
            "category": "picture",
            "format": format_name,
            "src": src_path,
            "dst": dst_path,
            "img_config": deepcopy(img_config),
            "status": "pending",
        }

        self.task_table.add_task(t_id, src_path, format_name, dst_path)

    def _enqueue_doc_task(self, src_path: str, format_name: str, save_source: bool, out_dir: str):
        self.task_counter += 1
        t_id = f"task_{self.task_counter:04d}"

        base = os.path.splitext(os.path.basename(src_path))[0]
        folder = os.path.dirname(src_path) if save_source else out_dir

        ext_map = {
            "pdf2docx": ".docx",
            "docx2pdf": ".pdf",
            "pdf2xlsx": ".xlsx",
            "pdf2txt": ".txt",
            "pdf2html": ".html",
            "markitdown": ".md",
            "pdf_joiner": ".pdf",
        }
        dst_path = os.path.join(folder, f"{base}{ext_map.get(format_name, '.docx')}")
        dst_path = available_output(dst_path, [t["dst"] for t in self.all_tasks.values()])

        self.all_tasks[t_id] = {
            "id": t_id,
            "category": "doc",
            "format": format_name,
            "src": src_path,
            "dst": dst_path,
            "status": "pending",
        }

        self.task_table.add_task(t_id, src_path, format_name, dst_path)

    def _enqueue_pdf_joiner_task(self, src_paths: List[str], save_source: bool, out_dir: str, append_setting_name=False):
        if not src_paths:
            return
        self.task_counter += 1
        t_id = f"task_{self.task_counter:04d}"

        first = src_paths[0]
        base = os.path.splitext(os.path.basename(first))[0]
        folder = os.path.dirname(first) if save_source else out_dir
        suffix = "_PDF Joiner" if append_setting_name else ""
        dst_path = os.path.join(folder, f"Joined_{base}{suffix}.pdf")
        dst_path = available_output(dst_path, [t["dst"] for t in self.all_tasks.values()])

        self.all_tasks[t_id] = {
            "id": t_id,
            "category": "doc",
            "format": "pdf_joiner",
            "src": first,
            "additional_files": src_paths[1:],
            "dst": dst_path,
            "status": "pending",
        }

        label = f"{os.path.basename(first)} (+{len(src_paths)-1} files)" if len(src_paths) > 1 else os.path.basename(first)
        self.task_table.add_task(t_id, label, "PDF_JOIN", dst_path)

    def _start_conversion(self):
        if self.runner_thread and self.runner_thread.isRunning():
            if self.runner_thread.is_paused():
                self._resume_conversion()
            return

        pending = [t for t in self.all_tasks.values() if t["status"] in ("pending", "failed", "cancelled")]
        if not pending:
            QtWidgets.QMessageBox.information(self, "No Tasks", "No pending tasks to convert. Please add files first.")
            return

        self.btn_start.setEnabled(False)
        self.act_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.act_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.act_stop.setEnabled(True)

        self.runner_thread = ConversionRunnerThread(
            tasks=pending,
            max_concurrency=self.max_concurrency if self.chk_multithread.isChecked() else 1,
            ffmpeg_path=self.ffmpeg_path,
            parent=self,
        )
        self.runner_thread.task_started.connect(self._on_task_started)
        self.runner_thread.task_progress.connect(self._on_task_progress)
        self.runner_thread.task_completed.connect(self._on_task_completed)
        self.runner_thread.task_cancelled.connect(self._on_task_cancelled)
        self.runner_thread.batch_finished.connect(self._on_batch_finished)
        self.runner_thread.finished.connect(self._update_status_summary)
        self._elapsed_clock.start()
        self._elapsed_timer.start(1000)
        self.runner_thread.start()

    def _pause_conversion(self):
        if not self.runner_thread or not self.runner_thread.isRunning():
            return
        if self.runner_thread.is_paused():
            self._resume_conversion()
        else:
            self.runner_thread.pause()
            self.btn_pause.setText(" ▶ Resume ")
            self.act_pause.setText("▶ &Resume")
            for tid, t in self.all_tasks.items():
                if t["status"] == "running":
                    self.task_table.set_task_paused(tid)

    def _resume_conversion(self):
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.resume()
            self.btn_pause.setText(" ⏸ Pause ")
            self.act_pause.setText("⏸ &Pause")
            for tid, t in self.all_tasks.items():
                if t["status"] == "running":
                    self.task_table.set_task_resumed(tid)

    def _stop_conversion(self):
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.stop()
            self.runner_thread.wait(3000)
        self.btn_start.setEnabled(True)
        self.act_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.act_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.act_stop.setEnabled(False)
        self._update_status_summary()

    def _on_task_started(self, task_id: str):
        if task_id in self.all_tasks:
            self.all_tasks[task_id]["status"] = "running"
        self.task_table.set_task_started(task_id)
        self._update_status_summary()

    def _on_task_progress(self, task_id: str, pct: float, speed: float, cur_time: float):
        self.task_table.update_task_progress(task_id, pct, speed, cur_time)

    def _on_task_completed(self, task_id: str, success: bool, output_bytes: int, err_msg: str):
        if task_id in self.all_tasks:
            self.all_tasks[task_id]["status"] = "completed" if success else "failed"
            self.all_tasks[task_id]["error_message"] = err_msg
        self.task_table.set_task_completed(task_id, success, output_bytes, err_msg)
        self._update_status_summary()

    def _on_task_cancelled(self, task_id: str):
        if task_id in self.all_tasks:
            self.all_tasks[task_id]["status"] = "cancelled"
        self.task_table.set_task_cancelled(task_id)
        self._update_status_summary()

    def _on_batch_finished(self):
        self._elapsed_timer.stop()
        self._update_elapsed()
        self.btn_start.setEnabled(True)
        self.act_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.act_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.act_stop.setEnabled(False)

        self._update_status_summary()
        if self.chk_shutdown.isChecked():
            answer = QtWidgets.QMessageBox.question(self, tr("After Converting: Shut down computer", self.language),
                "تم الانتهاء. هل تريد إيقاف تشغيل الكمبيوتر الآن؟" if self.language == "ar" else "Conversion finished. Shut down this computer now?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer == QtWidgets.QMessageBox.StandardButton.Yes and sys.platform == "win32":
                subprocess.Popen(["shutdown", "/s", "/t", "60"])
        action = self.combo_after_done.currentText()
        if action == "Open output folder":
            self._open_output_folder()
        elif action == "Play alert sound" or self.play_sound:
            QtWidgets.QApplication.beep()

    def _update_status_summary(self):
        total = len(self.all_tasks)
        completed = sum(1 for t in self.all_tasks.values() if t["status"] == "completed")
        running = sum(1 for t in self.all_tasks.values() if t["status"] == "running")
        status_txt = f"Tasks: {total} | Completed: {completed}"
        if running > 0:
            status_txt += f" | Converting: {running}"
        self.lbl_status_summary.setText(status_txt)
        self.task_table.setToolTip(status_txt)
        active = bool(self.runner_thread and self.runner_thread.isRunning())
        self.btn_start.setEnabled(not active and any(t["status"] in ("pending", "failed", "cancelled") for t in self.all_tasks.values()))
        self.act_start.setEnabled(self.btn_start.isEnabled())
        self.btn_remove.setEnabled(bool(self.all_tasks) and not active)
        self.btn_clear.setEnabled(bool(self.all_tasks) and not active)

    def _delete_selected_tasks(self):
        if self.runner_thread and self.runner_thread.isRunning():
            return
        selected_ids = self.task_table.get_selected_task_ids()
        for t_id in selected_ids:
            if t_id in self.all_tasks:
                del self.all_tasks[t_id]

        self.task_table.remove_tasks(selected_ids)
        self._update_status_summary()

    def _reset_selected_tasks(self):
        if self.runner_thread and self.runner_thread.isRunning():
            return
        selected_ids = self.task_table.get_selected_task_ids()
        for t_id in selected_ids:
            if t_id in self.all_tasks:
                self.all_tasks[t_id]["status"] = "pending"
                self.task_table.reset_task(t_id)
        self._update_status_summary()

    def _clear_all_tasks(self):
        if self.runner_thread and self.runner_thread.isRunning():
            return
        self.task_table.clear_tasks()
        self.all_tasks.clear()
        self._update_status_summary()

    def _save_task_list(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Task List", "", "Transcodia Task List (*.tctask *.json);;All Files (*.*)"
        )
        if not path:
            return

        export_data = []
        for tid, t in self.all_tasks.items():
            cat = t.get("category", "video")
            entry: Dict[str, Any] = {
                "id": tid,
                "category": cat,
                "format": t["format"],
                "src": t["src"],
                "dst": t["dst"],
            }
            if "task_item" in t and t["task_item"]:
                entry["task_item"] = t["task_item"].to_dict()
            elif cat == "picture" and "img_config" in t:
                cfg = t["img_config"]
                entry["img_config"] = {
                    "width": getattr(cfg, "width", None),
                    "height": getattr(cfg, "height", None),
                    "quality": getattr(cfg, "quality", 85),
                    "keep_aspect_ratio": getattr(cfg, "keep_aspect_ratio", True),
                    "rotate_angle": getattr(cfg, "rotate_angle", 0),
                    "flip_h": getattr(cfg, "flip_h", False),
                    "flip_v": getattr(cfg, "flip_v", False),
                }
            elif cat == "doc" and t.get("format") == "pdf_joiner":
                entry["additional_files"] = list(t.get("additional_files", []))

            export_data.append(entry)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            QtWidgets.QMessageBox.information(self, "Saved", f"Task list successfully saved to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save task list: {e}")

    def _load_task_list(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Task List", "", "Transcodia Task List (*.tctask *.json);;All Files (*.*)"
        )
        if not path or not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
            if not isinstance(import_data, list):
                raise ValueError("A task list must contain an array of jobs.")
            # Validate every job first; a bad later entry must not leave a partial import.
            for item in import_data:
                if not isinstance(item, dict) or not item.get("src") or not item.get("dst"):
                    raise ValueError("Each job needs a source and destination.")
                if item.get("category", "video") not in ("video", "audio", "tool", "picture", "doc"):
                    raise ValueError("Unsupported task category.")
                inputs = [item["src"]] + item.get("additional_files", [])
                if item.get("task_item"):
                    restored = ConvertTaskItem.from_dict(item["task_item"])
                    inputs += [restored.src_file] + restored.additional_input_files
                if any(not os.path.isfile(source) for source in inputs):
                    raise ValueError("A task input is missing; the queue was not imported.")
            for item in import_data:
                cat = item.get("category", "video")
                fmt = item.get("format", "mp4")
                src = item.get("src", "")
                dst = item.get("dst", "")
                if not os.path.exists(src):
                    continue

                if "task_item" in item and item["task_item"]:
                    task_item = ConvertTaskItem.from_dict(item["task_item"])
                    self._enqueue_media_task(cat, fmt, task_item, apply_preferences=False)
                elif cat == "picture":
                    img_cfg_data = item.get("img_config", {})
                    img_cfg = ImageConfig(
                        width=img_cfg_data.get("width"),
                        height=img_cfg_data.get("height"),
                        quality=img_cfg_data.get("quality", 85),
                        keep_aspect_ratio=img_cfg_data.get("keep_aspect_ratio", True),
                        rotate_angle=img_cfg_data.get("rotate_angle", 0),
                        flip_h=img_cfg_data.get("flip_h", False),
                        flip_v=img_cfg_data.get("flip_v", False),
                    )
                    self._enqueue_picture_task(src, fmt, img_cfg, False, os.path.dirname(dst))
                elif cat == "doc":
                    if fmt == "pdf_joiner":
                        all_inputs = [src] + item.get("additional_files", [])
                        self._enqueue_pdf_joiner_task(all_inputs, False, os.path.dirname(dst))
                    else:
                        self._enqueue_doc_task(src, fmt, False, os.path.dirname(dst))
                else:
                    task_item = ConvertTaskItem(src_file=src, dst_file=dst)
                    self._enqueue_media_task(cat, fmt, task_item)

                restored_id = f"task_{self.task_counter:04d}"
                restored_task = self.all_tasks[restored_id]
                destination = available_output(dst, [t["dst"] for tid, t in self.all_tasks.items() if tid != restored_id])
                restored_task["dst"] = destination
                if restored_task.get("task_item"):
                    restored_task["task_item"].dst_file = destination
                self.task_table.set_task_destination(restored_id, destination)

            self._update_status_summary()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load task list: {e}")

    def _change_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_dir)
        if folder:
            self.output_dir = folder
            self.txt_bottom_output.setText(folder)

    def _open_output_folder(self):
        if os.path.exists(self.output_dir):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.output_dir))
        else:
            QtWidgets.QMessageBox.warning(self, "Folder Not Found", f"The directory does not exist:\n{self.output_dir}")

    def _open_options(self):
        dlg = OptionsDialog(
            default_output_dir=self.output_dir,
            max_concurrency=self.max_concurrency,
            hw_accel=self.preferred_hw,
            play_sound=self.play_sound,
            parent=self,
        )
        if dlg.exec():
            self.output_dir = dlg.output_dir
            self.txt_bottom_output.setText(self.output_dir)
            self.max_concurrency = dlg.max_concurrency
            self.preferred_hw = dlg.hw_accel
            self.play_sound = dlg.play_sound

    def _show_table_context_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        act_open_file = menu.addAction("▶ Play / View Output File")
        act_open_dir = menu.addAction("📁 Open Containing Folder")
        act_info = menu.addAction("View media details")
        act_clip = menu.addAction("✂ Fast Clip / Set Range")
        menu.addSeparator()
        act_reset = menu.addAction("🔄 Reset Task State")
        act_remove = menu.addAction("🗑 Remove Task")
        menu.addSeparator()
        act_clear = menu.addAction("🧹 Clear All Tasks")

        action = menu.exec(self.task_table.mapToGlobal(pos))
        selected_ids = self.task_table.get_selected_task_ids()
        if not selected_ids:
            return
        t_id = selected_ids[0]
        task_data = self.all_tasks.get(t_id)
        if not task_data:
            return

        if action == act_open_file:
            dst = task_data["dst"]
            target = dst if os.path.exists(dst) else (os.path.dirname(dst) if "%" in dst and os.path.isdir(os.path.dirname(dst)) else None)
            if target:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(target))
            else:
                QtWidgets.QMessageBox.information(self, "File Not Found", f"Output file does not exist yet:\n{dst}")
        elif action == act_open_dir:
            dst = task_data["dst"]
            folder = os.path.dirname(dst)
            if os.path.exists(folder):
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
        elif action == act_info:
            src = task_data["src"]
            if os.path.exists(src):
                dlg = MediaDetailsDialog(src, ffmpeg_path=self.ffmpeg_path, parent=self)
                dlg.exec()
        elif action == act_clip:
            src = task_data["src"]
            if os.path.exists(src):
                dlg = ClipDialog(src, parent=self)
                if dlg.exec():
                    s_in, s_out = dlg.get_range()
                    if task_data.get("task_item"):
                        task_data["task_item"].additional_config = MediaAdditionalConfig(start_time=s_in, end_time=s_out)
        elif action == act_reset:
            self._reset_selected_tasks()
        elif action == act_remove:
            self._delete_selected_tasks()
        elif action == act_clear:
            self._clear_all_tasks()

    def _show_about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            "About Transcodia",
            f"<h3>Transcodia {APP_VERSION}</h3>"
            "<p>Python/Qt conversion workspace for video, audio, pictures and documents.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Video, audio, picture and document conversion</li>"
            "<li>Custom Arabic/English workspace and generated interface artwork</li>"
            "<li>Hardware acceleration (NVENC, QSV, AMF, Windows Media Foundation)</li>"
            "<li>Fast Concat Video and Audio Joiner & Stream Muxer</li>"
            "<li>Fast Clip / Set Range trimming editor</li>"
            "<li>Subtitle styling and watermark overlay injection</li>"
            "<li>Detailed media stream inspection</li>"
            "<li>Five Transcodia workspace palettes</li>"
            "<li>Multi-task async worker queue with live progress bars and Pause/Resume</li>"
            "</ul>"
        )
