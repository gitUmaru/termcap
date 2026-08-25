"""Raster rendering: Cast -> GIF (animated), PNG/JPEG (single frame) via Pillow.

Uses a monospaced TrueType font when one can be found, otherwise Pillow's
built-in bitmap font. A glyph-level fallback chain lets characters missing from
the primary font (e.g. Nerd Font icons in the Private Use Area) be drawn from a
font that does contain them. Each terminal cell is drawn as a filled background
rect plus its glyph.
"""
from __future__ import annotations

import glob
import os
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFont

from termcap.cast import Cast
from termcap.render.frames import Frame, sample_frames

RGB = Tuple[int, int, int]

# A dark theme close to many terminal defaults.
DEFAULT_FG: RGB = (0xE5, 0xE5, 0xE5)
DEFAULT_BG: RGB = (0x1E, 0x1E, 0x1E)

# Primary monospaced fonts across platforms (plain text).
_FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "C:\\Windows\\Fonts\\consola.ttf",
]

# Directories to scan for Nerd Fonts / icon-capable fonts (glyph fallback).
_FONT_DIRS = [
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]

# Substrings that identify a font likely to carry icon glyphs.
_ICON_FONT_HINTS = ("nerdfont", "nerd font", " nf", "nf-", "nerd", "symbols", "powerline")


def _find_icon_fonts() -> List[str]:
    """Locate installed fonts that likely contain Nerd Font / icon glyphs.

    Prefers monospaced ('Mono') Nerd Font variants and Regular weights.
    """
    found: List[str] = []
    for d in _FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for path in glob.glob(os.path.join(d, "*.tt[fc]")) + glob.glob(
            os.path.join(d, "*.otf")
        ):
            name = os.path.basename(path).lower()
            if any(h in name for h in _ICON_FONT_HINTS):
                found.append(path)

    def rank(p: str) -> tuple:
        n = os.path.basename(p).lower()
        return (
            0 if "nerdfontmono" in n or "nf mono" in n or " nf" in n else 1,  # true monospaced icon variant
            0 if "regular" in n else 1,        # prefer regular weight
            0 if ("italic" not in n and "bold" not in n and "light" not in n
                  and "thin" not in n and "medium" not in n) else 1,
            len(n),
        )

    return sorted(set(found), key=rank)


@lru_cache(maxsize=None)
def _font_cmap(path: str) -> Optional[frozenset]:
    """Return the set of codepoints a font supports, or None if undetectable."""
    try:
        from fontTools.ttLib import TTFont, TTCollection

        if path.lower().endswith(".ttc"):
            coll = TTCollection(path, lazy=True)
            cps: set = set()
            for f in coll.fonts:
                try:
                    cps |= set(f.getBestCmap().keys())
                except Exception:
                    pass
            return frozenset(cps)
        ft = TTFont(path, lazy=True, fontNumber=0)
        return frozenset(ft.getBestCmap().keys())
    except Exception:
        return None


def _resolve_primary() -> Optional[str]:
    """Pick the primary text font.

    Order: TERMCAP_FONT, an installed monospaced Nerd Font (so text AND icons
    come from one crisp font), then plain system monospace.
    """
    env = os.environ.get("TERMCAP_FONT")
    if env and os.path.exists(env):
        return env
    icon_fonts = _find_icon_fonts()
    if icon_fonts:
        return icon_fonts[0]
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


class FontSet:
    """A primary font plus fallback fonts, chosen per-glyph by coverage."""

    def __init__(self, size: int):
        self.size = size
        self.truetype = False
        self._fonts: List[Tuple[ImageFont.FreeTypeFont, Optional[frozenset]]] = []
        self._cache: Dict[str, ImageFont.FreeTypeFont] = {}

        paths: List[str] = []
        primary = _resolve_primary()
        if primary:
            paths.append(primary)
        # add icon fonts as fallbacks (skip the primary if already an icon font)
        for p in _find_icon_fonts():
            if p not in paths:
                paths.append(p)
        # add plain monospace fonts as further fallbacks
        for p in _FONT_CANDIDATES:
            if os.path.exists(p) and p not in paths:
                paths.append(p)

        for p in paths:
            try:
                f = ImageFont.truetype(p, size)
                self._fonts.append((f, _font_cmap(p)))
                self.truetype = True
            except OSError:
                continue

        if not self._fonts:
            self._default = ImageFont.load_default()
        else:
            self._default = self._fonts[0][0]

    @property
    def primary(self) -> ImageFont.ImageFont:
        return self._default

    def for_char(self, ch: str) -> ImageFont.ImageFont:
        """Return the first font whose cmap covers ``ch`` (fallback: primary)."""
        if not self.truetype:
            return self._default
        if ch in self._cache:
            return self._cache[ch]
        cp = ord(ch[0]) if ch else 0x20
        chosen = self._default
        for font, cmap in self._fonts:
            if cmap is None or cp in cmap:
                chosen = font
                break
        self._cache[ch] = chosen
        return chosen


def _load_font(size: int) -> Tuple[FontSet, bool]:
    fs = FontSet(size)
    return fs, fs.truetype


def _cell_metrics(fontset: FontSet, truetype: bool, size: int) -> Tuple[int, int]:
    if truetype:
        bbox = fontset.primary.getbbox("M")
        cw = bbox[2] - bbox[0]
        ch = int(size * 1.35)
        return max(cw, size // 2), ch
    return 6, 12  # default bitmap font approx


def _render_grid(
    frame: Frame,
    fontset: FontSet,
    cw: int,
    ch: int,
    show_cursor: bool,
    padding: int,
) -> Image.Image:
    rows = len(frame.grid)
    cols = len(frame.grid[0]) if rows else 0
    W = cols * cw + padding * 2
    H = rows * ch + padding * 2
    img = Image.new("RGB", (W, H), DEFAULT_BG)
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(frame.grid):
        py = padding + y * ch
        for x, cell in enumerate(row):
            fg, bg = cell.style.resolved(DEFAULT_FG, DEFAULT_BG)
            px = padding + x * cw
            if bg != DEFAULT_BG:
                draw.rectangle([px, py, px + cw, py + ch], fill=bg)
            if cell.char and cell.char != " ":
                draw.text((px, py), cell.char, font=fontset.for_char(cell.char), fill=fg)
            if cell.style.underline:
                draw.line([px, py + ch - 2, px + cw, py + ch - 2], fill=fg)

    if show_cursor and frame.cursor_visible:
        cxp = padding + frame.cx * cw
        cyp = padding + frame.cy * ch
        draw.rectangle([cxp, cyp, cxp + cw, cyp + ch], outline=DEFAULT_FG)

    return img


def _frames_to_images(
    frames: List[Frame],
    font_size: int,
    padding: int,
    show_cursor: bool,
) -> Tuple[List[Image.Image], List[int]]:
    fontset, truetype = _load_font(font_size)
    cw, ch = _cell_metrics(fontset, truetype, font_size)
    images: List[Image.Image] = []
    durations: List[int] = []
    for fr in frames:
        images.append(_render_grid(fr, fontset, cw, ch, show_cursor, padding))
        durations.append(max(20, int(fr.delay * 1000)))  # ms, min 20
    return images, durations


def render_gif(
    cast: Cast,
    out_path: str,
    *,
    fps: float = 10.0,
    font_size: int = 16,
    padding: int = 10,
    idle_limit: float = 2.0,
    speed: float = 1.0,
    loop: int = 0,
) -> None:
    frames = sample_frames(cast, fps=fps, idle_limit=idle_limit, speed=speed)
    images, durations = _frames_to_images(frames, font_size, padding, show_cursor=True)
    if not images:
        raise ValueError("nothing to render")
    images[0].save(
        out_path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=loop,
        optimize=True,
        disposal=2,
    )


def render_image(
    cast: Cast,
    out_path: str,
    *,
    font_size: int = 16,
    padding: int = 10,
    fmt: Optional[str] = None,
) -> None:
    """Render the final screen to a single PNG/JPEG."""
    frames = sample_frames(cast, fps=1.0, idle_limit=0.0)
    last = frames[-1]
    fontset, truetype = _load_font(font_size)
    cw, ch = _cell_metrics(fontset, truetype, font_size)
    img = _render_grid(last, fontset, cw, ch, show_cursor=False, padding=padding)
    ext = (fmt or os.path.splitext(out_path)[1].lstrip(".")).lower()
    if ext in ("jpg", "jpeg"):
        img.save(out_path, "JPEG", quality=92)
    else:
        img.save(out_path, "PNG")
