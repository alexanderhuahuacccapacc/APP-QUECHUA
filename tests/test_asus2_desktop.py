from pathlib import Path
from typing import Any
from zipfile import ZipFile

import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.core.config import Config
from app.models.domain import Language
from app.models.voice import Speech
from app.services.asus2_local import PhraseLibrary, export_model, read_audio
from app.ui.asus2_desktop import Asus2Desktop, Interpretation


def test_mic_permission_and_optional_history_persist(
    qtbot: Any, monkeypatch: Any, tmp_path: Path,
) -> None:
    monkeypatch.setattr(Asus2Desktop, "load_model", lambda self: None)
    monkeypatch.setattr(Asus2Desktop, "refresh_microphones", lambda self: None)
    config = Config(data_dir=tmp_path)
    prompts = []

    def consent(*args: Any) -> QMessageBox.StandardButton:
        prompts.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", consent)
    window = Asus2Desktop(config)
    qtbot.addWidget(window)
    assert window.source_language.text() == "Quechua Collao"
    assert window.audio_supported
    assert window.may_record()
    assert window.may_record()
    assert len(prompts) == 1
    window.show_interpretation(Interpretation("Allin punchay", ["Buen día", "Buenos días"], [0.95, 0.45]))
    assert len(window.input.extraSelections()) == 1
    window.alternative_group.button(1).click()
    assert window.output.toPlainText() == "Buenos días"
    assert window.library.entries("history") == []
    window.history_setting.trigger()
    window.show_interpretation(Interpretation("Allin punchay", ["Buenos días"]))
    window.save_favorite()
    assert len(window.library.entries("history")) == 1
    window.input.insertPlainText("x")
    assert window.output.toPlainText() == ""
    window.close()

    reopened = Asus2Desktop(config)
    qtbot.addWidget(reopened)
    assert reopened.may_record()
    assert len(prompts) == 1
    assert reopened.history_setting.isChecked()
    reopened.clear_history()
    assert reopened.library.entries("history") == []
    assert reopened.library.entries("favorite")[0]["traduccion"] == "Buenos días"
    assert reopened.library.entries("favorite")[0]["variante"] == "Collao"


def test_audio_import_resamples_and_phrase_payload_stays_encrypted(tmp_path: Path) -> None:
    path = tmp_path / "entrada.wav"
    samples = np.sin(2 * np.pi * 440 * np.arange(12000) / 48000).astype(np.float32)
    sf.write(path, np.column_stack((samples, samples)), 48000)
    imported = read_audio(path)
    assert imported.shape == (4000,)
    assert imported.dtype == np.float32
    library = PhraseLibrary(tmp_path / "frases")
    library.save("report", {"texto": "frase confidencial"})
    assert b"frase confidencial" not in library.path.read_bytes()
    assert library.entries("report")[0]["texto"] == "frase confidencial"


def test_model_copy_keeps_package_paths(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model_index.json").write_text("{}", encoding="utf-8")
    archive = tmp_path / "ASUS2.zip"
    export_model(root, archive)
    with ZipFile(archive) as content:
        assert content.read("ASUS2/model_index.json") == b"{}"


def test_spanish_recording_and_file_route_to_reverse_translation(
    qtbot: Any, monkeypatch: Any, tmp_path: Path,
) -> None:
    monkeypatch.setattr(Asus2Desktop, "load_model", lambda self: None)
    monkeypatch.setattr(Asus2Desktop, "refresh_microphones", lambda self: None)
    samples = np.zeros(3200, dtype=np.float32)
    path = tmp_path / "espanol.wav"
    sf.write(path, samples, 16000)
    routes: list[tuple[str, bool]] = []
    playback: list[int] = []

    class Engines:
        spanish_audio_available = True

        def recognize(self, audio: np.ndarray, *, reverse: bool = False) -> tuple[str, list[float]]:
            assert audio.shape == samples.shape
            routes.append(("audio", reverse))
            return "Buenos días", []

        def translate_options(self, text: str, *, reverse: bool = False) -> list[str]:
            assert text == "Buenos días"
            routes.append(("texto", reverse))
            return ["Allin punchay"]

    window = Asus2Desktop(Config(data_dir=tmp_path))
    qtbot.addWidget(window)
    window.engine = Engines()

    class CollaoVoice:
        def supports(self, language: Language) -> bool:
            return language == Language.QUZ

        def synthesize(self, text: str, language: Language) -> Speech:
            assert text == "Allin punchay"
            assert language == Language.QUZ
            return Speech(samples, 16000, "tts")

    window.quechua_voice = CollaoVoice()
    monkeypatch.setattr(window.audio, "play", lambda audio, rate: playback.append(rate))
    window.swap_button.click()
    assert window.target_language.text() == "Quechua Collao"
    assert window.record_button.isEnabled() and window.file_button.isEnabled()

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), "Audio (*.wav)"))
    window.open_audio()
    qtbot.waitUntil(lambda: window.output.toPlainText() == "Allin punchay")
    assert window.input.toPlainText() == "Buenos días"

    window.microphone_permission.trigger()
    monkeypatch.setattr(window.audio, "capture", lambda *args, **kwargs: samples)
    window.record_or_stop()
    qtbot.waitUntil(lambda: window.output.toPlainText() == "Allin punchay")
    assert routes == [("audio", True), ("texto", True)] * 2
    assert window.speak_button.isEnabled()
    window.speak_output()
    qtbot.waitUntil(lambda: window.status.text() == "Lectura finalizada.")
    assert playback == [16000]


def test_mockup_phrase_filters_keep_saved_favorites_when_removing_history(
    qtbot: Any, monkeypatch: Any, tmp_path: Path,
) -> None:
    monkeypatch.setattr(Asus2Desktop, "load_model", lambda self: None)
    monkeypatch.setattr(Asus2Desktop, "refresh_microphones", lambda self: None)
    window = Asus2Desktop(Config(data_dir=tmp_path))
    qtbot.addWidget(window)
    window.library_search.setText("centro de salud")
    assert window.library_list.count() == 1
    sample = window.library_entries[5]
    assert sample["categoria"] == "Salud"
    window.open_library_entry(sample)
    assert window.input.toPlainText() == sample["texto"]
    assert window.output.toPlainText() == sample["traduccion"]
    window.history_setting.trigger()
    window.show_interpretation(Interpretation("Allin punchay", ["Buenos días"]))
    window.save_favorite()
    window.library_search.clear()
    window.filter_library("Historial")
    assert window.library_list.count() == 1
    entry = window.library.entries("history", include_id=True)[0]
    window.delete_phrase(dict(entry, _kind="history"))
    assert window.library_list.count() == 0
    window.filter_library("Favoritas")
    assert window.library_list.count() == 1
