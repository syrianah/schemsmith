"""Process handling: own process group, the whole tree dies (POSIX and Windows paths)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from schemsmith.harness.process import free_port, group_kwargs, kill_tree, start

CHILD = """
import subprocess, sys, time
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(p.pid, flush=True)
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie still answers kill(0): check its state on Linux
    stat = Path(f"/proc/{pid}/stat")
    return not (stat.exists() and stat.read_text().split()[2] == "Z")


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_kill_tree_kills_grandchildren(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    with log_path.open("wb") as log:
        proc = start([sys.executable, "-c", CHILD], tmp_path, log)
        deadline = time.monotonic() + 10
        while not log_path.read_text().strip() and time.monotonic() < deadline:
            time.sleep(0.05)
        grandchild = int(log_path.read_text().split()[0])
        assert _alive(grandchild)
        kill_tree(proc, timeout=5)
    assert proc.poll() is not None
    deadline = time.monotonic() + 5
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(grandchild)


def test_kill_tree_on_windows_uses_taskkill() -> None:
    calls: list[list[str]] = []

    class FakeProc:
        pid = 4242
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 1
            return 1

        def kill(self) -> None:
            pass

    def run(argv: list[str], **kw: Any) -> None:
        calls.append(argv)

    kill_tree(FakeProc(), windows=True, run=run)  # type: ignore[arg-type]
    assert calls == [["taskkill", "/T", "/F", "/PID", "4242"]]


def test_already_exited_process_is_fine(tmp_path: Path) -> None:
    with (tmp_path / "log").open("wb") as log:
        proc = start([sys.executable, "-c", "pass"], tmp_path, log)
        proc.wait(timeout=10)
        kill_tree(proc)
    assert proc.returncode == 0


def test_group_kwargs() -> None:
    assert group_kwargs(windows=False) == {"start_new_session": True}
    assert "creationflags" in group_kwargs(windows=True)


def test_free_port_is_free() -> None:
    port = free_port()
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))


def test_start_rejects_missing_program(tmp_path: Path) -> None:
    with (tmp_path / "log").open("wb") as log, pytest.raises(OSError):
        start(["definitely-not-a-program-xyz"], tmp_path, log)
    _ = subprocess  # keep the import for type checkers
