import ctypes
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet


def _dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    crypt.CryptProtectData.argtypes = [
        ctypes.POINTER(Blob),
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    crypt.CryptProtectData.restype = wintypes.BOOL
    crypt.CryptUnprotectData.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    if decrypt:
        result = crypt.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)
        )
    else:
        result = crypt.CryptProtectData(
            ctypes.byref(source), "Xandar", None, None, None, 1, ctypes.byref(target)
        )
    if not result:
        raise OSError("No se pudo acceder a la clave protegida de este usuario de Windows")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class Vault:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        keyfile = directory / ("key.dpapi" if os.name == "nt" else "key.fernet")
        if not keyfile.exists():
            key = Fernet.generate_key()
            try:
                fd = os.open(keyfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(_dpapi(key) if os.name == "nt" else key)
        stored = keyfile.read_bytes()
        self._key = _dpapi(stored, decrypt=True) if os.name == "nt" else stored
        self.cipher = Fernet(self._key)

    def export_key(self) -> bytes:
        """Only for the password-encrypted portable backup container."""
        return self._key

    @staticmethod
    def import_key(directory: Path, key: bytes) -> None:
        Fernet(key)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ("key.dpapi" if os.name == "nt" else "key.fernet")
        with path.open("xb") as stream:
            stream.write(_dpapi(key) if os.name == "nt" else key)

    def encrypt(self, text: str) -> str:
        return self.cipher.encrypt(text.encode()).decode("ascii")

    def decrypt(self, token: str) -> str:
        return self.cipher.decrypt(token.encode("ascii")).decode()

    @staticmethod
    def username_hash(username: str) -> str:
        return hashlib.sha256(username.strip().casefold().encode()).hexdigest()
