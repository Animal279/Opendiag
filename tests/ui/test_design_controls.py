"""DS-01 interaction and data presentation contracts, independent of QSS."""

from importlib import import_module
from importlib.util import find_spec

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QAccessible, QFont
from PySide6.QtWidgets import (
    QAbstractButton, QLineEdit, QPushButton, QStyleOptionViewItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


def _api(module_name, name):
    assert find_spec(module_name) is not None, f"DS-01 missing module: {module_name}"
    value = getattr(import_module(module_name), name, None)
    assert value is not None, f"DS-01 missing API: {module_name}.{name}"
    return value


def test_addressing_selector_keeps_one_selection_without_duplicate_events(qtbot):
    selector = _api("src.ui.controls", "AddressingSelector")()
    qtbot.addWidget(selector)
    physical, functional = selector.physical_button, selector.functional_button
    assert isinstance(physical, QPushButton) and isinstance(functional, QPushButton)
    assert physical.isChecked() and not functional.isChecked()
    changes = []
    functional.toggled.connect(changes.append)

    physical.click()
    functional.click()
    functional.click()
    assert not physical.isChecked() and functional.isChecked()
    assert changes == [True]
    physical.click()
    physical.click()
    assert physical.isChecked() and not functional.isChecked()
    assert changes == [True, False]


def test_addressing_selector_supports_tab_arrows_and_space(qtbot):
    selector = _api("src.ui.controls", "AddressingSelector")()
    host = QWidget()
    layout = QVBoxLayout(host)
    before, after = QLineEdit(), QLineEdit()
    for widget in (before, selector, after):
        layout.addWidget(widget)
    qtbot.addWidget(host)
    host.show()
    host.activateWindow()
    before.setFocus()
    qtbot.waitUntil(before.hasFocus)
    qtbot.keyClick(before, Qt.Key.Key_Tab)
    qtbot.waitUntil(selector.physical_button.hasFocus)
    qtbot.keyClick(selector.physical_button, Qt.Key.Key_Right)
    qtbot.waitUntil(selector.functional_button.hasFocus)
    qtbot.keyClick(selector.functional_button, Qt.Key.Key_Space)
    assert selector.functional_button.isChecked()
    qtbot.keyClick(selector.functional_button, Qt.Key.Key_Left)
    qtbot.waitUntil(selector.physical_button.hasFocus)
    qtbot.keyClick(selector.physical_button, Qt.Key.Key_Space)
    assert selector.physical_button.isChecked()
    assert selector.physical_button.accessibleName()
    assert selector.functional_button.accessibleName()


def test_toggle_switch_exposes_boolean_state_changes_once(qtbot):
    switch = _api("src.ui.controls", "ToggleSwitch")()
    qtbot.addWidget(switch)
    assert isinstance(switch, QAbstractButton)
    assert switch.isCheckable() and not switch.isChecked()
    assert switch.text() == "保持会话"
    changes = []
    switch.toggled.connect(changes.append)
    switch.click()
    assert switch.isChecked()
    switch.setChecked(True)
    switch.setChecked(False)
    assert changes == [True, False]


def test_toggle_switch_keyboard_and_disabled_state(qtbot):
    switch = _api("src.ui.controls", "ToggleSwitch")()
    qtbot.addWidget(switch)
    switch.show()
    switch.activateWindow()
    switch.setFocus()
    qtbot.waitUntil(switch.hasFocus)
    assert switch.accessibleName()
    qtbot.keyClick(switch, Qt.Key.Key_Space)
    assert switch.isChecked()
    switch.setEnabled(False)
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    qtbot.keyClick(switch, Qt.Key.Key_Space)
    assert switch.isChecked()
    switch.setEnabled(True)
    switch.setFocus()
    qtbot.keyClick(switch, Qt.Key.Key_Space)
    assert not switch.isChecked()


def test_data_font_uses_explicit_monospace_pixel_size(qapp):
    data_font = _api("src.ui.theme", "data_font")
    default = data_font()
    assert default.fixedPitch()
    assert default.styleHint() == QFont.StyleHint.Monospace
    assert default.pixelSize() == 13
    large = data_font(15)
    assert large.fixedPitch() and large.pixelSize() == 15
    assert default.pixelSize() == 13


def _table(qtbot):
    table = QTableWidget(1, 2)
    qtbot.addWidget(table)
    table.setHorizontalHeaderLabels(["描述", "请求"])
    table.setItem(0, 0, QTableWidgetItem("读取状态"))
    request = QTableWidgetItem("22 F1 90")
    request.setData(Qt.ItemDataRole.UserRole, b"\x22\xf1\x90")
    table.setItem(0, 1, request)
    return table


def test_table_style_only_changes_data_column_font_without_mutating_values(qtbot):
    apply_table_style = _api("src.ui.theme", "apply_table_style")
    table = _table(qtbot)
    flags = table.item(0, 1).flags()
    apply_table_style(table, data_columns=(1,))
    apply_table_style(table, data_columns=(1,))
    assert table.item(0, 0).text() == "读取状态"
    assert table.item(0, 1).text() == "22 F1 90"
    assert table.item(0, 1).data(Qt.ItemDataRole.UserRole) == b"\x22\xf1\x90"
    assert table.item(0, 1).flags() == flags
    for column in (0, 1):
        option = QStyleOptionViewItem()
        option.initFrom(table)
        index = table.model().index(0, column)
        delegate = table.itemDelegateForColumn(column) or table.itemDelegate()
        delegate.initStyleOption(option, index)
        if column == 1:
            assert option.font.fixedPitch()
            assert option.font.styleHint() == QFont.StyleHint.Monospace
        else:
            assert option.font == table.font()
    assert table.horizontalHeaderItem(1).data(Qt.ItemDataRole.FontRole) is None


def test_table_data_delegate_preserves_edit_contract_and_raw_bytes(qtbot):
    apply_table_style = _api("src.ui.theme", "apply_table_style")
    table = _table(qtbot)
    apply_table_style(table, data_columns=(1,))
    index = table.model().index(0, 1)
    option = QStyleOptionViewItem()
    option.initFrom(table)
    delegate = table.itemDelegateForColumn(1) or table.itemDelegate()
    editor = delegate.createEditor(table, option, index)
    assert isinstance(editor, QLineEdit)
    delegate.setEditorData(editor, index)
    assert editor.text() == "22 F1 90"
    editor.setText("22 F1 91")
    delegate.setModelData(editor, table.model(), index)
    assert table.item(0, 1).text() == "22 F1 91"
    assert table.item(0, 1).data(Qt.ItemDataRole.UserRole) == b"\x22\xf1\x90"


def test_minimum_window_keeps_error_actions_and_complete_data_rows_visible(qtbot, qapp, tmp_path):
    from src.application.app_container import AppContainer
    from src.ui.main_window import PAGE_DEFINITIONS

    container = AppContainer(tmp_path)
    window = container.create_window(ui_demo=True)
    qtbot.addWidget(window)
    try:
        window.resize(1080, 680)
        window.show()
        qtbot.waitUntil(lambda: window.pages.count() == len(PAGE_DEFINITIONS))
        editor, logs = window.command_editor, window.communication
        editor.command_input.setText("GG")
        editor.add_button.click()
        editor.addressing_selector.functional_button.click()
        editor.keep_alive_button.click()
        qapp.processEvents()
        qtbot.waitUntil(editor.error_label.isVisible)

        assert window.size() == QSize(1080, 680), "Minimum layout forced the window to grow"
        assert editor.command_input.text() == "GG"
        assert editor.error_label.text()
        assert editor.error_label.height() >= editor.error_label.fontMetrics().height()
        assert editor.addressing_button.isChecked()
        assert editor.keep_alive_button.isChecked()

        controls = (
            editor.command_input, editor.error_label, editor.send_button,
            editor.add_button, editor.addressing_selector.physical_button,
            editor.addressing_selector.functional_button, editor.keep_alive_button,
            editor.batch_button, *editor.action_buttons.values(),
            logs.copy_button, logs.save_button, logs.clear_button,
        )
        for control in controls:
            name = control.objectName() or getattr(control, "text", lambda: "")()
            assert control.isVisibleTo(window), f"Hidden minimum-window control: {name}"
            ancestor = control.parentWidget()
            while ancestor is not None:
                mapped = QRect(control.mapTo(ancestor, QPoint()), control.size())
                assert ancestor.rect().contains(mapped), f"Clipped minimum-window control: {name}"
                if ancestor is window:
                    break
                ancestor = ancestor.parentWidget()
        for table in (editor.table, logs.table):
            assert table.rowCount() > 0
            assert table.viewport().height() >= table.rowHeight(0), (
                f"No complete data row remains visible in {table.objectName()}"
            )
    finally:
        window.close()
        container.shutdown()
    assert not container.file_logging.thread.is_alive()


def test_collapsed_navigation_retains_names_in_qt_accessibility_tree(qtbot, tmp_path):
    from src.application.app_container import AppContainer

    names = ("UDS手动", "UDS自动化", "DoIP刷写", "DTC测试", "DoIP手动", "DoIP自动化")
    container = AppContainer(tmp_path)
    window = container.create_window(ui_demo=True)
    qtbot.addWidget(window)
    try:
        window.show()
        qtbot.waitUntil(lambda: window.pages.count() == len(names))
        window.collapse_button.click()
        assert all(window.navigation.item(index).text() == "" for index in range(len(names)))
        interface = QAccessible.queryAccessibleInterface(window.navigation)
        assert interface is not None
        assert interface.childCount() == len(names)
        actual = tuple(interface.child(index).text(QAccessible.Text.Name) for index in range(len(names)))
        assert actual == names
    finally:
        window.close()
        container.shutdown()
    assert not container.file_logging.thread.is_alive()
