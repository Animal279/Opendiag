"""Nonblocking project chooser; filesystem enumeration is supplied by a Port."""

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from src.ports.projects import ProjectPort
from src.ui.theme import SPACE


class ProjectControls(QDialog):
    project_requested = Signal(str)

    def __init__(self, projects: ProjectPort, parent=None):
        super().__init__(parent)
        self._projects = projects
        self.setWindowTitle("加载项目")
        self.resize(440, 190)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*([SPACE["lg"]] * 4))
        self.message = QLabel("正在读取项目列表…")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.project_combo = QComboBox()
        self.project_combo.setAccessibleName("项目选择")
        layout.addWidget(self.project_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.rejected.connect(self.reject)
        self.load_button = buttons.addButton("加载项目", QDialogButtonBox.ButtonRole.ActionRole)
        self.load_button.setProperty("role", "primary")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self._load)
        layout.addWidget(buttons)
        self._task = projects.list_projects()
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._poll)
        self.finished.connect(self._finished)
        self.timer.start()

    @Slot()
    def _poll(self):
        self._projects.poll()
        if not self._task.done.is_set() or self._projects.busy:
            return
        self.timer.stop()
        if self._task.error:
            self.message.setText(f"项目枚举失败：{self._task.error}")
        else:
            self.project_combo.addItems(self._task.result)
            self.load_button.setEnabled(bool(self._task.result))
            self.message.setText("选择项目后加载；不会自动连接 ECU。" if self._task.result else "未找到 config/<项目>/config.json")

    @Slot()
    def _load(self):
        if self.project_combo.currentText():
            self.project_requested.emit(self.project_combo.currentText())
            self.accept()

    @Slot(int)
    def _finished(self, result):
        self.timer.stop()
