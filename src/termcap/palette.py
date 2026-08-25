"""Color handling: the xterm 256-color palette and SGR attribute state."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

RGB = Tuple[int, int, int]

# The 16 ANSI base colors (a common dark-theme rendition).
ANSI_16: List[RGB] = [
    (0x00, 0x00, 0x00),  # 0 black
    (0xCD, 0x31, 0x31),  # 1 red
    (0x0D, 0xBC, 0x79),  # 2 green
    (0xE5, 0xE5, 0x10),  # 3 yellow
    (0x24, 0x72, 0xC8),  # 4 blue
    (0xBC, 0x3F, 0xBC),  # 5 magenta
    (0x11, 0xA8, 0xCD),  # 6 cyan
    (0xE5, 0xE5, 0xE5),  # 7 white
    (0x66, 0x66, 0x66),  # 8 bright black
    (0xF1, 0x4C, 0x4C),  # 9 bright red
    (0x23, 0xD1, 0x8B),  # 10 bright green
    (0xF5, 0xF5, 0x43),  # 11 bright yellow
    (0x3B, 0x8E, 0xEA),  # 12 bright blue
    (0xD6, 0x70, 0xD6),  # 13 bright magenta
    (0x29, 0xB8, 0xDB),  # 14 bright cyan
    (0xFF, 0xFF, 0xFF),  # 15 bright white
]


def _build_256() -> List[RGB]:
    table = list(ANSI_16)
    # 216-color cube (indices 16..231)
    levels = [0, 95, 135, 175, 215, 255]
    for r in range(6):
        for g in range(6):
            for b in range(6):
                table.append((levels[r], levels[g], levels[b]))
    # grayscale ramp (indices 232..255)
    for i in range(24):
        v = 8 + i * 10
        table.append((v, v, v))
    return table


XTERM_256: List[RGB] = _build_256()


def color256(idx: int) -> RGB:
    idx = max(0, min(255, idx))
    return XTERM_256[idx]


@dataclass(frozen=True)
class Style:
    """Rendered text attributes for a single cell."""

    fg: Optional[RGB] = None  # None => default foreground
    bg: Optional[RGB] = None  # None => default background
    bold: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False

    def resolved(self, default_fg: RGB, default_bg: RGB) -> Tuple[RGB, RGB]:
        fg = self.fg if self.fg is not None else default_fg
        bg = self.bg if self.bg is not None else default_bg
        if self.bold and self.fg is not None:
            fg = tuple(min(255, int(c * 1.15)) for c in fg)  # type: ignore
        if self.inverse:
            fg, bg = bg, fg
        return fg, bg  # type: ignore


DEFAULT_STYLE = Style()


def apply_sgr(style: Style, params: List[int]) -> Style:
    """Apply an SGR (Select Graphic Rendition) sequence to a style."""
    if not params:
        params = [0]
    i = 0
    fg = style.fg
    bg = style.bg
    bold = style.bold
    italic = style.italic
    underline = style.underline
    inverse = style.inverse
    while i < len(params):
        p = params[i]
        if p == 0:
            fg = bg = None
            bold = italic = underline = inverse = False
        elif p == 1:
            bold = True
        elif p == 3:
            italic = True
        elif p == 4:
            underline = True
        elif p == 7:
            inverse = True
        elif p == 22:
            bold = False
        elif p == 23:
            italic = False
        elif p == 24:
            underline = False
        elif p == 27:
            inverse = False
        elif 30 <= p <= 37:
            fg = ANSI_16[p - 30]
        elif 90 <= p <= 97:
            fg = ANSI_16[p - 90 + 8]
        elif 40 <= p <= 47:
            bg = ANSI_16[p - 40]
        elif 100 <= p <= 107:
            bg = ANSI_16[p - 100 + 8]
        elif p == 39:
            fg = None
        elif p == 49:
            bg = None
        elif p in (38, 48):
            # Extended color: 38;5;n (256) or 38;2;r;g;b (truecolor)
            target_fg = p == 38
            if i + 1 < len(params) and params[i + 1] == 5:
                if i + 2 < len(params):
                    col = color256(params[i + 2])
                    if target_fg:
                        fg = col
                    else:
                        bg = col
                i += 2
            elif i + 1 < len(params) and params[i + 1] == 2:
                if i + 4 < len(params):
                    col = (params[i + 2], params[i + 3], params[i + 4])
                    if target_fg:
                        fg = col
                    else:
                        bg = col
                i += 4
        i += 1
    return replace(
        style,
        fg=fg,
        bg=bg,
        bold=bold,
        italic=italic,
        underline=underline,
        inverse=inverse,
    )
