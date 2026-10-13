"""Check UI draft interactions without loading project data or executing IO."""

import pytest
from PySide6.QtWidgets import QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget

from src.ui.workspace_pages import create_workspace_page


_UNAVAILABLE_ACTIONS = {
    1: (
        "loadScriptsButton", "removeScriptButton", "exportReportButton",
        "startAutomationButton", "pauseAutomationButton", "resumeAutomationButton",
        "stopAutomationButton",
    ),
    2: (
        "loadFirmwareButton", "loadFlashStepsButton", "moveFirmwareUpButton",
        "moveFirmwareDownButton", "removeFirmwareButton", "startFlashButton",
        "stopFlashButton", "retryFlashButton",
    ),
    3: ("readDtcButton", "clearDtcButton", "readDtcSnapshotButton", "readDtcExtendedButton"),
    4: ("connectPoolSocketButton", "closePoolSocketButton", "sendDoipButton"),
    5: (
        "loadScriptsButton", "removeScriptButton", "exportReportButton",
        "startAutomationButton", "pauseAutomationButton", "resumeAutomationButton",
        "stopAutomationButton",
    ),
}


@pytest.mark.parametrize("index", (1, 2, 3, 4, 5))
def test_unimplemented_actions_are_unavailable_and_results_start_empty(qtbot, index):
    page = create_workspace_page(index)
    qtbot.addWidget(page)
    for name in _UNAVAILABLE_ACTIONS[index]:
        button = page.findChild(QPushButton, name)
        assert button is not None
        assert not button.isEnabled()
        assert button.toolTip()
    assert all(table.rowCount() == 0 for table in page.findChildren(QTableWidget))
    assert all(tree.topLevelItemCount() == 0 for tree in page.findChildren(QTreeWidget))


def test_raw_mode_preserves_the_draft_and_restores_editable_fields(qtbot):
    page = create_workspace_page(4)
    qtbot.addWidget(page)
    page.payload_type.setEditText("0x9000")
    page.version.setCurrentText("0x03")
    page.source_address.setText("ABCD")
    page.target_address.setText("0123")
    page.payload.setPlainText("02 FD 00 05")
    page.raw_mode.setChecked(True)
    fields = (page.payload_type, page.version, page.source_address, page.target_address)
    assert all(not field.isEnabled() for field in fields)
    assert page.socket_choice.isEnabled()
    assert page.payload.isEnabled()
    assert "完整" in page.payload_caption.text()
    page.raw_mode.setChecked(False)
    assert all(field.isEnabled() for field in fields)
    assert page.payload_type.currentText() == "0x9000"
    assert page.version.currentText() == "0x03"
    assert page.source_address.text() == "ABCD"
    assert page.target_address.text() == "0123"
    assert page.payload.toPlainText() == "02 FD 00 05"


@pytest.mark.parametrize("text, count", (("02 FD\n00 05", 4), ("00\tFF", 2), (" \n", 0)))
def test_hex_byte_count_updates_without_sending(qtbot, text, count):
    page = create_workspace_page(4)
    qtbot.addWidget(page)
    page.payload.setPlainText(text)
    assert page.byte_count.text().split(" ", 1)[0] == str(count)
    assert page.payload.toPlainText() == text
    assert not page.findChild(QPushButton, "sendDoipButton").isEnabled()


@pytest.mark.parametrize("text", ("0", "0G", "0x02"))
def test_invalid_hex_is_reported_and_clear_only_clears_the_payload(qtbot, text):
    page = create_workspace_page(4)
    qtbot.addWidget(page)
    page.source_address.setText("ABCD")
    page.payload.setPlainText(text)
    assert "无效" in page.byte_count.text()
    clear_button = page.findChild(QPushButton, "clearDoipInputButton")
    assert clear_button.isEnabled()
    clear_button.click()
    assert page.payload.toPlainText() == ""
    assert page.byte_count.text().startswith("0 ")
    assert page.source_address.text() == "ABCD"


def test_dtc_search_hides_rows_without_changing_result_data(qtbot):
    page = create_workspace_page(3)
    qtbot.addWidget(page)
    # These are explicitly test-owned records, never application demo results.
    records = (("ABCDEF", "Synthetic sensor A"), ("123456", "Synthetic sensor B"))
    page.dtc_table.setRowCount(len(records))
    for row, values in enumerate(records):
        for column, value in enumerate(values):
            page.dtc_table.setItem(row, column, QTableWidgetItem(value))
    page.search.setText("  abc  ")
    assert not page.dtc_table.isRowHidden(0)
    assert page.dtc_table.isRowHidden(1)
    page.search.setText("SENSOR b")
    assert page.dtc_table.isRowHidden(0)
    assert not page.dtc_table.isRowHidden(1)
    page.search.clear()
    assert not any(page.dtc_table.isRowHidden(row) for row in range(len(records)))
    actual = tuple(
        tuple(page.dtc_table.item(row, column).text() for column in (0, 1))
        for row in range(page.dtc_table.rowCount())
    )
    assert actual == records


@pytest.mark.parametrize("index", (1, 5))
def test_automation_views_and_run_parameters_are_local_drafts(qtbot, index):
    page = create_workspace_page(index)
    qtbot.addWidget(page)
    assert page.result_tabs.currentIndex() == 0
    assert page.rounds.value() == 1
    page.result_tabs.setCurrentIndex(1)
    page.rounds.setValue(3)
    page.phase_filter.setCurrentIndex(2)
    assert page.result_tabs.currentWidget() is page.results_table
    assert page.rounds.value() == 3
    assert page.phase_filter.currentIndex() == 2
    assert page.steps_table.rowCount() == page.results_table.rowCount() == 0
    assert not page.findChild(QPushButton, "startAutomationButton").isEnabled()
    if index == 1:
        assert page.keep_alive_filter.isChecked()
        page.keep_alive_filter.setChecked(False)
        assert not page.keep_alive_filter.isChecked()
