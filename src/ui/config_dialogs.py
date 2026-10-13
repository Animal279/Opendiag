"""Editable UI previews for connection and hardware settings.

The values belong to the current window session. These dialogs do not load a
project, write a configuration, connect a socket, or initialize hardware.
"""

from copy import deepcopy
from ipaddress import ip_address
import re

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout,
    QWidget,
)

from src.ui.theme import METRICS, SPACE, data_font


def _label(text: str, name: str = "muted") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _card(title: str) -> tuple[QFrame, QVBoxLayout, QFormLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(*([SPACE["lg"]] * 4))
    layout.setSpacing(SPACE["md"])
    layout.addWidget(_label(title, "sectionTitle"))
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(SPACE["lg"])
    form.setVerticalSpacing(SPACE["md"])
    layout.addLayout(form)
    return frame, layout, form


def _edit(value: object, name: str, placeholder: str = "", *, data: bool = True) -> QLineEdit:
    field = QLineEdit(str(value))
    field.setObjectName(name)
    field.setPlaceholderText(placeholder)
    field.setFixedHeight(METRICS["control"])
    if data:
        field.setProperty("data", True)
        field.setFont(data_font())
    return field


def _combo(name: str, choices: tuple, value: object = None, *, data: bool = False) -> QComboBox:
    field = QComboBox()
    field.setObjectName(name)
    field.setFixedHeight(METRICS["control"])
    if data:
        field.setProperty("data", True)
        field.setFont(data_font())
    for text, data in choices:
        field.addItem(text, data)
    index = field.findData(value)
    if index < 0:
        field.addItem(f"无效值：{value}", value)
        index = field.count() - 1
    field.setCurrentIndex(index)
    return field


class _PreviewDialog(QDialog):
    def __init__(self, title: str, description: str, parent: QWidget | None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} · UI 预览")
        screen = parent.screen() if parent is not None else QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        width = min(690, available.width() - 60) if available is not None else 690
        height = min(660, available.height() - 90) if available is not None else 660
        self.resize(width, height)
        self.setMinimumSize(min(540, width), min(400, height))
        self._values: dict = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([SPACE["lg"]] * 4))
        layout.setSpacing(SPACE["md"])
        layout.addWidget(_label(title, "pageTitle"))
        layout.addWidget(_label(description))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, SPACE["xs"], 0)
        self.body.setSpacing(SPACE["lg"])
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.error_label = _label("", "validationError")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        footer = QHBoxLayout()
        footer.setSpacing(SPACE["sm"])
        self.footer_hint = _label("仅在本次窗口会话中生效")
        footer.addWidget(self.footer_hint, 1)
        self.footer = footer
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("dialogCancel")
        self.cancel_button.setProperty("role", "secondary")
        self.cancel_button.setFixedHeight(METRICS["control"])
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        self.apply_button = QPushButton("应用到预览")
        self.apply_button.setObjectName("dialogApply")
        self.apply_button.setProperty("role", "primary")
        self.apply_button.setFixedHeight(METRICS["control"])
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.accept)
        footer.addWidget(self.apply_button)
        layout.addLayout(footer)

    @property
    def values(self) -> dict:
        """Return an isolated snapshot of the last accepted settings."""
        return deepcopy(self._values)

    def _error(self, message: str, field: QWidget) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        field.setFocus()


class ConnectionDialog(_PreviewDialog):
    """Connection form preview; use open() and retain the dialog until finished."""

    def __init__(self, parent: QWidget | None = None, state: dict | None = None):
        state = deepcopy(state or {})
        super().__init__(
            "连接配置",
            "以下是可编辑的界面示意值。未加载真实项目，应用后不会连接 ECU 或保存配置文件。",
            parent,
        )
        card, _, form = _card("连接方式")
        self.transport = _combo("connectionTransport", (("DoIP", "doip"), ("DoCAN", "docan")), state.get("transport", "doip"))
        self.project = _edit("UI 演示 / 未加载真实项目", "connectionProject", data=False)
        self.project.setReadOnly(True)
        form.addRow("传输协议", self.transport)
        form.addRow("当前项目", self.project)
        self.body.addWidget(card)

        self.protocol_pages = QStackedWidget()
        doip, doip_layout, doip_form = _card("DoIP 参数 · 示意值")
        self.address = _edit(state.get("address", "127.0.0.1"), "connectionAddress", "IPv4 或 IPv6 地址")
        self.port = _edit(state.get("port", 13400), "connectionPort", "1–65535")
        self.source = _edit(state.get("source", "0x0E80"), "connectionSource", "16 位逻辑地址")
        self.target = _edit(state.get("target", "0x0001"), "connectionTarget", "16 位逻辑地址")
        self.version = _combo("connectionVersion", (("0x02 · 2012", 2), ("0x03 · 2019", 3)), state.get("protocol_version", 2), data=True)
        doip_form.addRow("目标 IP", self.address)
        doip_form.addRow("目标端口", self.port)
        doip_form.addRow("Tester 逻辑地址", self.source)
        doip_form.addRow("ECU 逻辑地址", self.target)
        doip_form.addRow("协议版本", self.version)
        doip_layout.addWidget(_label("127.0.0.1 为界面演示地址；这些字段不代表任何项目或 ECU 的实际参数。"))
        self.protocol_pages.addWidget(doip)

        docan_state = state.get("docan", {})
        docan, docan_layout, docan_form = _card("DoCAN 参数 · 示意值")
        self.req_id = _edit(docan_state.get("req_id", "0x7E0"), "connectionReqId")
        self.rsp_id = _edit(docan_state.get("rsp_id", "0x7E8"), "connectionRspId")
        self.functional_id = _edit(docan_state.get("functional_id", "0x7DF"), "connectionFunctionalId")
        self.extended = QCheckBox("扩展帧（29 位 ID）")
        self.extended.setObjectName("connectionExtended")
        self.extended.setMinimumHeight(METRICS["control"])
        self.extended.setChecked(bool(docan_state.get("is_extended", False)))
        self.canfd = QCheckBox("外层使用 CAN FD")
        self.canfd.setObjectName("connectionCanFd")
        self.canfd.setMinimumHeight(METRICS["control"])
        self.canfd.setChecked(bool(docan_state.get("is_canfd", False)))
        docan_form.addRow("请求 ID", self.req_id)
        docan_form.addRow("响应 ID", self.rsp_id)
        docan_form.addRow("功能寻址 ID", self.functional_id)
        docan_form.addRow("帧类型", self.extended)
        docan_form.addRow("CAN FD", self.canfd)
        docan_layout.addWidget(_label("CAN 通道在硬件配置中选择。SDK 尚未接入；原诊断 ISO-TP 为 8 字节布局，最大载荷 4095 字节。"))
        self.protocol_pages.addWidget(docan)
        self.body.addWidget(self.protocol_pages)
        self.body.addStretch()
        self.transport.currentIndexChanged.connect(self._change_transport)
        self._change_transport()

    @Slot()
    def _change_transport(self) -> None:
        self.protocol_pages.setCurrentIndex(1 if self.transport.currentData() == "docan" else 0)
        self.error_label.hide()

    def _hex(self, field: QLineEdit, label: str, maximum: int, digits: int) -> str | None:
        text = field.text().strip()
        if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", text):
            self._error(f"{label}请输入十六进制值，可带 0x 前缀。", field)
            return None
        value = int(text, 16)
        if value > maximum:
            self._error(f"{label}应在 0x0–0x{maximum:X} 范围内。", field)
            return None
        return f"0x{value:0{digits}X}"

    @Slot()
    def accept(self) -> None:
        transport = self.transport.currentData()
        if transport not in ("doip", "docan"):
            self._error("请选择 DoIP 或 DoCAN 传输协议。", self.transport)
            return
        values = {
            "transport": transport, "project": "UI 演示",
            "address": self.address.text().strip(), "port": self.port.text().strip(),
            "source": self.source.text().strip(), "target": self.target.text().strip(),
            "protocol_version": self.version.currentData(),
        }
        port_text = values["port"]
        if not port_text.isascii() or not port_text.isdigit() or len(port_text) > 5 or not 1 <= int(port_text) <= 65535:
            if transport == "docan":
                self._error("DoIP 草稿端口无效，请切换到 DoIP，输入 1–65535 范围内的整数。", self.transport)
            else:
                self._error("目标端口请输入 1–65535 范围内的整数。", self.port)
            return
        values["port"] = int(port_text)
        values["docan"] = {
            "req_id": self.req_id.text().strip(), "rsp_id": self.rsp_id.text().strip(),
            "functional_id": self.functional_id.text().strip(),
            "is_extended": self.extended.isChecked(), "is_canfd": self.canfd.isChecked(),
        }
        if transport == "doip":
            try:
                ip_address(values["address"])
            except ValueError:
                self._error("目标 IP 请输入有效的 IPv4 或 IPv6 地址。", self.address)
                return
            source = self._hex(self.source, "Tester 逻辑地址", 0xFFFF, 4)
            if source is None:
                return
            target = self._hex(self.target, "ECU 逻辑地址", 0xFFFF, 4)
            if target is None:
                return
            if self.version.currentData() not in (2, 3):
                self._error("请选择已确认的 DoIP 协议版本 0x02 或 0x03。", self.version)
                return
            values.update(source=source, target=target)
        else:
            maximum = 0x1FFFFFFF if self.extended.isChecked() else 0x7FF
            identifiers = []
            for field, label in ((self.req_id, "请求 ID"), (self.rsp_id, "响应 ID"), (self.functional_id, "功能寻址 ID")):
                value = self._hex(field, label, maximum, 8 if self.extended.isChecked() else 3)
                if value is None:
                    return
                identifiers.append(value)
            values["docan"] = {
                "req_id": identifiers[0], "rsp_id": identifiers[1],
                "functional_id": identifiers[2], "is_extended": self.extended.isChecked(),
                "is_canfd": self.canfd.isChecked(),
            }
        self._values = values
        super().accept()


class DiagnosticConnectionDialog(_PreviewDialog):
    """Validated project parameters. Apply is local; save is an asynchronous Port action."""

    from PySide6.QtCore import Signal as _Signal
    save_requested = _Signal(object)

    def __init__(self, settings, name, *, can_edit, parent=None):
        super().__init__("连接配置", "修改在下次连接时生效；连接及释放期间锁定。", parent)
        self.setWindowTitle("连接配置")
        self.footer_hint.setText("应用仅改本次会话；保存写项目 JSON")
        self.apply_button.setText("应用到当前配置")
        self._can_edit = can_edit
        self.settings = settings
        card, _, form = _card(f"{name} · DoIP")
        self._fields = {}
        values = settings.to_config()["doip"]
        definitions = (
            ("target_ip", "目标 IPv4", "address"), ("target_port", "目标端口", "port"),
            ("source_address", "Tester 逻辑地址", "source"), ("target_address", "ECU 物理地址", "target"),
            ("functional_address", "功能地址", "functional"),
            ("routing_activation_type", "RA activation type", "activation_type"),
            ("routing_oem_data", "RA OEM（4B）", "oem_data"),
            ("connect_timeout_ms", "TCP 连接超时（ms）", "connect_timeout"),
            ("routing_timeout_ms", "RA 等待超时（ms）", "routing_timeout"),
            ("max_payload_length", "接收 payload 上限（B）", "max_payload"),
            ("tester_present_interval_ms", "TesterPresent 间隔（ms）", "keep_interval"))
        for key, label, attribute in definitions:
            value = values[key]
            if key.endswith("address") or key == "routing_activation_type":
                value = f"0x{value:04X}" if key.endswith("address") else f"0x{value:02X}"
            field = _edit(value, f"diagnostic_{key}")
            field.setAccessibleName(label)
            self._fields[key] = field
            setattr(self, attribute, field)
            form.addRow(label, field)
        self.version = _combo("diagnosticVersion", (("0x02 · 2012", 2), ("0x03 · 2019", 3)), settings.protocol_version, data=True)
        form.addRow("协议版本", self.version)
        self.body.addWidget(card)
        self.body.addWidget(_label("RA reserved 为四个零字节；P2/P2* 本轮未消费。保持会话默认关闭。"))
        self.body.addStretch()
        self.save_button = QPushButton("保存到项目")
        self.save_button.setProperty("role", "secondary")
        self.save_button.clicked.connect(self._save)
        self.footer.insertWidget(self.footer.count() - 1, self.save_button)

    def _validate(self):
        from src.ports.model_types import DoIPSettings
        if not self._can_edit():
            self._error("诊断连接或项目任务尚未释放，不能修改配置", self.apply_button)
            return None
        section = {key: field.text().strip() for key, field in self._fields.items()}
        for key in ("source_address", "target_address", "functional_address", "routing_activation_type"):
            text = section[key]
            if re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", text) is None:
                self._error(f"{key}: 请输入十六进制值", self._fields[key])
                return None
            section[key] = int(text, 16)
        section["protocol_version"] = self.version.currentData()
        try:
            return DoIPSettings.from_config({"transport": "doip", "doip": section})
        except ValueError as exc:
            key = str(exc).split(":", 1)[0]
            self._error(str(exc), self._fields.get(key, self.version))
            return None

    @Slot()
    def accept(self):
        settings = self._validate()
        if settings is not None:
            self.settings = settings
            super().accept()

    @Slot()
    def _save(self):
        settings = self._validate()
        if settings is not None:
            self.settings = settings
            self.save_requested.emit(settings)


class HardwareDialog(_PreviewDialog):
    """Hardware form preview with explicit unavailable device operations."""

    CAN_MODELS = (None, "USBCANFD-200U", "TC1014", "TC1016")
    POWER_MODELS = (None, "JY-DAM0800", "KPS3020D")

    def __init__(self, parent: QWidget | None = None, state: dict | None = None):
        state = deepcopy(state or {})
        super().__init__(
            "硬件配置",
            "硬件未初始化。以下表单用于确认布局；SDK、串口与电源能力尚未接入，应用只保留本次窗口会话的选项。",
            parent,
        )
        can, can_layout, form = _card("CAN 设备")
        self.can_model = _combo("hardwareCanModel", (("未选择", None), ("ZLG · USBCANFD-200U", "USBCANFD-200U"), ("TOSUN · TC1014", "TC1014"), ("TOSUN · TC1016", "TC1016")), state.get("can_model"))
        self.can_channel = _combo("hardwareCanChannel", (("未选择", None), ("物理通道 0 · CAN1", 0), ("物理通道 1 · CAN2", 1)), state.get("can_channel"))
        self.device_index = QSpinBox()
        self.device_index.setObjectName("hardwareDeviceIndex")
        self.device_index.setProperty("data", True)
        self.device_index.setFont(data_font())
        self.device_index.setFixedHeight(METRICS["control"])
        self.device_index.setRange(0, 255)
        self.device_index.setValue(state.get("device_index", 0))
        self.device_index.setToolTip("界面示意值；尚未枚举或打开设备。")
        self.frame_type = _combo("hardwareFrameType", (("未选择", None), ("CAN", "can"), ("CAN FD", "canfd")), state.get("frame_type"))
        self.arbitration_baud = _combo("hardwareArbitrationBaud", (("未选择", None), ("250 kbit/s", 250000), ("500 kbit/s", 500000), ("1 Mbit/s", 1000000)), state.get("arbitration_baud"), data=True)
        self.data_baud = _combo("hardwareDataBaud", (("未选择", None), ("1 Mbit/s", 1000000), ("2 Mbit/s", 2000000), ("4 Mbit/s", 4000000)), state.get("data_baud"), data=True)
        self.terminal_resistor = QCheckBox("启用终端电阻")
        self.terminal_resistor.setObjectName("hardwareTerminalResistor")
        self.terminal_resistor.setMinimumHeight(METRICS["control"])
        self.terminal_resistor.setChecked(bool(state.get("terminal_resistor", False)))
        for label, field in (("设备型号", self.can_model), ("设备索引", self.device_index), ("物理通道", self.can_channel), ("默认帧类型", self.frame_type), ("仲裁段速率", self.arbitration_baud), ("数据段速率", self.data_baud), ("终端电阻", self.terminal_resistor)):
            form.addRow(label, field)
        can_layout.addWidget(_label("型号列表来自已收到资料；速率选项为本机布局设计，尚未验证设备能力。"))
        self._unavailable(can_layout, "初始化 CAN", "CAN SDK 尚未接入，不能初始化设备。", "hardwareInitCan")
        self.body.addWidget(can)

        power, power_layout, form = _card("继电器 / 程控电源")
        self.power_model = _combo("hardwarePowerModel", (("未选择", None), ("继电器 · JY-DAM0800", "JY-DAM0800"), ("程控电源 · KPS3020D", "KPS3020D")), state.get("power_model"))
        self.serial_port = _edit(state.get("serial_port", ""), "hardwareSerialPort", "例如 COM3；未扫描串口")
        self.baudrate = _combo("hardwareBaudrate", (("未选择", None), ("9600", 9600), ("19200", 19200)), state.get("baudrate"), data=True)
        self.slave_id = QSpinBox()
        self.slave_id.setObjectName("hardwareSlaveId")
        self.slave_id.setProperty("data", True)
        self.slave_id.setFont(data_font())
        self.slave_id.setFixedHeight(METRICS["control"])
        self.slave_id.setRange(1, 247)
        self.slave_id.setValue(state.get("slave_id", 1))
        self.slave_id.setToolTip("界面示意值；未加载台架配置。")
        form.addRow("设备型号", self.power_model)
        form.addRow("串口", self.serial_port)
        form.addRow("波特率", self.baudrate)
        form.addRow("从站地址", self.slave_id)
        form.addRow("接线映射", _label("KL15：未配置    KL30：未配置"))
        power_layout.addWidget(_label("串口格式示意：8N1。实际接线、允许电压 / 电流和停止恢复策略仍待补充。"))
        self._unavailable(power_layout, "测试串口 / 电源", "串口与电源适配器尚未接入，不能测试或改变硬件输出。", "hardwareTestPower")
        self.body.addWidget(power)

        resources, resources_layout, form = _card("项目资源")
        form.addRow("DBC", _label("未加载真实项目资源"))
        form.addRow("E2E", _label("未加载保护参数 / 验证向量"))
        self._unavailable(resources_layout, "选择 DBC / E2E", "资源加载器尚未接入；完整项目资源仍待提供。", "hardwareResources")
        self.body.addWidget(resources)
        self.body.addStretch()

    @staticmethod
    def _unavailable(layout: QVBoxLayout, text: str, tooltip: str, name: str) -> None:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setProperty("role", "secondary")
        button.setFixedHeight(METRICS["control"])
        button.setToolTip(tooltip)
        button.setEnabled(False)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)

    @Slot()
    def accept(self) -> None:
        if self.can_model.currentData() not in self.CAN_MODELS:
            self._error("所选 CAN 型号不在已确认型号列表中，请重新选择。", self.can_model)
            return
        if self.power_model.currentData() not in self.POWER_MODELS:
            self._error("所选电源 / 继电器型号不在已确认型号列表中，请重新选择。", self.power_model)
            return
        for field, permitted, label in (
            (self.can_channel, (None, 0, 1), "物理通道"),
            (self.frame_type, (None, "can", "canfd"), "默认帧类型"),
            (self.arbitration_baud, (None, 250000, 500000, 1000000), "仲裁段速率"),
            (self.data_baud, (None, 1000000, 2000000, 4000000), "数据段速率"),
            (self.baudrate, (None, 9600, 19200), "串口波特率"),
        ):
            if field.currentData() not in permitted:
                self._error(f"{label}无效，请重新选择；尚未配置时可选未选择。", field)
                return
        serial_port = self.serial_port.text().strip().upper()
        if serial_port and not re.fullmatch(r"COM[1-9][0-9]*", serial_port):
            self._error("串口请输入 COM 加正整数，例如 COM3；未配置时可留空。", self.serial_port)
            return
        self._values = {
            "can_model": self.can_model.currentData(), "can_channel": self.can_channel.currentData(),
            "device_index": self.device_index.value(), "frame_type": self.frame_type.currentData(),
            "arbitration_baud": self.arbitration_baud.currentData(), "data_baud": self.data_baud.currentData(),
            "terminal_resistor": self.terminal_resistor.isChecked(), "power_model": self.power_model.currentData(),
            "serial_port": serial_port, "baudrate": self.baudrate.currentData(), "slave_id": self.slave_id.value(),
        }
        super().accept()
