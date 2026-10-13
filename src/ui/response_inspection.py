"""DS-01 read-only views; the application inspector owns protocol interpretation."""

from datetime import datetime

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QHBoxLayout, QLabel,
                              QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from src.application.response_inspection import inspect_response, inspection_text
from src.ports.model_types import parse_hex
from src.ui.theme import METRICS, SPACE, data_font


class ResponsePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw = None
        self.inspection = None
        self._timing = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["sm"], SPACE["xs"], SPACE["sm"], SPACE["xs"])
        layout.setSpacing(SPACE["xs"])
        self.timing_label = QLabel()
        self.timing_label.setWordWrap(True)
        self.timing_label.setObjectName("muted")
        self.source_label = QLabel()
        self.source_label.setObjectName("muted")
        header = QHBoxLayout()
        labels = QVBoxLayout()
        labels.setSpacing(0)
        labels.addWidget(self.timing_label)
        labels.addWidget(self.source_label)
        header.addLayout(labels, 1)
        self.copy_button = QPushButton("复制完整 UDS")
        self.copy_button.setProperty("role", "quiet")
        self.copy_button.clicked.connect(self.copy_data)
        header.addWidget(self.copy_button)
        layout.addLayout(header)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(METRICS["row"])
        self.details.setAccessibleName("UDS 响应解析结果")
        layout.addWidget(self.details, 1)
        self.clear()

    def showEvent(self, event):
        # Tabs acquire their parent's stylesheet after construction. Measure
        # the final font/padding when shown, not the unparented default style.
        self.details.ensurePolished()
        margins = self.details.contentsMargins()
        self.details.setMinimumHeight(2 * self.details.fontMetrics().lineSpacing()
                                      + int(2 * self.details.document().documentMargin())
                                      + margins.top() + margins.bottom())
        self.layout().invalidate()
        self.setMinimumHeight(self.layout().minimumSize().height())
        super().showEvent(event)

    def show_response(self, data, timestamp):
        self.inspection = inspect_response(data)
        self.raw = data
        response = self.inspection.response
        if response and response.timing:
            self._timing = response.timing
        self.details.setPlainText(inspection_text(self.inspection))
        if self._timing:
            timing = self._timing
            self.timing_label.setText(f"上次有效会话 0x{timing.session:02X}：ECU 声明 P2 {timing.p2_ms} ms / P2* {timing.p2_star_ms} ms；仅显示")
        self.source_label.setText("接收 " + datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3])
        self.copy_button.setEnabled(True)

    @Slot()
    def clear(self):
        self.raw = self.inspection = self._timing = None
        self.details.setPlainText("尚无本连接的 UDS 响应。发送请求后在这里查看解析；原始通信日志持续保留。")
        self.timing_label.setText("ECU 会话时序：尚未取得；客户端等待策略保持现状")
        self.source_label.clear()
        self.copy_button.setEnabled(False)

    @Slot()
    def copy_data(self):
        if self.raw is not None:
            QApplication.clipboard().setText(self.raw.hex(" ").upper())


class ResponseInspectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("报文解析 · UDS 响应")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([SPACE["xl"]] * 4))
        layout.setSpacing(SPACE["md"])
        self.input_kind = QComboBox()
        self.input_kind.addItem("UDS 响应载荷", "uds")
        self.input_kind.addItem("完整 DoIP 诊断帧", "doip")
        self.input_kind.setAccessibleName("报文解析输入类型")
        layout.addWidget(self.input_kind)
        hint = QLabel("本地只读解析；不会发送。会话时序按 ISO 14229 2013+ 布局显示，不应用到客户端等待。")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.editor = QPlainTextEdit()
        self.editor.setProperty("data", True)
        self.editor.setFont(data_font())
        self.editor.setPlaceholderText("粘贴所选类型的完整十六进制响应")
        layout.addWidget(self.editor, 1)
        self.result_label = QLabel()
        self.result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.result_label)
        layout.addWidget(scroll, 1)
        close = QPushButton("关闭")
        close.clicked.connect(self.reject)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.inspection = None
        self.editor.textChanged.connect(self._update)
        self.input_kind.currentIndexChanged.connect(self._update)
        self._update()

    @Slot()
    def _update(self):
        self.inspection = None
        if not self.editor.toPlainText().strip():
            self.result_label.setText("等待输入")
            return
        try:
            data = parse_hex(self.editor.toPlainText())
        except ValueError as exc:
            self.result_label.setText(str(exc))
            return
        self.inspection = inspect_response(data, self.input_kind.currentData())
        self.result_label.setText(inspection_text(self.inspection))
