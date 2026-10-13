"""Qt owner-thread projection of asynchronous project and diagnostic Ports."""

from PySide6.QtCore import QObject, QTimer, Slot

from src.ports.events import DataReceivedEvent, ErrorEvent, LogEvent, SessionStateChangedEvent
from src.ports.model_types import SessionState
from src.ui.config_dialogs import DiagnosticConnectionDialog
from src.ui.project_controls import ProjectControls


class DiagnosticController(QObject):
    def __init__(self, context, window):
        super().__init__(window)
        self._context = context
        self.window = window
        self._projects = context.projects
        self._manual = context.manual_diagnostic
        self.settings = self._projects.current.settings if self._projects.current else None
        self._task = None
        self._save_dialog = None
        self._closed = False
        context.event_bus.subscribe(SessionStateChangedEvent, self._session_changed)
        context.event_bus.subscribe(ErrorEvent, self._error)
        context.event_bus.subscribe(DataReceivedEvent, self._response)
        window.project_button.clicked.connect(self.show_projects)
        window.connect_button.clicked.connect(self.toggle_connection)
        window.command_editor.request_requested.connect(self.send)
        window.command_editor.keep_alive_requested.connect(self.keep_alive)
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        self._project_state()
        self._render()

    def can_edit(self):
        return (not self._closed and not self._projects.busy
                and self._manual.snapshot.state in (SessionState.DISCONNECTED, SessionState.FAILED))

    def _project_state(self):
        self.window.communication.response_panel.clear()
        current = self._projects.current
        if current is not None:
            self.window.project_label.setText(f"{current.name} | DoIP")
            if self.settings:
                self.window.project_label.setToolTip(f"{self.settings.target_ip}:{self.settings.target_port} / Tester 0x{self.settings.source_address:04X} / ECU 0x{self.settings.target_address:04X}")

    def _render(self):
        snapshot = self._manual.snapshot
        state = snapshot.state
        idle = state in (SessionState.DISCONNECTED, SessionState.FAILED)
        label = self.window.connection_label
        label.setText(f"连接：{state.value}")
        label.setToolTip(snapshot.reason)
        label.setProperty("connected", state is SessionState.READY)
        label.style().unpolish(label)
        label.style().polish(label)
        button = self.window.connect_button
        button.setText("连接" if idle else ("断开" if state is SessionState.READY else "释放中" if state is SessionState.DISCONNECTING else "取消连接"))
        button.setEnabled(not self._projects.busy and self.settings is not None and state is not SessionState.DISCONNECTING)
        button.setToolTip("主诊断 TCP 与路由激活" if idle else "仅释放诊断 MAIN")
        self.window.settings_button.setEnabled(self.can_edit() and self.settings is not None)
        self.window.project_button.setEnabled(self.can_edit())
        self.window.command_editor.set_connection_ready(state is SessionState.READY)
        message = snapshot.reason or ("请显式加载项目；启动不会连接 ECU" if self.settings is None else f"{state.value} · 参数在下次连接时生效")
        if self._projects.busy:
            message = "正在处理项目文件…"
        self.window.statusBar().showMessage(message)

    def _session_changed(self, event):
        if not self._closed:
            if event.snapshot.state is not SessionState.READY:
                self.window.communication.response_panel.clear()
            self._render()

    def _response(self, event):
        if not self._closed and self._manual.snapshot.state is SessionState.READY:
            self.window.communication.response_panel.show_response(event.data, event.timestamp)

    def _error(self, event):
        if not self._closed:
            self.window.statusBar().showMessage(event.message)
            if event.source != "doip-main":
                self._context.event_bus.publish(LogEvent("ERROR", None, event.message, timestamp=event.timestamp))

    @Slot()
    def show_projects(self):
        if not self.can_edit(): return
        chooser = ProjectControls(self._projects, self.window)
        chooser.project_requested.connect(self.load_project)
        self.window._open_dialog(chooser)

    @Slot(str)
    def load_project(self, name):
        if self._task is not None:
            self.window._feedback("ERROR", "已有项目任务正在处理")
            return
        self._task = self._projects.load_project(name)
        self._render()

    @Slot()
    def show_config(self):
        if not self.can_edit() or self.settings is None:
            return
        dialog = DiagnosticConnectionDialog(self.settings, self._projects.current.name, can_edit=self.can_edit, parent=self.window)
        dialog.accepted.connect(self._apply_config)
        dialog.save_requested.connect(self._save_config)
        dialog.finished.connect(self._config_finished)
        self.window._open_dialog(dialog)

    @Slot(int)
    def _config_finished(self, result):
        if self.sender() is self._save_dialog:
            self._save_dialog = None

    @Slot()
    def _apply_config(self):
        if self.can_edit():
            self.settings = self.sender().settings
            self._project_state()
            self.window._feedback("INFO", "配置已应用到当前会话；下次连接生效，尚未保存文件")

    @Slot(object)
    def _save_config(self, settings):
        if not self.can_edit(): return
        self._save_dialog = self.sender()
        self._save_dialog.apply_button.setEnabled(False)
        self._save_dialog.save_button.setEnabled(False)
        self._task = self._projects.save_project(settings)
        self._render()

    @Slot()
    def toggle_connection(self):
        if self._closed or self._projects.busy: return
        if self._manual.snapshot.state in (SessionState.DISCONNECTED, SessionState.FAILED):
            if self.settings is not None and not self._manual.connect(self.settings):
                self.window._feedback("ERROR", "连接任务未受理")
        else:
            self._manual.disconnect()
        self._render()

    @Slot(bytes, bool)
    def send(self, data, functional):
        if not self._manual.send(data, "functional" if functional else "physical"):
            self.window.command_editor._error("UDS 请求未受理，请检查连接与输入")

    @Slot(bool)
    def keep_alive(self, enabled):
        self._manual.set_keep_alive(enabled)

    @Slot()
    def poll(self):
        if self._closed: return
        self._manual.poll()
        self._projects.poll()
        self.window.communication.poll_export()
        if self._task is not None and self._task.done.is_set() and not self._projects.busy:
            task, self._task = self._task, None
            dialog, self._save_dialog = self._save_dialog, None
            if task.error:
                self.window._feedback("ERROR", f"项目操作失败：{task.error}")
                if dialog is not None and dialog.isVisible():
                    dialog._error(task.error, dialog.save_button)
                    dialog.apply_button.setEnabled(True)
                    dialog.save_button.setEnabled(True)
            else:
                self.settings = task.result.settings
                self._project_state()
                if dialog is not None and dialog.isVisible():
                    dialog.reject()
                self.window._feedback("INFO", f"项目 {task.result.name} 配置已就绪")
        self._render()

    def close(self):
        if self._closed: return
        self._closed = True
        self.timer.stop()
        self._context.event_bus.unsubscribe(SessionStateChangedEvent, self._session_changed)
        self._context.event_bus.unsubscribe(ErrorEvent, self._error)
        self._context.event_bus.unsubscribe(DataReceivedEvent, self._response)
        self.window.communication.response_panel.clear()
        self._manual.close()
        self._projects.close()
