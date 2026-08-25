"""Render a Cast to plain text (the final terminal screen, or full transcript)."""
from __future__ import annotations

from termcap.cast import Cast
from termcap.terminal import Terminal


def render_text(cast: Cast, mode: str = "screen") -> str:
    """Render a cast to text.

    mode="screen": replay everything and dump the final terminal screen.
    mode="raw":    concatenate every stdout payload with escape codes stripped
                   by the emulator, line by line as it scrolled (transcript).
    """
    if mode == "raw":
        term = Terminal(cast.header.width, cast.header.height)
        lines: list[str] = []

        # Capture each line as it scrolls off the top of the screen.
        original_scroll_up = term._scroll_up

        def capture_scroll(n: int = 1) -> None:
            for _ in range(n):
                lines.append("".join(c.char for c in term.grid[term.scroll_top]).rstrip())
                original_scroll_up(n=1)

        term._scroll_up = capture_scroll  # type: ignore[method-assign]
        for _, _, data in cast.outputs():
            term.feed(data)
        # append whatever remains on screen
        tail = term.text()
        result = "\n".join(lines)
        if tail:
            result = (result + "\n" + tail) if result else tail
        return result

    # default: final screen
    term = Terminal(cast.header.width, cast.header.height)
    for _, code, data in cast.events:
        if code == "o":
            term.feed(data)
        elif code == "r":
            try:
                c, r = data.lower().split("x")
                term.resize(int(c), int(r))
            except ValueError:
                pass
    return term.text()
