import io

import pytest

from termcap.cast import Header, Writer, load
from termcap.render.raster import render_gif
from termcap.render.video import extract_frame, have_ffmpeg, render_mp4, render_webm

ffmpeg_only = pytest.mark.skipif(not have_ffmpeg(), reason="ffmpeg not installed")


def _cast():
    buf = io.StringIO()
    w = Writer(buf, Header(width=20, height=3, timestamp=1))
    w.event(0.0, "o", "hello")
    w.event(0.3, "o", "\r\nworld")
    w.flush()
    buf.seek(0)
    return load(buf)


@ffmpeg_only
def test_render_mp4(tmp_path):
    p = tmp_path / "out.mp4"
    render_mp4(_cast(), str(p), fps=5)
    assert p.exists() and p.stat().st_size > 0


@ffmpeg_only
def test_render_webm(tmp_path):
    p = tmp_path / "out.webm"
    render_webm(_cast(), str(p), fps=5)
    assert p.exists() and p.stat().st_size > 0


@ffmpeg_only
def test_extract_frame_from_gif(tmp_path):
    gif = tmp_path / "a.gif"
    render_gif(_cast(), str(gif), fps=5)
    png = tmp_path / "still.png"
    extract_frame(str(gif), str(png), at=0.0)
    from PIL import Image

    with Image.open(png) as im:
        assert im.format == "PNG"
        assert im.width > 0
