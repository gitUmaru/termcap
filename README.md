# termcap

[![CI](https://github.com/gitUmaru/termcap/actions/workflows/ci.yml/badge.svg)](https://github.com/gitUmaru/termcap/actions/workflows/ci.yml)

Record your terminal and export it to **text, SVG, GIF, PNG, JPEG, or MP4** — with a
**self-contained core**. The PTY session recorder, the asciicast v2 reader/writer, the
ANSI/VT terminal emulator, and the text/SVG renderers are all implemented in this
package. GIF/PNG/JPEG are rendered with [Pillow]; MP4 is the only feature that shells
out to `ffmpeg` at runtime (encoding H.264 in pure Python isn't practical).

No dependency on `asciinema`, `agg`, `svg-term`, or `vhs`.

## Install

### Homebrew (macOS/Linux)

```sh
brew tap gitUmaru/termcap
brew install termcap
```

Or in a single command:

```sh
brew install gitUmaru/termcap/termcap
```

The formula lives in the [gitUmaru/homebrew-termcap](https://github.com/gitUmaru/homebrew-termcap)
tap (included here as the `homebrew-termcap` submodule) and installs a
self-contained build (bundled Pillow + fonttools).

### Arch Linux (AUR)

The [`packaging/aur`](packaging/aur) directory contains a `PKGBUILD`. Once
published to the AUR you can install it with an AUR helper:

```sh
yay -S termcap        # or: paru -S termcap
```

To build straight from the packaging files:

```sh
git clone https://github.com/gitUmaru/termcap.git
cd termcap/packaging/aur
makepkg -si
```

### pip / from source

```sh
git clone https://github.com/gitUmaru/termcap.git
cd termcap
python3 -m pip install .
```

Or grab a built wheel from the [Releases](https://github.com/gitUmaru/termcap/releases) page.

For MP4/WebM output, also install ffmpeg (`brew install ffmpeg`, `apt install ffmpeg`, …).

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
termcap webm <cast> [out.webm]                     Cast -> WebM VP9 video (needs ffmpeg)
termcap frame <media> [out.png] [--at S]           Extract a still from GIF/MP4/WebM
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
- **Fonts & Nerd Font icons:** the raster renderer auto-selects an installed
  monospaced Nerd Font (e.g. JetBrainsMono Nerd Font, MesloLGS NF) as the primary
  so icon glyphs render instead of empty boxes. Characters missing from the primary
  font are drawn from a per-glyph fallback chain across your other installed icon
  fonts. Force a specific font with `TERMCAP_FONT=/path/to/Font.ttf`. For SVG output,
  the font is named in CSS (viewers need it installed); override the family list with
  `TERMCAP_SVG_FONT`.

## License

MIT — see [LICENSE](LICENSE).

[Pillow]: https://python-pillow.org/
