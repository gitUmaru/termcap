"""PTY-based terminal session recorder.

Spawns a shell (or a given command) attached to a pseudo-terminal, mirrors it to
the user's real terminal so the session is interactive, and records every byte
of output as asciicast v2 "o" events with timestamps.

Uses only the standard library (pty, tty, termios, fcntl, select, signal). This
is POSIX-only; on Windows use WSL. The recorder is a no-op import elsewhere.
"""
from __future__ import annotations

import os
import select
import shutil
import signal
import struct
import sys
import time
from typing import List, Optional

from termcap.cast import Header, Writer, now_ts

try:
    import fcntl
    import pty
    import termios
    import tty

    _POSIX = True
except ImportError:  # pragma: no cover - Windows
    _POSIX = False


def _term_size(fd: int) -> tuple[int, int]:
    try:
        cols, rows = os.get_terminal_size(fd)
        return cols, rows
    except OSError:
        return 80, 24


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def record(
    out_path: str,
    command: Optional[List[str]] = None,
    *,
    title: Optional[str] = None,
    quiet: bool = False,
) -> None:
    """Record an interactive PTY session to ``out_path`` (asciicast v2)."""
    if not _POSIX:
        raise RuntimeError("recording requires a POSIX PTY (macOS/Linux/WSL)")

    shell = command or [os.environ.get("SHELL", "/bin/sh")]
    stdin_fd = sys.stdin.fileno()
    cols, rows = _term_size(sys.stdout.fileno())

    header = Header(
        width=cols,
        height=rows,
        timestamp=now_ts(),
        title=title,
        command=" ".join(shell) if command else None,
        env={
            "SHELL": os.environ.get("SHELL", ""),
            "TERM": os.environ.get("TERM", "xterm-256color"),
        },
    )

    if not quiet:
        sys.stderr.write(
            f"\033[36m▸\033[0m recording to {out_path} "
            f"({cols}x{rows}) — exit the shell (ctrl-d) to stop\n"
        )
        sys.stderr.flush()

    pid, master_fd = pty.fork()
    if pid == 0:
        # Child: exec the shell. Inherits the slave pty as its controlling tty.
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        try:
            os.execvpe(shell[0], shell, env)
        except FileNotFoundError:
            sys.stderr.write(f"termcap: command not found: {shell[0]}\n")
            os._exit(127)

    # Parent: relay bytes and record output.
    _set_winsize(master_fd, rows, cols)

    old_attr = None
    try:
        old_attr = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
    except (termios.error, ValueError):
        old_attr = None  # stdin not a tty (e.g. piped) — keep going

    # Forward window-resize signals to the pty.
    def _on_winch(signum, frame):
        try:
            c, r = _term_size(sys.stdout.fileno())
            _set_winsize(master_fd, r, c)
        except OSError:
            pass

    old_winch = signal.getsignal(signal.SIGWINCH)
    signal.signal(signal.SIGWINCH, _on_winch)

    start = time.time()
    with open(out_path, "w", encoding="utf-8", newline="") as fp:
        writer = Writer(fp, header)
        try:
            while True:
                try:
                    rlist, _, _ = select.select([master_fd, stdin_fd], [], [])
                except InterruptedError:
                    continue

                if master_fd in rlist:
                    try:
                        data = os.read(master_fd, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    text = data.decode("utf-8", errors="replace")
                    writer.event(time.time() - start, "o", text)
                    writer.flush()
                    os.write(sys.stdout.fileno(), data)

                if stdin_fd in rlist:
                    try:
                        data = os.read(stdin_fd, 65536)
                    except OSError:
                        data = b""
                    if data:
                        os.write(master_fd, data)
        finally:
            signal.signal(signal.SIGWINCH, old_winch)
            if old_attr is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attr)
            try:
                os.close(master_fd)
            except OSError:
                pass
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass

    if not quiet:
        sys.stderr.write(f"\033[36m▸\033[0m saved {out_path}\n")
        sys.stderr.flush()
