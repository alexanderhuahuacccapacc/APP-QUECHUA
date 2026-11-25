import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

RECORD = Path(__file__).with_name("asus2_companions.json")


def matches(path: Path, size: int, checksum: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == checksum


def install_companions(root: Path) -> None:
    from huggingface_hub import snapshot_download

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    for folder, source in record["sources"].items():
        files = {
            name.removeprefix(folder + "/"): info
            for name, info in record["files"].items() if name.startswith(folder + "/")
        }
        target = root / folder
        if all(matches(target / name, info["bytes"], info["sha256"]) for name, info in files.items()):
            continue
        print(f"Descargando {source['repo']}", flush=True)
        with TemporaryDirectory(prefix=".asus2-", dir=root) as staging:
            directory = Path(staging)
            snapshot_download(
                source["repo"], revision=source["revision"], allow_patterns=list(files),
                local_dir=directory, max_workers=3,
            )
            for name, info in files.items():
                if not matches(directory / name, info["bytes"], info["sha256"]):
                    raise ValueError(f"El archivo auxiliar no coincide con su SHA-256: {folder}/{name}")
            target.mkdir(exist_ok=True)
            for name in files:
                (directory / name).replace(target / name)

    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=root, prefix=".manifest-", suffix=".tmp", delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(record, stream, ensure_ascii=False, indent=2)
    try:
        temporary.replace(root / "manifest.json")
    finally:
        temporary.unlink(missing_ok=True)
