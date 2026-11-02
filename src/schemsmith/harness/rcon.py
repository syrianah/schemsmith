"""A minimal Source RCON client (stdlib sockets), as spoken by the vanilla server.

Packet: ``int32 length`` (little endian, counts the rest), ``int32 request id``,
``int32 type``, payload bytes, two NUL bytes. Types: 3 = login, 2 = command,
0 = response. A failed login answers with request id -1.

The vanilla server reads one packet per socket read (at most 1460 bytes) and drops
the connection when a read holds more than one packet, so the client sends exactly
one packet and waits for its answer. Long output arrives split into response
packets of 4096 characters; a full-size packet means more may follow, so the
client then waits briefly for the next one.
"""

from __future__ import annotations

import socket
import struct
from types import TracebackType

LOGIN = 3
COMMAND = 2
RESPONSE = 0
MAX_PAYLOAD = 1446
"""Longest command the vanilla server accepts in one packet."""
CHUNK = 4096
"""Characters per response packet; a full packet may be followed by more."""
MORE_WAIT_S = 0.25
"""How long to wait for a further packet after a full-size one."""


class RconError(ConnectionError):
    """The RCON connection failed or the server answered nonsense."""


class RconAuthError(RconError):
    """Wrong RCON password."""


def encode_packet(request_id: int, kind: int, payload: str) -> bytes:
    """One RCON packet."""
    body = struct.pack("<ii", request_id, kind) + payload.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(body)) + body


class RconClient:
    """``with RconClient(host, port, password) as rcon: rcon.command("list")``."""

    def __init__(self, host: str, port: int, password: str, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._next_id = 1

    def __enter__(self) -> RconClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        """Open the socket and log in."""
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise RconError(f"cannot connect to RCON at {self.host}:{self.port}: {exc}") from exc
        rid = self._send(LOGIN, self.password)
        while True:
            got_id, kind, _ = self._read()
            if got_id == -1:
                self.close()
                raise RconAuthError("RCON login refused (wrong password)")
            if got_id == rid and kind == COMMAND:  # the login answer uses type 2
                return

    def close(self) -> None:
        """Close the socket (safe to call twice)."""
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def command(self, cmd: str) -> str:
        """Run one server command and return its full output."""
        if self._sock is None:
            raise RconError("not connected")
        if len(cmd.encode("utf-8")) > MAX_PAYLOAD:
            raise RconError(f"command longer than {MAX_PAYLOAD} bytes")
        rid = self._send(COMMAND, cmd)
        parts: list[str] = []
        while True:
            got_id, _kind, text = self._read()
            if got_id == rid:
                parts.append(text)
                if len(text) < CHUNK or not self._more_waiting():
                    return "".join(parts)

    def _more_waiting(self) -> bool:
        """True if another packet arrives within :data:`MORE_WAIT_S`."""
        assert self._sock is not None
        self._sock.settimeout(MORE_WAIT_S)
        try:
            return bool(self._sock.recv(1, socket.MSG_PEEK))
        except TimeoutError:
            return False
        except OSError as exc:
            raise RconError(f"RCON receive failed: {exc}") from exc
        finally:
            self._sock.settimeout(self.timeout)

    def _send(self, kind: int, payload: str) -> int:
        assert self._sock is not None
        rid = self._next_id
        self._next_id += 1
        try:
            self._sock.sendall(encode_packet(rid, kind, payload))
        except OSError as exc:
            raise RconError(f"RCON send failed: {exc}") from exc
        return rid

    def _recv_exact(self, n: int) -> bytes:
        assert self._sock is not None
        buf = bytearray()
        while len(buf) < n:
            try:
                chunk = self._sock.recv(n - len(buf))
            except OSError as exc:  # includes socket.timeout
                raise RconError(f"RCON receive failed: {exc}") from exc
            if not chunk:
                raise RconError("RCON connection closed by the server")
            buf += chunk
        return bytes(buf)

    def _read(self) -> tuple[int, int, str]:
        (length,) = struct.unpack("<i", self._recv_exact(4))
        if not 10 <= length <= 1 << 20:
            raise RconError(f"bad RCON packet length {length}")
        body = self._recv_exact(length)
        rid, kind = struct.unpack("<ii", body[:8])
        return rid, kind, body[8:-2].decode("utf-8", errors="replace")


__all__ = ["RconAuthError", "RconClient", "RconError", "encode_packet"]
