import io
import time

from termcap.cast import Header, Writer, load
from termcap.player import play


def _cast():
    buf = io.StringIO()
    w = Writer(buf, Header(width=20, height=3, timestamp=1))
    w.event(0.0, "o", "a")
    w.event(0.05, "o", "b")
    w.event(0.10, "o", "c")
    w.flush()
    buf.seek(0)
    return load(buf)


def test_play_writes_output_in_order():
    out = io.StringIO()
    play(_cast(), speed=1000.0, out=out)  # fast: collapse timing
    assert out.getvalue() == "abc"


def test_play_respects_idle_limit_timing():
    buf = io.StringIO()
    w = Writer(buf, Header(width=10, height=2))
    w.event(0.0, "o", "x")
    w.event(5.0, "o", "y")  # big gap, should be capped
    w.flush()
    buf.seek(0)
    cast = load(buf)

    out = io.StringIO()
    start = time.time()
    play(cast, speed=1.0, idle_limit=0.05, out=out)
    elapsed = time.time() - start
    assert out.getvalue() == "xy"
    assert elapsed < 1.0  # 5s gap capped to 0.05s
