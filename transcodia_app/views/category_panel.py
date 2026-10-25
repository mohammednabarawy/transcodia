"""Transcodia's navigation rail and two-column tool library."""
from PySide6 import QtCore, QtGui, QtWidgets
from transcodia_app.icons import icon
from transcodia_app.i18n import tr


class FormatTile(QtWidgets.QPushButton):
    def __init__(self, label, artwork, wide=False):
        super().__init__(label)
        self.setProperty("sourceText", label)
        self.setProperty("class", "format-tile")
        self.setIcon(icon(artwork))
        self.setMinimumSize(108, 82)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setFixedHeight(82)
        self.wide = wide
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        painter = QtWidgets.QStylePainter(self)
        option = QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        option.icon = QtGui.QIcon()
        painter.drawControl(QtWidgets.QStyle.ControlElement.CE_PushButton, option)
        area = QtCore.QRect(9, 6, self.width() - 18, 43)
        size = self.icon().actualSize(QtCore.QSize(40, 40))
        self.icon().paint(painter, QtWidgets.QStyle.alignedRect(self.layoutDirection(), QtCore.Qt.AlignmentFlag.AlignCenter, size, area))
        painter.drawText(QtCore.QRect(7, 49, self.width() - 14, 28),
                         QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap, self.text().replace("-> ", ""))


class CategoryHeader(QtWidgets.QToolButton):
    pass


class CategoryAccordion(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current = 0
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(14)
        rail = QtWidgets.QFrame()
        rail.setObjectName("navigationRail")
        rail.setFixedWidth(66)
        self._navigation = QtWidgets.QVBoxLayout(rail)
        self._navigation.setContentsMargins(7, 12, 7, 12)
        self._navigation.setSpacing(10)
        self._navigation.addStretch()
        self._layout.addWidget(rail)
        content = QtWidgets.QVBoxLayout()
        self._title = QtWidgets.QLabel()
        self._title.setObjectName("sectionTitle")
        content.addWidget(self._title)
        self._stack = QtWidgets.QStackedWidget()
        content.addWidget(self._stack, 1)
        self._layout.addLayout(content, 1)

    def addItem(self, page, artwork, title):
        index = len(self._items)
        header = CategoryHeader()
        header.setText(title)
        header.setToolTip(title)
        header.setAccessibleName(title)
        header.setProperty("class", "category-header")
        header.setIcon(artwork)
        header.setIconSize(QtCore.QSize(36, 36))
        header.setFixedSize(50, 50)
        header.setCheckable(True)
        header.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        header.clicked.connect(lambda: self.setCurrentIndex(index))
        self._navigation.insertWidget(index, header)
        self._stack.addWidget(page)
        page.setVisible(index == self._current)
        self._items.append((header, page))
        self.setCurrentIndex(self._current)

    def setCurrentIndex(self, index):
        if 0 <= index < len(self._items):
            self._current = index
            self._stack.setCurrentIndex(index)
            self._title.setText(self._items[index][0].text())
            for i, (button, page) in enumerate(self._items):
                button.setChecked(i == index)

    def currentIndex(self):
        return self._current

    def count(self):
        return len(self._items)

    def setItemText(self, index, text):
        self._items[index][0].setText(text)
        self._items[index][0].setToolTip(text)
        self._items[index][0].setAccessibleName(text)
        if index == self._current:
            self._title.setText(text)

    def itemText(self, index):
        return self._items[index][0].text()

    def widget(self, index):
        return self._items[index][1]


# label, dispatch category, format key, artwork, occupied columns
CATEGORIES = [
    ("Video", "video", [
        ("-> MP4", "video", "mp4", "mp4", 1), ("-> MKV", "video", "mkv", "mkv", 1),
        ("-> GIF", "video", "gif", "gif", 1), ("-> WebM", "video", "webm", "webm", 1),
        ("Video Joiner & Mux", "tool", "video_joiner", "join_video", 2),
        ("-> AVI FLV\nMOV Etc...", "tool", "other_video", "other_video", 1),
        ("Splitter", "tool", "split", "split", 1), ("Clip", "tool", "clip", "clip", 1),
        ("Fast Clip", "tool", "clip", "fast_clip", 1), ("Delogo", "tool", "delogo", "delogo", 1),
        ("Export Frames", "tool", "frames", "frames", 1), ("Screen Recorder", "external", "recorder", "recorder", 1),
        ("Media\nPlayer", "external", "player", "player", 1), ("Video Downloader", "external", "download", "download", 1),
    ]),
    ("Audio", "audio", [("-> " + fmt.upper(), "audio", fmt, fmt, 1) for fmt in ("mp3", "wma", "flac", "aac", "wav", "m4a", "ogg", "m4r", "ac3")] + [
        ("Audio Joiner & Mix", "tool", "audio_joiner", "audio_join", 2)]),
    ("Picture", "picture", [("-> " + fmt.upper(), "picture", fmt, fmt, 1) for fmt in ("webp", "jpg", "png", "ico", "bmp", "gif", "tiff", "tga")] + [
        ("Batch Resize & Transform", "picture", "batch_resize", "picture", 2)]),
    ("Document", "document", [
        ("PDF -> DOCX", "doc", "pdf2docx", "pdf2docx", 1), ("DOCX -> PDF", "doc", "docx2pdf", "docx2pdf", 1),
        ("PDF -> XLSX", "doc", "pdf2xlsx", "pdf2xlsx", 1), ("PDF -> TXT", "doc", "pdf2txt", "pdf2txt", 1),
        ("PDF -> HTML", "doc", "pdf2html", "pdf2html", 1), ("PDF Joiner", "doc", "pdf_joiner", "pdf_joiner", 1),
        ("Document -> Markdown", "doc", "markitdown", "markitdown", 2),
    ]),
    ("ROM Device / DVD / CD / ISO", "disc", [
        ("DVD to Video File", "rom", "dvd2video", "dvd2video", 2), ("Music CD to Audio File", "rom", "cd2audio", "cd2audio", 2),
        ("DVD/CD to ISO/CSO", "rom", "disc2iso", "disc2iso", 2), ("ISO <-> CSO", "rom", "iso2cso", "iso2cso", 2),
    ]),
    ("Utilities", "utilities", [
        ("Media information", "tool", "info", "utilities", 2), ("Video Joiner & Mux", "tool", "video_joiner", "join_video", 2),
        ("Audio Joiner & Mix", "tool", "audio_joiner", "audio_join", 2), ("PDF Joiner", "doc", "pdf_joiner", "pdf_joiner", 2),
    ]),
]


class CategoryPanel(QtWidgets.QWidget):
    format_selected = QtCore.Signal(str, str)

    def __init__(self, parent=None, language="ar"):
        super().__init__(parent)
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        self.toolbox = CategoryAccordion(self)
        self.toolbox.setObjectName("categoryToolbox")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbox)
        for title, artwork, entries in CATEGORIES:
            scroll = QtWidgets.QScrollArea()
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            page = QtWidgets.QWidget()
            page.setObjectName("categoryPage")
            scroll.viewport().setObjectName("categoryViewport")
            grid = QtWidgets.QGridLayout(page)
            grid.setContentsMargins(0, 12, 6, 10)
            grid.setHorizontalSpacing(7)
            grid.setVerticalSpacing(7)
            row = column = 0
            for label, category, key, asset, span in entries:
                if column + span > 2:
                    row += 1
                    column = 0
                button = FormatTile(label, asset, span > 1)
                button.setText(tr(label, language))
                button.setAccessibleName(tr(label.replace("\n", " "), language))
                button.clicked.connect(lambda checked=False, c=category, f=key: self.format_selected.emit(c, f))
                grid.addWidget(button, row, column, 1, span)
                column += span
                if column == 2:
                    row += 1
                    column = 0
            for col in range(2):
                grid.setColumnStretch(col, 1)
            grid.setRowStretch(row + 1, 1)
            scroll.setWidget(page)
            self.toolbox.addItem(scroll, icon(artwork), tr(title, language))

    def set_language(self, language):
        for i, (title, _, _) in enumerate(CATEGORIES):
            self.toolbox.setItemText(i, tr(title, language))
        for button in self.findChildren(FormatTile):
            button.setText(tr(button.property("sourceText"), language))
