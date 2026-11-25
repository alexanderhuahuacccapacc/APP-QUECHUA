import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


def configure_fonts(application: QApplication) -> None:
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
        application.setFont(QFont("Segoe UI", 10))


def configure_theme(application: QApplication) -> None:
    """Use a low-glare palette in every window, including login and the wizard."""
    configure_fonts(application)
    application.setStyle("Fusion")
    application.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#191f28",
        QPalette.ColorRole.WindowText: "#dce3ed",
        QPalette.ColorRole.Base: "#121821",
        QPalette.ColorRole.AlternateBase: "#242d39",
        QPalette.ColorRole.Text: "#dce3ed",
        QPalette.ColorRole.Button: "#293443",
        QPalette.ColorRole.ButtonText: "#dce3ed",
        QPalette.ColorRole.Highlight: "#286e70",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#293443",
        QPalette.ColorRole.ToolTipText: "#dce3ed",
        QPalette.ColorRole.PlaceholderText: "#98a6b9",
        QPalette.ColorRole.Link: "#8fd1ce",
        QPalette.ColorRole.LinkVisited: "#c3b5e8",
        QPalette.ColorRole.Light: "#455267",
        QPalette.ColorRole.Midlight: "#354254",
        QPalette.ColorRole.Mid: "#303c4d",
        QPalette.ColorRole.Dark: "#10151d",
        QPalette.ColorRole.Shadow: "#0b1017",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#8995a7"))
    application.setPalette(palette)
    checkmark = (Path(__file__).resolve().parents[1] / "resources/dark-check.svg").as_posix()
    application.setStyleSheet("""
        QWidget { color: #dce3ed; }
        QDialog, QMainWindow, QWizard, QWizardPage, QScrollArea, QWidget#workspace {
            background-color: #191f28;
        }
        QScrollArea > QWidget > QWidget { background-color: #191f28; }
        QLabel, QCheckBox, QRadioButton { background-color: transparent; }
        QGroupBox { background-color: #202936; border: 1px solid #39475a;
                    border-radius: 9px; margin-top: 12px; padding: 18px 12px 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
        QLineEdit, QTextEdit, QPlainTextEdit, QListView, QTreeView, QTableView,
        QAbstractSpinBox, QComboBox {
            background-color: #121821; color: #dce3ed; border: 1px solid #455267;
            border-radius: 5px; padding: 6px; selection-background-color: #286e70;
            selection-color: #ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
            border-color: #80c9c6;
        }
        QComboBox QAbstractItemView { background-color: #202936; color: #dce3ed;
                                    selection-background-color: #286e70; }
        QPushButton { background-color: #293443; color: #dce3ed; border: 1px solid #455267;
                      border-radius: 6px; min-height: 26px; padding: 5px 12px; }
        QPushButton:hover { background-color: #354558; border-color: #80c9c6; }
        QPushButton:pressed { background-color: #203b43; }
        QPushButton:default { border: 2px solid #80c9c6; }
        QPushButton:disabled { background-color: #222b37; color: #8995a7;
                               border-color: #354254; }
        QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
        QCheckBox::indicator { background-color: #121821; border: 1px solid #8192aa;
                               border-radius: 3px; }
        QCheckBox::indicator:checked { background-color: #286e70;
                                       border-color: #80c9c6; image: url("@CHECKMARK@"); }
        QCheckBox::indicator:disabled { border-color: #526176; }
        QTabWidget::pane { border: 1px solid #39475a; }
        QTabBar::tab { background-color: #222b37; color: #b6c2d2; padding: 10px 16px; }
        QTabBar::tab:selected { background-color: #293846; color: #a3e0dc;
                               border-bottom: 3px solid #80c9c6; }
        QMenuBar, QMenu, QStatusBar, QToolBar { background-color: #202936; color: #dce3ed; }
        QMenuBar::item:selected, QMenu::item:selected { background-color: #286e70; }
        QHeaderView::section { background-color: #293443; color: #dce3ed;
                               border: 1px solid #39475a; padding: 6px; }
        QToolTip { background-color: #293443; color: #dce3ed;
                   border: 1px solid #61748b; padding: 6px; }
        QProgressBar { background-color: #121821; border: 1px solid #455267;
                        color: #dce3ed; text-align: center; }
        QProgressBar::chunk { background-color: #286e70; }
        QScrollBar { background-color: #191f28; }
        QScrollBar::handle { background-color: #526176; border-radius: 5px; min-height: 20px; }
    """.replace("@CHECKMARK@", checkmark))
