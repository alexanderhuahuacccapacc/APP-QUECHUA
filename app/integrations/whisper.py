import gc
from pathlib import Path
from typing import Any

from app.services.interfaces import Samples


class SpanishASR:
    def __init__(self, root: Path, device: str) -> None:
        self.root = root / "whisper-es"
        self.device = device
        self.processor: Any = None
        self.model: Any = None

    def unload(self) -> None:
        self.model = None
        self.processor = None
        gc.collect()

    def load(self) -> None:
        if self.model is not None:
            return
        import torch
        from transformers import AutoProcessor, WhisperForConditionalGeneration

        self.processor = AutoProcessor.from_pretrained(self.root, local_files_only=True)
        model = WhisperForConditionalGeneration.from_pretrained(self.root, local_files_only=True).eval()
        if self.device == "cpu":
            torch.set_num_threads(4)
            self.model = torch.ao.quantization.quantize_dynamic(
                model, {torch.nn.Linear}, dtype=torch.qint8, inplace=True
            )
        else:
            self.model = model.to(self.device)

    def transcribe(self, samples: Samples) -> str:
        import torch

        self.load()
        inputs = self.processor(
            samples, sampling_rate=16000, return_tensors="pt", return_attention_mask=True
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with torch.inference_mode():
            generated = self.model.generate(
                **inputs, language="spanish", task="transcribe", max_new_tokens=200
            )
        return str(self.processor.batch_decode(generated, skip_special_tokens=True)[0]).strip()
