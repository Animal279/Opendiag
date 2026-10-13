"""Screenshot-based desktop shell with explicitly local UI demonstration mode."""

from collections import deque
from datetime import datetime

from PySide6.QtCore import QEvent, QPropertyAnimation, QSize, QTimer, Qt, Slot
from PySide6.QtGui import QColor, QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QFileDialog,
    QHeaderView, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSizeGrip, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from src.application.page_context import PageContext
from src.ports.events import LogEvent
from src.ui.command_editor import CommandEditor, TextTransferDialog, parse_hex
from src.ui.config_dialogs import ConnectionDialog, HardwareDialog
from src.ui.theme import COLORS, METRICS, SPACE, STYLESHEET, apply_table_style, data_font, icon
from src.ui.workspace_pages import create_workspace_page
from src.ui.diagnostic_controller import DiagnosticController
from src.ui.response_inspection import ResponseInspectorDialog, ResponsePanel


PAGE_DEFINITIONS = (
    ("UDS手动", "terminal"), ("UDS自动化", "play"), ("DoIP刷写", "flash"),
    ("DTC测试", "dtc"), ("DoIP手动", "terminal"), ("DoIP自动化", "play"),
)


class TitleBar(QFrame):
    def __init__(self, window: QMainWindow, version: str, demo: bool):
        super().__init__(window)
        self.window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(METRICS["title"])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], 0, SPACE["xs"], 0)
        layout.setSpacing(SPACE["sm"])
        logo = QLabel()
        logo.setPixmap(icon("hardware", COLORS["primary"]).pixmap(18, 18))
        layout.addWidget(logo)
        title = QLabel(f"OpenDiag v{version}")
        title.setObjectName("windowTitle")
        layout.addWidget(title)
        if demo:
            badge = QLabel("UI 演示 · 无硬件")
            badge.setObjectName("demoBadge")
            layout.addWidget(badge)
        layout.addStretch()
        self.help_button = QToolButton()
        self.help_button.setIcon(icon("help"))
        self.help_button.setToolTip("关于 OpenDiag")
        self.help_button.setAccessibleName("关于 OpenDiag")
        self.help_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.help_button)
        for text, tip, callback in (("−", "最小化", window.showMinimized),
                                    ("□", "最大化 / 还原", self.toggle_maximized),
                                    ("×", "关闭", window.close)):
            button = QToolButton()
            button.setText(text)
            button.setFixedSize(36, 28)
            button.setToolTip(tip)
            button.setAccessibleName(tip)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if text == "×":
                button.setObjectName("closeButton")
            button.clicked.connect(callback)
            layout.addWidget(button)

    @Slot()
    def toggle_maximized(self) -> None:
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.window.windowHandle():
            self.window.windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class CommunicationPanel(QWidget):
    """Owner-thread log view; retains full bytes when truncating table text."""

    def __init__(self, parent=None, *, log_export=None, event_bus=None):
        super().__init__(parent)
        self._export_port = log_export
        self._export_bus = event_bus
        self._export_task = None
        self.setObjectName("communicationPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.records: deque[LogEvent] = deque(maxlen=5000)
        self._dialogs = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["sm"], SPACE["lg"], SPACE["sm"])
        layout.setSpacing(SPACE["sm"])
        self.tabs = QTabWidget()
        self.tabs.setObjectName("logTabs")
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("communicationLog")
        self.table.setHorizontalHeaderLabels(("时间", "类型", "数据", "描述"))
        self.table.verticalHeader().hide()
        apply_table_style(self.table, data_columns=(0, 2))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 75)
        self.table.setColumnWidth(3, 350)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tabs.addTab(self.table, "通信日志")
        self.application_log = QPlainTextEdit()
        self.application_log.setReadOnly(True)
        self.application_log.document().setMaximumBlockCount(5000)
        self.tabs.addTab(self.application_log, "应用日志")
        self.response_panel = ResponsePanel()
        self.tabs.addTab(self.response_panel, "UDS 响应")
        self.debug_checkbox = QCheckBox("DEBUG")
        self.debug_checkbox.setToolTip("显示通信日志中的 DEBUG；应用日志仍只显示 WARN / ERROR")
        self.debug_checkbox.toggled.connect(self._rebuild)
        self.tabs.setCornerWidget(self.debug_checkbox)
        layout.addWidget(self.tabs, 1)
        footer = QHBoxLayout()
        footer.setSpacing(SPACE["sm"])
        self.count_label = QLabel("0 条日志")
        self.count_label.setObjectName("muted")
        footer.addWidget(self.count_label)
        hint = QLabel("选中日志可复制完整数据")
        hint.setObjectName("muted")
        footer.addWidget(hint)
        footer.addStretch()
        self.copy_button = QPushButton("复制数据")
        self.copy_button.setProperty("role", "quiet")
        self.copy_button.clicked.connect(self._copy_data)
        footer.addWidget(self.copy_button)
        self.save_button = QPushButton("保存日志")
        self.save_button.setToolTip("异步保存当前日志快照，保留完整字节" if log_export else "提供完整日志文本与复制")
        self.save_button.clicked.connect(self.export_logs)
        footer.addWidget(self.save_button)
        self.clear_button = QPushButton("清空日志")
        self.clear_button.setProperty("role", "danger")
        self.clear_button.clicked.connect(self.clear)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)
        self._update_count()

    def append(self, event: LogEvent) -> None:
        evicted = self.records[0] if len(self.records) == self.records.maxlen else None
        self.records.append(event)
        if evicted is not None and (evicted.level != "DEBUG" or self.debug_checkbox.isChecked()):
            self.table.removeRow(0)
        if event.level != "DEBUG" or self.debug_checkbox.isChecked():
            self._append_row(event)
        if event.level in ("WARN", "ERROR"):
            self.application_log.appendPlainText(f"[{event.level}] {event.description}")
        self._update_count()

    def _append_row(self, event: LogEvent) -> None:
        row = self.table.rowCount()
        bar = self.table.verticalScrollBar()
        follow = bar.value() == bar.maximum()
        self.table.insertRow(row)
        timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S.%f")[:-3]
        # Limit conversion itself, not just the resulting string: log subscribers
        # must stay lightweight even when a future transport supplies large data.
        shown = event.data[:171].hex(" ").upper() if event.data is not None else ""
        if event.data is not None and len(event.data) > 171:
            shown += " …"
        for col, text in enumerate((timestamp, event.level, shown, event.description)):
            item = QTableWidgetItem(text)
            if col == 1:
                item.setForeground(QColor({"TX": COLORS["primary"], "RX": COLORS["success"],
                                           "WARN": COLORS["warning"], "ERROR": COLORS["danger"]}
                                          .get(event.level, COLORS["muted"])))
            if col == 2:
                item.setData(Qt.ItemDataRole.UserRole, event.data)
                item.setToolTip("显示最多 512 个字符；复制数据保留完整字节")
            if col == 3:
                item.setToolTip(event.description)
            self.table.setItem(row, col, item)
        if follow:
            self.table.scrollToBottom()

    def _update_count(self) -> None:
        self.count_label.setText(f"{len(self.records)} 条日志")
        self.save_button.setEnabled(bool(self.records) and self._export_task is None)
        for button in (self.clear_button, self.copy_button):
            button.setEnabled(bool(self.records))

    @Slot()
    def _rebuild(self) -> None:
        self.table.setRowCount(0)
        for event in self.records:
            if event.level != "DEBUG" or self.debug_checkbox.isChecked():
                self._append_row(event)

    @Slot()
    def clear(self) -> None:
        self.records.clear()
        self.table.setRowCount(0)
        self.application_log.clear()
        self._update_count()

    @Slot()
    def _copy_data(self) -> None:
        from PySide6.QtWidgets import QApplication

        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        text = "\n".join((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or b"").hex(" ").upper()
                         for row in rows)
        if rows:
            QApplication.clipboard().setText(text)

    @Slot()
    def export_logs(self) -> None:
        if self._export_port is not None:
            if self._export_task is not None:
                self._export_busy()
                return
            dialog = QFileDialog(self, "保存通信日志")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilter("文本日志 (*.txt)")
            dialog.setDefaultSuffix("txt")
            dialog.fileSelected.connect(self._export_selected)
            self._dialogs.add(dialog)
            dialog.finished.connect(self._release_dialog)
            dialog.open()
            return
        text = "\n".join(
            f"{datetime.fromtimestamp(event.timestamp).isoformat(timespec='milliseconds')}\t{event.level}\t"
            f"{event.data.hex(' ').upper() if event.data is not None else ''}\t{event.description}"
            for event in self.records
        )
        dialog = TextTransferDialog("保存日志 · 文本预览", text, parent=self)
        self._dialogs.add(dialog)
        dialog.finished.connect(self._release_dialog)
        dialog.open()

    @Slot(str)
    def _export_selected(self, path):
        if self._export_task is None:
            self._export_task = self._export_port.export(tuple(self.records), path)
            self.save_button.setEnabled(False)
        else:
            self._export_busy()

    def _export_busy(self):
        if self._export_bus is not None:
            self._export_bus.publish(LogEvent("WARN", None, "正在导出日志，请等待本次任务完成"))

    def poll_export(self):
        if self._export_task is not None and self._export_task.done.is_set():
            task, self._export_task = self._export_task, None
            self._export_bus.publish(LogEvent("ERROR" if task.error else "INFO", None,
                f"日志导出失败：{task.error}" if task.error else f"日志已保存：{task.result}"))
            self._update_count()

    @Slot(int)
    def _release_dialog(self, _result) -> None:
        self._dialogs.discard(self.sender())


class BytePreviewDialog(ResponseInspectorDialog):
    """Keep the existing local-parser entry point and window ownership."""


class MainWindow(QMainWindow):
    def __init__(self, context: PageContext, *, ui_demo: bool = False):
        super().__init__()
        self._context = context
        self.ui_demo = ui_demo
        self._closing = False
        self._preview_connected = False
        self._connection_settings = {}
        self._hardware_settings = {}
        self._dialogs = set()
        self._collapsed = False
        self.diagnostic_controller = None
        self.setWindowTitle(f"OpenDiag v{context.version}" + (" · UI 演示（无硬件）" if ui_demo else ""))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(1440, 860)
        self.setMinimumSize(1080, 680)
        self.setStyleSheet(STYLESHEET)
        central = QFrame(self)
        central.setObjectName("windowFrame")
        central.setMouseTracking(True)
        central.installEventFilter(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 1, 5, 0)
        layout.setSpacing(0)
        self.title_bar = TitleBar(self, context.version, ui_demo)
        self.title_bar.setMouseTracking(True)
        self.title_bar.installEventFilter(self)
        self.title_bar.help_button.clicked.connect(self.show_about)
        layout.addWidget(self.title_bar)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(METRICS["sidebar"])
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(0, SPACE["sm"], 0, SPACE["sm"])
        side.setSpacing(SPACE["xs"])
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setAccessibleName("功能导航")
        self.navigation.setIconSize(QSize(19, 19))
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setSpacing(0)
        for title, symbol in PAGE_DEFINITIONS:
            item = QListWidgetItem(icon(symbol, COLORS["sidebar_text"]), title)
            item.setToolTip(title)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
            item.setSizeHint(QSize(160, METRICS["navigation"] + SPACE["xs"]))
            self.navigation.addItem(item)
        side.addWidget(self.navigation, 1)
        self.parse_button = QPushButton("报文解析")
        self.parse_button.setIcon(icon("parse", COLORS["sidebar_text"]))
        self.parse_button.setProperty("role", "nav")
        self.parse_button.setAccessibleName("报文解析")
        self.parse_button.setToolTip("本地解析 UDS 响应或完整 DoIP 诊断帧")
        self.parse_button.clicked.connect(self.show_byte_preview)
        side.addWidget(self.parse_button)
        self.capture_button = QPushButton("Wireshark录制")
        self.capture_button.setIcon(icon("capture", COLORS["sidebar_text"]))
        self.capture_button.setProperty("role", "nav")
        self.capture_button.setAccessibleName("Wireshark录制")
        self.capture_button.setToolTip("录制入口预览；TShark / PCAP 适配器尚未接入")
        self.capture_button.clicked.connect(self.show_capture)
        side.addWidget(self.capture_button)
        self.collapse_button = QPushButton("折叠 / 展开")
        self.collapse_button.setObjectName("collapseButton")
        self.collapse_button.setIcon(icon("collapse", COLORS["sidebar_text"]))
        self.collapse_button.setAccessibleName("折叠 / 展开导航")
        self.collapse_button.setToolTip("折叠 / 展开导航")
        self.collapse_button.clicked.connect(self.toggle_navigation)
        side.addWidget(self.collapse_button)
        content.addWidget(self.sidebar)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        bar = QFrame()
        bar.setObjectName("connectionBar")
        bar.setFixedHeight(METRICS["connection"])
        connection = QHBoxLayout(bar)
        connection.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        connection.setSpacing(SPACE["sm"])
        self.hardware_button = QPushButton("硬件配置")
        self.hardware_button.setIcon(icon("hardware"))
        self.hardware_button.clicked.connect(self.show_hardware_settings)
        connection.addWidget(self.hardware_button)
        self.settings_button = QPushButton("连接配置")
        self.settings_button.setIcon(icon("settings"))
        self.settings_button.clicked.connect(self.show_connection_settings)
        connection.addWidget(self.settings_button)
        self.project_button = QPushButton("项目…")
        self.project_button.setProperty("role", "secondary")
        self.project_button.setEnabled(not ui_demo and context.projects is not None)
        self.project_button.setToolTip("选择 config 目录中的项目，显式加载")
        connection.addWidget(self.project_button)
        self.connect_button = QPushButton("演示连接" if ui_demo else "连接")
        self.connect_button.setIcon(icon("socket", COLORS["primary"]))
        self.connect_button.setProperty("role", "connection")
        self.connect_button.setEnabled(ui_demo)
        self.connect_button.setToolTip("只切换本地演示状态，无网络或硬件连接" if ui_demo else "连接 Port 尚未接入")
        self.connect_button.clicked.connect(self.toggle_preview_connection)
        connection.addWidget(self.connect_button)
        connection.addStretch()
        self.project_label = QLabel("UI 演示 | DoIP" if ui_demo else "项目：未加载")
        self.project_label.setObjectName("projectBadge")
        connection.addWidget(self.project_label)
        self.connection_label = QLabel("● 演示未连接" if ui_demo else "连接：未连接")
        self.connection_label.setObjectName("connectionBadge")
        connection.addWidget(self.connection_label)
        right_layout.addWidget(bar)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        work = QVBoxLayout(workspace)
        self._work_layout = work
        work.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        work.setSpacing(SPACE["lg"])
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName("workspaceSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(METRICS["splitter"])
        self.pages = QStackedWidget()
        self.pages.setObjectName("workspacePages")
        self.pages.setAccessibleName("功能页面")
        self.command_editor = CommandEditor(demo=ui_demo)
        self.command_editor.feedback.connect(self._feedback)
        self.command_editor.preview_requested.connect(self._preview_request)
        self.pages.addWidget(self.command_editor)
        self.splitter.addWidget(self.pages)
        self.communication = CommunicationPanel(log_export=None if ui_demo else context.log_export, event_bus=context.event_bus)
        self.communication.setMinimumHeight(METRICS["log_min"])
        self.log_view = self.communication.application_log
        self.splitter.addWidget(self.communication)
        self.splitter.setSizes([380, 335])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        work.addWidget(self.splitter, 1)
        right_layout.addWidget(workspace, 1)
        content.addWidget(right, 1)
        layout.addLayout(content, 1)
        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage("UI 演示 · 所有操作在当前窗口预览 · 未初始化硬件" if ui_demo else
                                     "界面结构预览 · 诊断业务尚未接入 · 未初始化硬件")
        self.statusBar().addPermanentWidget(QSizeGrip(self))
        self.toast = QFrame(self)
        self.toast.setObjectName("toast")
        toast_layout = QHBoxLayout(self.toast)
        toast_layout.setContentsMargins(18, 10, 18, 10)
        self.toast_label = QLabel()
        toast_layout.addWidget(self.toast_label)
        self.toast_effect = QGraphicsOpacityEffect(self.toast)
        self.toast.setGraphicsEffect(self.toast_effect)
        self.toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(2000)
        self._toast_timer.timeout.connect(self._fade_toast)
        self._toast_animation = QPropertyAnimation(self.toast_effect, b"opacity", self)
        self._toast_animation.setDuration(500)
        self._toast_animation.finished.connect(self.toast.hide)
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self._select_page)
        self._next_page = 1
        self._page_timer = QTimer(self)
        self._page_timer.setInterval(0)
        self._page_timer.timeout.connect(self._load_next_page)
        self._page_timer.start()
        context.event_bus.subscribe(LogEvent, self._on_log)
        if not ui_demo and context.projects is not None and context.manual_diagnostic is not None:
            self.diagnostic_controller = DiagnosticController(context, self)
        if ui_demo:
            context.event_bus.publish(LogEvent(level="INFO", data=None,
                                               description="UI 演示已就绪；示例指令仅用于本地预览。"))

    @Slot()
    def _load_next_page(self) -> None:
        if self._closing or self._next_page >= len(PAGE_DEFINITIONS):
            self._page_timer.stop()
            return
        self.pages.addWidget(create_workspace_page(self._next_page))
        self._next_page += 1
        self._select_page(self.navigation.currentRow())
        if self._next_page == len(PAGE_DEFINITIONS):
            self._page_timer.stop()

    @Slot(int)
    def _select_page(self, row: int) -> None:
        if 0 <= row < self.pages.count():
            self.pages.setCurrentIndex(row)

    @Slot()
    def toggle_navigation(self) -> None:
        self._collapsed = not self._collapsed
        self.sidebar.setFixedWidth(METRICS["sidebar_collapsed"] if self._collapsed else METRICS["sidebar"])
        for index, (title, _) in enumerate(PAGE_DEFINITIONS):
            item = self.navigation.item(index)
            item.setText("" if self._collapsed else title)
            item.setSizeHint(QSize(42 if self._collapsed else 160, 48))
        for button, title in ((self.parse_button, "报文解析"), (self.capture_button, "Wireshark录制"),
                              (self.collapse_button, "折叠 / 展开")):
            button.setText("" if self._collapsed else title)

    @Slot()
    def toggle_preview_connection(self) -> None:
        if not self.ui_demo or self._closing:
            return
        self._preview_connected = not self._preview_connected
        self.connect_button.setText("演示断开" if self._preview_connected else "演示连接")
        self.connection_label.setText("● 演示已连接" if self._preview_connected else "● 演示未连接")
        self.connection_label.setProperty("connected", self._preview_connected)
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)
        self.command_editor.set_preview_connection(self._preview_connected)
        self._feedback("INFO", "[UI演示] 本地连接状态已切换；未创建 socket 或初始化硬件。")

    @Slot(str, str)
    def _feedback(self, level: str, description: str) -> None:
        if self._closing:
            return
        self._context.event_bus.publish(LogEvent(level=level, data=None, description=description))
        if level == "INFO":
            self._show_toast(description.replace("[UI演示] ", ""))

    @Slot(bytes, bool)
    def _preview_request(self, payload: bytes, functional: bool) -> None:
        if self.ui_demo and self._preview_connected and not self._closing:
            self._context.event_bus.publish(LogEvent(
                level="INFO", data=payload,
                description=f"[UI演示] 请求预览 · {'功能' if functional else '物理'}寻址；未发往 ECU。",
            ))
            self._show_toast("已生成请求预览 · 未发往 ECU")

    def _on_log(self, event: LogEvent) -> None:
        if not self._closing:
            self.communication.append(event)

    def _open_dialog(self, dialog: QDialog) -> None:
        self._dialogs.add(dialog)
        dialog.finished.connect(self._release_dialog)
        dialog.open()

    @Slot(int)
    def _release_dialog(self, _result) -> None:
        dialog = self.sender()
        self._dialogs.discard(dialog)
        if dialog is not None:
            dialog.deleteLater()

    @Slot()
    def show_connection_settings(self) -> None:
        if self.diagnostic_controller is not None:
            self.diagnostic_controller.show_config()
            return
        dialog = ConnectionDialog(self, self._connection_settings)
        dialog.accepted.connect(self._apply_connection_settings)
        self._open_dialog(dialog)

    @Slot()
    def _apply_connection_settings(self) -> None:
        self._connection_settings = self.sender().values
        transport = self._connection_settings["transport"]
        if self.ui_demo:
            self.project_label.setText(f"UI 演示 | {'DoIP' if transport == 'doip' else 'DoCAN'}")
        self._feedback("INFO", "连接参数已应用到界面预览；未保存文件或连接 ECU。")

    @Slot()
    def show_hardware_settings(self) -> None:
        dialog = HardwareDialog(self, self._hardware_settings)
        dialog.accepted.connect(self._apply_hardware_settings)
        self._open_dialog(dialog)

    @Slot()
    def _apply_hardware_settings(self) -> None:
        self._hardware_settings = self.sender().values
        self._feedback("INFO", "硬件参数已应用到界面预览；设备仍未初始化。")

    @Slot()
    def show_byte_preview(self) -> None:
        self._open_dialog(BytePreviewDialog(self))

    @Slot()
    def show_capture(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Wireshark录制 · 入口预览")
        dialog.resize(520, 240)
        layout = QVBoxLayout(dialog)
        title = QLabel("报文录制")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        notice = QLabel("TShark / PCAP 录制适配器尚未接入。真实网卡列表、录制状态和文件输出将在后续阶段实现。")
        notice.setWordWrap(True)
        notice.setObjectName("muted")
        layout.addWidget(notice)
        interface = QComboBox()
        interface.addItem("网卡：未检测")
        interface.setEnabled(False)
        layout.addWidget(interface)
        actions = QHBoxLayout()
        for title in ("开始录制", "停止录制"):
            button = QPushButton(title)
            button.setEnabled(False)
            button.setToolTip("录制适配器尚未接入")
            actions.addWidget(button)
        actions.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.reject)
        actions.addWidget(close)
        layout.addLayout(actions)
        self._open_dialog(dialog)

    @Slot()
    def show_about(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("关于 OpenDiag")
        dialog.setText(f"OpenDiag v{self._context.version}")
        dialog.setInformativeText("基于部分原界面截图重建的 UI 预览。\n诊断、刷写、安全访问和真实硬件尚未接入。")
        self._open_dialog(dialog)

    def _position_toast(self) -> None:
        self.toast.move(max(5, self.width() - self.toast.width() - 24), 92)

    def _show_toast(self, text: str) -> None:
        self._toast_timer.stop()
        self._toast_animation.stop()
        self.toast_effect.setOpacity(1.0)
        self.toast_label.setText(text)
        self.toast.adjustSize()
        self._position_toast()
        self.toast.show()
        self.toast.raise_()
        self._toast_timer.start()

    @Slot()
    def _fade_toast(self) -> None:
        self._toast_animation.setStartValue(1.0)
        self._toast_animation.setEndValue(0.0)
        self._toast_animation.start()

    def resizeEvent(self, event) -> None:
        if hasattr(self, "_work_layout"):
            margin = SPACE["lg"] if self.width() < 1200 else SPACE["xl"]
            self._work_layout.setContentsMargins(margin, SPACE["lg"], margin, SPACE["lg"])
        if hasattr(self, "toast"):
            self._position_toast()
        super().resizeEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.centralWidget(), getattr(self, "title_bar", None)) and event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            if self.isMaximized():
                return False
            point = self.mapFromGlobal(event.globalPosition().toPoint())
            edges = Qt.Edge(0)
            if point.x() < 5:
                edges |= Qt.Edge.LeftEdge
            if point.x() >= self.width() - 5:
                edges |= Qt.Edge.RightEdge
            if point.y() < 5:
                edges |= Qt.Edge.TopEdge
            if point.y() >= self.height() - 5:
                edges |= Qt.Edge.BottomEdge
            if event.type() == QEvent.Type.MouseMove:
                horizontal = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
                vertical = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
                if horizontal and vertical:
                    diagonal = bool(edges & Qt.Edge.LeftEdge) == bool(edges & Qt.Edge.TopEdge)
                    watched.setCursor(Qt.CursorShape.SizeFDiagCursor if diagonal else Qt.CursorShape.SizeBDiagCursor)
                elif horizontal:
                    watched.setCursor(Qt.CursorShape.SizeHorCursor)
                elif vertical:
                    watched.setCursor(Qt.CursorShape.SizeVerCursor)
                else:
                    watched.unsetCursor()
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and edges:
                handle = self.windowHandle()
                if handle:
                    return handle.startSystemResize(edges)
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        if self.diagnostic_controller is not None:
            self.diagnostic_controller.close()
        self._page_timer.stop()
        self._toast_timer.stop()
        self._toast_animation.stop()
        self.toast.hide()
        for dialog in self.findChildren(QDialog):
            dialog.reject()
        self._context.event_bus.unsubscribe(LogEvent, self._on_log)
        super().closeEvent(event)
