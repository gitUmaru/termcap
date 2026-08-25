import io

from termcap.cast import Cast, Header, Writer, load


def test_header_roundtrip():
    h = Header(width=100, height=30, timestamp=123, title="t", env={"TERM": "xterm"})
    buf = io.StringIO(h.to_json() + "\n")
    parsed = Header.from_obj(__import__("json").loads(buf.readline()))
    assert parsed.width == 100
    assert parsed.height == 30
    assert parsed.title == "t"
    assert parsed.env["TERM"] == "xterm"


def test_rejects_v3():
    import pytest

    with pytest.raises(ValueError):
        Header.from_obj({"version": 3, "width": 80, "height": 24})


def test_writer_and_load():
    buf = io.StringIO()
    w = Writer(buf, Header(width=80, height=24, timestamp=1))
    w.event(0.0, "o", "hello")
    w.event(0.5, "o", "\r\nworld")
    w.flush()
    buf.seek(0)
    cast = load(buf)
    assert cast.header.width == 80
    assert len(cast.events) == 2
    assert cast.events[0] == (0.0, "o", "hello")
    assert cast.duration == 0.5
    assert [e[2] for e in cast.outputs()] == ["hello", "\r\nworld"]
