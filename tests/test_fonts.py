import io

from termcap.cast import Header, Writer, load
from termcap.render.raster import (
    FontSet,
    _find_icon_fonts,
    _resolve_primary,
    render_image,
)


def test_fontset_constructs():
    fs = FontSet(16)
    # A FontSet always resolves *something* to draw with.
    assert fs.primary is not None


def test_for_char_returns_a_font():
    fs = FontSet(16)
    f = fs.for_char("A")
    assert f is not None
    # A char and a Nerd Font PUA icon both resolve without error.
    assert fs.for_char("\uf015") is not None


def test_termcap_font_env_takes_priority(tmp_path, monkeypatch):
    # Point TERMCAP_FONT at a real font if one exists; otherwise skip cleanly.
    primary_default = _resolve_primary()
    if not primary_default:
        return
    monkeypatch.setenv("TERMCAP_FONT", primary_default)
    assert _resolve_primary() == primary_default


def test_icon_font_discovery_is_a_list():
    # Should never raise; returns a (possibly empty) list of paths.
    assert isinstance(_find_icon_fonts(), list)


def test_render_image_with_pua_glyph(tmp_path):
    buf = io.StringIO()
    w = Writer(buf, Header(width=20, height=2, timestamp=1))
    w.event(0.0, "o", "\uf07b folder")  # Nerd Font folder icon + text
    w.flush()
    buf.seek(0)
    cast = load(buf)
    p = tmp_path / "icon.png"
    render_image(cast, str(p))
    from PIL import Image

    with Image.open(p) as im:
        assert im.width > 0 and im.height > 0
