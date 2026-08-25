"""Raster rendering: Cast -> GIF (animated), PNG/JPEG (single frame) via Pillow.

Uses a monospaced TrueType font when one can be found, otherwise Pillow's
built-in bitmap font. Each terminal cell is drawn as a filled background rect
plus its glyph.
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFont

from termcap.cast import Cast
from termcap.render.frames import Frame, sample_frames

RGB = Tuple[int, int, int]

# A dark theme close to many terminal defaults.
DEFAULT_FG: RGB = (0xE5, 0xE5, 0xE5)
DEFAULT_BG: RGB = (0x1E, 0x1E, 0x1E)

# Candidate monospaced fonts across platforms.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "C:\\Windows\\Fonts\\consola.ttf",
]


def _load_font(size: int) -> Tuple[ImageFont.FreeTypeFont, bool]:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size), True
            except OSError:
                continue
    env = os.environ.get("TERMCAP_FONT")
    if env and os.path.exists(env):
        try:
            return ImageFont.truetype(env, size), True
        except OSError:
            pass
    return ImageFont.load_default(), False


def _cell_metrics(font, truetype: bool, size: int) -> Tuple[int, int]:
    if truetype:
        bbox = font.getbbox("M")
        cw = bbox[2] - bbox[0]
        ch = int(size * 1.35)
        return max(cw, size // 2), ch
    return 6, 12  # default bitmap font approx


def _render_grid(
    frame: Frame,
    font,
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
                draw.text((px, py), cell.char, font=font, fill=fg)
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
    font, truetype = _load_font(font_size)
    cw, ch = _cell_metrics(font, truetype, font_size)
    images: List[Image.Image] = []
    durations: List[int] = []
    for fr in frames:
        images.append(_render_grid(fr, font, cw, ch, show_cursor, padding))
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
    font, truetype = _load_font(font_size)
    cw, ch = _cell_metrics(font, truetype, font_size)
    img = _render_grid(last, font, cw, ch, show_cursor=False, padding=padding)
    ext = (fmt or os.path.splitext(out_path)[1].lstrip(".")).lower()
    if ext in ("jpg", "jpeg"):
        img.save(out_path, "JPEG", quality=92)
    else:
        img.save(out_path, "PNG")
