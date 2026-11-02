"""Start the server process in its own group and kill the whole tree on exit.

Java may start helper processes; a plain ``terminate()`` can leave them running,
and on Windows Ctrl+C does not reach a child in another console. So the server
starts in a new process group (``start_new_session`` on POSIX,
``CREATE_NEW_PROCESS_GROUP`` on Windows) and :func:`kill_tree` kills the group
(``os.killpg``) or the tree (``taskkill /T /F``).
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import IO, Any

Runner = Callable[..., Any]


def free_port(host: str = "127.0.0.1") -> int:
    """A TCP port nobody listens on right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def group_kwargs(windows: bool | None = None) -> dict[str, Any]:
    """``Popen`` arguments that put the child in its own process group."""
    if windows if windows is not None else os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
    return {"start_new_session": True}


def start(
    argv: Sequence[str], cwd: Path, log: IO[bytes], env: dict[str, str] | None = None
) -> subprocess.Popen[bytes]:
    """Start ``argv`` in ``cwd`` with output to ``log``, in a new process group."""
    return subprocess.Popen(
        list(argv),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
        **group_kwargs(),
    )


def kill_tree(
    proc: subprocess.Popen[Any],
    timeout: float = 10.0,
    windows: bool | None = None,
    run: Runner = subprocess.run,
) -> None:
    """Kill ``proc`` and everything it started; safe if it already exited."""
    if proc.poll() is None:
        if windows if windows is not None else os.name == "nt":
            run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            try:
                # getattr: these names do not exist on Windows, where mypy also runs
                getattr(os, "killpg")(proc.pid, getattr(signal, "SIGKILL"))  # noqa: B009
            except (ProcessLookupError, PermissionError):
                proc.kill()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)


__all__ = ["free_port", "group_kwargs", "kill_tree", "start"]
