"""Editable secondary workspaces for the screenshot-based UI preview.

These pages keep the known business entry points visible. They do not load
project assets, execute scripts, talk to hardware, or fabricate ECU results.
All editable values are temporary UI drafts and are discarded on exit.
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import METRICS, SPACE, apply_table_style, data_font


def _label(text: str, *, muted: bool = False, name: str = "") -> QLabel:
    label = QLabel(text)
    if name or muted:
        label.setObjectName(name or "muted")
    return label


def _row() -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(SPACE["sm"])
    return layout


def _button(
    text: str,
    name: str,
    *,
    unavailable: str = "",
    role: str = "secondary",
) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.setProperty("role", role)
    button.setFixedHeight(METRICS["control"])
    if unavailable:
        button.setEnabled(False)
        button.setToolTip(unavailable)
    return button


def _table(
    name: str, columns: tuple[str, ...], stretch_column: int, *, data_columns: tuple[int, ...] = ()
) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setObjectName(name)
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().hide()
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    apply_table_style(table, data_columns=data_columns)
    table.setMinimumHeight(METRICS["row"] * 3)
    header = table.horizontalHeader()
    header.setDefaultSectionSize(94)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    return table


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*([SPACE["lg"]] * 4))
    layout.setSpacing(SPACE["md"])
    return frame, layout


def _scroll_region(name: str, layout: QLayout) -> QScrollArea:
    """Let the middle workspace scroll without shrinking its children below their minimums."""
    content = QWidget()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    content.setLayout(layout)
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(content)
    return scroll


class _WorkspacePage(QWidget):
    def __init__(self, title: str, notice: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*([SPACE["lg"]] * 4))
        self.body.setSpacing(SPACE["sm"])
        header = _row()
        heading = _label(title)
        heading.setObjectName("pageTitle")
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(_label("界面预览 · 未接入业务", muted=True))
        self.body.addLayout(header)
        description = _label(notice, muted=True)
        description.setWordWrap(True)
        self.body.addWidget(description)


class _AutomationPage(_WorkspacePage):
    def __init__(self, doip: bool, parent: QWidget | None = None):
        title = "DoIP 自动化" if doip else "UDS 自动化"
        notice = (
            "一致性脚本、Socket 池与 expect 匹配执行器尚未接入。"
            if doip
            else "支持多脚本与 pre / steps / post 结构；脚本加载和执行器尚未接入。"
        )
        super().__init__(title, notice, parent)
        self.setObjectName("doipAutomationPage" if doip else "udsAutomationPage")
        workspace = _row()
        workspace.setSpacing(SPACE["md"])

        scripts_card, scripts_layout = _card()
        scripts_card.setMaximumWidth(330)
        files_header = _row()
        files_header.addWidget(_label("测试脚本", name="sectionTitle"))
        files_header.addStretch()
        files_header.addWidget(_label("YAML / JSON", muted=True))
        scripts_layout.addLayout(files_header)
        self.script_tree = QTreeWidget()
        self.script_tree.setObjectName("scriptTree")
        self.script_tree.setHeaderLabels(["脚本 / 用例", "状态"])
        self.script_tree.setIndentation(SPACE["lg"])
        self.script_tree.setMinimumHeight(METRICS["row"] * 3)
        self.script_tree.setUniformRowHeights(True)
        self.script_tree.header().setFixedHeight(METRICS["header"])
        self.script_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.script_tree.header().resizeSection(1, 70)
        scripts_layout.addWidget(self.script_tree, 1)
        files_actions = _row()
        files_actions.addWidget(
            _button("加载脚本", "loadScriptsButton", unavailable="脚本文件加载服务尚未接入")
        )
        files_actions.addWidget(
            _button("移除", "removeScriptButton", unavailable="当前未加载脚本", role="danger")
        )
        scripts_layout.addLayout(files_actions)
        workspace.addWidget(scripts_card, 1)

        steps_card, steps_layout = _card()
        steps_header = _row()
        steps_header.addWidget(_label("步骤与结果", name="sectionTitle"))
        steps_header.addStretch()
        self.phase_filter = QComboBox()
        self.phase_filter.setObjectName("phaseFilter")
        self.phase_filter.setFixedHeight(METRICS["control"])
        self.phase_filter.addItems(["全部阶段", "pre", "steps", "post"])
        self.phase_filter.setToolTip("界面阶段选择；当前没有已加载步骤")
        steps_header.addWidget(self.phase_filter)
        steps_layout.addLayout(steps_header)
        self.result_tabs = QTabWidget()
        self.result_tabs.setObjectName("automationResultTabs")
        columns = (
            ("序号", "Socket", "操作 / 报文", "预期", "状态")
            if doip
            else ("序号", "阶段", "操作", "预期 / 参数", "状态")
        )
        self.steps_table = _table("automationStepsTable", columns, 3, data_columns=(0,))
        self.results_table = _table(
            "automationResultsTable", ("轮次", "用例", "结果", "详情"), 3, data_columns=(0,)
        )
        self.result_tabs.addTab(self.steps_table, "用例步骤")
        self.result_tabs.addTab(self.results_table, "运行结果")
        steps_layout.addWidget(self.result_tabs, 1)
        workspace.addWidget(steps_card, 3)
        self.body.addWidget(_scroll_region("automationWorkspaceScroll", workspace), 1)

        controls = _row()
        controls.addWidget(_label("轮次"))
        self.rounds = QSpinBox()
        self.rounds.setObjectName("automationRounds")
        self.rounds.setProperty("data", True)
        self.rounds.setFont(data_font())
        self.rounds.setFixedHeight(METRICS["control"])
        self.rounds.setRange(1, 999999)
        self.rounds.setValue(1)
        self.rounds.setFixedWidth(92)
        self.rounds.setToolTip("临时运行参数，不写入项目或脚本")
        controls.addWidget(self.rounds)
        if not doip:
            self.keep_alive_filter = QCheckBox("过滤保活响应")
            self.keep_alive_filter.setObjectName("keepAliveFilter")
            self.keep_alive_filter.setMinimumHeight(METRICS["control"])
            self.keep_alive_filter.setChecked(True)
            self.keep_alive_filter.setToolTip("临时参数；执行器尚未接入")
            controls.addWidget(self.keep_alive_filter)
        controls.addStretch()
        controls.addWidget(_label("未执行 · 尚无报告", muted=True))
        controls.addWidget(
            _button("导出报告", "exportReportButton", unavailable="尚无执行结果可导出")
        )
        for text, name in (
            ("开始测试", "startAutomationButton"),
            ("暂停", "pauseAutomationButton"),
            ("恢复", "resumeAutomationButton"),
            ("停止", "stopAutomationButton"),
        ):
            controls.addWidget(
                _button(text, name, unavailable="自动化执行器尚未接入", role="primary" if text == "开始测试" else "secondary")
            )
        self.body.addLayout(controls)


class _FlashPage(_WorkspacePage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            "DoIP 刷写", "按文件加载顺序执行三阶段流程；固件解析和刷写状态机尚未接入。", parent
        )
        self.setObjectName("flashPage")
        file_actions = _row()
        file_actions.addWidget(
            _button("加载固件", "loadFirmwareButton", unavailable="Intel HEX 解析服务尚未接入")
        )
        file_actions.addWidget(
            _button("加载刷写步骤", "loadFlashStepsButton", unavailable="项目刷写配置加载尚未接入")
        )
        file_actions.addWidget(_label("尚未加载固件或项目步骤", muted=True))
        file_actions.addStretch()
        for text, name in (("上移", "moveFirmwareUpButton"), ("下移", "moveFirmwareDownButton"), ("移除", "removeFirmwareButton")):
            file_actions.addWidget(_button(text, name, unavailable="当前未加载固件", role="danger" if text == "移除" else "quiet"))
        self.body.addLayout(file_actions)
        self.firmware_table = _table(
            "firmwareTable", ("序号", "固件文件", "起始地址", "大小", "状态"), 1, data_columns=(0, 2, 3)
        )
        self.body.addWidget(self.firmware_table, 1)

        phases = _row()
        phases.setSpacing(SPACE["md"])
        for sequence, title, phase in (
            ("01", "预刷写", "Pre-Flash"),
            ("02", "程序下载", "Flash"),
            ("03", "后刷写", "Post-Flash"),
        ):
            card, layout = _card()
            heading = _row()
            heading.addWidget(_label(f"{sequence}  {title}", name="sectionTitle"))
            heading.addStretch()
            heading.addWidget(_label(phase, muted=True))
            layout.addLayout(heading)
            layout.addWidget(_label("待加载步骤", muted=True))
            phases.addWidget(card, 1)
        self.body.addLayout(phases)

        progress_row = _row()
        self.progress = QProgressBar()
        self.progress.setObjectName("flashProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(_label("未开始 · 速度 —", muted=True))
        for text, name in (
            ("开始刷写", "startFlashButton"),
            ("停止", "stopFlashButton"),
            ("重试", "retryFlashButton"),
        ):
            progress_row.addWidget(
                _button(text, name, unavailable="刷写状态机尚未接入", role="primary" if text == "开始刷写" else "secondary")
            )
        self.body.addLayout(progress_row)


class _DtcPage(_WorkspacePage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__("DTC 测试", "故障码、快照与扩展数据；诊断传输和项目中文码表尚未接入。", parent)
        self.setObjectName("dtcPage")
        filters = _row()
        filters.addWidget(_label("状态掩码"))
        self.status_mask = QLineEdit()
        self.status_mask.setObjectName("dtcStatusMask")
        self.status_mask.setProperty("data", True)
        self.status_mask.setFont(data_font())
        self.status_mask.setFixedHeight(METRICS["control"])
        self.status_mask.setPlaceholderText("hex")
        self.status_mask.setMaxLength(2)
        self.status_mask.setFixedWidth(90)
        self.status_mask.setToolTip("留空；实际值待项目配置和诊断服务提供")
        filters.addWidget(self.status_mask)
        filters.addSpacing(SPACE["sm"])
        self.search = QLineEdit()
        self.search.setObjectName("dtcSearch")
        self.search.setFixedHeight(METRICS["control"])
        self.search.setPlaceholderText("筛选故障码或中文描述")
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.search, 1)
        filters.addWidget(
            _button("读取 DTC", "readDtcButton", unavailable="诊断传输尚未接入", role="primary")
        )
        filters.addWidget(
            _button("清除 DTC", "clearDtcButton", unavailable="诊断传输尚未接入", role="danger")
        )
        self.body.addLayout(filters)
        self.dtc_table = _table(
            "dtcTable", ("故障码", "中文描述", "状态字节", "状态说明"), 1, data_columns=(0, 2)
        )
        self.body.addWidget(self.dtc_table, 1)
        details = _row()
        details.addWidget(_label("DTC"))
        self.dtc_code = QLineEdit()
        self.dtc_code.setObjectName("dtcCode")
        self.dtc_code.setProperty("data", True)
        self.dtc_code.setFont(data_font())
        self.dtc_code.setFixedHeight(METRICS["control"])
        self.dtc_code.setPlaceholderText("6 位 hex")
        self.dtc_code.setMaxLength(6)
        self.dtc_code.setFixedWidth(118)
        details.addWidget(self.dtc_code)
        details.addWidget(_label("记录号"))
        self.record_number = QLineEdit()
        self.record_number.setObjectName("dtcRecordNumber")
        self.record_number.setProperty("data", True)
        self.record_number.setFont(data_font())
        self.record_number.setFixedHeight(METRICS["control"])
        self.record_number.setPlaceholderText("hex")
        self.record_number.setMaxLength(2)
        self.record_number.setFixedWidth(80)
        details.addWidget(self.record_number)
        details.addWidget(
            _button("读取快照", "readDtcSnapshotButton", unavailable="快照读取服务尚未接入")
        )
        details.addWidget(
            _button("读取扩展数据", "readDtcExtendedButton", unavailable="扩展数据服务尚未接入")
        )
        details.addStretch()
        details.addWidget(_label("尚未读取故障码", muted=True))
        self.body.addLayout(details)
        self.search.textChanged.connect(self._filter_codes)

    @Slot(str)
    def _filter_codes(self, text: str) -> None:
        query = text.strip().casefold()
        for row in range(self.dtc_table.rowCount()):
            searchable = " ".join(
                self.dtc_table.item(row, column).text()
                for column in (0, 1)
                if self.dtc_table.item(row, column) is not None
            )
            self.dtc_table.setRowHidden(row, query not in searchable.casefold())


# Display choices from the protocol specification; no frame construction here.
_PAYLOAD_CHOICES = (
    "0x0005 · 路由激活请求",
    "0x8001 · 诊断报文",
    "0x0001 · 车辆识别请求",
    "0x0002 · EID 车辆识别请求",
    "0x0003 · VIN 车辆识别请求",
    "0x0004 · 车辆公告 / 识别响应",
    "0x0006 · 路由激活响应",
    "0x0007 · Alive Check 请求",
    "0x0008 · Alive Check 响应",
    "0x4001 · 实体状态请求",
    "0x4002 · 实体状态响应",
    "0x8002 · 诊断 ACK",
    "0x8003 · 诊断 NACK",
    "0x0000 · 通用 NACK",
)


class _DoipManualPage(_WorkspacePage):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            "DoIP 手动", "编辑协议字段和原始报文；DoIP 构包、发送及 Socket 池尚未接入。", parent
        )
        self.setObjectName("doipManualPage")
        parameters = QVBoxLayout()
        parameters.setSpacing(SPACE["sm"])
        fields = _row()
        fields.addWidget(_label("Payload Type"))
        self.payload_type = QComboBox()
        self.payload_type.setObjectName("doipPayloadType")
        self.payload_type.setFixedHeight(METRICS["control"])
        self.payload_type.setEditable(True)
        self.payload_type.addItems(_PAYLOAD_CHOICES)
        self.payload_type.setToolTip("可选择已有类型，或临时输入自定义类型；不执行构包")
        fields.addWidget(self.payload_type, 2)
        fields.addWidget(_label("版本"))
        self.version = QComboBox()
        self.version.setObjectName("doipVersion")
        self.version.setProperty("data", True)
        self.version.setFont(data_font())
        self.version.setFixedHeight(METRICS["control"])
        self.version.addItems(["0x02", "0x03", "0x01"])
        self.version.setFixedWidth(87)
        fields.addWidget(self.version)
        fields.addWidget(_label("Socket"))
        self.socket_choice = QComboBox()
        self.socket_choice.setObjectName("doipSocket")
        self.socket_choice.setFixedHeight(METRICS["control"])
        self.socket_choice.addItems(["MAIN", "TEMP", "TEMP1", "UDP"])
        self.socket_choice.setFixedWidth(98)
        fields.addWidget(self.socket_choice)
        parameters.addLayout(fields)

        addresses = _row()
        addresses.addWidget(_label("源地址 SA"))
        self.source_address = QLineEdit()
        self.source_address.setObjectName("doipSourceAddress")
        self.source_address.setProperty("data", True)
        self.source_address.setFont(data_font())
        self.source_address.setFixedHeight(METRICS["control"])
        self.source_address.setPlaceholderText("项目源地址")
        self.source_address.setMaxLength(4)
        addresses.addWidget(self.source_address)
        addresses.addWidget(_label("目标地址 TA"))
        self.target_address = QLineEdit()
        self.target_address.setObjectName("doipTargetAddress")
        self.target_address.setProperty("data", True)
        self.target_address.setFont(data_font())
        self.target_address.setFixedHeight(METRICS["control"])
        self.target_address.setPlaceholderText("项目目标地址")
        self.target_address.setMaxLength(4)
        addresses.addWidget(self.target_address)
        self.raw_mode = QCheckBox("完整原始帧（raw）")
        self.raw_mode.setObjectName("doipRawMode")
        self.raw_mode.setMinimumHeight(METRICS["control"])
        self.raw_mode.setToolTip("切换编辑区域含义；不会生成或发送报文")
        addresses.addWidget(self.raw_mode)
        parameters.addLayout(addresses)

        editor_card, editor_layout = _card()
        self.payload_caption = _label("Payload（hex）", name="sectionTitle")
        editor_layout.addWidget(self.payload_caption)
        self.payload = QPlainTextEdit()
        self.payload.setObjectName("doipPayloadEditor")
        self.payload.setProperty("data", True)
        self.payload.setFont(data_font())
        self.payload.setPlaceholderText("输入 payload 的十六进制字节；空格和换行可用于分隔")
        self.payload.setMinimumHeight(METRICS["row"] * 3)
        editor_layout.addWidget(self.payload, 1)
        self.byte_count = _label("0 字节 · 仅编辑，未发送", muted=True)
        self.byte_count.setObjectName("doipByteCount")
        editor_layout.addWidget(self.byte_count)
        parameters.addWidget(editor_card, 1)
        self.body.addWidget(_scroll_region("doipParametersScroll", parameters), 1)

        actions = _row()
        actions.addWidget(
            _button("连接 Socket", "connectPoolSocketButton", unavailable="Socket 池尚未接入", role="connection")
        )
        actions.addWidget(
            _button("关闭 Socket", "closePoolSocketButton", unavailable="Socket 池尚未接入")
        )
        actions.addStretch()
        clear_button = _button("清空输入", "clearDoipInputButton", role="danger")
        actions.addWidget(clear_button)
        actions.addWidget(
            _button("发送", "sendDoipButton", unavailable="DoIP 测试传输尚未接入", role="primary")
        )
        self.body.addLayout(actions)
        clear_button.clicked.connect(self.payload.clear)
        self.payload.textChanged.connect(self._update_byte_count)
        self.raw_mode.toggled.connect(self._toggle_raw_mode)

    @Slot()
    def _update_byte_count(self) -> None:
        compact = "".join(self.payload.toPlainText().split())
        if not compact:
            self.byte_count.setText("0 字节 · 仅编辑，未发送")
            return
        try:
            data = bytes.fromhex(compact)
        except ValueError:
            self.byte_count.setText("输入无效：使用十六进制完整字节，例如 02 FD")
        else:
            self.byte_count.setText(f"{len(data)} 字节 · 仅编辑，未发送")

    @Slot(bool)
    def _toggle_raw_mode(self, enabled: bool) -> None:
        for field in (self.payload_type, self.version, self.source_address, self.target_address):
            field.setEnabled(not enabled)
        self.payload_caption.setText("完整 DoIP 帧（hex）" if enabled else "Payload（hex）")
        self.payload.setPlaceholderText(
            "输入含 DoIP 通用头的完整帧；当前仅检查十六进制字节格式"
            if enabled
            else "输入 payload 的十六进制字节；空格和换行可用于分隔"
        )


def create_workspace_page(index: int, parent: QWidget | None = None) -> QWidget:
    """Create a secondary page in the screenshot's navigation order (1–5)."""
    if index == 1:
        return _AutomationPage(False, parent)
    if index == 2:
        return _FlashPage(parent)
    if index == 3:
        return _DtcPage(parent)
    if index == 4:
        return _DoipManualPage(parent)
    if index == 5:
        return _AutomationPage(True, parent)
    raise ValueError(f"Secondary workspace index must be 1–5, got {index}")
