import hashlib
import json
from pathlib import Path


def verify_models(root: Path, include_tts: bool = False) -> str:
    manifest = root / "manifest.json"
    if not manifest.is_file():
        raise ValueError(
            "Faltan modelos. Ejecute scripts/download_models.py durante la instalación."
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    files = data.get("files", {})
    required = {
        "nllb-ct2/model.bin",
        "mms-asr/config.json",
        "whisper-es/config.json",
        "mms-asr/adapter.quz.safetensors",
        "mms-asr/adapter.ayr.safetensors",
    }
    if data.get("format") != 1 or not required.issubset(files):
        raise ValueError("Manifiesto de modelos incompleto")
    base = root.resolve()
    checked = 0
    for name, info in files.items():
        if name.startswith("tts-") and not include_tts:
            continue
        path = (base / name).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError("Modelo ausente o ruta inválida en manifiesto")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                hasher.update(block)
        if path.stat().st_size != info["bytes"] or hasher.hexdigest() != info["sha256"]:
            raise ValueError(f"Modelo modificado o incompleto: {name}")
        checked += 1
    return f"{checked} archivos verificados"


def verify_voice(root: Path, folder: str) -> None:
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    files = {name: value for name, value in data["files"].items() if name.startswith(folder + "/")}
    if not files or folder not in ("tts-es", "tts-quz", "tts-aym", "tts-quy"):
        raise ValueError("Voz no verificada en el manifiesto de instalación")
    for name, info in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Archivo de voz ausente")
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                hasher.update(block)
        if hasher.hexdigest() != info["sha256"]:
            raise ValueError("Archivo de voz modificado")
