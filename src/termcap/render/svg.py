"""Native animated-SVG renderer.

Produces a self-contained SVG where each captured frame is a <g> group toggled
via CSS keyframe animation (visibility stepping). No external tools required.
Text is real <text> so it stays crisp and selectable.
"""
from __future__ import annotations

from typing import List
from xml.sax.saxutils import escape

from termcap.cast import Cast
from termcap.render.frames import Frame, sample_frames

DEFAULT_FG = "#e5e5e5"
DEFAULT_BG = "#1e1e1e"
CW = 8.4   # cell width in px (approx for a 14px monospaced font)
CH = 17.0  # cell height in px
PAD = 10.0
FONT = 'ui-monospace, SFMono-Regular, Menlo, "DejaVu Sans Mono", monospace'
FONT_SIZE = 14


def _rgb(t) -> str:
    return "#%02x%02x%02x" % t


def _frame_group(fr: Frame, idx: int) -> str:
    rows = len(fr.grid)
    cols = len(fr.grid[0]) if rows else 0
    parts: List[str] = [f'<g class="f" id="f{idx}">']
    # backgrounds
    for y, row in enumerate(fr.grid):
        x = 0
        while x < cols:
            cell = row[x]
            _, bg = cell.style.resolved((229, 229, 229), (30, 30, 30))
            if bg != (30, 30, 30):
                # merge horizontal run of same bg
                run = 1
                while x + run < cols:
                    _, nbg = row[x + run].style.resolved((229, 229, 229), (30, 30, 30))
                    if nbg != bg:
                        break
                    run += 1
                parts.append(
                    f'<rect x="{PAD + x * CW:.1f}" y="{PAD + y * CH:.1f}" '
                    f'width="{run * CW:.1f}" height="{CH:.1f}" fill="{_rgb(bg)}"/>'
                )
                x += run
            else:
                x += 1
    # text runs (merge same-fg adjacent glyphs)
    for y, row in enumerate(fr.grid):
        x = 0
        ty = PAD + y * CH + FONT_SIZE
        while x < cols:
            cell = row[x]
            if cell.char == " ":
                x += 1
                continue
            fg, _ = cell.style.resolved((229, 229, 229), (30, 30, 30))
            weight = "bold" if cell.style.bold else "normal"
            italic = "italic" if cell.style.italic else "normal"
            buf = [cell.char]
            run_x = x
            x += 1
            while x < cols:
                nc = row[x]
                nfg, _ = nc.style.resolved((229, 229, 229), (30, 30, 30))
                if (
                    nc.char == " "
                    or nfg != fg
                    or ("bold" if nc.style.bold else "normal") != weight
                    or ("italic" if nc.style.italic else "normal") != italic
                ):
                    break
                buf.append(nc.char)
                x += 1
            txt = escape("".join(buf)).replace(" ", "&#160;")
            style = ""
            if weight == "bold":
                style += "font-weight:bold;"
            if italic == "italic":
                style += "font-style:italic;"
            parts.append(
                f'<text x="{PAD + run_x * CW:.1f}" y="{ty:.1f}" '
                f'fill="{_rgb(fg)}"'
                + (f' style="{style}"' if style else "")
                + f'>{txt}</text>'
            )
    parts.append("</g>")
    return "".join(parts)


def render_svg(
    cast: Cast,
    out_path: str,
    *,
    fps: float = 10.0,
    idle_limit: float = 2.0,
    speed: float = 1.0,
) -> None:
    frames = sample_frames(cast, fps=fps, idle_limit=idle_limit, speed=speed)
    cols = cast.header.width
    rows = cast.header.height
    W = cols * CW + PAD * 2
    H = rows * CH + PAD * 2

    total = sum(f.delay for f in frames) or 1.0
    # Build CSS steps: each frame visible for its slice of the total timeline.
    n = len(frames)
    css_rules = [
        ".f{visibility:hidden}",
        f"svg{{font-family:{FONT};font-size:{FONT_SIZE}px}}",
    ]
    keyframes = []
    acc = 0.0
    for i, fr in enumerate(frames):
        start_pct = acc / total * 100
        acc += fr.delay
        end_pct = acc / total * 100
        keyframes.append(
            f"@keyframes f{i}{{"
            f"0%,{start_pct:.4f}%{{visibility:hidden}}"
            f"{start_pct:.4f}%,{end_pct:.4f}%{{visibility:visible}}"
            f"{end_pct:.4f}%,100%{{visibility:hidden}}}}"
        )
        css_rules.append(
            f"#f{i}{{animation:f{i} {total:.3f}s step-end infinite}}"
        )

    groups = "".join(_frame_group(fr, i) for i, fr in enumerate(frames))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}">'
        f'<style>{"".join(css_rules)}{"".join(keyframes)}</style>'
        f'<rect width="100%" height="100%" fill="{DEFAULT_BG}" rx="6"/>'
        f"{groups}"
        f"</svg>"
    )
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(svg)
