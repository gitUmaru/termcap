"""Shared helpers for time-sampling a cast into terminal snapshots (frames)."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List

from termcap.cast import Cast
from termcap.terminal import Terminal


@dataclass
class Frame:
    grid: list  # List[List[Cell]] snapshot
    cx: int
    cy: int
    cursor_visible: bool
    delay: float  # seconds this frame is shown


def _apply_event(term: Terminal, code: str, data: str) -> None:
    if code == "o":
        term.feed(data)
    elif code == "r":
        try:
            c, r = data.lower().split("x")
            term.resize(int(c), int(r))
        except ValueError:
            pass


def sample_frames(
    cast: Cast,
    fps: float = 10.0,
    idle_limit: float = 2.0,
    speed: float = 1.0,
) -> List[Frame]:
    """Replay the cast and snapshot the screen on a fixed FPS grid.

    idle_limit caps long gaps (dead time) so pauses don't bloat the output.
    speed > 1 compresses time (faster playback).
    """
    term = Terminal(cast.header.width, cast.header.height)
    events = list(cast.events)
    if not events:
        return [
            Frame(copy.deepcopy(term.grid), term.cx, term.cy, term.cursor_visible, 1 / fps)
        ]

    # Build a compressed timeline honoring the idle limit.
    frame_dt = 1.0 / fps
    frames: List[Frame] = []
    prev_t = 0.0
    virtual_t = 0.0  # compressed time
    next_capture = 0.0

    def snapshot(delay: float) -> None:
        frames.append(
            Frame(
                copy.deepcopy(term.grid),
                term.cx,
                term.cy,
                term.cursor_visible,
                max(frame_dt, delay),
            )
        )

    for t, code, data in events:
        gap = (t - prev_t) / max(speed, 1e-6)
        gap = min(gap, idle_limit)
        # emit frames spanning the gap before applying this event
        while virtual_t + frame_dt <= next_capture + gap:
            virtual_t += frame_dt
            snapshot(frame_dt)
        virtual_t = next_capture = next_capture + gap
        _apply_event(term, code, data)
        prev_t = t

    # final frame held a moment
    snapshot(max(frame_dt, 0.8))
    return frames
