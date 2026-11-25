import os
import socket
import sys
from typing import Any

import pytest

from app.core.offline import enforce_offline

os.environ["QT_QPA_PLATFORM"] = "offscreen"
enforce_offline()


@pytest.fixture(autouse=True)
def disconnected_network(monkeypatch: pytest.MonkeyPatch) -> None:
    native_connect = socket.socket.connect

    def blocked_connect(connection: Any, address: Any) -> Any:
        caller = sys._getframe(1)
        if (
            isinstance(address, tuple)
            and address[0] in ("127.0.0.1", "::1")
            and caller.f_code.co_name == "_fallback_socketpair"
            and caller.f_code.co_filename == socket.__file__
        ):
            return native_connect(connection, address)
        raise AssertionError("El núcleo intentó acceder a la red")

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("El núcleo intentó acceder a la red")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
