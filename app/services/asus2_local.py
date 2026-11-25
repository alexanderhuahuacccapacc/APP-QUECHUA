"""Offline audio and personal phrase storage for the ASUS2 desktop interface."""

import base64
import json
import os
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime
from pathlib import Path
from shutil import disk_usage
from tempfile import NamedTemporaryFile
from typing import Any
from zipfile import ZIP_STORED, ZipFile

import numpy as np
import soundfile as sf

from app.core.security import Vault
from app.services.interfaces import AudioInputError, Samples


class PhraseLibrary:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.path = directory / "frases.sqlite3"
        self._vault: Vault | None = None

    @property
    def vault(self) -> Vault:
        if self._vault is None:
            self._vault = Vault(self.directory)
        return self._vault

    def save(self, kind: str, phrase: dict[str, Any]) -> None:
        encrypted = self.vault.encrypt(json.dumps(phrase, ensure_ascii=False))
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS phrases "
                "(kind TEXT NOT NULL, saved_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute("INSERT INTO phrases VALUES (?, ?, ?)",
                               (kind, datetime.now().isoformat(timespec="seconds"), encrypted))

    def entries(self, kind: str, *, include_id: bool = False) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT rowid, saved_at, payload FROM phrases WHERE kind = ? ORDER BY rowid DESC", (kind,)
            )
            entries = []
            for row_id, saved_at, payload in rows:
                entry = dict(json.loads(self.vault.decrypt(payload)), fecha=saved_at)
                if include_id:
                    entry["_id"] = row_id
                entries.append(entry)
            return entries

    def delete(self, kind: str, row_id: int) -> None:
        if not self.path.is_file():
            return
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA secure_delete=ON")
            connection.execute("DELETE FROM phrases WHERE kind = ? AND rowid = ?", (kind, row_id))

    def clear(self, kind: str) -> None:
        if not self.path.is_file():
            return
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA secure_delete=ON")
            connection.execute("DELETE FROM phrases WHERE kind = ?", (kind,))


def read_audio(path: Path) -> Samples:
    try:
        with sf.SoundFile(path) as audio:
            rate = audio.samplerate
            if not 0.1 <= audio.frames / rate <= 60:
                raise AudioInputError("Elige un audio de entre 0,1 y 60 segundos.")
            samples: Samples = audio.read(dtype="float32", always_2d=True).mean(axis=1)
    except (OSError, RuntimeError) as exc:
        raise AudioInputError("El archivo de audio no se pudo abrir. Prueba con WAV, MP3, FLAC u OGG.") from exc
    if rate == 16000:
        return samples
    if rate > 16000:
        positions = np.arange(-40, 41)
        cutoff = 0.45 * 16000 / rate
        kernel = 2 * cutoff * np.sinc(2 * cutoff * positions) * np.hanning(81)
        samples = np.convolve(samples, kernel / kernel.sum(), mode="same")
    positions = np.arange(round(len(samples) * 16000 / rate)) * rate / 16000
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def export_model(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target.is_relative_to(root):
        raise AudioInputError("Guarda la copia en una carpeta fuera de ASUS2.")
    files = [path for path in root.rglob("*")
             if path.is_file() and path.resolve().is_relative_to(root)
             and "__pycache__" not in path.relative_to(root).parts]
    expected = sum(path.stat().st_size for path in files)
    if disk_usage(target.parent).free < expected + 1024 * 1024:
        raise AudioInputError("La unidad seleccionada necesita espacio para una copia completa de ASUS2.")
    with NamedTemporaryFile(prefix=".asus2-", suffix=".zip", dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_STORED) as archive:
            for path in files:
                archive.write(path, (Path("ASUS2") / path.relative_to(root)).as_posix())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def speak_spanish(text: str) -> None:
    if os.name != "nt":
        raise AudioInputError("La lectura local en español usa las voces instaladas en Windows.")
    script = """
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Speech
$voice = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
  $spanish = $voice.GetInstalledVoices() | Where-Object {
    $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es'
  } | Select-Object -First 1
  if (!$spanish) { exit 7 }
  $voice.SelectVoice($spanish.VoiceInfo.Name)
  $voice.Speak([Console]::In.ReadToEnd())
} finally {
  $voice.Dispose()
}
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        response = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=60, check=False, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioInputError("La voz de Windows no pudo completar la lectura.") from exc
    if response.returncode == 7:
        raise AudioInputError("Instala una voz en español en Configuración de Windows → Voz.")
    if response.returncode:
        raise AudioInputError("No se pudo reproducir la voz en español. Comprueba la salida de audio.")
