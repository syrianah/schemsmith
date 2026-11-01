"""GameServer and verify end to end with a fake server process (no Minecraft)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from schemsmith.harness.eula import EulaNotAccepted
from schemsmith.harness.server import GameServer, HarnessError, ServerConfig, server_properties
from schemsmith.harness.verify import verify
from schemsmith.redstone.sim import parse_script
from tests.redstone.circuits import build

FAKE = Path(__file__).with_name("fake_server.py")
YES = "eula" + "=" + "true"


def config(
    tmp_path: Path, accepted: bool = True, start_timeout_s: float = 20, **kw: object
) -> ServerConfig:
    home = tmp_path / "home" / ".schemsmith"
    home.mkdir(parents=True)
    if accepted:
        (home / "eula.txt").write_text(YES + "\n", encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / "26.3").mkdir(parents=True)
    (cache / "26.3" / "server.jar").write_bytes(b"not a real jar")
    return ServerConfig(
        cache=cache,
        java=(sys.executable, str(FAKE)),
        eula_path=home / "eula.txt",
        start_timeout_s=start_timeout_s,
        **kw,  # type: ignore[arg-type]
    )


def eula_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("eula.txt"))


def test_no_eula_no_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = config(tmp_path, accepted=False)
    started: list[object] = []
    monkeypatch.setattr("schemsmith.harness.server.start", lambda *a, **k: started.append(a))
    with pytest.raises(EulaNotAccepted):
        GameServer(cfg).start()
    assert started == []
    assert not (cfg.cache / "harness").exists()  # nothing was created
    assert eula_files(tmp_path) == []


def test_missing_jar(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    (cfg.cache / "26.3" / "server.jar").unlink()
    with pytest.raises(HarnessError, match="gen_registry"):
        GameServer(cfg).start()


def test_properties() -> None:
    text = server_properties(25565, 25575, "secret")
    assert "server-ip=127.0.0.1\n" in text and "online-mode=false\n" in text
    assert "enable-rcon=true\n" in text and "rcon.password=secret\n" in text
    assert "eula" not in text


def test_argv_passes_acceptance_only_as_a_flag(tmp_path: Path) -> None:
    argv = GameServer(config(tmp_path)).argv()
    assert "-Dcom.mojang.eula.agree=true" in argv and argv[-1] == "nogui"


def test_verify_end_to_end_with_a_fake_server(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    s = build(
        {
            (1, 1, 1): "stone_button[face=floor,facing=north,powered=false]",
            (2, 1, 1): "bell[attachment=floor,facing=north,powered=false]",
        }
    )
    s.data_version = 4671
    script = parse_script(
        {
            "name": "ring once",
            "ticks": 60,
            "actions": [{"at": 5, "press": [1, 1, 1]}],
            "expect": [{"events": "bell", "count": 1}],
        }
    )
    report = verify(s, script, cfg, compare_sim=True)
    assert report.passed, report.format()
    assert report.game.count("bell") == 1
    assert "PASSED" in report.format()
    assert report.to_dict()["simulator"]["passed"] is True
    # the run folder is gone, and no eula.txt was written anywhere except the owner's own
    assert list((cfg.cache / "harness").iterdir()) == []
    assert eula_files(tmp_path) == ["home/.schemsmith/eula.txt"]


def test_keep_leaves_the_run_folder_for_debugging(tmp_path: Path) -> None:
    cfg = config(tmp_path, keep=True)
    with GameServer(cfg) as server:
        assert server.command("time query gametime").startswith("The time is")
    runs = list((cfg.cache / "harness").iterdir())
    assert len(runs) == 1 and (runs[0] / "server.log").is_file()
    assert not (runs[0] / "eula.txt").exists()


def test_start_timeout_kills_the_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_SERVER_MODE", "hang")
    cfg = config(tmp_path, start_timeout_s=2)
    server = GameServer(cfg)
    with pytest.raises(HarnessError, match="RCON did not come up"):
        server.start()
    assert server.proc is None  # stopped and killed


def test_server_without_the_flag_refuses(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    server = GameServer(cfg)
    server.argv = lambda: [sys.executable, str(FAKE), "nogui"]  # type: ignore[method-assign]
    with pytest.raises(HarnessError, match="exited during start-up"):
        server.start()
