"""Native asciicast v2 reader/writer.

asciicast v2 is a newline-delimited JSON stream:

  line 0: a header object, e.g.
      {"version": 2, "width": 80, "height": 24, "timestamp": 1700000000,
       "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"}}

  line 1..n: event arrays [time, code, data]
      time  float  seconds since start
      code  str    "o" (stdout), "i" (stdin), "r" (resize), "m" (marker)
      data  str    payload; for "r" it is "COLSxROWS"

Reference: https://docs.asciinema.org/manual/asciicast/v2/
"""
from __future__ import annotations

import json
import time as _time
from dataclasses import dataclass, field
from typing import IO, Iterable, Iterator, List, Optional, Tuple


@dataclass
class Header:
    version: int = 2
    width: int = 80
    height: int = 24
    timestamp: Optional[int] = None
    title: Optional[str] = None
    command: Optional[str] = None
    env: dict = field(default_factory=dict)

    def to_json(self) -> str:
        obj = {"version": self.version, "width": self.width, "height": self.height}
        if self.timestamp is not None:
            obj["timestamp"] = self.timestamp
        if self.title:
            obj["title"] = self.title
        if self.command:
            obj["command"] = self.command
        if self.env:
            obj["env"] = self.env
        return json.dumps(obj, ensure_ascii=False)

    @classmethod
    def from_obj(cls, obj: dict) -> "Header":
        if int(obj.get("version", 0)) != 2:
            raise ValueError(
                f"unsupported asciicast version {obj.get('version')!r}; "
                "termcap reads/writes v2 (convert v3 with `asciinema convert`)"
            )
        return cls(
            version=2,
            width=int(obj.get("width", 80)),
            height=int(obj.get("height", 24)),
            timestamp=obj.get("timestamp"),
            title=obj.get("title"),
            command=obj.get("command"),
            env=obj.get("env", {}) or {},
        )


# An event is (time_seconds, code, data)
Event = Tuple[float, str, str]


@dataclass
class Cast:
    header: Header
    events: List[Event] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.events[-1][0] if self.events else 0.0

    def outputs(self) -> Iterator[Event]:
        """Yield only stdout ("o") events."""
        for ev in self.events:
            if ev[1] == "o":
                yield ev


def load(fp: IO[str]) -> Cast:
    """Parse an asciicast v2 stream from a text file object."""
    first = fp.readline()
    if not first.strip():
        raise ValueError("empty file: no asciicast header")
    header = Header.from_obj(json.loads(first))
    events: List[Event] = []
    for lineno, line in enumerate(fp, start=2):
        line = line.strip()
        if not line:
            continue
        try:
            arr = json.loads(line)
            events.append((float(arr[0]), str(arr[1]), str(arr[2])))
        except (ValueError, IndexError, TypeError) as exc:
            raise ValueError(f"malformed event on line {lineno}: {exc}") from exc
    return Cast(header=header, events=events)


def load_path(path: str) -> Cast:
    with open(path, "r", encoding="utf-8") as fp:
        return load(fp)


class Writer:
    """Incrementally write an asciicast v2 file.

    Used by the recorder so a session is persisted as it happens (crash-safe).
    """

    def __init__(self, fp: IO[str], header: Header):
        self._fp = fp
        self._fp.write(header.to_json() + "\n")
        self._fp.flush()

    def event(self, t: float, code: str, data: str) -> None:
        self._fp.write(json.dumps([round(t, 6), code, data], ensure_ascii=False) + "\n")

    def flush(self) -> None:
        self._fp.flush()


def dump_path(cast: Cast, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        w = Writer(fp, cast.header)
        for t, code, data in cast.events:
            w.event(t, code, data)
        w.flush()


def now_ts() -> int:
    return int(_time.time())
