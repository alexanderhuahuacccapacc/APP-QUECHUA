import os
import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installation_root() -> Path:
    return (
        Path(sys.executable).resolve().parent if frozen() else Path(__file__).resolve().parents[2]
    )


def default_data() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
    return base / "XandarInterprete"


def settings_file() -> Path:
    return default_data() / "settings.env" if frozen() else installation_root() / ".env"


def default_models() -> Path:
    return installation_root().parent / "models" if frozen() else installation_root() / "models"


def save_setting(name: str, value: str, target: Path | None = None) -> None:
    import json
    import re

    if name not in {"XANDAR_MODELS_DIR", "XANDAR_DATA_DIR"} or any(c in value for c in "\r\n\x00"):
        raise ValueError("Configuración inválida")
    target = target or settings_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8-sig") if target.exists() else ""
    line = name + "=" + json.dumps(value, ensure_ascii=False)
    pattern = re.compile(r"(?m)^" + name + r"=.*$")
    content = (
        pattern.sub(lambda _: line, existing)
        if pattern.search(existing)
        else existing.rstrip() + "\n" + line + "\n"
    )
    temporary = target.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)
