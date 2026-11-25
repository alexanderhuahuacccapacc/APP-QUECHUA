"""Punto de entrada para la edición de escritorio de ASUS2."""

import argparse
import sys
from pathlib import Path

from app.core.offline import enforce_offline

enforce_offline()


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from app.core.config import Config
    from app.core.paths import frozen, installation_root
    from app.ui.asus2_desktop import Asus2Desktop

    root = installation_root()
    parser = argparse.ArgumentParser(description="Xandar · ASUS2 de escritorio")
    packed_model = root / "ASUS2"
    default_model = packed_model if frozen() and packed_model.is_dir() else root / "models" / "ASUS2"
    parser.add_argument("--asus2", type=Path, default=default_model)
    args = parser.parse_args()
    application = QApplication([sys.argv[0]])
    application.setApplicationName("Xandar · ASUS2")
    window = Asus2Desktop(
        Config(models_dir=args.asus2.resolve()), companion_root=root / "models"
    )
    window.showMaximized()
    application.exec()


if __name__ == "__main__":
    main()
