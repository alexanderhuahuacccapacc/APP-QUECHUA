"""Install the locked desktop model package from APP-QUECHUA releases."""

import hashlib
import json
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from scripts.companion_models import matches

MANIFEST = Path(__file__).with_name("asus2-release.json")
RELEASE_URL = "https://github.com/alexanderhuahuacccapacc/APP-QUECHUA/releases/download"
BLOCK_SIZE = 4 * 1024 * 1024


def download_asset(url: str, name: str, expected: dict, output: BinaryIO) -> None:
    start = output.tell()
    request = Request(f"{url}/{name}", headers={"User-Agent": "APP-QUECHUA-ASUS2"})
    for attempt in range(3):
        output.seek(start)
        output.truncate()
        digest = hashlib.sha256()
        received = 0
        last = time.monotonic()
        print(f"Descargando {name} ({expected['bytes']:,} bytes)", flush=True)
        try:
            with urlopen(request, timeout=45) as response:
                while block := response.read(BLOCK_SIZE):
                    received += len(block)
                    if received > expected["bytes"]:
                        raise ValueError(f"Tamaño inesperado de {name}")
                    output.write(block)
                    digest.update(block)
                    now = time.monotonic()
                    if now - last >= 20:
                        print(f"{name}: {received * 100 / expected['bytes']:.1f}%", flush=True)
                        last = now
            if received != expected["bytes"]:
                raise OSError(f"Descarga incompleta de {name}")
        except OSError as error:
            if attempt == 2 or (isinstance(error, HTTPError) and error.code in (401, 403, 404)):
                raise OSError(f"No se pudo descargar {name} desde GitHub: {error}") from error
            print(f"Reintentando {name}: {error}", flush=True)
            time.sleep(2 * (attempt + 1))
            continue
        if digest.hexdigest() != expected["sha256"]:
            raise ValueError(f"SHA-256 incorrecto para {name}")
        print(f"SHA-256 verificado: {name}", flush=True)
        return


def target_path(root: Path, name: str) -> Path:
    target = root / name
    if not target.resolve().is_relative_to(root):
        raise ValueError(f"Ruta fuera de la carpeta de modelos: {name}")
    return target


def install_archive(root: Path, url: str, name: str, manifest: dict) -> None:
    entries = manifest["archives"][name]
    targets = {filename: target_path(root, filename) for filename in entries}
    missing = [
        filename for filename, expected in entries.items()
        if not matches(targets[filename], expected["bytes"], expected["sha256"])
    ]
    if not missing:
        return
    with TemporaryDirectory(prefix=".asus2-", dir=root) as directory:
        staging = Path(directory)
        archive_path = staging / "download.zip"
        with archive_path.open("wb") as output:
            download_asset(url, name, manifest["assets"][name], output)
        with ZipFile(archive_path) as archive:
            members = archive.namelist()
            if len(members) != len(entries) or set(members) != set(entries):
                raise ValueError(f"Archivos inesperados en {name}")
            for filename in missing:
                target = targets[filename]
                temporary = staging / filename
                temporary.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(filename) as source, temporary.open("wb") as output:
                    shutil.copyfileobj(source, output, BLOCK_SIZE)
                expected = entries[filename]
                if not matches(temporary, expected["bytes"], expected["sha256"]):
                    raise ValueError(f"Archivo de modelo incorrecto: {filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary.replace(target)


def install_weights(root: Path, url: str, component: str, manifest: dict) -> None:
    expected = manifest["weights"][component]
    target = target_path(root, f"ASUS2/{component}/model.safetensors")
    if matches(target, expected["bytes"], expected["sha256"]):
        print(f"Peso local verificado: {component}", flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".asus2-", dir=target.parent) as directory:
        temporary = Path(directory) / target.name
        with temporary.open("wb") as output:
            for name in expected["assets"]:
                download_asset(url, name, manifest["assets"][name], output)
        if not matches(temporary, expected["bytes"], expected["sha256"]):
            raise ValueError(f"El peso final de {component} no coincide con ASUS2")
        temporary.replace(target)


def install_release(root: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    url = f"{RELEASE_URL}/{manifest['tag']}"
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    install_archive(root, url, "asus2-config.zip", manifest)
    for component in manifest["weights"]:
        install_weights(root, url, component, manifest)
    install_archive(root, url, "asus2-companions.zip", manifest)
