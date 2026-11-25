"""Download the ASUS2 research package and verify both model weight files."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import time
from pathlib import Path, PurePosixPath

PACKAGE_ROOT = PurePosixPath()


def inventory(sftp, source: str, relative: PurePosixPath = PACKAGE_ROOT):
    for item in sftp.listdir_attr(f"{source}/{relative}" if relative.parts else source):
        if item.filename in (".", "..") or any(char in item.filename for char in "/\\:"):
            raise ValueError(f"Invalid package path: {item.filename!r}")
        path = relative / item.filename
        if item.filename == "__pycache__" and stat.S_ISDIR(item.st_mode):
            continue
        if stat.S_ISDIR(item.st_mode):
            yield from inventory(sftp, source, path)
        elif stat.S_ISREG(item.st_mode):
            yield path, item.st_size
        else:
            raise ValueError(f"Unsupported package member: {path}")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(
    sftp, source: str, destination: Path, reuse_from: Path | None, *,
    expected_weights: dict[PurePosixPath, str] | None = None,
) -> dict:
    with sftp.open(f"{source}/MANIFEST.json", "rb") as stream:
        manifest_bytes = stream.read()
    manifest = json.loads(manifest_bytes)
    if manifest["name"] != "ASUS2":
        raise ValueError("Unexpected model in the package manifest")
    expected = {
        PurePosixPath(component, "model.safetensors"): manifest[component]["weights_sha256"]
        for component in ("speech", "translation")
    }
    if expected_weights is not None and expected != expected_weights:
        raise ValueError("Los pesos del servidor no corresponden a la versión ASUS2 esperada.")
    files = dict(inventory(sftp, source))
    if not expected.keys() <= files.keys():
        raise ValueError("Package is missing model weights")
    destination.mkdir(parents=True, exist_ok=True)
    pending = []
    checksums = {}
    reused_weights = []
    for relative, size in files.items():
        target = destination.joinpath(*relative.parts)
        if not target.resolve().is_relative_to(destination):
            raise ValueError(f"Package path resolves outside the destination: {relative}")
        if relative in expected and target.is_file() and target.stat().st_size == size:
            checksum = sha256(target)
            if checksum == expected[relative]:
                checksums[str(relative)] = checksum
                continue
        if reuse_from is not None and relative in expected and not target.exists():
            previous = reuse_from.joinpath(*relative.parts)
            if previous.is_file() and previous.stat().st_size == size:
                checksum = sha256(previous)
                if checksum == expected[relative]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.hardlink_to(previous)
                    checksums[str(relative)] = checksum
                    reused_weights.append(str(relative))
                    print(f"Verified SHA-256 and linked local weight: {relative}", flush=True)
                    continue
        pending.append((relative, target, size))
    if shutil.disk_usage(destination).free < sum(size for _, _, size in pending):
        raise OSError("Not enough disk space for the ASUS2 download")

    pending.sort(key=lambda item: (str(item[0]) == "MANIFEST.json", item[2]))
    for relative, target, size in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".downloading")
        if temporary.is_symlink() or temporary.is_junction():
            raise ValueError(f"Temporary path is a link: {relative}")
        print(f"Downloading {relative} ({size:,} bytes)", flush=True)
        last_report = time.monotonic()

        def progress(received: int, total: int, path: PurePosixPath = relative) -> None:
            nonlocal last_report
            now = time.monotonic()
            if now - last_report >= 15:
                print(f"{path}: {received:,}/{total:,} bytes", flush=True)
                last_report = now

        sftp.get(f"{source}/{relative}", str(temporary), callback=progress,
                 max_concurrent_prefetch_requests=48)
        if temporary.stat().st_size != size:
            raise OSError(f"Incomplete file: {relative}")
        if relative == PurePosixPath("MANIFEST.json") and temporary.read_bytes() != manifest_bytes:
            raise OSError("Server manifest changed during the download")
        checksum = sha256(temporary)
        if relative in expected and checksum != expected[relative]:
            raise OSError(f"SHA-256 mismatch: {relative}")
        checksums[str(relative)] = checksum
        temporary.replace(target)
    return {
        "model": manifest["name"],
        "package": source,
        "destination": str(destination),
        "total_bytes": sum(files.values()),
        "file_count": len(files),
        "sha256": checksums,
        "hardlinked_verified_weights": reused_weights,
        "weights_match_server_manifest": True,
    }
