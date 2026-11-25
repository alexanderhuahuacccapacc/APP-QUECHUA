"""The ASUS2-only offline desktop workspace."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from math import log10
from pathlib import Path
from shutil import disk_usage
from textwrap import wrap
from threading import Event
from typing import Any

from PySide6.QtCore import (
    QElapsedTimer,
    QIODevice,
    QSaveFile,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.config import Config
from app.integrations.asus2 import Asus2Engines
from app.models.domain import Language
from app.services.asus2_local import PhraseLibrary, export_model, read_audio, speak_spanish
from app.services.audio import MicrophoneAudio
from app.services.interfaces import AudioInputError, Samples
from app.services.tts import MmsTTS
from app.ui.asus2_style import WaveMeter, stylesheet, swap_icon
from app.ui.theme import configure_theme
from app.ui.workers import Job

VARIANT = "Collao"
COMMON = (
    ("Saludos", "Allillanchu", "Hola, ¿cómo estás?"),
    ("Saludos", "Imaynallan kachkanki?", "¿Cómo te encuentras?"),
    ("Mercado", "Hayk’ataq kay?", "¿Cuánto cuesta esto?"),
    ("Saludos", "Sulpayki", "Gracias"),
    ("Emergencias", "Yanapaway, mana allinchu kani", "Ayúdame, no me siento bien"),
    ("Salud", "Hampi wasi maypi?", "¿Dónde está el centro de salud?"),
    ("Mercado", "Pisi llasayachiway", "Rebájame un poco"),
)


@dataclass
class Interpretation:
    text: str
    alternatives: list[str]
    scores: list[float] = field(default_factory=list)


class Asus2Desktop(QMainWindow):
    level_changed = Signal(float)
    audio_ready = Signal(object)

    def __init__(self, config: Config, *, companion_root: Path | None = None) -> None:
        super().__init__()
        self.config = config
        self.root = config.models_dir.resolve()
        self.companion_root = companion_root
        self.quechua_voice = MmsTTS(companion_root) if companion_root is not None else None
        directory = config.data_dir / "asus2"
        self.settings = QSettings(str(directory / "ajustes.ini"), QSettings.Format.IniFormat)
        self.library = PhraseLibrary(directory)
        self.engine: Asus2Engines | None = None
        self._reverse = False
        self.results: list[str] = []
        self.library_filter = "Todas"
        self.library_entries: list[dict[str, Any]] = []
        self.result_variant = VARIANT
        self.audio = MicrophoneAudio(config.max_record_seconds, config.silence_seconds)
        self.samples: Samples | None = None
        self.stop = Event()
        self.record_allowed = Event()
        self.recording = False
        self.job: Job | None = None
        self.job_success: Callable[[Any], None] | None = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.elapsed = QElapsedTimer()
        self.clock = QTimer(self, interval=100)
        self.clock.timeout.connect(self.update_timer)
        self.level_changed.connect(self.update_level)
        self.audio_ready.connect(self.accept_audio)
        self.setWindowTitle("Xandar · ASUS2 Mejorado")
        self.resize(1150, 780)
        self._build_interface()
        self._build_menu()
        self.apply_appearance()
        self.refresh_microphones()
        self.update_direction()
        self.refresh_library()
        QTimer.singleShot(0, self.load_model)

    def _build_interface(self) -> None:
        workspace = QWidget(objectName="workspace")
        self.setCentralWidget(workspace)
        centered = QHBoxLayout(workspace)
        centered.setContentsMargins(16, 14, 16, 18)
        content = QWidget()
        content.setMaximumWidth(1140)
        centered.addStretch()
        centered.addWidget(content, 20)
        centered.addStretch()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Xandar")
        title.setStyleSheet("font-size: 22pt; font-weight: 750")
        header.addWidget(title)
        header.addWidget(QLabel("Modelo ASUS2 Mejorado", objectName="modelName"))
        header.addStretch()
        theme = QPushButton("Tema")
        theme.setToolTip("Cambiar entre tema claro y oscuro")
        theme.clicked.connect(lambda: self.dark_theme.trigger())
        header.addWidget(theme)
        offline = QLabel("100 % offline", objectName="offlineBadge")
        header.addWidget(offline)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        interpreter = QWidget()
        panel = QVBoxLayout(interpreter)
        panel.setContentsMargins(16, 14, 16, 14)
        panel.setSpacing(11)
        self.tabs.addTab(interpreter, "Intérprete")

        route = QHBoxLayout()
        self.source_language = QLabel("Quechua Collao", objectName="languageBadge")
        self.target_language = QLabel("Español", objectName="languageBadge")
        for badge in (self.source_language, self.target_language):
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setMinimumWidth(106)
        self.swap_button = QPushButton(objectName="swapButton")
        self.swap_button.setIconSize(QSize(22, 22))
        self.swap_button.setToolTip("Intercambiar idiomas (Ctrl+I)")
        self.swap_button.setAccessibleName("Intercambiar idiomas")
        self.swap_button.clicked.connect(self.swap_languages)
        route.addWidget(self.source_language)
        route.addWidget(self.swap_button)
        route.addWidget(self.target_language)
        route.addStretch()
        self.microphone = QComboBox()
        self.microphone.setAccessibleName("Micrófono")
        self.microphone.setMaximumWidth(310)
        self.microphone.setMinimumWidth(140)
        self.microphone.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        route.addWidget(self.microphone, 1)
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.refresh_microphones)
        route.addWidget(self.refresh_button)
        panel.addLayout(route)
        self.route_note = QLabel(wordWrap=True, objectName="routeNote")
        panel.addWidget(self.route_note)

        recorder = QFrame(objectName="recorder")
        audio_controls = QHBoxLayout(recorder)
        audio_controls.setContentsMargins(11, 10, 11, 10)
        self.record_button = QPushButton("●  Hablar en quechua", objectName="recordButton")
        self.record_button.setToolTip("Grabar o detener (Ctrl+Espacio)")
        self.record_button.clicked.connect(self.record_or_stop)
        self.record_button.setMinimumWidth(192)
        audio_controls.addWidget(self.record_button)
        self.time = QLabel("0:00", objectName="recordTime")
        self.time.setMinimumWidth(44)
        self.time.setAccessibleName("Tiempo de grabación")
        audio_controls.addWidget(self.time)
        self.level = WaveMeter()
        audio_controls.addWidget(self.level, 1)
        self.file_button = QPushButton("Abrir audio…")
        self.file_button.clicked.connect(self.open_audio)
        audio_controls.addWidget(self.file_button)
        self.play_button = QPushButton("Reproducir audio")
        self.play_button.clicked.connect(self.play_audio)
        audio_controls.addWidget(self.play_button)
        panel.addWidget(recorder)

        self.status = QLabel(wordWrap=True, objectName="operationStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        panel.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        panel.addWidget(self.progress)

        editors = QHBoxLayout()
        input_column = QVBoxLayout()
        input_header = QHBoxLayout()
        self.input_label = QLabel("Quechua Collao")
        input_header.addWidget(self.input_label, 1)
        input_header.addWidget(self._copy_button(lambda: self.input.toPlainText()))
        input_column.addLayout(input_header)
        self.input = QPlainTextEdit()
        self.input.textChanged.connect(self.input_changed)
        self.input.setAccessibleName("Texto de entrada")
        input_column.addWidget(self.input, 1)
        counter_row = QHBoxLayout()
        self.confidence = QLabel(wordWrap=True, objectName="wordConfidence")
        counter_row.addWidget(self.confidence, 1)
        self.char_count = QLabel(f"0 / {self.config.max_text_chars}", objectName="charCount")
        counter_row.addWidget(self.char_count)
        input_column.addLayout(counter_row)
        editors.addLayout(input_column, 1)

        output_column = QVBoxLayout()
        output_header = QHBoxLayout()
        self.output_label = QLabel("Español")
        output_header.addWidget(self.output_label, 1)
        output_header.addWidget(self._copy_button(lambda: self.output.toPlainText()))
        self.speak_button = QPushButton("Escuchar")
        self.speak_button.clicked.connect(self.speak_output)
        output_header.addWidget(self.speak_button)
        output_column.addLayout(output_header)
        self.output = QPlainTextEdit(readOnly=True)
        self.output.setAccessibleName("Traducción")
        self.output.setPlaceholderText("Aquí aparecerá la traducción")
        output_column.addWidget(self.output, 1)
        self.alternatives = QWidget()
        self.alternatives.setMinimumHeight(28)
        self.alternative_layout = QHBoxLayout(self.alternatives)
        self.alternative_layout.setContentsMargins(0, 0, 0, 0)
        self.alternative_layout.addStretch()
        self.alternative_group = QButtonGroup(self.alternatives)
        self.alternative_group.idClicked.connect(self.select_alternative)
        output_column.addWidget(self.alternatives)
        editors.addLayout(output_column, 1)
        panel.addLayout(editors, 1)

        actions = QHBoxLayout()
        self.translate_button = QPushButton("Traducir", objectName="primaryButton")
        self.translate_button.setToolTip("Traducir (Ctrl+Enter)")
        self.translate_button.clicked.connect(self.translate_input)
        actions.addWidget(self.translate_button)
        self.favorite_button = QPushButton("Guardar favorita")
        self.favorite_button.clicked.connect(self.save_favorite)
        actions.addWidget(self.favorite_button)
        self.report_button = QPushButton("Reportar mala traducción")
        self.report_button.clicked.connect(self.report_translation)
        actions.addWidget(self.report_button)
        actions.addStretch()
        panel.addLayout(actions)

        self._build_library()
        self.toast = QLabel(self, objectName="toast")
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.setWordWrap(True)
        self.toast.setMaximumWidth(460)
        self.toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.toast.hide()
        self.toast_timer = QTimer(self, singleShot=True, interval=1700)
        self.toast_timer.timeout.connect(self.toast.hide)

    def _build_library(self) -> None:
        library_page = QWidget()
        library_layout = QVBoxLayout(library_page)
        library_layout.setContentsMargins(16, 14, 16, 14)
        tools = QHBoxLayout()
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Buscar frase")
        self.library_search.setAccessibleName("Buscar frase")
        self.library_search.setClearButtonEnabled(True)
        self.library_search.textChanged.connect(self.render_library)
        tools.addWidget(self.library_search, 1)
        clear = QPushButton("Borrar historial")
        clear.clicked.connect(self.clear_history)
        tools.addWidget(clear)
        library_layout.addLayout(tools)
        common = QHBoxLayout()
        group = QButtonGroup(self)
        for category in ("Todas", "Favoritas", "Historial", "Saludos", "Salud", "Mercado", "Emergencias"):
            button = QPushButton(category, checkable=True, objectName="chip")
            button.setChecked(category == self.library_filter)
            group.addButton(button)
            button.clicked.connect(lambda checked=False, name=category: self.filter_library(name))
            common.addWidget(button)
        common.addStretch()
        library_layout.addLayout(common)
        self.library_list = QListWidget(wordWrap=True, objectName="phraseList")
        self.library_list.setSpacing(4)
        self.library_list.itemActivated.connect(self.open_saved_phrase)
        library_layout.addWidget(self.library_list, 1)
        self.library_status = QLabel(wordWrap=True, objectName="libraryNote")
        library_layout.addWidget(self.library_status)
        self.tabs.addTab(library_page, "Frases e historial")

    def _build_menu(self) -> None:
        settings = self.menuBar().addMenu("Ajustes")
        self.microphone_permission = QAction("Permitir grabaciones", self, checkable=True)
        self.microphone_permission.setChecked(self.settings.value("microphone", False, type=bool))
        if self.microphone_permission.isChecked():
            self.record_allowed.set()
        self.microphone_permission.triggered.connect(self.set_microphone_permission)
        settings.addAction(self.microphone_permission)
        self.history_setting = QAction("Guardar historial local", self, checkable=True)
        self.history_setting.setChecked(self.settings.value("history", False, type=bool))
        self.history_setting.triggered.connect(self.set_history)
        settings.addAction(self.history_setting)
        settings.addAction("Borrar todo el historial…", self.clear_history)
        settings.addSeparator()
        settings.addAction("Tamaño de letra…", self.change_font)
        self.dark_theme = QAction("Modo oscuro", self, checkable=True)
        self.dark_theme.setChecked(self.settings.value("dark", True, type=bool))
        self.dark_theme.triggered.connect(self.change_theme)
        settings.addAction(self.dark_theme)
        self.reset_action = settings.addAction("Reiniciar modelo", self.load_model)
        settings.addAction("Exportar reportes…", self.export_reports)

        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addAction("Información del modelo", self.show_model)
        help_menu.addAction("Licencias y avisos", self.show_licenses)
        help_menu.addAction("Guía de instalación", self.show_installation)
        help_menu.addAction("Manual de uso", self.show_help)
        downloads = self.menuBar().addMenu("Modelo")
        self.export_model_action = downloads.addAction("Guardar copia del modelo…", self.save_model_copy)
        downloads.addAction("Abrir carpeta del modelo", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root))))

        self.record_shortcut = QAction("Grabar o detener", self, shortcut=QKeySequence("Ctrl+Space"))
        self.record_shortcut.triggered.connect(self.record_or_stop)
        self.addAction(self.record_shortcut)
        self.translate_shortcut = QAction("Traducir", self, shortcut=QKeySequence("Ctrl+Return"))
        self.translate_shortcut.triggered.connect(self.translate_input)
        self.addAction(self.translate_shortcut)
        self.swap_shortcut = QAction("Intercambiar idiomas", self, shortcut=QKeySequence("Ctrl+I"))
        self.swap_shortcut.triggered.connect(self.swap_languages)
        self.addAction(self.swap_shortcut)
        self.tabs.currentChanged.connect(self.update_controls)

    def _copy_button(self, getter: Callable[[], str]) -> QPushButton:
        button = QPushButton("Copiar")
        button.clicked.connect(lambda: self.copy_text(getter()))
        return button

    def copy_text(self, text: str) -> None:
        if text.strip():
            QApplication.clipboard().setText(text.strip())
            self.notify("Texto copiado.")
        else:
            self.notify("No hay texto para copiar.")

    def notify(self, text: str) -> None:
        self.toast.setText(text)
        self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2, self.height() - self.toast.height() - 26)
        self.toast.show()
        self.toast.raise_()
        self.toast_timer.start()

    @property
    def reverse(self) -> bool:
        return self._reverse

    @property
    def audio_supported(self) -> bool:
        return not self.reverse or bool(self.engine and self.engine.spanish_audio_available)

    def set_direction(self, reverse: bool) -> None:
        self._reverse = reverse
        self.update_direction()

    def swap_languages(self) -> None:
        if self.job:
            return
        source, translated = self.input.toPlainText(), self.output.toPlainText()
        self.set_direction(not self.reverse)
        if translated:
            self.input.setPlainText(translated)
            self.set_alternatives([source] if source else [])
        self.set_status("Idiomas intercambiados.")

    def update_direction(self) -> None:
        source, target = ("Español", "Quechua Collao") if self.reverse else ("Quechua Collao", "Español")
        self.source_language.setText(source)
        self.target_language.setText(target)
        self.input_label.setText(source)
        self.output_label.setText(target)
        if not self.recording:
            self.update_record_label()
        self.input.setPlaceholderText("Escribe en español o graba una frase" if self.reverse
                                      else "Escribe en quechua o graba una frase")
        self.update_route_note()
        self.clear_confidence()
        self.set_alternatives([])

    def update_route_note(self) -> None:
        if not self.reverse:
            self.route_note.setText("Traducción aproximada para Collao. Más detalles en Ayuda.")
        elif self.engine and not self.audio_supported:
            self.route_note.setText("Para usar audio en español, instala el reconocedor local indicado en Ayuda.")
        else:
            self.route_note.setText("Español → quechua es experimental para Collao.")

    def update_controls(self) -> None:
        idle = self.job is None
        ready = self.engine is not None
        for widget in (self.swap_button, self.microphone, self.refresh_button, self.alternatives):
            widget.setEnabled(idle)
        self.swap_shortcut.setEnabled(idle and self.tabs.currentIndex() == 0)
        self.input.setReadOnly(not idle)
        self.record_button.setEnabled(self.recording or (idle and ready and self.audio_supported))
        self.record_shortcut.setEnabled(self.record_button.isEnabled())
        self.file_button.setEnabled(idle and ready and self.audio_supported)
        self.play_button.setEnabled(idle and self.samples is not None)
        self.translate_button.setEnabled(idle and ready)
        self.translate_shortcut.setEnabled(self.translate_button.isEnabled())
        has_output = bool(self.output.toPlainText())
        voice_available = not self.reverse or bool(self.quechua_voice and self.quechua_voice.supports(Language.QUZ))
        self.speak_button.setEnabled(idle and has_output and voice_available)
        self.speak_button.setToolTip("" if voice_available else "Instala la voz Collao indicada en Ayuda.")
        self.favorite_button.setEnabled(idle and has_output)
        self.report_button.setEnabled(idle and has_output)
        self.reset_action.setEnabled(idle)
        self.export_model_action.setEnabled(idle and ready)

    def set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        self.refresh_style(self.status, "error", error)

    @staticmethod
    def refresh_style(widget: QWidget, name: str, value: bool) -> None:
        if widget.property(name) != value:
            widget.setProperty(name, value)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def start_job(self, operation: Callable[[], Any], success: Callable[[Any], None],
                  status: str, *, recording: bool = False) -> None:
        if self.job is not None:
            return
        self.recording = recording
        self.set_status(status)
        self.progress.setVisible(not recording)
        self.job_success = success
        self.job = Job(operation)
        self.job.signals.done.connect(self.finish_job)
        self.job.signals.failed.connect(self.fail_job)
        self.update_controls()
        self.pool.start(self.job)

    def finish_job(self, result: Any) -> None:
        callback = self.job_success
        self.end_job()
        if callback:
            callback(result)
        self.update_controls()

    def fail_job(self, message: str) -> None:
        self.end_job()
        self.set_status(message, error=True)
        if self.tabs.currentIndex() == 1:
            self.notify(message)
        self.update_controls()

    def end_job(self) -> None:
        self.end_recording()
        self.progress.hide()
        self.job = None
        self.job_success = None

    def load_model(self) -> None:
        def load() -> Asus2Engines:
            if self.engine is not None:
                self.engine.unload()
            return Asus2Engines(self.root, self.config.device, spanish_root=self.companion_root)

        def ready(engine: Asus2Engines) -> None:
            self.engine = engine
            self.update_route_note()
            self.set_status("ASUS2 listo. Graba una frase o escribe para traducir.")

        self.start_job(load, ready, "Preparando ASUS2…")

    def refresh_microphones(self) -> None:
        previous = self.microphone.currentData()
        self.microphone.clear()
        self.microphone.addItem("Micrófono predeterminado", None)
        for index, name in self.audio.input_devices():
            self.microphone.addItem(name, index)
        self.microphone.setCurrentIndex(max(0, self.microphone.findData(previous)))

    def may_record(self) -> bool:
        if not self.settings.contains("microphone"):
            answer = QMessageBox.question(
                self, "Permitir micrófono",
                "¿Permites que ASUS2 use el micrófono en esta laptop? La grabación queda en memoria durante la sesión. Puedes cambiar tu elección en Ajustes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            permitted = answer == QMessageBox.StandardButton.Yes
            self.microphone_permission.setChecked(permitted)
            self.set_microphone_permission(permitted)
        if not self.microphone_permission.isChecked():
            self.set_status("Para grabar, activa Permitir grabaciones en Ajustes.", error=True)
            return False
        return True

    def set_microphone_permission(self, allowed: bool) -> None:
        self.save_setting("microphone", allowed)
        if allowed:
            self.record_allowed.set()
        else:
            self.record_allowed.clear()
            if self.recording:
                self.record_or_stop()

    def record_or_stop(self) -> None:
        if self.recording:
            self.stop.set()
            self.recording = False
            self.record_button.setEnabled(False)
            self.record_shortcut.setEnabled(False)
            self.set_status("Terminando grabación…")
            return
        if self.job or not self.engine or not self.audio_supported or not self.may_record():
            return
        self.audio.device = self.microphone.currentData()
        self.stop.clear()
        self.samples = None
        self.clear_results()
        self.elapsed.start()
        self.time.setText("0:00")
        self.level.begin(True)
        self.clock.start()
        self.record_button.setText("■  Detener")
        self.record_button.setAccessibleName("Detener")
        self.refresh_style(self.record_button, "recording", True)
        reverse = self.reverse

        def capture() -> Interpretation:
            samples = self.audio.capture(self.stop, on_level=self.level_changed.emit)
            if not self.record_allowed.is_set():
                raise AudioInputError("Grabación descartada al retirar el permiso del micrófono.")
            return self.interpret_audio(samples, reverse=reverse)

        self.start_job(capture, self.show_interpretation, "Grabando…", recording=True)

    def update_timer(self) -> None:
        seconds = self.elapsed.elapsed() // 1000
        self.time.setText(f"{seconds // 60}:{seconds % 60:02d}")

    def update_level(self, level: float) -> None:
        if self.recording:
            db = 20 * log10(max(0.00001, level))
            self.level.add_peak(max(0.0, min(1.0, (db + 55) / 55)))

    def update_record_label(self) -> None:
        label = "Hablar en español" if self.reverse else "Hablar en quechua"
        self.record_button.setText(f"●  {label}")
        self.record_button.setAccessibleName(label)

    def end_recording(self) -> None:
        self.recording = False
        self.clock.stop()
        self.level.begin(False)
        self.update_record_label()
        self.refresh_style(self.record_button, "recording", False)

    def interpret_audio(self, samples: Samples, *, reverse: bool) -> Interpretation:
        assert self.engine is not None
        self.audio_ready.emit(samples)
        text, scores = self.engine.recognize(samples, reverse=reverse)
        return Interpretation(text, self.engine.translate_options(text, reverse=reverse), scores)

    def accept_audio(self, samples: Samples) -> None:
        self.samples = samples
        self.end_recording()
        self.set_status("Reconociendo y traduciendo… La primera frase puede tardar.")
        self.progress.show()
        self.update_controls()

    def open_audio(self) -> None:
        if self.job or not self.engine or not self.audio_supported:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.aiff *.aif);;Todos los archivos (*)"
        )
        if path:
            self.samples = None
            self.clear_results()
            reverse = self.reverse
            self.start_job(lambda: self.interpret_audio(read_audio(Path(path)), reverse=reverse),
                           self.show_interpretation, "Abriendo audio…")

    def play_audio(self) -> None:
        samples = self.samples
        if samples is not None:
            self.start_job(lambda: self.audio.play(samples), lambda _: self.set_status("Reproducción finalizada."),
                           "Reproduciendo audio…")

    def translate_input(self) -> None:
        engine = self.engine
        if self.job or engine is None:
            return
        text = self.input.toPlainText().strip()
        if not 1 <= len(text) <= self.config.max_text_chars:
            self.set_status(f"Escribe entre 1 y {self.config.max_text_chars} caracteres.", error=True)
            return
        reverse = self.reverse
        self.start_job(lambda: Interpretation(text, engine.translate_options(text, reverse=reverse)),
                       self.show_interpretation, "Traduciendo… La primera frase puede tardar.")

    def show_interpretation(self, result: Interpretation) -> None:
        self.result_variant = VARIANT
        if result.text != self.input.toPlainText():
            self.input.setPlainText(result.text)
        if result.scores:
            self.highlight_words(result.scores)
        self.set_alternatives(result.alternatives)
        if not result.alternatives:
            self.set_status("No se obtuvo una traducción. Revisa el texto o vuelve a grabar.", error=True)
            return
        self.set_status("Traducción lista.")
        if self.history_setting.isChecked():
            self.save_phrase("history")

    def set_alternatives(self, results: list[str]) -> None:
        self.results = results
        for button in self.alternative_group.buttons():
            self.alternative_group.removeButton(button)
            self.alternative_layout.removeWidget(button)
            button.deleteLater()
        if len(results) > 1:
            for index in range(len(results)):
                label = "Principal" if index == 0 else f"Alternativa {index}"
                button = QPushButton(label, checkable=True, objectName="chip")
                button.setToolTip(results[index])
                self.alternative_group.addButton(button, index)
                button.setChecked(index == 0)
                self.alternative_layout.insertWidget(index, button)
        self.select_alternative(0)

    def select_alternative(self, index: int) -> None:
        self.output.setPlainText(self.results[index] if 0 <= index < len(self.results) else "")
        self.update_controls()

    def clear_results(self) -> None:
        self.input.clear()
        self.set_alternatives([])

    def clear_confidence(self) -> None:
        self.input.setExtraSelections([])
        self.confidence.clear()

    def input_changed(self) -> None:
        length = len(self.input.toPlainText())
        self.char_count.setText(f"{length} / {self.config.max_text_chars}")
        self.clear_confidence()
        self.set_alternatives([])

    def highlight_words(self, scores: list[float]) -> None:
        selections = []
        cursor = QTextCursor(self.input.document())
        for score in scores:
            while not cursor.atEnd() and self.input.document().characterAt(cursor.position()).isspace():
                cursor.movePosition(QTextCursor.MoveOperation.Right)
            cursor.setPosition(cursor.position())
            while not cursor.atEnd() and not self.input.document().characterAt(cursor.position()).isspace():
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
            if score < 0.70 and cursor.hasSelection():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(cursor)
                selection.format.setBackground(QColor("#ffe195"))
                selection.format.setForeground(QColor("#352500"))
                selections.append(selection)
            cursor.clearSelection()
        self.input.setExtraSelections(selections)
        average = sum(scores) / len(scores)
        self.confidence.setText(f"Confianza orientativa {average:.0%}. El amarillo marca palabras dudosas.")

    def speak_output(self) -> None:
        self.speak_text(self.output.toPlainText(), quechua=self.reverse)

    def speak_text(self, text: str, *, quechua: bool) -> None:
        if self.job or not text.strip():
            return
        if not quechua:
            self.start_job(lambda: speak_spanish(text), self.speech_finished, "Leyendo en español…")
            return
        voice = self.quechua_voice
        if voice is None or not voice.supports(Language.QUZ):
            self.notify("La voz Collao requiere el modelo indicado en Ayuda.")
            return

        def play() -> None:
            for chunk in wrap(text, width=500):
                speech = voice.synthesize(chunk, Language.QUZ)
                if speech.samples is None:
                    raise AudioInputError("No se pudo generar la voz Collao. Comprueba el modelo de voz.")
                self.audio.play(speech.samples, speech.sample_rate)

        self.start_job(play, self.speech_finished, "Leyendo en quechua Collao…")

    def speech_finished(self, _: Any) -> None:
        self.set_status("Lectura finalizada.")
        if self.tabs.currentIndex() == 1:
            self.notify("Lectura finalizada.")

    def save_phrase(self, kind: str, note: str = "") -> bool:
        if not self.output.toPlainText():
            return False
        entry = dict(texto=self.input.toPlainText(), traduccion=self.output.toPlainText(),
                     reversa=self.reverse, variante=self.result_variant, nota=note)
        try:
            self.library.save(kind, entry)
        except Exception:
            self.set_status("No se pudo guardar la frase en este perfil de Windows.", error=True)
            return False
        self.refresh_library()
        return True

    def save_favorite(self) -> None:
        if self.save_phrase("favorite"):
            self.set_status("Frase guardada en favoritas.")
            self.notify("Guardada en favoritas.")

    def report_translation(self) -> None:
        note, accepted = QInputDialog.getMultiLineText(self, "Reportar mala traducción",
                                                       "Puedes indicar cuál sería la traducción correcta.")
        if accepted and self.save_phrase("report", note.strip()):
            self.set_status("Reporte guardado en esta laptop. Puedes exportarlo desde Ajustes.")

    def export_reports(self) -> None:
        try:
            entries = self.library.entries("report")
        except Exception:
            self.set_status("No se pudieron abrir los reportes locales.", error=True)
            return
        if not entries:
            self.set_status("Todavía no hay reportes.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar reportes", "asus2-reportes.json", "JSON (*.json)")
        if not path:
            return
        payload = (json.dumps(entries, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        file = QSaveFile(path)
        if not file.open(QIODevice.OpenModeFlag.WriteOnly) or file.write(payload) != len(payload) or not file.commit():
            self.set_status("No se pudo exportar el archivo de reportes.", error=True)
        else:
            self.set_status("Reportes exportados.")

    def refresh_library(self) -> None:
        hidden = set(self.settings.value("hidden_examples", [], type=list))
        self.library_entries = [
            dict(texto=source, traduccion=target, reversa=False, categoria=category, _kind="example", _id=index)
            for index, (category, source, target) in enumerate(COMMON)
            if str(index) not in hidden
        ]
        try:
            favorites = [dict(entry, _kind="favorite") for entry in self.library.entries("favorite", include_id=True)]
            history = [dict(entry, _kind="history") for entry in self.library.entries("history", include_id=True)]
        except Exception:
            self.render_library()
            self.library_status.setText("No se pudieron abrir las frases de este perfil de Windows.")
            return
        self.library_entries = favorites + self.library_entries + history
        self.render_library()

    def filter_library(self, name: str) -> None:
        self.library_filter = name
        self.render_library()

    def render_library(self) -> None:
        self.library_list.clear()
        query = self.library_search.text().strip().casefold()
        category = self.library_filter
        kind = {"Favoritas": "favorite", "Historial": "history"}.get(category)
        for entry in self.library_entries:
            searchable = f"{entry['texto']} {entry['traduccion']}".casefold()
            matches_category = category == "Todas" or (entry["_kind"] == kind if kind else
                                                         entry.get("categoria") == category)
            if query in searchable and matches_category:
                self.add_phrase_card(entry)
        if category == "Historial" and not self.history_setting.isChecked():
            self.library_status.setText("El historial automático está desactivado. Puedes activarlo en Ajustes.")
        else:
            self.library_status.setText("" if self.library_list.count() else "No hay frases que coincidan.")

    def add_phrase_card(self, entry: dict[str, Any]) -> None:
        card = QFrame(objectName="phraseCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(11, 8, 11, 8)
        pair = QVBoxLayout()
        pair.setSpacing(2)
        heading = QLabel(wordWrap=True)
        heading.setTextFormat(Qt.TextFormat.RichText)
        color = "#e8f0ef" if self.dark_theme.isChecked() else "#14211f"
        heading.setText(f'<a href="open" style="color:{color};text-decoration:none"><b>{escape(entry["texto"])}</b></a>')
        heading.linkActivated.connect(lambda: self.open_library_entry(entry))
        pair.addWidget(heading)
        meaning = QLabel(entry["traduccion"], wordWrap=True, objectName="cardTranslation")
        meaning.setTextFormat(Qt.TextFormat.PlainText)
        pair.addWidget(meaning)
        row.addLayout(pair, 1)
        row.addWidget(self._copy_button(lambda: entry["texto"]))
        listen = QPushButton("Escuchar")
        listen.clicked.connect(lambda: self.speak_text(entry["texto"], quechua=not entry["reversa"]))
        row.addWidget(listen)
        remove = QPushButton("Borrar")
        remove.clicked.connect(lambda: self.delete_phrase(entry))
        row.addWidget(remove)
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self.library_list.addItem(item)
        item.setSizeHint(card.sizeHint())
        self.library_list.setItemWidget(item, card)

    def delete_phrase(self, entry: dict[str, Any]) -> None:
        if entry["_kind"] == "example":
            hidden = self.settings.value("hidden_examples", [], type=list)
            self.save_setting("hidden_examples", [*hidden, str(entry["_id"])])
        else:
            try:
                self.library.delete(entry["_kind"], entry["_id"])
            except Exception:
                self.notify("No se pudo borrar la frase.")
                return
        self.refresh_library()
        self.notify("Frase borrada.")

    def open_saved_phrase(self, item: QListWidgetItem) -> None:
        self.open_library_entry(item.data(Qt.ItemDataRole.UserRole))

    def open_library_entry(self, entry: dict[str, Any]) -> None:
        if self.job:
            return
        self.set_direction(bool(entry["reversa"]))
        self.result_variant = entry.get("variante", VARIANT)
        self.input.setPlainText(entry["texto"])
        self.set_alternatives([entry["traduccion"]])
        self.tabs.setCurrentIndex(0)
        self.set_status("Frase de ejemplo." if entry["_kind"] == "example" else "Frase guardada abierta.")

    def clear_history(self) -> None:
        answer = QMessageBox.question(self, "Borrar historial", "¿Quieres borrar todo el historial local?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.library.clear("history")
            except Exception:
                self.set_status("No se pudo borrar el historial.", error=True)
                return
            self.refresh_library()
            self.set_status("Historial borrado.")
            self.notify("Historial borrado.")

    def set_history(self, enabled: bool) -> None:
        self.save_setting("history", enabled)
        self.refresh_library()

    def save_setting(self, key: str, value: Any) -> None:
        self.settings.setValue(key, value)
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            self.set_status("No se pudo guardar el ajuste en este perfil de Windows.", error=True)

    def change_font(self) -> None:
        size, accepted = QInputDialog.getInt(self, "Tamaño de letra", "Puntos",
                                             self.settings.value("font_size", 11, type=int), 9, 24)
        if accepted:
            self.save_setting("font_size", size)
            self.apply_appearance()

    def change_theme(self, dark: bool) -> None:
        self.save_setting("dark", dark)
        self.apply_appearance()
        self.render_library()

    def apply_appearance(self) -> None:
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        if self.dark_theme.isChecked():
            configure_theme(app)
        else:
            app.styleHints().setColorScheme(Qt.ColorScheme.Light)
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("")
        app.setFont(QFont("Segoe UI", self.settings.value("font_size", 11, type=int)))
        self.level.dark = self.dark_theme.isChecked()
        self.level.update()
        self.swap_button.setIcon(swap_icon(self.dark_theme.isChecked()))
        self.setStyleSheet(stylesheet(self.dark_theme.isChecked()))

    def inform(self, title: str, body: str) -> None:
        dialog = QMessageBox(QMessageBox.Icon.Information, title, body, parent=self)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        dialog.exec()

    def show_model(self) -> None:
        try:
            index = json.loads((self.root / "model_index.json").read_text(encoding="utf-8"))
            bytes_used = sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())
            usage = disk_usage(self.root)
        except (OSError, ValueError):
            self.set_status("La carpeta del modelo no está disponible.", error=True)
            return
        device = self.engine.device if self.engine else "Pendiente"
        self.inform("Información del modelo",
                    f"Paquete {index.get('name', 'ASUS2')} · formato {index.get('format_version', '—')}\n"
                    f"Tamaño del paquete: {bytes_used / 1e9:.2f} GB\n"
                    f"Unidad: {usage.used / 1e9:.2f} GB usados · {usage.free / 1e9:.2f} GB libres\n"
                    f"Dispositivo: {device}\n{self.root}")

    def save_model_copy(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar copia local", "ASUS2.zip", "ZIP (*.zip)")
        if path:
            self.start_job(lambda: export_model(self.root, Path(path)),
                           lambda _: self.set_status("Copia local del modelo guardada."),
                           "Guardando copia local del modelo…")

    def show_licenses(self) -> None:
        path = self.root / "NOTICE/ATRIBUCIONES.md"
        dialog = QDialog(self)
        dialog.resize(720, 530)
        dialog.setWindowTitle("Licencias y avisos")
        layout = QVBoxLayout(dialog)
        viewer = QTextEdit(readOnly=True)
        try:
            viewer.setMarkdown(path.read_text(encoding="utf-8"))
        except OSError:
            viewer.setPlainText("ASUS2 usa Meta MMS y NLLB bajo CC BY-NC 4.0.")
        layout.addWidget(viewer, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.close)
        layout.addWidget(close)
        dialog.exec()

    def show_installation(self) -> None:
        self.inform("Guía de instalación",
                    "Desde Git, sigue la guía del README para instalar ASUS2 en models/ASUS2. "
                    "Si usas Xandar.exe, conserva _internal y ASUS2 junto al ejecutable.\n\n"
                    "Para usar audio en español, conserva también models/whisper-es y models/manifest.json "
                    "junto al ejecutable. Para escuchar la traducción a quechua, conserva models/tts-quz.\n\n"
                    "En Windows, habilita el acceso de las aplicaciones de escritorio "
                    "al micrófono para poder grabar. Instala una voz en español en Windows para usar Escuchar.")

    def show_help(self) -> None:
        self.inform("Manual de uso",
                    "Pulsa ⇄ o Ctrl+I para intercambiar idiomas. Escribe y traduce o abre un audio de hasta un minuto. "
                    "Para grabar, pulsa Grabar y concede permiso la primera vez. Ctrl+Espacio graba o detiene. "
                    "Ctrl+Enter traduce el texto.\n\n"
                    "Puedes revisar las palabras resaltadas, copiar el texto o escuchar la traducción. "
                    "Activa el historial en Ajustes si quieres conservar tus frases. Los reportes se "
                    "guardan en esta laptop y se exportan desde Ajustes.")

    def closeEvent(self, event: Any) -> None:
        if self.job is not None:
            self.stop.set()
            self.set_status("Espera a que termine la operación para cerrar.")
            event.ignore()
            return
        super().closeEvent(event)
