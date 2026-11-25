"""Expose the standalone ASUS2 runtime through the desktop service interfaces."""

from pathlib import Path

from app.integrations.whisper import SpanishASR
from app.models.domain import Language, Recognition, Translation
from app.services.interfaces import (
    ASRService,
    AudioInputError,
    Samples,
    TranslationService,
)
from asus import AHuaCcAsus


class Asus2Engines(ASRService, TranslationService):
    def __init__(self, root: Path, device: str, *, spanish_root: Path | None = None) -> None:
        from torch import set_num_threads

        self.runtime = AHuaCcAsus(root, None if device == "auto" else device)
        self.device: str = self.runtime.AHuaCcDevice
        index = self.runtime.AHuaCcIndex
        self.spanish_root = spanish_root
        self.spanish_asr: SpanishASR | None = None
        if index.get("name") != "ASUS2":
            raise ValueError("La carpeta seleccionada debe contener ASUS2.")
        for component in ("speech", "translation"):
            weights = root / index["components"][component] / "model.safetensors"
            if not weights.resolve().is_relative_to(root.resolve()) or not weights.is_file():
                raise ValueError("Faltan los pesos de ASUS2.")
        if self.device == "cpu":
            set_num_threads(4)

    def transcribe(self, samples: Samples, language: Language) -> Recognition:
        if language != Language.QUZ:
            raise ValueError("ASUS2 reconoce quechua Collao.")
        text, scores = self.recognize(samples)
        return Recognition(text, sum(scores) / len(scores) if scores else None)

    @property
    def spanish_audio_available(self) -> bool:
        root = self.spanish_root
        return root is not None and all(
            (root / filename).is_file()
            for filename in ("manifest.json", "whisper-es/config.json", "whisper-es/model.safetensors")
        )

    def unload(self) -> None:
        self.runtime.AHuaCcUnload()
        if self.spanish_asr is not None:
            self.spanish_asr.unload()

    def recognize(self, samples: Samples, *, reverse: bool = False) -> tuple[str, list[float]]:
        if not 1600 <= len(samples) <= 960000:
            raise ValueError("Usa un audio de entre 0,1 y 60 segundos.")
        if reverse:
            root = self.spanish_root
            if root is None or not self.spanish_audio_available:
                raise AudioInputError("Falta el reconocedor de español local. Consulta Ayuda → Guía de instalación.")
            recognizer = self.spanish_asr
            if recognizer is None:
                recognizer = SpanishASR(root, self.device)
                self.spanish_asr = recognizer
            segment_size = (len(samples) + 1) // 2 if len(samples) > 30 * 16000 else len(samples)
            segments = (
                recognizer.transcribe(samples[start : start + segment_size])
                for start in range(0, len(samples), segment_size)
            )
            return " ".join(text for text in segments if text), []
        text, scores = self.runtime.AHuaCcRecognize(samples, AHuaCcConfidence=True)
        return str(text), list(scores)

    def translate_options(self, text: str, *, reverse: bool = False) -> list[str]:
        if not text.strip():
            return []
        options = self.runtime.AHuaCcTranslateOptions(text, AHuaCcReverse=reverse, AHuaCcCount=3)
        return [value for value in options if value.strip()]

    def translate(self, text: str, source: Language, target: Language) -> Translation:
        if (source, target) != (Language.QUZ, Language.ES):
            raise ValueError("ASUS2 traduce de quechua a español.")
        return Translation(self.runtime.AHuaCcTranslate(text), None, "ASUS2 · Traducción local")
