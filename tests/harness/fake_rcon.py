"""A fake RCON server for offline tests (no Minecraft involved)."""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable

Handler = Callable[[str], str]


class FakeRconServer:
    """Speaks the vanilla RCON protocol; ``handler`` answers commands."""

    def __init__(self, password: str, handler: Handler, chunk: int = 4096, port: int = 0) -> None:
        self.password = password
        self.handler = handler
        self.chunk = chunk
        self.commands: list[str] = []
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", port))
        self._srv.listen()
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._srv.close()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    @staticmethod
    def _send(conn: socket.socket, rid: int, kind: int, text: str) -> None:
        body = struct.pack("<ii", rid, kind) + text.encode("utf-8") + b"\x00\x00"
        conn.sendall(struct.pack("<i", len(body)) + body)

    def _client(self, conn: socket.socket) -> None:
        authed = False
        with conn:
            while True:
                head = conn.recv(4, socket.MSG_WAITALL)
                if len(head) < 4:
                    return
                (length,) = struct.unpack("<i", head)
                body = conn.recv(length, socket.MSG_WAITALL)
                rid, kind = struct.unpack("<ii", body[:8])
                text = body[8:-2].decode("utf-8")
                if kind == 3:
                    authed = text == self.password
                    self._send(conn, rid if authed else -1, 2, "")
                elif kind == 2 and authed:
                    self.commands.append(text)
                    out = self.handler(text)
                    for i in range(0, max(len(out), 1), self.chunk):
                        self._send(conn, rid, 0, out[i : i + self.chunk])
                else:
                    self._send(conn, rid, 0, f"Unknown request {kind:x}")
