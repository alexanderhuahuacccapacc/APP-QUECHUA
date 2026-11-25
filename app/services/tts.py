from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from app.core.offline import enforce_offline
from app.models.domain import Language
from app.models.voice import Speech

enforce_offline()


class TTSService(ABC):
    @abstractmethod
    def supports(self, language: Language) -> bool: ...

    @abstractmethod
    def synthesize(self, text: str, language: Language) -> Speech: ...


class MmsTTS(TTSService):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.model: Any = None
        self.tokenizer: Any = None
        self.language: Language | None = None

    def supports(self, language: Language) -> bool:
        path = self.root / f"tts-{language.value}"
        return (path / "config.json").is_file() and any(
            (path / name).is_file() for name in ("model.safetensors", "pytorch_model.bin")
        )

    def synthesize(self, text: str, language: Language) -> Speech:
        if not text.strip() or len(text) > 500:
            raise ValueError("La voz requiere una frase de 1 a 500 caracteres.")
        if not self.supports(language):
            return Speech(
                None, 16000, "texto", "Voz no instalada: se conserva la respuesta escrita."
            )
        import torch
        from transformers import VitsModel, VitsTokenizer

        torch.set_num_threads(4)
        if self.language != language:
            from app.core.integrity import verify_voice

            verify_voice(self.root, f"tts-{language.value}")
            self.model = None
            path = str(self.root / f"tts-{language.value}")
            tokenizer_factory: Any = VitsTokenizer
            self.tokenizer = tokenizer_factory.from_pretrained(path, local_files_only=True)
            self.model = VitsModel.from_pretrained(path, local_files_only=True).eval()
            self.language = language
        inputs = self.tokenizer(text, return_tensors="pt")
        if inputs["input_ids"].numel() < 1:
            raise ValueError("El texto no contiene caracteres reconocidos por esta voz.")
        with torch.inference_mode():
            waveform = self.model(**inputs).waveform[0].cpu().numpy()
        return Speech(
            np.asarray(waveform, dtype=np.float32),
            int(self.model.config.sampling_rate),
            "tts",
            "Voz sintética: pronunciación pendiente de revisión local.",
        )
