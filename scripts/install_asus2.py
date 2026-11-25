"""Install the exact ASUS2 desktop models on a clean development checkout."""

import argparse
import getpass
import os
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from zipfile import BadZipFile

from scripts.companion_models import install_companions
from scripts.download_asus2 import download as download_asus2
from scripts.release_models import install_release

if TYPE_CHECKING:
    from paramiko import SSHClient

ROOT = Path(__file__).resolve().parents[1]
HOST = "172.22.2.44"
HOST_KEY = "SHA256:mr8Y+gxQGtL6zhk4AguWGdhDJOiZ0PQM8i7IbswK4hE"
PACKAGE = "/mnt/temp/xandar-cusco-alexccama-20261104/experiments/asus2-20261122/ASUS2"
WEIGHTS = {
    PurePosixPath("speech/model.safetensors"):
        "3c9fc5832b0a7971eb2502cc6ae9ac4a8cc9553605db2145addfd56490e51ad3",
    PurePosixPath("translation/model.safetensors"):
        "0b318d9c0a0e07229130afaa7e9ffeb84eef82129d06edec2e9d544bc06287a2",
}


def connect(host: str, user: str, password: str) -> "SSHClient":
    import paramiko

    class PinnedHostKey(paramiko.MissingHostKeyPolicy):
        def missing_host_key(
            self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey,
        ) -> None:
            if key.fingerprint != HOST_KEY:
                raise paramiko.SSHException("La identidad del servidor ASUS2 no coincide.")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(PinnedHostKey())
    try:
        client.connect(
            host, username=user, password=password, timeout=15, banner_timeout=20,
            auth_timeout=20, allow_agent=False, look_for_keys=False,
        )
    except Exception:
        client.close()
        raise
    return client


def install(host: str, user: str, password: str, root: Path) -> None:
    target = (root / "ASUS2").resolve()
    with connect(host, user, password) as client, client.open_sftp() as sftp:
        sftp.get_channel().settimeout(120)
        download_asus2(sftp, PACKAGE, target, None, expected_weights=WEIGHTS)

    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ.pop(key, None)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    install_companions(root)


def main() -> None:
    import paramiko

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", help="Cuenta SSH para descargar desde el servidor universitario")
    parser.add_argument("--host", default=HOST, help="Dirección del servidor ASUS2")
    args = parser.parse_args()
    root = ROOT / "models"
    try:
        if args.user:
            password = getpass.getpass("Contraseña SSH del servidor ASUS2: ")
            install(args.host, args.user, password, root)
        else:
            install_release(root)
    except paramiko.AuthenticationException:
        parser.exit(1, "El servidor ASUS2 rechazó las credenciales de la cuenta.\n")
    except (OSError, ValueError, BadZipFile, paramiko.SSHException) as error:
        parser.exit(1, f"No se pudo completar la instalación de ASUS2: {error}\n")
    print("ASUS2 instalado y verificado. Los modelos ya se pueden usar sin conexión.", flush=True)


if __name__ == "__main__":
    main()
