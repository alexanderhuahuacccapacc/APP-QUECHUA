from dataclasses import dataclass

from app.services.interfaces import Samples


@dataclass(frozen=True)
class Speech:
    samples: Samples | None
    sample_rate: int
    source: str
    note: str = ""
