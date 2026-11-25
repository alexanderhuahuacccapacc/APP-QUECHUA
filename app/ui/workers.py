from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from app.services.interfaces import AudioInputError


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = Signals()

    @Slot()
    def run(self) -> None:
        try:
            value = self.operation()
        except Exception as exc:
            import logging

            # Do not log model inputs, transcripts, passwords or file contents.
            logging.getLogger(__name__).error("worker_failed type=%s", type(exc).__name__)
            self.signals.failed.emit(
                str(exc) if isinstance(exc, AudioInputError) else
                f"{type(exc).__name__}: no se pudo completar la operación. Revisa modelos, audio y espacio en disco."
            )
        else:
            self.signals.done.emit(value)
