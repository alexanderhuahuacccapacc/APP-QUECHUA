from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Language(StrEnum):
    ES = "es"
    QUZ = "quz"
    AYM = "aym"
    QUY = "quy"
    QXP = "qxp"

    @property
    def nllb(self) -> str:
        if self == self.QXP:
            raise ValueError("NLLB no incluye una ruta propia para Puno (qxp)")
        return {
            self.ES: "spa_Latn",
            self.QUZ: "quy_Latn",
            self.QUY: "quy_Latn",
            self.AYM: "ayr_Latn",
        }[self]

    @property
    def mms(self) -> str:
        if self == self.QXP:
            raise ValueError("Puno requiere un paquete ASR propio; no se sustituye por Cusco")
        return {self.ES: "spa", self.QUZ: "quz", self.QUY: "quy", self.AYM: "ayr"}[self]


@dataclass(frozen=True)
class Recognition:
    text: str
    score: float | None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Translation:
    text: str
    score: float | None
    origin: str = "modelo"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    message_id: str
    original: str
    translated: str
    confidence: float | None
    audio_path: Path | None
    critical: bool
    latency: dict[str, float]
    origin: str = "modelo"


@dataclass(frozen=True)
class MessageView:
    id: str
    direction: str
    language: str
    original: str
    translated: str
    confidence: float | None
    audio_path: str | None
    correction: str | None
    created: str
    origin: str = "modelo"
    correction_state: str | None = None
    processing: dict[str, object] = field(default_factory=dict)
