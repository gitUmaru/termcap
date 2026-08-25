"""Replay an asciicast in the terminal with original timing.

Writes the recorded stdout stream to the real terminal, sleeping between events
to reproduce the pacing. Idle gaps can be capped and playback sped up.
"""
from __future__ import annotations

import sys
import time
from typing import Optional

from termcap.cast import Cast


def play(
    cast: Cast,
    *,
    speed: float = 1.0,
    idle_limit: Optional[float] = None,
    out=None,
) -> None:
    """Replay ``cast`` to ``out`` (default: stdout) honoring timing.

    speed>1 plays faster; idle_limit caps long pauses (seconds).
    """
    stream = out if out is not None else sys.stdout
    write = stream.write
    flush = stream.flush

    prev = 0.0
    for t, code, data in cast.events:
        if code not in ("o", "r"):
            continue
        delay = (t - prev) / max(speed, 1e-6)
        if idle_limit is not None:
            delay = min(delay, idle_limit)
        if delay > 0:
            time.sleep(delay)
        prev = t
        if code == "o":
            write(data)
            flush()
