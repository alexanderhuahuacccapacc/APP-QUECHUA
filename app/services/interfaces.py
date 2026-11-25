from abc import ABC, abstractmethod
from pathlib import Path
from threading import Event

import numpy as np
from numpy.typing import NDArray

from app.models.domain import Language, Recognition, Result, Translation

Samples = NDArray[np.float32]


class MissingASRModel(ValueError):
    """Catalog entry without an installed speech-recognition route."""


class AudioInputError(ValueError):
    """An actionable microphone failure, safe to display without model inputs."""


class AudioService(ABC):
    @abstractmethod
    def capture(self, stop: Event) -> Samples: ...

    @abstractmethod
    def play(
        self, samples: Samples, sample_rate: int = 16000, device: int | None = None
    ) -> None: ...


class ASRService(ABC):
    @abstractmethod
    def transcribe(self, samples: Samples, language: Language) -> Recognition: ...


class TranslationService(ABC):
    @abstractmethod
    def translate(self, text: str, source: Language, target: Language) -> Translation: ...


class AudioStorage(ABC):
    @abstractmethod
    def save(self, samples: Samples) -> Path: ...

    @abstractmethod
    def load(self, path: Path) -> Samples: ...


class PipelineService(ABC):
    @abstractmethod
    def from_audio(self, samples: Samples, language: Language, conversation: str) -> Result: ...

    @abstractmethod
    def from_text(self, text: str, target: Language, conversation: str) -> Result: ...
