import asyncio
import json
import secrets
import signal
import socket
import sys

import uvicorn

from . import config
from .api import create_app


class ReadyServer(uvicorn.Server):
    def __init__(self, config_: uvicorn.Config, ready_line: str):
        super().__init__(config_)
        self.ready_line = ready_line

    async def startup(self, sockets=None):
        await super().startup(sockets)
        if self.started:
            print(self.ready_line, flush=True)


def _free_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    return sock


def main() -> None:
    if config.DEV:
        port, token = config.DEV_PORT, config.DEV_TOKEN
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
    else:
        sock = _free_socket()
        port, token = sock.getsockname()[1], secrets.token_urlsafe(32)

    app = create_app(token=token)
    ready = "NMWFM_READY " + json.dumps({"port": port, "token": token})
    server = ReadyServer(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="info" if config.DEV else "warning"
        ),
        ready,
    )
    app.state.salir = lambda: setattr(server, "should_exit", True)

    async def servir() -> None:
        loop = asyncio.get_running_loop()
        for nombre in ("SIGTERM", "SIGINT", "SIGBREAK"):
            numero = getattr(signal, nombre, None)
            if numero is None:
                continue
            try:
                loop.add_signal_handler(numero, app.state.salir)
            except NotImplementedError:
                signal.signal(numero, lambda *_: loop.call_soon_threadsafe(app.state.salir))
        await server.serve(sockets=[sock])

    try:
        asyncio.run(servir())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
