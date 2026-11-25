import argparse
import gc
import json
from itertools import groupby as AHuaCcGroupBy
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

    def AHuaCcTranscribe(self, AHuaCcAudio, *, AHuaCcConfidence=False):
        import numpy as AHuaCcNumpy
        import soundfile as AHuaCcSoundFile
        import torch

        AHuaCcWaveform, AHuaCcRate = AHuaCcSoundFile.read(AHuaCcAudio, dtype='float32', always_2d=True)
        AHuaCcWaveform = AHuaCcWaveform.mean(axis=1, dtype=AHuaCcNumpy.float32)
        if AHuaCcRate != 16000:
            try:
                import torchaudio.functional as AHuaCcAudioFunctional

                AHuaCcWaveform = AHuaCcAudioFunctional.resample(
                    torch.from_numpy(AHuaCcWaveform), int(AHuaCcRate), 16000
                ).numpy()
            except (ImportError, OSError):
                import math

                from scipy.signal import resample_poly

                AHuaCcDivisor = math.gcd(int(AHuaCcRate), 16000)
                AHuaCcWaveform = resample_poly(
                    AHuaCcWaveform, 16000 // AHuaCcDivisor, int(AHuaCcRate) // AHuaCcDivisor
                ).astype(AHuaCcNumpy.float32)
        if not 1600 <= len(AHuaCcWaveform) <= 60 * 16000:
            raise ValueError('Provide an audio segment between 0.1 and 60 seconds')
        AHuaCcText, AHuaCcScores = self.AHuaCcRecognize(AHuaCcWaveform, AHuaCcConfidence=AHuaCcConfidence)
        return (AHuaCcText, AHuaCcScores) if AHuaCcConfidence else AHuaCcText

    def AHuaCcRecognize(self, AHuaCcWaveform, *, AHuaCcConfidence=False):
        import torch

        self.AHuaCcLoad('speech')
        AHuaCcEncoded = self.AHuaCcProcessor(AHuaCcWaveform, sampling_rate=16000, return_tensors='pt')
        with torch.inference_mode(), torch.autocast(
            'cuda', dtype=torch.float16, enabled=self.AHuaCcDevice.startswith('cuda')
        ):
            AHuaCcLogits = self.AHuaCcModel(input_values=AHuaCcEncoded.input_values.to(self.AHuaCcDevice)).logits
        AHuaCcIds = AHuaCcLogits.argmax(dim=-1)
        AHuaCcText = self.AHuaCcProcessor.batch_decode(AHuaCcIds)[0].strip()
        if not AHuaCcText or not AHuaCcConfidence:
            return AHuaCcText, []
        AHuaCcProbabilities = AHuaCcLogits[0].float().softmax(dim=-1).gather(1, AHuaCcIds[0, :, None]).flatten()
        AHuaCcTokenizer = self.AHuaCcProcessor.tokenizer
        AHuaCcWordScores = []
        AHuaCcScores = []
        AHuaCcFrames = zip(AHuaCcIds[0].tolist(), AHuaCcProbabilities.tolist(), strict=True)
        for AHuaCcSymbol, AHuaCcGroup in AHuaCcGroupBy(AHuaCcFrames, key=lambda AHuaCcItem: AHuaCcItem[0]):
            AHuaCcToken = AHuaCcTokenizer.convert_ids_to_tokens(AHuaCcSymbol)
            if AHuaCcToken == AHuaCcTokenizer.word_delimiter_token:
                if AHuaCcScores:
                    AHuaCcWordScores.append(sum(AHuaCcScores) / len(AHuaCcScores))
                    AHuaCcScores = []
            elif AHuaCcSymbol != AHuaCcTokenizer.pad_token_id:
                AHuaCcScores.append(max(AHuaCcScore for _, AHuaCcScore in AHuaCcGroup))
        if AHuaCcScores:
            AHuaCcWordScores.append(sum(AHuaCcScores) / len(AHuaCcScores))
        return AHuaCcText, AHuaCcWordScores if len(AHuaCcWordScores) == len(AHuaCcText.split()) else []

    def AHuaCcTranslate(self, AHuaCcText, *, AHuaCcReverse=False):
        AHuaCcOptions = self.AHuaCcTranslateOptions(AHuaCcText, AHuaCcReverse=AHuaCcReverse)
        return AHuaCcOptions[0] if AHuaCcOptions else ''

    def AHuaCcTranslateOptions(self, AHuaCcText, *, AHuaCcReverse=False, AHuaCcCount=1):
        import torch

        if not AHuaCcText.strip():
            return []
        self.AHuaCcLoad('translation')
        AHuaCcSource = self.AHuaCcIndex['source_language_token']
        AHuaCcTarget = self.AHuaCcIndex['target_language_token']
        if AHuaCcReverse:
            AHuaCcSource, AHuaCcTarget = AHuaCcTarget, AHuaCcSource
        self.AHuaCcProcessor.src_lang = AHuaCcSource
        self.AHuaCcProcessor.tgt_lang = AHuaCcTarget
        AHuaCcEncoded = self.AHuaCcProcessor(AHuaCcText, return_tensors='pt').to(self.AHuaCcDevice)
        if AHuaCcEncoded.input_ids.shape[-1] > 512:
            raise ValueError('Text exceeds evaluated input length; split the input')
        AHuaCcGeneration = dict(self.AHuaCcIndex['generation'])
        if AHuaCcCount > 1:
            AHuaCcGeneration.update(
                num_beams=max(AHuaCcGeneration['num_beams'], AHuaCcCount), num_return_sequences=AHuaCcCount
            )
        with torch.inference_mode():
            AHuaCcGenerated = self.AHuaCcModel.generate(
                **AHuaCcEncoded,
                forced_bos_token_id=self.AHuaCcProcessor.convert_tokens_to_ids(AHuaCcTarget),
                **AHuaCcGeneration,
            )
        return list(dict.fromkeys(self.AHuaCcProcessor.batch_decode(AHuaCcGenerated, skip_special_tokens=True)))

    def AHuaCcInterpret(self, AHuaCcAudio, *, AHuaCcCount=1):
        AHuaCcText, AHuaCcScores = self.AHuaCcTranscribe(AHuaCcAudio, AHuaCcConfidence=True)
        AHuaCcOptions = self.AHuaCcTranslateOptions(AHuaCcText, AHuaCcCount=AHuaCcCount)
        AHuaCcResult = {
            'transcription': AHuaCcText,
            'word_confidence': [round(AHuaCcScore, 4) for AHuaCcScore in AHuaCcScores],
            'translation': AHuaCcOptions[0] if AHuaCcOptions else '',
        }
        if AHuaCcCount > 1:
            AHuaCcResult['alternatives'] = AHuaCcOptions[1:]
        return AHuaCcResult


def AHuaCcMain():
    AHuaCcParser = argparse.ArgumentParser(
        description='Standalone ASUS entry point: Quechua audio or text to Spanish, and Spanish text '
        'to Quechua, entirely local.'
    )
    AHuaCcEntry = AHuaCcParser.add_mutually_exclusive_group(required=True)
    AHuaCcEntry.add_argument('--audio', dest='AHuaCcAudio', type=Path)
    AHuaCcEntry.add_argument('--text', dest='AHuaCcText')
    AHuaCcParser.add_argument(
        '--reverse', dest='AHuaCcReverse', action='store_true',
        help='Translate Spanish text to Quechua (experimental; text input only)',
    )
    AHuaCcParser.add_argument(
        '--alternatives', dest='AHuaCcCount', type=int, choices=range(1, 4), default=1,
        help='Number of distinct translations to return (1 to 3)',
    )
    AHuaCcParser.add_argument('--root', dest='AHuaCcRoot', type=Path)
    AHuaCcParser.add_argument('--device', dest='AHuaCcDevice')
    AHuaCcArgs = AHuaCcParser.parse_args()
    if AHuaCcArgs.AHuaCcReverse and AHuaCcArgs.AHuaCcAudio:
        AHuaCcParser.error('--reverse only accepts --text; ASUS2 recognizes Quechua speech')
    AHuaCcRuntime = AHuaCcAsus(AHuaCcArgs.AHuaCcRoot, AHuaCcArgs.AHuaCcDevice)
    try:
        if AHuaCcArgs.AHuaCcAudio:
            AHuaCcResult = AHuaCcRuntime.AHuaCcInterpret(AHuaCcArgs.AHuaCcAudio, AHuaCcCount=AHuaCcArgs.AHuaCcCount)
        else:
            AHuaCcOptions = AHuaCcRuntime.AHuaCcTranslateOptions(
                AHuaCcArgs.AHuaCcText, AHuaCcReverse=AHuaCcArgs.AHuaCcReverse, AHuaCcCount=AHuaCcArgs.AHuaCcCount
            )
            AHuaCcResult = {'translation': AHuaCcOptions[0] if AHuaCcOptions else ''}
            if AHuaCcArgs.AHuaCcCount > 1:
                AHuaCcResult['alternatives'] = AHuaCcOptions[1:]
        print(json.dumps(AHuaCcResult, ensure_ascii=False))
    finally:
        AHuaCcRuntime.AHuaCcUnload()


if __name__ == '__main__':
    AHuaCcMain()
