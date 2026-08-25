# termcap

[![CI](https://github.com/gitUmaru/termcap/actions/workflows/ci.yml/badge.svg)](https://github.com/gitUmaru/termcap/actions/workflows/ci.yml)

Record your terminal and export it to **text, SVG, GIF, PNG, JPEG, or MP4** — with a
**self-contained core**. The PTY session recorder, the asciicast v2 reader/writer, the
ANSI/VT terminal emulator, and the text/SVG renderers are all implemented in this
package. GIF/PNG/JPEG are rendered with [Pillow]; MP4 is the only feature that shells
out to `ffmpeg` at runtime (encoding H.264 in pure Python isn't practical).

No dependency on `asciinema`, `agg`, `svg-term`, or `vhs`.

## Install

```sh
git clone https://github.com/gitUmaru/termcap.git
cd termcap
python3 -m pip install .
```

For MP4 output, also install ffmpeg (`brew install ffmpeg`, `apt install ffmpeg`, …).

Recording uses a POSIX pseudo-terminal — macOS, Linux, and WSL. Everything else
(rendering casts to any format) is fully cross-platform.

## Usage

```
termcap rec [file.cast] [-t TITLE] [-c CMD ...]   Record a session (asciicast v2)
termcap play <cast> [--speed N] [--idle-limit S]  Replay a cast in the terminal
termcap txt <cast> [out|-] [--mode screen|raw]    Cast -> plain text
termcap gif <cast> [out.gif]                      Cast -> animated GIF
termcap svg <cast> [out.svg]                      Cast -> animated SVG (native)
termcap png <cast> [out.png] [--jpeg]             Cast -> still image (PNG/JPEG)
termcap mp4 <cast> [out.mp4]                       Cast -> MP4 video (needs ffmpeg)
termcap doctor                                     Check dependencies
```

Common render options: `--fps`, `--idle-limit` (cap dead time), `--speed`,
`--font-size`.

### Example

```sh
termcap rec demo.cast              # record; exit the shell (ctrl-d) to stop
termcap txt demo.cast -            # print the final screen
termcap gif demo.cast              # -> demo.gif
termcap svg demo.cast              # -> demo.svg
termcap png demo.cast poster.png
termcap mp4 demo.cast --fps 12     # -> demo.mp4

# record a single command instead of an interactive shell:
termcap rec build.cast -c make -j4
```

One `.cast` recording feeds every output format.

## How it works

```
                       ┌────────────┐
  your shell ⇄ PTY ───▶│ recorder   │──▶ .cast (asciicast v2, native writer)
                       └────────────┘
                                          │
                            ┌─────────────┼──────────────┐
                            ▼             ▼              ▼
                     terminal.py    render/svg.py   render/raster.py
                    (ANSI emulator)  (native SVG)    (Pillow: GIF/PNG/JPEG)
                            │                              │
                            ▼                              ▼
                      render/text.py                render/video.py
                       (plain text)                (frames → ffmpeg → MP4)
```

- `cast.py` — asciicast v2 reader/writer.
- `recorder.py` — stdlib `pty` session recorder (POSIX).
- `terminal.py` — VT100/xterm-subset emulator producing a grid of styled cells.
- `palette.py` — xterm 256-color table + SGR attribute handling.
- `render/` — text, SVG, raster (GIF/PNG/JPEG), and video (MP4) backends.

## Development

```sh
python3 -m pip install -e ".[dev]"
pytest
```

## Notes

- **asciicast v2, not v3:** `asciinema` 3.x records v3 by default. termcap reads/writes
  v2 for portability; convert a v3 cast first with `asciinema convert`.
- **Fonts:** the raster renderer looks for a monospaced TrueType font (SF Mono, Menlo,
  DejaVu Sans Mono, Consolas). Override with the `TERMCAP_FONT` environment variable.

## License

MIT — see [LICENSE](LICENSE).

[Pillow]: https://python-pillow.org/
