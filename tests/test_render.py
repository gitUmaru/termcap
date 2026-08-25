import io
import os

from PIL import Image

from termcap.cast import Cast, Header, Writer, load
from termcap.render.raster import render_gif, render_image
from termcap.render.svg import render_svg
from termcap.render.text import render_text


def _sample_cast():
    buf = io.StringIO()
    w = Writer(buf, Header(width=20, height=3, timestamp=1))
    w.event(0.0, "o", "\x1b[32mhello\x1b[0m")
    w.event(0.3, "o", "\r\n\x1b[1mworld\x1b[0m")
    w.event(0.6, "o", "!")
    w.flush()
    buf.seek(0)
    return load(buf)


def test_render_text_screen():
    cast = _sample_cast()
    out = render_text(cast, mode="screen")
    assert "hello" in out
    assert "world!" in out


def test_render_gif(tmp_path):
    cast = _sample_cast()
    p = tmp_path / "out.gif"
    render_gif(cast, str(p), fps=5)
    assert p.exists() and p.stat().st_size > 0
    with Image.open(p) as im:
        assert im.format == "GIF"


def test_render_png(tmp_path):
    cast = _sample_cast()
    p = tmp_path / "out.png"
    render_image(cast, str(p))
    with Image.open(p) as im:
        assert im.format == "PNG"
        assert im.width > 0 and im.height > 0


def test_render_jpeg(tmp_path):
    cast = _sample_cast()
    p = tmp_path / "out.jpg"
    render_image(cast, str(p), fmt="jpg")
    with Image.open(p) as im:
        assert im.format == "JPEG"


def test_render_svg(tmp_path):
    cast = _sample_cast()
    p = tmp_path / "out.svg"
    render_svg(cast, str(p), fps=5)
    data = p.read_text(encoding="utf-8")
    assert data.startswith("<svg")
    assert "hello" in data
    assert "@keyframes" in data
