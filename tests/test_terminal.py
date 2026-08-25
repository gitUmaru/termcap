from termcap.palette import ANSI_16, XTERM_256, Style, apply_sgr, color256
from termcap.terminal import Terminal


def test_plain_text():
    t = Terminal(20, 3)
    t.feed("hello")
    assert t.text() == "hello"


def test_newline_and_cr():
    t = Terminal(20, 3)
    t.feed("ab\r\ncd")
    assert t.text() == "ab\ncd"


def test_wrapping():
    t = Terminal(3, 3)
    t.feed("abcdef")
    assert t.text().splitlines()[:2] == ["abc", "def"]


def test_cursor_movement_cup():
    t = Terminal(10, 3)
    t.feed("\x1b[2;3HX")  # row2 col3
    line = t.grid[1]
    assert line[2].char == "X"


def test_erase_line():
    t = Terminal(10, 1)
    t.feed("abcdef")
    t.feed("\x1b[3G")   # column 3
    t.feed("\x1b[0K")   # erase to end
    assert t.text() == "ab"


def test_erase_display():
    t = Terminal(10, 3)
    t.feed("line1\r\nline2")
    t.feed("\x1b[2J")
    assert t.text() == ""


def test_sgr_color():
    s = apply_sgr(Style(), [31])  # red fg
    assert s.fg == ANSI_16[1]
    s2 = apply_sgr(s, [0])         # reset
    assert s2.fg is None


def test_sgr_256_and_truecolor():
    s = apply_sgr(Style(), [38, 5, 196])
    assert s.fg == color256(196)
    s2 = apply_sgr(Style(), [38, 2, 10, 20, 30])
    assert s2.fg == (10, 20, 30)


def test_palette_sizes():
    assert len(XTERM_256) == 256
    assert len(ANSI_16) == 16


def test_scroll_up_on_overflow():
    t = Terminal(5, 2)
    t.feed("a\r\nb\r\nc")  # third line forces scroll
    assert t.text() == "b\nc"
