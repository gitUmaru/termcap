"""A pragmatic ANSI/VT terminal emulator.

Feeds on the raw byte/character stream recorded in an asciicast and maintains a
grid of styled cells plus a cursor. Renderers snapshot the grid to produce
text, SVG, or raster frames.

Implements a practical subset of VT100/xterm:
  - printable text with wrapping
  - CR, LF, BS, TAB, carriage control
  - CSI cursor movement (CUU/CUD/CUF/CUB/CUP/HVP)
  - CSI erase (ED / EL)
  - CSI SGR (colors + attributes) via palette.apply_sgr
  - line insert/delete, char erase (IL/DL/ECH/DCH/ICH)
  - scroll region (DECSTBM) and index/reverse-index
  - alternate screen buffer enable/disable (best-effort)
It intentionally ignores things irrelevant to static/animated rendering
(mouse reporting, bracketed paste, most private modes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from termcap.palette import DEFAULT_STYLE, Style, apply_sgr


@dataclass
class Cell:
    char: str = " "
    style: Style = DEFAULT_STYLE


def _blank_row(width: int) -> List[Cell]:
    return [Cell() for _ in range(width)]


class Terminal:
    def __init__(self, width: int = 80, height: int = 24):
        self.width = width
        self.height = height
        self.grid: List[List[Cell]] = [_blank_row(width) for _ in range(height)]
        self.cx = 0
        self.cy = 0
        self.style = DEFAULT_STYLE
        self.scroll_top = 0
        self.scroll_bottom = height - 1
        self.cursor_visible = True
        self._saved = (0, 0, DEFAULT_STYLE)
        # parser state
        self._state = "ground"
        self._params: List[str] = []
        self._priv = ""
        self._intermediate = ""

    # ------------------------------------------------------------- grid ops
    def resize(self, width: int, height: int) -> None:
        new = [_blank_row(width) for _ in range(height)]
        for y in range(min(height, self.height)):
            for x in range(min(width, self.width)):
                new[y][x] = self.grid[y][x]
        self.grid = new
        self.width = width
        self.height = height
        self.scroll_top = 0
        self.scroll_bottom = height - 1
        self.cx = min(self.cx, width - 1)
        self.cy = min(self.cy, height - 1)

    def _clamp_cursor(self) -> None:
        self.cx = max(0, min(self.cx, self.width - 1))
        self.cy = max(0, min(self.cy, self.height - 1))

    def _scroll_up(self, n: int = 1) -> None:
        for _ in range(n):
            del self.grid[self.scroll_top]
            self.grid.insert(self.scroll_bottom, _blank_row(self.width))

    def _scroll_down(self, n: int = 1) -> None:
        for _ in range(n):
            del self.grid[self.scroll_bottom]
            self.grid.insert(self.scroll_top, _blank_row(self.width))

    def _newline(self) -> None:
        if self.cy == self.scroll_bottom:
            self._scroll_up(1)
        else:
            self.cy += 1

    # ------------------------------------------------------------- feed
    def feed(self, text: str) -> None:
        for ch in text:
            self._feed_char(ch)

    def _feed_char(self, ch: str) -> None:
        o = ord(ch)
        st = self._state
        if st == "ground":
            self._ground(ch, o)
        elif st == "esc":
            self._esc(ch)
        elif st == "csi":
            self._csi(ch)
        elif st == "osc":
            self._osc(ch)
        elif st == "esc_ignore":
            self._state = "ground"

    # ------------------------------------------------------------- ground
    def _ground(self, ch: str, o: int) -> None:
        if o == 0x1B:  # ESC
            self._state = "esc"
            self._params = []
            self._priv = ""
            self._intermediate = ""
        elif o == 0x0D:  # CR
            self.cx = 0
        elif o == 0x0A or o == 0x0B or o == 0x0C:  # LF / VT / FF
            self._newline()
        elif o == 0x08:  # BS
            self.cx = max(0, self.cx - 1)
        elif o == 0x09:  # TAB
            self.cx = min(self.width - 1, (self.cx // 8 + 1) * 8)
        elif o == 0x07:  # BEL
            pass
        elif o < 0x20:
            pass  # ignore other control chars
        else:
            self._put(ch)

    def _put(self, ch: str) -> None:
        if self.cx >= self.width:
            self.cx = 0
            self._newline()
        self.grid[self.cy][self.cx] = Cell(ch, self.style)
        self.cx += 1

    # ------------------------------------------------------------- ESC
    def _esc(self, ch: str) -> None:
        if ch == "[":
            self._state = "csi"
            self._params = []
            self._priv = ""
            self._intermediate = ""
        elif ch == "]":
            self._state = "osc"
            self._osc_buf = ""
        elif ch == "M":  # Reverse Index
            if self.cy == self.scroll_top:
                self._scroll_down(1)
            else:
                self.cy -= 1
            self._state = "ground"
        elif ch == "D":  # Index
            self._newline()
            self._state = "ground"
        elif ch == "E":  # Next line
            self.cx = 0
            self._newline()
            self._state = "ground"
        elif ch == "7":  # save cursor
            self._saved = (self.cx, self.cy, self.style)
            self._state = "ground"
        elif ch == "8":  # restore cursor
            self.cx, self.cy, self.style = self._saved
            self._state = "ground"
        elif ch in "()#%":  # charset selection intros; consume next char
            self._state = "esc_ignore"
        else:
            self._state = "ground"

    # ------------------------------------------------------------- CSI
    def _csi(self, ch: str) -> None:
        o = ord(ch)
        if ch in "?>!":
            self._priv += ch
            return
        if 0x30 <= o <= 0x3B and ch not in "?":  # digits and ';' and ':'
            self._params.append(ch)
            return
        if 0x20 <= o <= 0x2F:  # intermediate bytes
            self._intermediate += ch
            return
        # final byte
        self._dispatch_csi(ch)
        self._state = "ground"

    def _nums(self, default: int = 0) -> List[int]:
        raw = "".join(self._params)
        if raw == "":
            return []
        out = []
        for part in raw.replace(":", ";").split(";"):
            out.append(int(part) if part.isdigit() else default)
        return out

    def _dispatch_csi(self, ch: str) -> None:
        p = self._nums()

        def arg(i: int, d: int) -> int:
            return p[i] if i < len(p) and p[i] != 0 else d

        if ch == "A":  # CUU up
            self.cy -= arg(0, 1)
        elif ch == "B":  # CUD down
            self.cy += arg(0, 1)
        elif ch == "C":  # CUF right
            self.cx += arg(0, 1)
        elif ch == "D":  # CUB left
            self.cx -= arg(0, 1)
        elif ch == "E":  # CNL
            self.cx = 0
            self.cy += arg(0, 1)
        elif ch == "F":  # CPL
            self.cx = 0
            self.cy -= arg(0, 1)
        elif ch == "G" or ch == "`":  # CHA column
            self.cx = arg(0, 1) - 1
        elif ch == "d":  # VPA row
            self.cy = arg(0, 1) - 1
        elif ch in "Hf":  # CUP / HVP
            self.cy = arg(0, 1) - 1
            self.cx = arg(1, 1) - 1
        elif ch == "J":  # ED erase display
            self._erase_display(p[0] if p else 0)
        elif ch == "K":  # EL erase line
            self._erase_line(p[0] if p else 0)
        elif ch == "L":  # IL insert lines
            self._insert_lines(arg(0, 1))
        elif ch == "M":  # DL delete lines
            self._delete_lines(arg(0, 1))
        elif ch == "P":  # DCH delete chars
            self._delete_chars(arg(0, 1))
        elif ch == "@":  # ICH insert chars
            self._insert_chars(arg(0, 1))
        elif ch == "X":  # ECH erase chars
            self._erase_chars(arg(0, 1))
        elif ch == "S":  # SU scroll up
            self._scroll_up(arg(0, 1))
        elif ch == "T":  # SD scroll down
            self._scroll_down(arg(0, 1))
        elif ch == "r":  # DECSTBM scroll region
            top = arg(0, 1) - 1
            bot = (p[1] - 1) if len(p) > 1 and p[1] != 0 else self.height - 1
            if 0 <= top < bot < self.height:
                self.scroll_top = top
                self.scroll_bottom = bot
                self.cx = 0
                self.cy = top
        elif ch == "m":  # SGR
            self.style = apply_sgr(self.style, p)
        elif ch == "h" or ch == "l":  # set/reset mode (incl. private)
            self._mode(p, ch == "h")
        elif ch == "s":  # save cursor (ANSI.SYS)
            self._saved = (self.cx, self.cy, self.style)
        elif ch == "u":  # restore cursor (ANSI.SYS)
            self.cx, self.cy, self.style = self._saved
        # unknown finals are ignored
        self._clamp_cursor()

    def _mode(self, params: List[int], set_: bool) -> None:
        if "?" in self._priv:
            for m in params:
                if m == 25:
                    self.cursor_visible = set_
                elif m in (1049, 47, 1047):
                    # alternate screen: clear on enter/leave (best-effort)
                    self.grid = [_blank_row(self.width) for _ in range(self.height)]
                    self.cx = self.cy = 0

    # ------------------------------------------------------------- erase ops
    def _erase_display(self, mode: int) -> None:
        if mode == 0:  # cursor to end
            self._erase_line(0)
            for y in range(self.cy + 1, self.height):
                self.grid[y] = _blank_row(self.width)
        elif mode == 1:  # start to cursor
            self._erase_line(1)
            for y in range(0, self.cy):
                self.grid[y] = _blank_row(self.width)
        elif mode in (2, 3):  # whole display
            self.grid = [_blank_row(self.width) for _ in range(self.height)]

    def _erase_line(self, mode: int) -> None:
        row = self.grid[self.cy]
        if mode == 0:
            for x in range(self.cx, self.width):
                row[x] = Cell()
        elif mode == 1:
            for x in range(0, min(self.cx + 1, self.width)):
                row[x] = Cell()
        elif mode == 2:
            self.grid[self.cy] = _blank_row(self.width)

    def _erase_chars(self, n: int) -> None:
        row = self.grid[self.cy]
        for x in range(self.cx, min(self.cx + n, self.width)):
            row[x] = Cell()

    def _insert_chars(self, n: int) -> None:
        row = self.grid[self.cy]
        for _ in range(n):
            row.insert(self.cx, Cell())
        del row[self.width:]

    def _delete_chars(self, n: int) -> None:
        row = self.grid[self.cy]
        for _ in range(min(n, self.width - self.cx)):
            del row[self.cx]
            row.append(Cell())

    def _insert_lines(self, n: int) -> None:
        if not (self.scroll_top <= self.cy <= self.scroll_bottom):
            return
        for _ in range(n):
            del self.grid[self.scroll_bottom]
            self.grid.insert(self.cy, _blank_row(self.width))

    def _delete_lines(self, n: int) -> None:
        if not (self.scroll_top <= self.cy <= self.scroll_bottom):
            return
        for _ in range(n):
            del self.grid[self.cy]
            self.grid.insert(self.scroll_bottom, _blank_row(self.width))

    # ------------------------------------------------------------- OSC
    def _osc(self, ch: str) -> None:
        # OSC ... terminated by BEL (0x07) or ST (ESC \). We just swallow it.
        if ord(ch) == 0x07:
            self._state = "ground"
        elif ch == "\\" and getattr(self, "_osc_prev", "") == "\x1b":
            self._state = "ground"
        self._osc_prev = ch

    # esc_ignore consumes exactly one char (charset designations)
    def _feed_char_esc_ignore(self, ch: str) -> None:  # pragma: no cover
        self._state = "ground"

    # ------------------------------------------------------------- snapshot
    def text(self, strip_trailing: bool = True) -> str:
        lines = []
        for row in self.grid:
            s = "".join(c.char for c in row)
            if strip_trailing:
                s = s.rstrip()
            lines.append(s)
        if strip_trailing:
            while lines and lines[-1] == "":
                lines.pop()
        return "\n".join(lines)
