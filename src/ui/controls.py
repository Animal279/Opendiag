"""Shared DS-01 controls. State and signals remain native Qt button semantics."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QHBoxLayout, QPushButton, QWidget

from src.ui.theme import COLORS, METRICS, SPACE


class AddressingSelector(QWidget):
    """Physical/functional choice; a selected option cannot be unchecked by clicking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("addressingSelector")
        self.setAccessibleName("寻址方式")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["xs"])
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.physical_button = QPushButton("物理")
        self.functional_button = QPushButton("功能")
        for button, name in ((self.physical_button, "physicalAddressing"),
                             (self.functional_button, "functionalAddressing")):
            button.setObjectName(name)
            button.setProperty("role", "segment")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setAccessibleName(button.text() + "寻址")
            self.group.addButton(button)
            layout.addWidget(button)
        self.physical_button.setChecked(True)


class ToggleSwitch(QAbstractButton):
    """A labelled bool with track, explicit state and keyboard focus; no animation."""

    def __init__(self, text: str = "保持会话", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setObjectName("toggleSwitch")
        self.setAccessibleName(text)
        self.setCheckable(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(METRICS["control"])
        self.toggled.connect(self._update_state_description)
        self._update_state_description(False)

    def _update_state_description(self, checked: bool) -> None:
        self.setAccessibleDescription("开启" if checked else "关闭")
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 92, METRICS["control"])

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isEnabled() and (self.underMouse() or self.isDown()):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["selected"] if self.isDown() else COLORS["hover"]))
            painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 4, 4)
        text_color = COLORS["ink"] if self.isEnabled() else COLORS["disabled"]
        painter.setPen(QColor(text_color))
        painter.setFont(self.font())
        label_width = self.fontMetrics().horizontalAdvance(self.text())
        painter.drawText(QRectF(4, 0, label_width, self.height()),
                         Qt.AlignmentFlag.AlignVCenter, self.text())
        track = QRectF(label_width + 16, (self.height() - 18) / 2, 34, 18)
        color = COLORS["primary"] if self.isChecked() else COLORS["muted"]
        if not self.isEnabled():
            color = COLORS["disabled"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(track, 9, 9)
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawEllipse(QRectF(track.x() + (18 if self.isChecked() else 2), track.y() + 2, 14, 14))
        painter.setPen(QColor(text_color))
        painter.drawText(QRectF(track.right() + 8, 0, 28, self.height()),
                         Qt.AlignmentFlag.AlignVCenter, "开" if self.isChecked() else "关")
        if self.hasFocus():
            painter.setPen(QPen(QColor(COLORS["primary"]), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 4, 4)
