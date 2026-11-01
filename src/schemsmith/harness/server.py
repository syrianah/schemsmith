"""A throwaway vanilla dedicated server for one harness run.

Order of operations (each step only after the previous one succeeded):

1. the EULA gate (:func:`~schemsmith.harness.eula.require_eula`): nothing is created
   or started without the owner's own acceptance file;
2. find ``server.jar`` in ``.mc-cache/<version>/`` (downloaded earlier by
   ``scripts/gen_registry.py`` from Mojang's official manifest; never committed);
3. a fresh directory ``.mc-cache/harness/run-*`` with ``server.properties``:
   127.0.0.1, random ports, offline mode, RCON with a random password, a flat
   world; no ``eula.txt`` is written;
4. ``java -Dcom.mojang.eula.agree=true -jar server.jar nogui`` in its own process
   group, output to ``server.log``;
5. wait for RCON, install the structure as a data pack (the ``schemsmith install``
   writer), ``/reload``, force-load the chunks, ``/place template``;
6. on exit, error, timeout or Ctrl+C: ``/stop``, then kill the process tree, then
   delete the directory (unless ``keep``).
"""

from __future__ import annotations

import contextlib
import secrets
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import IO

from schemsmith.core import Structure
from schemsmith.harness.eula import EULA_PROPERTY, require_eula
from schemsmith.harness.process import free_port, kill_tree, start
from schemsmith.harness.rcon import RconClient, RconError
from schemsmith.install import install_structure

ORIGIN = (0, -60, 0)
"""Where structures are placed: on top of the flat world (surface at y=-61)."""
FLAT_WORLD = (
    '{"layers":[{"block":"minecraft:bedrock","height":1},'
    '{"block":"minecraft:stone","height":3}],"biome":"minecraft:plains"}'
)
NAMESPACE = "schemsmith_harness"
GAMERULES = (
    ("advance_time", "doDaylightCycle", "false"),
    ("advance_weather", "doWeatherCycle", "false"),
    ("random_tick_speed", "randomTickSpeed", "0"),
    ("spawn_mobs", "doMobSpawning", "false"),
)
"""(26.x name, older name, value): set best effort, the run does not depend on them."""


class HarnessError(RuntimeError):
    """The server could not be started or driven."""


@dataclass
class ServerConfig:
    """Everything a run needs; paths are resolved by :class:`GameServer`."""

    mc_version: str = "26.3"
    cache: Path = field(default_factory=lambda: Path.cwd() / ".mc-cache")
    java: Sequence[str] = ("java",)
    memory: str = "2G"
    start_timeout_s: float = 300.0
    keep: bool = False
    eula_path: Path | None = None
    """Only for tests: read the gate from here instead of ``~/.schemsmith/eula.txt``."""


def server_properties(port: int, rcon_port: int, password: str) -> str:
    """``server.properties`` for a private, flat, offline test world."""
    props = {
        "server-ip": "127.0.0.1",
        "server-port": str(port),
        "online-mode": "false",
        "enable-rcon": "true",
        "rcon.port": str(rcon_port),
        "rcon.password": password,
        "broadcast-rcon-to-ops": "false",
        "level-name": "world",
        "level-type": "minecraft\\:flat",
        "generator-settings": FLAT_WORLD,
        "generate-structures": "false",
        "difficulty": "peaceful",
        "spawn-monsters": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": "3",
        "simulation-distance": "4",
        "enable-command-block": "false",
        "sync-chunk-writes": "false",
        "motd": "schemsmith harness",
    }
    return "".join(f"{k}={v}\n" for k, v in props.items())


class GameServer:
    """``with GameServer(cfg) as server: server.place(structure, "name")``."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.workdir: Path | None = None
        self.proc: subprocess.Popen[bytes] | None = None
        self.rcon: RconClient | None = None
        self._log: IO[bytes] | None = None
        self.port = 0
        self.rcon_port = 0

    @property
    def jar(self) -> Path:
        """``.mc-cache/<version>/server.jar``."""
        return self.config.cache / self.config.mc_version / "server.jar"

    def argv(self) -> list[str]:
        """The server command line (the EULA flag is passed for this run only)."""
        return [
            *self.config.java,
            f"-Xmx{self.config.memory}",
            EULA_PROPERTY,
            "-jar",
            str(self.jar),
            "nogui",
        ]

    def __enter__(self) -> GameServer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    def start(self) -> None:
        """Gate, prepare the directory, launch, wait for RCON."""
        require_eula(self.config.eula_path)  # before anything is created or started
        if not self.jar.is_file():
            raise HarnessError(
                f"{self.jar.as_posix()} not found; download it with "
                f"`uv run python scripts/gen_registry.py {self.config.mc_version}` "
                "(official Mojang manifest, kept in .mc-cache/)"
            )
        base = self.config.cache / "harness"
        base.mkdir(parents=True, exist_ok=True)
        self.workdir = base / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        self.workdir.mkdir()
        self.port, self.rcon_port = free_port(), free_port()
        password = secrets.token_urlsafe(18)
        (self.workdir / "server.properties").write_text(
            server_properties(self.port, self.rcon_port, password),
            encoding="utf-8",
            newline="\n",
        )
        self._log = (self.workdir / "server.log").open("wb")
        try:
            self.proc = start(self.argv(), self.workdir, self._log)
            self._wait_for_rcon(password)
            self._configure()
        except BaseException:
            self.stop()
            raise

    def _wait_for_rcon(self, password: str) -> None:
        assert self.proc is not None
        deadline = time.monotonic() + self.config.start_timeout_s
        last: Exception | None = None
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise HarnessError(f"the server exited during start-up:\n{self.log_tail()}")
            try:
                client = RconClient("127.0.0.1", self.rcon_port, password, timeout=30)
                client.connect()
            except RconError as exc:
                last = exc
                time.sleep(0.5)
                continue
            self.rcon = client
            return
        raise HarnessError(
            f"RCON did not come up within {self.config.start_timeout_s:.0f} s ({last}):\n"
            f"{self.log_tail()}"
        )

    def command(self, cmd: str) -> str:
        """Run a server command."""
        if self.rcon is None:
            raise HarnessError("the server is not running")
        return self.rcon.command(cmd)

    def _configure(self) -> None:
        for new, old, value in GAMERULES:
            out = self.command(f"gamerule {new} {value}")
            if "unknown" in out.lower() or "incorrect" in out.lower():
                self.command(f"gamerule {old} {value}")

    @property
    def world(self) -> Path:
        """The world folder of this run."""
        assert self.workdir is not None
        return self.workdir / "world"

    def place(self, structure: Structure, name: str, origin: tuple[int, int, int] = ORIGIN) -> str:
        """Install ``structure`` as a data pack and ``/place template`` it at ``origin``."""
        deadline = time.monotonic() + 60
        while not (self.world / "level.dat").is_file():
            if time.monotonic() > deadline:
                raise HarnessError("the server did not create world/level.dat")
            self.command("save-all flush")
            time.sleep(0.5)
        res = install_structure(
            structure,
            self.world,
            name,
            namespace=NAMESPACE,
            pack="schemsmith_harness",
            mc_version=self.config.mc_version,
            overwrite=True,
        )
        self.command("reload")
        self.command('datapack enable "file/schemsmith_harness"')
        _, size = structure.bounds()
        x0, z0 = origin[0] - 16, origin[2] - 16
        x1, z1 = origin[0] + size[0] + 16, origin[2] + size[2] + 16
        self.command(f"forceload add {x0} {z0} {x1} {z1}")
        out = self.command(f"place template {res.resource} {origin[0]} {origin[1]} {origin[2]}")
        if "placed" not in out.lower():
            raise HarnessError(f"/place template failed: {out}")
        return res.resource

    def log_tail(self, lines: int = 30) -> str:
        """The end of ``server.log``."""
        if self.workdir is None:
            return ""
        path = self.workdir / "server.log"
        if not path.is_file():
            return ""
        text = path.read_bytes().decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])

    def stop(self) -> None:
        """Stop politely, then kill the tree, then remove the run directory."""
        asked = False
        if self.rcon is not None:
            with contextlib.suppress(RconError):
                self.rcon.command("stop")
                asked = True
            self.rcon.close()
            self.rcon = None
        if self.proc is not None:
            if asked:  # give the server time to save and exit by itself
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self.proc.wait(timeout=30)
            kill_tree(self.proc)
            self.proc = None
        if self._log is not None:
            self._log.close()
            self._log = None
        if self.workdir is not None and not self.config.keep:
            shutil.rmtree(self.workdir, ignore_errors=True)


__all__ = [
    "NAMESPACE",
    "ORIGIN",
    "GameServer",
    "HarnessError",
    "ServerConfig",
    "server_properties",
]
