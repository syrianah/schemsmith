"""Stands in for ``java ... -jar server.jar nogui`` in offline tests.

Run as ``python fake_server.py <the server's arguments>`` in the run directory. It
refuses to start without an accepting ``eula.txt`` in its working directory (like
the real server), creates ``world/level.dat``, and serves RCON on the configured port
with a :class:`FakeWorld`. ``FAKE_SERVER_MODE=hang`` never opens RCON.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from schemsmith.harness.eula import decode_text, parse_eula
from tests.harness.fake_rcon import FakeRconServer
from tests.harness.fake_world import FakeWorld


def main() -> int:
    eula = Path("eula.txt")
    if not eula.is_file() or not parse_eula(decode_text(eula.read_bytes())):
        print("You need to agree to the EULA in order to run the server.", flush=True)
        return 1
    props = {}
    for line in Path("server.properties").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        props[key] = value
    assert props["server-ip"] == "127.0.0.1" and props["online-mode"] == "false"
    if os.environ.get("FAKE_SERVER_MODE") == "hang":
        time.sleep(600)
        return 0
    world = Path("world")
    world.mkdir(exist_ok=True)
    (world / "level.dat").write_bytes(b"fake")
    fake = FakeWorld(world_dir=world)
    srv = FakeRconServer(props["rcon.password"], fake.handle, port=int(props["rcon.port"]))
    print('Done (0.1s)! For help, type "help"', flush=True)
    while not fake.stopped:
        time.sleep(0.05)
    srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
