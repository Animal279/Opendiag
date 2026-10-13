"""Screenshot-based command editor. Requests are UI previews until a Port exists."""

from PySide6.QtCore import QItemSelectionModel, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
    QFrame, QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.ui.controls import AddressingSelector, ToggleSwitch
from src.ports.model_types import parse_hex
from src.ui.theme import COLORS, METRICS, SPACE, apply_table_style, data_font, icon


class TextTransferDialog(QDialog):
    """Clipboard transfer makes the limited preview format explicit; no file IO."""

    imported = Signal(object)

    def __init__(self, title: str, text: str = "", *, importing: bool = False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.resize(630, 410)
        self.importing = importing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([SPACE["xl"]] * 4))
        layout.setSpacing(SPACE["md"])
        description = QLabel(
            "粘贴指令，每行一条 hex。校验全部通过后追加到当前列表。"
            if importing else "可复制当前内容。原版文件格式与文件导入 / 保存将在业务接入时补齐。"
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        layout.addWidget(description)
        self.editor = QPlainTextEdit(text)
        self.editor.setObjectName("transferEditor")
        self.editor.setProperty("data", True)
        self.editor.setFont(data_font())
        self.editor.setReadOnly(not importing)
        self.editor.setPlaceholderText("10 03\n3E 80")
        layout.addWidget(self.editor, 1)
        self.error_label = QLabel()
        self.error_label.setObjectName("validationError")
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("关闭" if not importing else "取消")
        action = buttons.addButton("导入到列表" if importing else "复制全部", QDialogButtonBox.ButtonRole.ActionRole)
        action.setProperty("role", "primary")
        action.clicked.connect(self._transfer)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @Slot()
    def _transfer(self) -> None:
        text = self.editor.toPlainText()
        if not self.importing:
            QApplication.clipboard().setText(text)
            self.error_label.setText("已复制到剪贴板。")
            return
        result = []
        try:
            for number, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    try:
                        result.append(parse_hex(line))
                    except ValueError as error:
                        raise ValueError(f"第 {number} 行：{error}") from error
            if not result:
                raise ValueError("没有可导入的指令。")
        except ValueError as error:
            self.error_label.setText(str(error))
            return
        self.imported.emit(tuple(result))
        self.accept()


class CommandEditor(QWidget):
    feedback = Signal(str, str)
    preview_requested = Signal(bytes, bool)
    request_requested = Signal(bytes, bool)
    keep_alive_requested = Signal(bool)

    def __init__(self, *, demo: bool = False, parent=None):
        super().__init__(parent)
        self.demo = demo
        self._can_preview = False
        self._connection_ready = False
        self._editing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([SPACE["lg"]] * 4))
        layout.setSpacing(SPACE["sm"])
        heading = QHBoxLayout()
        title = QLabel("报文构造")
        title.setObjectName("sectionTitle")
        heading.addWidget(title)
        heading.addStretch()
        hint = QLabel("Ctrl+Enter 发送    Shift+Enter 添加到列表")
        hint.setObjectName("muted")
        heading.addWidget(hint)
        layout.addLayout(heading)
        input_row = QHBoxLayout()
        input_row.setSpacing(SPACE["sm"])
        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setAccessibleName("UDS 十六进制指令")
        self.command_input.setProperty("data", True)
        self.command_input.setProperty("large", True)
        self.command_input.setFont(data_font(15))
        self.command_input.setFixedHeight(METRICS["input"])
        self.command_input.setPlaceholderText("输入 UDS 字节，例如 10 03")
        self.command_input.setMaxLength(16384)
        input_row.addWidget(self.command_input, 1)
        self.send_button = QPushButton("演示发送" if demo else "发送")
        self.send_button.setObjectName("sendCommand")
        self.send_button.setIcon(icon("send", COLORS["surface"]))
        self.send_button.setProperty("role", "primary")
        self.send_button.setProperty("large", True)
        self.send_button.setFixedHeight(METRICS["input"])
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_current)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)

        tools = QHBoxLayout()
        tools.setSpacing(SPACE["sm"])
        self.add_button = QPushButton("添加到列表")
        self.add_button.setObjectName("addCommand")
        self.add_button.clicked.connect(self.add_current)
        tools.addWidget(self.add_button)
        self.dll_button = QPushButton("加载 DLL")
        self.dll_button.setEnabled(False)
        self.dll_button.setToolTip("真实安全访问 Port、DLL 和调用契约尚未接入")
        tools.addWidget(self.dll_button)
        dll_state = QLabel("未加载安全算法")
        dll_state.setObjectName("muted")
        tools.addWidget(dll_state)
        tools.addStretch()
        self.addressing_selector = AddressingSelector()
        self.addressing_selector.setToolTip("寻址方式仅用于当前指令预览；不会发出报文")
        # Preserve the functional bool API used by command storage/preview callers.
        self.addressing_button = self.addressing_selector.functional_button
        tools.addWidget(self.addressing_selector)
        tools.addSpacing(SPACE["sm"])
        self.keep_alive_button = ToggleSwitch()
        self.keep_alive_button.setToolTip("仅预览开关状态；尚未启动 TesterPresent 保活线程")
        self.keep_alive_button.toggled.connect(self._keep_alive_changed)
        self.keep_alive_button.setEnabled(demo)
        tools.addWidget(self.keep_alive_button)
        layout.addLayout(tools)
        self.error_label = QLabel()
        self.error_label.setObjectName("validationError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("commandTable")
        self.table.setHorizontalHeaderLabels(("选中", "序号", "指令", "安全访问", "功能寻址", "状态"))
        self.table.horizontalHeaderItem(3).setToolTip("Security Access")
        self.table.horizontalHeaderItem(4).setToolTip("Functional Address")
        self.table.verticalHeader().hide()
        apply_table_style(self.table, data_columns=(2,))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setMinimumHeight(METRICS["header"] + 2 * METRICS["row"])
        header = self.table.horizontalHeader()
        for column, width in ((0, 48), (1, 48), (3, 96), (4, 96), (5, 84)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._item_changed)
        layout.addWidget(self.table, 1)
        self.empty_label = QLabel("暂无指令 · 在上方输入 hex，按 Shift+Enter 添加")
        self.empty_label.setObjectName("muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        actions = QHBoxLayout()
        actions.setSpacing(SPACE["xs"])
        self.action_buttons = {}
        for name, callback in (("导入", self.import_commands), ("导出", self.export_commands),
                               ("上移", self.move_up), ("下移", self.move_down),
                               ("全选", self.select_all), ("删除", self.remove_selected), ("清空", self.clear_commands)):
            if name in ("上移", "删除"):
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.VLine)
                divider.setObjectName("toolbarDivider")
                divider.setFixedHeight(16)
                actions.addSpacing(SPACE["sm"])
                actions.addWidget(divider)
                actions.addSpacing(SPACE["sm"])
            button = QPushButton(name)
            button.setProperty("role", "danger" if name in ("删除", "清空") else
                               ("quiet" if name in ("上移", "下移", "全选") else "secondary"))
            button.clicked.connect(callback)
            self.action_buttons[name] = button
            actions.addWidget(button)
        actions.addStretch()
        self.count_label = QLabel("0 条指令")
        self.count_label.setObjectName("muted")
        actions.addWidget(self.count_label)
        self.batch_button = QPushButton("批量演示" if demo else "批量发送")
        self.batch_button.setObjectName("batchSend")
        self.batch_button.setEnabled(False)
        self.batch_button.clicked.connect(self.send_checked)
        actions.addWidget(self.batch_button)
        layout.addLayout(actions)
        for key, callback in (("Ctrl+Return", self.send_current), ("Ctrl+Enter", self.send_current),
                              ("Shift+Return", self.add_current), ("Shift+Enter", self.add_current)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        self._refresh()
        if demo:
            self.add_payloads((bytes.fromhex("10 03"), bytes.fromhex("3E 80"), bytes.fromhex("19 02 FF")))
            self.command_input.setText("10 03")

    def _error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    @Slot()
    def add_current(self) -> None:
        try:
            payload = parse_hex(self.command_input.text())
        except ValueError as error:
            self._error(str(error))
            return
        self._clear_error()
        self.add_payloads((payload,))
        self.feedback.emit("INFO", "已添加 1 条指令到当前窗口列表。")

    @Slot(object)
    def add_payloads(self, payloads) -> None:
        self._editing = True
        try:
            for payload in payloads:
                row = self.table.rowCount()
                self.table.insertRow(row)
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                check.setCheckState(Qt.CheckState.Checked)
                self.table.setItem(row, 0, check)
                sequence = QTableWidgetItem(str(row + 1))
                sequence.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                sequence.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, sequence)
                command = QTableWidgetItem(payload.hex(" ").upper())
                command.setData(Qt.ItemDataRole.UserRole, payload)
                command.setToolTip("双击或按 F2 编辑指令；仅在当前窗口保留")
                self.table.setItem(row, 2, command)
                security = QTableWidgetItem("未接入")
                security.setFlags(Qt.ItemFlag.ItemIsSelectable)
                security.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                security.setToolTip("真实安全算法尚未接入；不会计算 seed/key")
                self.table.setItem(row, 3, security)
                functional = QTableWidgetItem()
                functional.setFlags(check.flags())
                functional.setCheckState(self.addressing_button.isChecked() and Qt.CheckState.Checked or Qt.CheckState.Unchecked)
                self.table.setItem(row, 4, functional)
                status = QTableWidgetItem("待演示" if self.demo else "待发送")
                status.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, 5, status)
        finally:
            self._editing = False
        self._refresh()

    @Slot(QTableWidgetItem)
    def _item_changed(self, item) -> None:
        if self._editing:
            return
        if item.column() == 2:
            self._editing = True
            try:
                try:
                    payload = parse_hex(item.text())
                except ValueError as error:
                    payload = item.data(Qt.ItemDataRole.UserRole)
                    self._error(str(error))
                else:
                    item.setData(Qt.ItemDataRole.UserRole, payload)
                    self.table.item(item.row(), 5).setText("待演示" if self.demo else "待发送")
                    self._clear_error()
                item.setText(payload.hex(" ").upper())
            finally:
                self._editing = False
        self._refresh()

    def _refresh(self) -> None:
        count = self.table.rowCount()
        self.empty_label.setVisible(count == 0)
        self.count_label.setText(f"{count} 条指令")
        for name in ("导出", "上移", "下移", "删除", "全选", "清空"):
            self.action_buttons[name].setEnabled(count > 0)
        self.batch_button.setEnabled(self._can_preview and any(
            self.table.item(row, 0).checkState() == Qt.CheckState.Checked for row in range(count)
        ))

    def set_preview_connection(self, connected: bool) -> None:
        self._can_preview = connected and self.demo
        self.send_button.setEnabled(self._can_preview)
        self.send_button.setToolTip("仅生成本地请求预览，无网络 IO" if self._can_preview else
                                    ("请先点击顶部演示连接" if self.demo else "诊断传输 Port 尚未接入"))
        self._refresh()

    def set_connection_ready(self, ready: bool) -> None:
        if self.demo:
            return
        self._connection_ready = ready
        self.send_button.setEnabled(ready)
        self.send_button.setToolTip("提交 UDS 请求；通信日志分别记录写出和回应" if ready else "请加载项目并完成路由激活")
        self.keep_alive_button.setEnabled(ready)
        self.keep_alive_button.setToolTip("功能寻址 3E 80，间隔取当前连接参数")
        self.addressing_selector.setToolTip("本次 UDS 请求的物理/功能寻址")
        if not ready:
            self.keep_alive_button.blockSignals(True)
            self.keep_alive_button.setChecked(False)
            self.keep_alive_button.blockSignals(False)
        self.batch_button.setToolTip("批量执行器尚未接入")

    @Slot()
    def send_current(self) -> None:
        if not (self._can_preview if self.demo else self._connection_ready):
            self._error("请先建立演示连接。" if self.demo else "请先加载项目并完成路由激活。")
            return
        try:
            payload = parse_hex(self.command_input.text())
        except ValueError as error:
            self._error(str(error))
            return
        self._clear_error()
        signal = self.preview_requested if self.demo else self.request_requested
        signal.emit(payload, self.addressing_button.isChecked())

    @Slot()
    def send_checked(self) -> None:
        if not self._can_preview:
            return
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                self.preview_requested.emit(self.table.item(row, 2).data(Qt.ItemDataRole.UserRole),
                                            self.table.item(row, 4).checkState() == Qt.CheckState.Checked)
                self.table.item(row, 5).setText("已预览")

    def _selected_rows(self) -> list[int]:
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        if not rows:
            rows = {row for row in range(self.table.rowCount())
                    if self.table.item(row, 0).checkState() == Qt.CheckState.Checked}
        return sorted(rows)

    @Slot()
    def remove_selected(self) -> None:
        for row in reversed(self._selected_rows()):
            self.table.removeRow(row)
        self._renumber()

    @Slot()
    def clear_commands(self) -> None:
        self.table.setRowCount(0)
        self._refresh()

    @Slot()
    def select_all(self) -> None:
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

    def _move(self, direction: int) -> None:
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1:
            self._error("请在表格中选中一行后移动。")
            return
        row = rows[0].row()
        target = row + direction
        if not 0 <= target < self.table.rowCount():
            return
        self._editing = True
        try:
            for col in range(self.table.columnCount()):
                first = self.table.takeItem(row, col)
                second = self.table.takeItem(target, col)
                self.table.setItem(row, col, second)
                self.table.setItem(target, col, first)
            self.table.setCurrentCell(target, 0, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        finally:
            self._editing = False
        self._clear_error()
        self._renumber()

    def _renumber(self) -> None:
        self._editing = True
        try:
            for row in range(self.table.rowCount()):
                self.table.item(row, 1).setText(str(row + 1))
        finally:
            self._editing = False
        self._refresh()

    @Slot()
    def move_up(self) -> None:
        self._move(-1)

    @Slot()
    def move_down(self) -> None:
        self._move(1)

    @Slot()
    def import_commands(self) -> None:
        dialog = TextTransferDialog("导入指令 · 文本预览", importing=True, parent=self)
        dialog.imported.connect(self.add_payloads)
        dialog.open()

    @Slot()
    def export_commands(self) -> None:
        text = "\n".join(self.table.item(row, 2).text() for row in range(self.table.rowCount()))
        TextTransferDialog("导出指令 · 文本预览", text, parent=self).open()

    @Slot(bool)
    def _keep_alive_changed(self, enabled: bool) -> None:
        if self.demo:
            self.feedback.emit("INFO", "保持会话开关仅作界面预览，尚未发送保活报文。")
        else:
            self.keep_alive_requested.emit(enabled)
