"""DS-01 shared desktop tokens, data presentation and locally drawn icons."""

from string import Template
from types import MappingProxyType
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QStyledItemDelegate


COLORS = MappingProxyType({
    "ink": "#263C50", "canvas": "#F2F5F7", "surface": "#FFFFFF",
    "primary": "#2458D5", "muted": "#627488", "border": "#D8E1E8",
    "selected": "#EAF0FC", "hover": "#F3F6FB", "disabled": "#8A99A8",
    "sidebar_text": "#D9E4EF", "sidebar_active": "#34516B",
    "muted_canvas": "#5F7185", "sidebar_accent": "#8FB4FF",
    "success": "#28785D", "warning": "#936215", "danger": "#B94141",
})
SPACE = MappingProxyType({"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32})
METRICS = MappingProxyType({
    "control": 32, "input": 40, "row": 32, "header": 32, "radius": 4,
    "title": 36, "sidebar": 200, "sidebar_collapsed": 64, "navigation": 44,
    "connection": 64, "splitter": 4, "log_min": 192,
})


def apply_application_theme(app) -> None:
    """Use the same Fusion fallback palette for native widgets and preview rendering."""
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(13)
    app.setFont(font)
    palette = QPalette()
    for role, token in ((QPalette.ColorRole.Window, "canvas"), (QPalette.ColorRole.WindowText, "ink"),
                        (QPalette.ColorRole.Base, "surface"), (QPalette.ColorRole.AlternateBase, "hover"),
                        (QPalette.ColorRole.Text, "ink"), (QPalette.ColorRole.Button, "surface"),
                        (QPalette.ColorRole.ButtonText, "ink"), (QPalette.ColorRole.Highlight, "primary"),
                        (QPalette.ColorRole.HighlightedText, "surface")):
        palette.setColor(role, QColor(COLORS[token]))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(COLORS["disabled"]))
    app.setPalette(palette)


def data_font(size: int = 13) -> QFont:
    font = QFont()
    font.setFamilies(["Consolas", "Cascadia Mono", "monospace"])
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setPixelSize(size)
    return font


class _DataColumnDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.font = data_font()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if editor is not None:
            editor.setProperty("data", True)
            editor.setFont(data_font())
        return editor


def apply_table_style(table, *, data_columns=()) -> None:
    """Style view/delegates only; values, metadata and edit flags remain owned by callers."""
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setDefaultSectionSize(METRICS["row"])
    table.horizontalHeader().setFixedHeight(METRICS["header"])
    for column in data_columns:
        if not 0 <= column < table.columnCount():
            raise ValueError(f"Data column outside table: {column}")
        if not isinstance(table.itemDelegateForColumn(column), _DataColumnDelegate):
            table.setItemDelegateForColumn(column, _DataColumnDelegate(table))


_PATHS = {
    "terminal": '<path d="m5 6 5 6-5 6M13 18h6"/>',
    "play": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m10 8 6 4-6 4z"/>',
    "flash": '<path d="m13 2-8 12h6l-1 8 9-13h-6z"/>',
    "dtc": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 8 8 8m0-8-8 8"/>',
    "socket": '<path d="M8 3v5m8-5v5M5 8h14v4a7 7 0 0 1-14 0zM12 19v3"/>',
    "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
    "hardware": '<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
    "send": '<path d="m3 3 19 9-19 9 4-9zM7 12h15"/>',
    "parse": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13l-2 2 2 2m8-4 2 2-2 2m-3-5-2 6"/>',
    "capture": '<rect x="3" y="5" width="13" height="14" rx="3"/><path d="m16 10 5-3v10l-5-3"/>',
    "collapse": '<path d="M4 4v16m15-14-6 6 6 6M7 12h6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3h.01"/>',
    "chevron": '<path d="m8 5 7 7-7 7"/>',
}


def icon(name: str, color: str = COLORS["muted"]) -> QIcon:
    body = _PATHS.get(name, _PATHS["terminal"])
    result = QIcon()
    for mode, stroke in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, COLORS["disabled"])):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
               f'viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="1.7" '
               f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(svg.encode())).render(painter)
        painter.end()
        result.addPixmap(pixmap, mode)
    return result


_ASSETS = Path(__file__).resolve().parent / "assets"

STYLESHEET = Template("""
    QWidget { font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI';
              font-size: 13px; color: $ink; }
    QMainWindow, QDialog { background: $surface; }
    QFrame#windowFrame { border: 1px solid $border; background: $surface; }
    QFrame#titleBar { background: $surface; border-bottom: 1px solid $border; }
    QLabel#windowTitle { color: $muted; font-size: 12px; }
    QLabel#demoBadge { color: $warning; background: $canvas; border-radius: 4px;
                       padding: 3px 8px; font-size: 11px; }
    QWidget#workspace { background: $canvas; }
    QStackedWidget#workspacePages, QWidget#communicationPanel { background: $surface; }
    QFrame#sidebar { background: $ink; border: none; }
    QListWidget#navigation { border: none; background: transparent; outline: none; }
    QListWidget#navigation::item { height: 44px; padding-left: 12px; margin: 2px 8px;
                                  border-radius: 4px; color: $sidebar_text; border-left: 3px solid transparent; }
    QListWidget#navigation::item:selected { background: $sidebar_active; color: $surface;
                                           border-left-color: $sidebar_accent; }
    QListWidget#navigation::item:hover:!selected { background: $sidebar_active; }
    QListWidget#navigation:focus { border: 1px solid $sidebar_accent; }
    QPushButton { background: $surface; border: 1px solid $border; border-radius: 4px;
                  padding: 6px 12px; min-height: 18px; max-height: 18px; }
    QPushButton:hover { background: $hover; border-color: $muted; }
    QPushButton:pressed { background: $selected; }
    QPushButton:focus { border: 1px solid $primary; }
    QPushButton:disabled { color: $disabled; background: $canvas; border-color: $border; }
    QPushButton[role='primary'] { background: $primary; border-color: $primary; color: $surface; }
    QPushButton[role='primary']:hover { background: $ink; border-color: $ink; }
    QPushButton[role='primary']:focus { border: 1px solid $ink; }
    QPushButton[role='primary']:disabled { background: $canvas; border-color: $border; color: $disabled; }
    QPushButton[role='connection'] { color: $primary; border-color: $primary; }
    QPushButton[role='connection']:disabled { color: $disabled; border-color: $border; }
    QPushButton[role='quiet'] { background: transparent; border-color: transparent; }
    QPushButton[role='quiet']:hover { background: $hover; border-color: $border; }
    QPushButton[role='danger'] { color: $danger; background: transparent; border-color: transparent; }
    QPushButton[role='danger']:hover { background: $hover; border-color: $danger; }
    QPushButton[role='danger']:disabled { color: $disabled; }
    QPushButton[role='quiet']:focus, QPushButton[role='danger']:focus { border-color: $primary; }
    QPushButton[role='segment'] { padding: 6px 12px; background: $canvas; color: $muted_canvas; }
    QPushButton[role='segment']:checked { background: $selected; color: $primary; border-color: $primary; }
    QPushButton[role='segment']:focus { border: 1px solid $ink; }
    QPushButton[role='segment']:disabled { color: $disabled; background: $canvas; border-color: $border; }
    QPushButton[large='true'] { min-height: 26px; max-height: 26px; }
    QPushButton[role='nav'], QPushButton#collapseButton {
        text-align: left; background: transparent; border: 1px solid transparent;
        padding: 12px 16px; color: $sidebar_text; min-height: 18px; max-height: 18px; }
    QPushButton[role='nav']:hover, QPushButton#collapseButton:hover { background: $sidebar_active; }
    QPushButton[role='nav']:focus, QPushButton#collapseButton:focus { border-color: $sidebar_accent; }
    QToolButton { border: 1px solid transparent; background: transparent; border-radius: 4px; padding: 4px; }
    QToolButton:hover { background: $hover; }
    QToolButton:focus { border-color: $primary; }
    QToolButton#closeButton:hover { background: $danger; color: $surface; }
    QFrame#connectionBar { border-bottom: 1px solid $border; background: $surface; }
    QFrame#toolbarDivider { color: $border; }
    QLabel#projectBadge { color: $ink; background: $canvas; border-radius: 4px; padding: 6px 12px; }
    QLabel#connectionBadge { color: $muted; padding: 6px 0px 6px 12px; }
    QLabel#connectionBadge[connected='true'] { color: $success; }
    QLabel#sectionTitle { font-size: 14px; font-weight: 600; color: $ink; }
    QLabel#pageTitle { font-size: 16px; font-weight: 600; color: $ink; }
    QLabel#muted { color: $muted; font-size: 12px; }
    QLabel#validationError { color: $danger; font-size: 12px; }
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        border: 1px solid $border; border-radius: 4px; background: $surface;
        padding: 6px 8px; selection-background-color: $selected; selection-color: $ink; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { min-height: 18px; max-height: 18px; }
    QLineEdit[large='true'] { min-height: 26px; max-height: 26px; font-size: 15px; }
    QWidget[data='true'] { font-family: 'Consolas', 'Cascadia Mono', monospace; font-size: 13px; }
    QLineEdit[data='true'][large='true'] { font-size: 15px; }
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QComboBox:focus { border-color: $primary; }
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
        color: $disabled; background: $canvas; }
    QLineEdit:read-only { background: $canvas; }
    QComboBox::drop-down { width: 24px; border: none; border-left: 1px solid $border; }
    QComboBox::down-arrow { image: url('$arrow_down'); width: 12px; height: 12px; }
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        subcontrol-origin: border; subcontrol-position: top right; width: 24px;
        border-left: 1px solid $border; border-bottom: 1px solid $border; border-top-right-radius: 4px; }
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-origin: border; subcontrol-position: bottom right; width: 24px;
        border-left: 1px solid $border; border-bottom-right-radius: 4px; }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: $selected; }
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url('$arrow_up'); width: 12px; height: 8px; }
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url('$arrow_down'); width: 12px; height: 8px; }
    QCheckBox { spacing: 8px; min-height: 28px; }
    QCheckBox:focus { color: $primary; }
    QTableWidget, QTreeWidget { border: 1px solid $border; background: $surface;
        alternate-background-color: $hover; gridline-color: $border;
        selection-background-color: $selected; selection-color: $ink; }
    QTableWidget:focus, QTreeWidget:focus { border-color: $primary; }
    QHeaderView::section { background: $canvas; color: $muted_canvas; border: none;
        border-bottom: 1px solid $border; padding: 4px 8px; font-size: 12px; }
    QTableWidget::item { padding: 4px 8px; border: none; }
    QTableWidget::item:selected { background: $selected; color: $ink; }
    QFrame#card { background: $surface; border: none; border-top: 1px solid $border; border-radius: 0; }
    QScrollArea, QScrollArea > QWidget > QWidget { background: $surface; border: none; }
    QTabWidget::pane { border: none; border-top: 1px solid $border; }
    QTabBar::tab { background: transparent; padding: 8px 16px; color: $muted;
                   border-bottom: 2px solid transparent; }
    QTabBar::tab:selected { color: $primary; border-bottom-color: $primary; }
    QTabBar::tab:hover { background: $hover; }
    QTabBar::tab:focus { color: $ink; }
    QSplitter::handle:horizontal, QSplitter::handle:vertical { background: $canvas; }
    QSplitter::handle:hover { background: $border; }
    QStatusBar { background: $surface; border-top: 1px solid $border; color: $muted; font-size: 11px; }
    QScrollBar:vertical { background: $canvas; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 24px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: $canvas; height: 10px; }
    QScrollBar::handle:horizontal { background: $border; border-radius: 4px; min-width: 24px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QProgressBar { border: none; background: $canvas; border-radius: 4px; height: 8px; text-align: center; }
    QProgressBar::chunk { background: $primary; border-radius: 4px; }
    QFrame#toast { background: $surface; border: 1px solid $success; border-radius: 16px; }
    QFrame#toast QLabel { color: $success; }
    QToolTip { background: $ink; color: $surface; border: none; padding: 6px 8px; }
""").substitute(dict(COLORS, arrow_down=(_ASSETS / "chevron-down.svg").as_posix(),
                      arrow_up=(_ASSETS / "chevron-up.svg").as_posix()))
