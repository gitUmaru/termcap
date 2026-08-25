"""termcap command-line interface."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from typing import List, Optional

from termcap import __version__

C_CYAN = "\033[36m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_RESET = "\033[0m"


def _info(msg: str) -> None:
    sys.stderr.write(f"{C_CYAN}▸{C_RESET} {msg}\n")


def _err(msg: str) -> None:
    sys.stderr.write(f"{C_RED}✘{C_RESET} {msg}\n")


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _default_out(inp: str, ext: str) -> str:
    stem = os.path.splitext(inp)[0]
    return f"{stem}.{ext}"


# ---------------------------------------------------------------- commands
def cmd_rec(args: argparse.Namespace) -> int:
    from termcap.recorder import record

    out = args.file or f"cast-{_stamp()}.cast"
    command: Optional[List[str]] = args.command or None
    try:
        record(out, command=command, title=args.title, quiet=args.quiet)
    except RuntimeError as exc:
        _err(str(exc))
        return 1
    return 0


def _load(args: argparse.Namespace):
    from termcap.cast import load_path

    try:
        return load_path(args.input)
    except (OSError, ValueError) as exc:
        _err(f"cannot read cast: {exc}")
        raise SystemExit(1)


def cmd_txt(args: argparse.Namespace) -> int:
    from termcap.render.text import render_text

    cast = _load(args)
    text = render_text(cast, mode=args.mode)
    if args.output and args.output != "-":
        with open(args.output, "w", encoding="utf-8") as fp:
            fp.write(text + "\n")
        _info(f"saved {args.output}")
    else:
        sys.stdout.write(text + "\n")
    return 0


def cmd_gif(args: argparse.Namespace) -> int:
    from termcap.render.raster import render_gif

    cast = _load(args)
    out = args.output or _default_out(args.input, "gif")
    _info(f"GIF: {args.input} -> {out}")
    render_gif(
        cast, out, fps=args.fps, font_size=args.font_size,
        idle_limit=args.idle_limit, speed=args.speed,
    )
    _info(f"saved {out}")
    return 0


def cmd_svg(args: argparse.Namespace) -> int:
    from termcap.render.svg import render_svg

    cast = _load(args)
    out = args.output or _default_out(args.input, "svg")
    _info(f"SVG: {args.input} -> {out}")
    render_svg(cast, out, fps=args.fps, idle_limit=args.idle_limit, speed=args.speed)
    _info(f"saved {out}")
    return 0


def cmd_png(args: argparse.Namespace) -> int:
    from termcap.render.raster import render_image

    cast = _load(args)
    ext = "jpg" if args.jpeg else "png"
    out = args.output or _default_out(args.input, ext)
    _info(f"image: {args.input} -> {out}")
    render_image(cast, out, font_size=args.font_size, fmt="jpg" if args.jpeg else "png")
    _info(f"saved {out}")
    return 0


def cmd_mp4(args: argparse.Namespace) -> int:
    from termcap.render.video import render_mp4

    cast = _load(args)
    out = args.output or _default_out(args.input, "mp4")
    _info(f"MP4: {args.input} -> {out}")
    try:
        render_mp4(
            cast, out, fps=args.fps, font_size=args.font_size,
            idle_limit=args.idle_limit, speed=args.speed,
        )
    except RuntimeError as exc:
        _err(str(exc))
        return 1
    _info(f"saved {out}")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    from termcap.player import play

    cast = _load(args)
    idle = args.idle_limit if args.idle_limit and args.idle_limit > 0 else None
    try:
        play(cast, speed=args.speed, idle_limit=idle)
    except KeyboardInterrupt:
        return 130
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    try:
        import PIL  # noqa
        print(f"  {C_GREEN}✔{C_RESET} Pillow      {PIL.__version__}")
    except ImportError:
        print(f"  {C_RED}✘{C_RESET} Pillow      missing (pip install Pillow)")
        ok = False

    import termcap.recorder as rec
    if rec._POSIX:
        print(f"  {C_GREEN}✔{C_RESET} PTY record  available (POSIX)")
    else:
        print(f"  {C_RED}✘{C_RESET} PTY record  unavailable (Windows — use WSL)")

    if shutil.which("ffmpeg"):
        print(f"  {C_GREEN}✔{C_RESET} ffmpeg      {shutil.which('ffmpeg')} (MP4 output)")
    else:
        print(f"  {C_RED}✘{C_RESET} ffmpeg      missing — MP4 disabled (text/svg/gif/png still work)")

    print(f"\ntermcap {__version__}")
    return 0 if ok else 1


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="termcap",
        description="Record your terminal and export to text, SVG, GIF, PNG, JPEG, or MP4.",
    )
    p.add_argument("-V", "--version", action="version", version=f"termcap {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    # rec
    pr = sub.add_parser("rec", help="record a terminal session (asciicast v2)")
    pr.add_argument("file", nargs="?", help="output .cast path (default: timestamped)")
    pr.add_argument("-t", "--title", help="recording title")
    pr.add_argument("-q", "--quiet", action="store_true", help="suppress messages")
    pr.add_argument(
        "-c", "--command", nargs=argparse.REMAINDER,
        help="run this command instead of a shell (must be last)",
    )
    pr.set_defaults(func=cmd_rec)

    def add_render_common(sp, with_font=True):
        sp.add_argument("input", help="input .cast file")
        sp.add_argument("output", nargs="?", help="output path (default: derived)")
        sp.add_argument("--fps", type=float, default=10.0, help="frames per second (default 10)")
        sp.add_argument("--idle-limit", type=float, default=2.0, help="cap idle gaps, seconds (default 2)")
        sp.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
        if with_font:
            sp.add_argument("--font-size", type=int, default=16, help="font size px (default 16)")

    pg = sub.add_parser("gif", help="cast -> animated GIF")
    add_render_common(pg)
    pg.set_defaults(func=cmd_gif)

    ps = sub.add_parser("svg", help="cast -> animated SVG")
    add_render_common(ps, with_font=False)
    ps.set_defaults(func=cmd_svg)

    pm = sub.add_parser("mp4", help="cast -> MP4 (needs ffmpeg)")
    add_render_common(pm)
    pm.set_defaults(func=cmd_mp4)

    pp = sub.add_parser("png", help="cast -> still image (PNG/JPEG)")
    pp.add_argument("input", help="input .cast file")
    pp.add_argument("output", nargs="?", help="output path (default: derived)")
    pp.add_argument("--jpeg", action="store_true", help="write JPEG instead of PNG")
    pp.add_argument("--font-size", type=int, default=16, help="font size px (default 16)")
    pp.set_defaults(func=cmd_png)

    pt = sub.add_parser("txt", help="cast -> plain text")
    pt.add_argument("input", help="input .cast file")
    pt.add_argument("output", nargs="?", help="output path or - for stdout")
    pt.add_argument(
        "--mode", choices=["screen", "raw"], default="screen",
        help="'screen' = final screen; 'raw' = full transcript",
    )
    pt.set_defaults(func=cmd_txt)

    ppl = sub.add_parser("play", help="replay a cast in the terminal")
    ppl.add_argument("input", help="input .cast file")
    ppl.add_argument("--speed", type=float, default=1.0, help="playback speed multiplier")
    ppl.add_argument("--idle-limit", type=float, default=2.0, help="cap idle gaps, seconds (0 = no cap)")
    ppl.set_defaults(func=cmd_play)

    pd = sub.add_parser("doctor", help="check backends/dependencies")
    pd.set_defaults(func=cmd_doctor)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _err("interrupted")
        return 130
    except SystemExit as e:
        return int(e.code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
