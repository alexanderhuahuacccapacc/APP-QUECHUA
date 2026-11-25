from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import default_data, installation_root, settings_file

ROOT = installation_root()


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=settings_file(), env_file_encoding="utf-8", env_prefix="XANDAR_", extra="ignore"
    )
    data_dir: Path = Field(default_factory=default_data)
    models_dir: Path = ROOT / "models" / "ASUS2"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    max_record_seconds: int = Field(default=30, ge=1, le=60)
    silence_seconds: float = Field(default=1.5, ge=0.3, le=5)
    max_text_chars: int = Field(default=500, ge=1, le=1000)

    @field_validator("models_dir")
    @classmethod
    def absolute_models(cls, value: Path) -> Path:
        return (ROOT / value).resolve()
