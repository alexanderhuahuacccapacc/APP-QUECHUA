import argparse
import gc
import json
from pathlib import Path


class AHuaCcAsus:
    def __init__(self, AHuaCcRoot=None, AHuaCcDevice=None):
        import torch

        self.AHuaCcRoot = Path(AHuaCcRoot) if AHuaCcRoot is not None else Path(__file__).resolve().parent
        self.AHuaCcIndex = json.loads((self.AHuaCcRoot / 'model_index.json').read_text(encoding='utf-8'))
        self.AHuaCcDevice = AHuaCcDevice or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.AHuaCcModel = self.AHuaCcProcessor = None
        self.AHuaCcComponent = None

    def AHuaCcComponentPath(self, AHuaCcComponent):
        AHuaCcPath = (self.AHuaCcRoot / self.AHuaCcIndex['components'][AHuaCcComponent]).resolve()
        if not AHuaCcPath.is_relative_to(self.AHuaCcRoot.resolve()):
            raise ValueError('Component path escapes ASUS package')
        return AHuaCcPath

    def AHuaCcUnload(self):
        import torch

        self.AHuaCcModel = self.AHuaCcProcessor = None
        self.AHuaCcComponent = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def AHuaCcLoad(self, AHuaCcComponent):
        if self.AHuaCcComponent == AHuaCcComponent:
            return
        import torch
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            Wav2Vec2ForCTC,
            Wav2Vec2Processor,
        )

        self.AHuaCcUnload()
        AHuaCcPath = self.AHuaCcComponentPath(AHuaCcComponent)
        if AHuaCcComponent == 'speech':
            from safetensors import safe_open

            AHuaCcDtype = torch.float16 if self.AHuaCcDevice.startswith('cuda') else torch.float32
            self.AHuaCcModel = Wav2Vec2ForCTC.from_pretrained(
                AHuaCcPath, local_files_only=True, torch_dtype=AHuaCcDtype, attn_implementation='eager'
            )
            if self.AHuaCcDevice.startswith('cuda'):
                with safe_open(
                    str(AHuaCcPath / 'model.safetensors'), framework='pt', device='cpu'
                ) as AHuaCcHandle:
                    for AHuaCcName, AHuaCcParameter in self.AHuaCcModel.named_parameters():
                        AHuaCcValue = AHuaCcHandle.get_tensor(AHuaCcName)
                        if AHuaCcValue.dtype != AHuaCcParameter.dtype:
                            AHuaCcParameter.data = AHuaCcValue.clone()
            self.AHuaCcModel.target_lang = 'quz'
            self.AHuaCcModel.config.target_lang = 'quz'
            self.AHuaCcProcessor = Wav2Vec2Processor.from_pretrained(
                AHuaCcPath, target_lang='quz', local_files_only=True
            )
            self.AHuaCcProcessor.tokenizer.set_target_lang('quz')
        else:
            self.AHuaCcModel = AutoModelForSeq2SeqLM.from_pretrained(
                AHuaCcPath, local_files_only=True, use_safetensors=True, attn_implementation='eager'
            )
            self.AHuaCcProcessor = AutoTokenizer.from_pretrained(AHuaCcPath, local_files_only=True)
            self.AHuaCcProcessor.src_lang = self.AHuaCcIndex['source_language_token']
            self.AHuaCcProcessor.tgt_lang = self.AHuaCcIndex['target_language_token']
        self.AHuaCcModel.to(self.AHuaCcDevice).eval()
        self.AHuaCcComponent = AHuaCcComponent

    def AHuaCcTranscribe(self, AHuaCcAudio):
        import numpy as np
        import soundfile as sf
        import torch

        AHuaCcWaveform, AHuaCcRate = sf.read(AHuaCcAudio, dtype='float32', always_2d=True)
        AHuaCcWaveform = AHuaCcWaveform.mean(axis=1, dtype=np.float32)
        if AHuaCcRate != 16000:
            try:
                import torchaudio.functional as audio_functional

                AHuaCcWaveform = audio_functional.resample(
                    torch.from_numpy(AHuaCcWaveform), int(AHuaCcRate), 16000
                ).numpy()
            except (ImportError, OSError):
                import math

                from scipy.signal import resample_poly

                AHuaCcDivisor = math.gcd(int(AHuaCcRate), 16000)
                AHuaCcWaveform = resample_poly(
                    AHuaCcWaveform, 16000 // AHuaCcDivisor, int(AHuaCcRate) // AHuaCcDivisor
                ).astype(np.float32)
        if not 1600 <= len(AHuaCcWaveform) <= 60 * 16000:
            raise ValueError('Provide an audio segment between0.1and60seconds')
        self.AHuaCcLoad('speech')
        AHuaCcEncoded = self.AHuaCcProcessor(AHuaCcWaveform, sampling_rate=16000, return_tensors='pt')
        with torch.inference_mode(), torch.autocast(
            'cuda', dtype=torch.float16, enabled=self.AHuaCcDevice.startswith('cuda')
        ):
            AHuaCcLogits = self.AHuaCcModel(input_values=AHuaCcEncoded.input_values.to(self.AHuaCcDevice)).logits
        return self.AHuaCcProcessor.batch_decode(AHuaCcLogits.argmax(dim=-1))[0].strip()

    def AHuaCcTranslate(self, AHuaCcText):
        import torch

        if not AHuaCcText.strip():
            return ''
        self.AHuaCcLoad('translation')
        AHuaCcEncoded = self.AHuaCcProcessor(AHuaCcText, return_tensors='pt').to(self.AHuaCcDevice)
        if AHuaCcEncoded.input_ids.shape[-1] > 512:
            raise ValueError('Text exceeds evaluated input length; split the input')
        with torch.inference_mode():
            AHuaCcGenerated = self.AHuaCcModel.generate(
                **AHuaCcEncoded,
                forced_bos_token_id=self.AHuaCcProcessor.convert_tokens_to_ids(
                    self.AHuaCcIndex['target_language_token']
                ),
                **self.AHuaCcIndex['generation'],
            )
        return self.AHuaCcProcessor.decode(AHuaCcGenerated[0], skip_special_tokens=True)

    def AHuaCcInterpret(self, AHuaCcAudio):
        AHuaCcText = self.AHuaCcTranscribe(AHuaCcAudio)
        return dict(transcription=AHuaCcText, translation=self.AHuaCcTranslate(AHuaCcText))


def AHuaCcMain():
    AHuaCcParser = argparse.ArgumentParser(
        description='Standalone ASUS entry point: audio or Quechua text to Spanish, entirely local.'
    )
    AHuaCcEntry = AHuaCcParser.add_mutually_exclusive_group(required=True)
    AHuaCcEntry.add_argument('--audio', type=Path)
    AHuaCcEntry.add_argument('--text')
    AHuaCcParser.add_argument('--root', type=Path)
    AHuaCcParser.add_argument('--device')
    AHuaCcArgs = AHuaCcParser.parse_args()
    AHuaCcRuntime = AHuaCcAsus(AHuaCcArgs.root, AHuaCcArgs.device)
    try:
        AHuaCcResult = (
            AHuaCcRuntime.AHuaCcInterpret(AHuaCcArgs.audio)
            if AHuaCcArgs.audio
            else dict(translation=AHuaCcRuntime.AHuaCcTranslate(AHuaCcArgs.text))
        )
        print(json.dumps(AHuaCcResult, ensure_ascii=False))
    finally:
        AHuaCcRuntime.AHuaCcUnload()


if __name__ == '__main__':
    AHuaCcMain()
