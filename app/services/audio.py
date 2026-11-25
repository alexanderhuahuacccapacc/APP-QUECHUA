import io
from collections.abc import Callable
from pathlib import Path
from threading import Event
from uuid import uuid4

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad

from app.core.security import Vault
from app.services.interfaces import AudioInputError, AudioService, AudioStorage, Samples


class MicrophoneAudio(AudioService):
    def __init__(self, max_seconds: int = 30, silence_seconds: float = 1.5) -> None:
        self.max_seconds = max_seconds
        self.silence_seconds = silence_seconds
        self.device: int | None = None

    @staticmethod
    def input_devices() -> list[tuple[int, str]]:
        """List inputs compatible with the recognizer without opening a microphone."""
        try:
            devices = sd.query_devices()
            hosts = sd.query_hostapis()
            result = []
            for index, device in enumerate(devices):
                if device["max_input_channels"] < 1:
                    continue
                try:
                    sd.check_input_settings(
                        device=index, channels=1, samplerate=16000, dtype="int16"
                    )
                except sd.PortAudioError:
                    continue
                host = hosts[device["hostapi"]]["name"]
                result.append((index, f"{device['name']} · {host}"))
            return result
        except sd.PortAudioError:
            return []

    def _input_stream(self) -> sd.InputStream:
        try:
            selected = self.device if self.device is not None else int(sd.default.device[0])
            if selected < 0:
                raise AudioInputError(
                    "No hay micrófono predeterminado. Conecta uno y selecciónalo en Micrófono."
                )
            devices = sd.query_devices()
            if selected >= len(devices) or devices[selected]["max_input_channels"] < 1:
                raise AudioInputError(
                    "El micrófono seleccionado ya no está disponible. Actualiza la lista y elige otro."
                )
            candidates = [selected]
            if self.device is None:
                # Retry another Windows audio API for the same named microphone only.
                # Never silently switch to a different physical input or stereo mix.
                candidates.extend(
                    index
                    for index, device in enumerate(devices)
                    if index != selected
                    and device["max_input_channels"] > 0
                    and device["name"] == devices[selected]["name"]
                )
            for candidate in candidates:
                try:
                    sd.check_input_settings(
                        device=candidate, channels=1, samplerate=16000, dtype="int16"
                    )
                    return sd.InputStream(
                        device=candidate, samplerate=16000, channels=1,
                        dtype="int16", blocksize=480,
                    )
                except sd.PortAudioError:
                    continue
        except sd.PortAudioError:
            pass
        raise AudioInputError(
            "No se pudo abrir el micrófono. Selecciona otro en Micrófono y cierra otras "
            "apps que lo estén usando. En Windows revisa Configuración → Privacidad y "
            "seguridad → Micrófono → Permitir que las aplicaciones de escritorio accedan."
        ) from None

    def check_input(self) -> None:
        """Open and close the selected input without reading or retaining audio."""
        try:
            with self._input_stream():
                pass
        except sd.PortAudioError:
            raise AudioInputError(
                "No se pudo iniciar el micrófono. Revisa el dispositivo, sus permisos "
                "de Windows y las aplicaciones que lo estén utilizando."
            ) from None

    def capture(self, stop: Event, *, on_level: Callable[[float], None] | None = None) -> Samples:
        try:
            return self._capture(stop, on_level)
        except sd.PortAudioError:
            raise AudioInputError(
                "Se interrumpió el micrófono. Actualiza la lista, selecciona el dispositivo "
                "y comprueba sus permisos de Windows antes de volver a grabar."
            ) from None

    def _capture(self, stop: Event, on_level: Callable[[float], None] | None = None) -> Samples:
        vad = webrtcvad.Vad(2)
        frames: list[Samples] = []
        quiet = 0
        voiced = 0
        # 30ms frames at 16kHz, required by WebRTC VAD. Preserve the whole original.
        with self._input_stream() as stream:
            for _ in range(int(self.max_seconds / 0.03)):
                if stop.is_set():
                    break
                frame, overflow = stream.read(480)
                if overflow:
                    raise AudioInputError("El micrófono perdió audio; vuelve a grabar.")
                speaking = vad.is_speech(frame.tobytes(), 16000)
                samples = frame[:, 0].astype(np.float32) / 32768
                frames.append(samples)
                if on_level is not None:
                    on_level(float(np.max(np.abs(samples))))
                voiced += int(speaking)
                quiet = 0 if speaking else quiet + 1
                if voiced > 5 and quiet * 0.03 >= self.silence_seconds:
                    break
        if voiced < 3 or not frames:
            raise AudioInputError("No se detectó voz. Comprueba el micrófono y vuelve a hablar.")
        return np.concatenate(frames).astype(np.float32)

    def play(self, samples: Samples, sample_rate: int = 16000, device: int | None = None) -> None:
        sd.play(samples, samplerate=sample_rate, device=device)
        sd.wait()


class EncryptedWavStorage(AudioStorage):
    def __init__(self, directory: Path, vault: Vault) -> None:
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.vault = vault

    def save(self, samples: Samples) -> Path:
        buffer = io.BytesIO()
        sf.write(buffer, samples, 16000, format="WAV", subtype="PCM_16")
        path = self.directory / f"{uuid4()}.wav.enc"
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(self.vault.cipher.encrypt(buffer.getvalue()))
        temporary.replace(path)
        return path

    def load(self, path: Path) -> Samples:
        path = path.resolve()
        if not path.is_relative_to(self.directory):
            raise ValueError("Audio fuera del directorio permitido")
        raw = self.vault.cipher.decrypt(path.read_bytes())
        samples, rate = sf.read(io.BytesIO(raw), dtype="float32")
        if rate != 16000 or samples.ndim != 1:
            raise ValueError("Formato de audio original inválido")
        return np.asarray(samples, dtype=np.float32)
