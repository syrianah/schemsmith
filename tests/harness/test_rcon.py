"""The RCON client against a fake server."""

from __future__ import annotations

import socket

import pytest

from schemsmith.harness.rcon import RconAuthError, RconClient, RconError, encode_packet
from tests.harness.fake_rcon import FakeRconServer


def test_packet_layout() -> None:
    pkt = encode_packet(7, 2, "list")
    assert pkt == b"\x0e\x00\x00\x00" + b"\x07\x00\x00\x00" + b"\x02\x00\x00\x00" + b"list\x00\x00"


def test_login_and_command() -> None:
    srv = FakeRconServer("pw", lambda c: f"ran {c}")
    try:
        with RconClient("127.0.0.1", srv.port, "pw", timeout=5) as rcon:
            assert rcon.command("time query gametime") == "ran time query gametime"
            assert rcon.command("say ż") == "ran say ż"
        assert srv.commands == ["time query gametime", "say ż"]
    finally:
        srv.close()


def test_long_output_in_several_packets() -> None:
    big = "x" * 10_000
    srv = FakeRconServer("pw", lambda c: big, chunk=4096)
    try:
        with RconClient("127.0.0.1", srv.port, "pw", timeout=5) as rcon:
            assert rcon.command("data get block 0 0 0") == big
    finally:
        srv.close()


def test_wrong_password() -> None:
    srv = FakeRconServer("pw", lambda c: "")
    try:
        with pytest.raises(RconAuthError):
            RconClient("127.0.0.1", srv.port, "nope", timeout=5).connect()
    finally:
        srv.close()


def test_connection_refused_and_not_connected() -> None:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(RconError):
        RconClient("127.0.0.1", port, "pw", timeout=1).connect()
    with pytest.raises(RconError, match="not connected"):
        RconClient("127.0.0.1", port, "pw").command("list")


def test_too_long_command() -> None:
    srv = FakeRconServer("pw", lambda c: "")
    try:
        with RconClient("127.0.0.1", srv.port, "pw", timeout=5) as rcon, pytest.raises(RconError):
            rcon.command("say " + "a" * 2000)
    finally:
        srv.close()
