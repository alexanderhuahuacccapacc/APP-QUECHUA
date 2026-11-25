"""Native Qt styling for the Xandar desktop design."""

from collections import deque

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def stylesheet(dark: bool) -> str:
    if dark:
        bg, surface, raised, line = "#111a22", "#18232d", "#223240", "#2f4352"
        text, muted, accent, accent_text, error = "#e8f0ef", "#9db3ae", "#2aa198", "#06201d", "#f2b45a"
    else:
        bg, surface, raised, line = "#f3f6f5", "#ffffff", "#e8efed", "#c9d6d2"
        text, muted, accent, accent_text, error = "#14211f", "#4d625e", "#0f766e", "#ffffff", "#a53a13"
    return f"""
        QMainWindow, QWidget#workspace {{ background: {bg}; }}
        QWidget {{ color: {text}; }}
        QLabel#modelName, QLabel#routeNote, QLabel#charCount, QLabel#libraryNote,
        QLabel#cardTranslation {{ color: {muted}; }}
        QLabel#wordConfidence {{ color: {muted}; }}
        QLabel#offlineBadge {{ color: {accent}; background: {raised}; border: 1px solid {line};
            padding: 6px 13px; border-radius: 15px; font-weight: 700; }}
        QTabWidget::pane {{ background: {surface}; border: 1px solid {line}; border-radius: 10px; }}
        QTabBar::tab {{ background: transparent; color: {muted}; border: none;
            border-bottom: 3px solid transparent; padding: 9px 16px; }}
        QTabBar::tab:selected {{ color: {text}; border-bottom-color: {accent}; font-weight: 700; }}
        QPushButton {{ background: {raised}; color: {text}; border: 1px solid {line};
            border-radius: 8px; padding: 6px 12px; }}
        QPushButton:hover, QPushButton:focus, QLineEdit:focus, QComboBox:focus,
        QPlainTextEdit:focus {{ border-color: {accent}; }}
        QPushButton:disabled {{ color: {muted}; background: {surface}; border-style: dashed; }}
        QPushButton#chip {{ border-radius: 13px; padding: 5px 15px; }}
        QPushButton#primaryButton, QPushButton#chip:checked, QPushButton#recordButton {{
            background: {accent}; color: {accent_text}; border-color: {accent}; font-weight: 700; }}
        QPushButton#primaryButton:disabled, QPushButton#recordButton:disabled {{
            background: {raised}; color: {muted}; border-color: {line}; }}
        QPushButton#recordButton {{ border-radius: 21px; min-height: 30px; padding: 6px 17px; }}
        QPushButton#recordButton[recording="true"] {{
            background: #b52230; color: #ffffff; border-color: #b52230;
        }}
        QPushButton#swapButton {{ padding: 4px 8px; }}
        QLabel#languageBadge {{ background: {bg}; border: 1px solid {line}; border-radius: 8px;
            padding: 7px 13px; font-weight: 700; }}
        QFrame#recorder, QLabel#operationStatus, QFrame#phraseCard {{
            background: {bg}; border: 1px solid {line}; border-radius: 10px; }}
        QLabel#operationStatus {{ padding: 7px 10px; font-weight: 650; }}
        QLabel#operationStatus[error="true"] {{ border-color: {error}; color: {error}; }}
        QLabel#recordTime {{ color: {muted}; font-size: 14pt; }}
        QComboBox, QPlainTextEdit, QLineEdit, QTextEdit {{
            background: {bg}; color: {text}; border: 1px solid {line}; border-radius: 8px; padding: 6px;
            selection-background-color: {accent}; selection-color: {accent_text}; }}
        QComboBox QAbstractItemView {{ background: {surface}; color: {text}; }}
        QListWidget#phraseList {{ background: {surface}; border: 0; outline: 0; }}
        QListWidget#phraseList::item:selected {{ background: transparent; }}
        QFrame#phraseCard:hover {{ border-color: {accent}; }}
        QLabel#toast {{ background: {text}; color: {bg}; border-radius: 12px; padding: 6px 14px; }}
        QProgressBar {{ background: {raised}; border: none; border-radius: 3px; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 3px; }}
    """


def swap_icon(dark: bool) -> QIcon:
    pixmap = QPixmap(44, 44)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#e8f0ef" if dark else "#14211f"), 1.6))
    for x1, y1, x2, y2 in ((3, 7, 18, 7), (14, 3, 18, 7), (14, 11, 18, 7),
                           (19, 15, 4, 15), (8, 11, 4, 15), (8, 19, 4, 15)):
        painter.drawLine(x1, y1, x2, y2)
    painter.end()
    return QIcon(pixmap)


class WaveMeter(QWidget):
    """Show the last 28 measured microphone peaks."""

    def __init__(self) -> None:
        super().__init__()
        self.peaks: deque[float] = deque([0.0] * 28, maxlen=28)
        self.active = False
        self.dark = True
        self.setMinimumWidth(85)
        self.setFixedHeight(30)
        self.setAccessibleName("Nivel del micrófono")

    def begin(self, active: bool) -> None:
        self.active = active
        self.peaks.extend([0.0] * 28)
        self.update()

    def add_peak(self, value: float) -> None:
        self.peaks.append(value)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e34f59" if self.active else "#2f4352" if self.dark else "#c9d6d2"))
        pitch = self.width() / len(self.peaks)
        for i, peak in enumerate(self.peaks):
            height = max(4, (self.height() - 2) * peak)
            painter.drawRoundedRect(QRectF(i * pitch, self.height() - height, max(1, pitch - 2), height), 1, 1)
