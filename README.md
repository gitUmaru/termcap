# termcap

A single-file wrapper that records your terminal and exports it to **GIF, SVG, MP4, PNG, JPEG**, or a plain **text session** — from one recording.

It ties together well-established tools behind one command so you don't have to remember each one's flags:

| Need                        | Backend            |
| --------------------------- | ------------------ |
| Text session (`.cast`)      | `asciinema`        |
| Animated GIF                | `agg`              |
| Animated SVG                | `svg-term-cli`     |
| Direct-to-SVG recording     | `termtosvg`        |
| Scripted GIF/MP4/WebM/PNG   | `vhs`              |
| Video / format conversion   | `ffmpeg`           |
| Native pixel capture (macOS)| `screencapture`    |

## Install

### 1. Backends

macOS (Homebrew):

```sh
brew install asciinema agg vhs ffmpeg
npm  install -g svg-term-cli
pipx install termtosvg
```

`ffmpeg` and `screencapture` (macOS) are used for video and native pixel capture.
The record → GIF/SVG/MP4/frame pipeline is cross-platform (macOS, Linux, WSL).
Only `shot`, `shotwin`, and `screenrec` are macOS-only.

### 2. The script

```sh
git clone https://github.com/gitUmaru/termcap.git
install -m 0755 termcap/bin/termcap ~/bin/termcap   # or anywhere on your PATH
```

Make sure the install location is on your `PATH`.

## Usage

```
termcap rec  [file.cast] [-- command]     Record a text session (asciicast v2)
termcap play <file.cast>                  Replay a recording in the terminal
termcap gif  <file.cast> [out.gif]        Cast  -> animated GIF        (agg)
termcap svg  <file.cast> [out.svg]        Cast  -> animated SVG        (svg-term)
termcap mp4  <file.cast> [out.mp4]        Cast  -> MP4 video           (agg+ffmpeg)
termcap frame <in.gif|in.mp4> [out.png]   Extract a still (png/jpeg)   (ffmpeg)

termcap svgrec [file.svg] [-- command]    Record directly to SVG       (termtosvg)
termcap tape <file.tape>                  Run a vhs script -> its output(s)

termcap shot [out.png]                    macOS pixel screenshot (interactive)
termcap shotwin [out.png]                 macOS screenshot of a clicked window
termcap screenrec [out.mov]               macOS screen video recording

termcap doctor                            Check that all backends are present
termcap help                              Show help
```

### Example

```sh
termcap rec demo.cast          # record; press ctrl-d to stop
termcap gif   demo.cast        # -> demo.gif
termcap svg   demo.cast        # -> demo.svg
termcap mp4   demo.cast        # -> demo.mp4
termcap frame demo.gif poster.png
```

One `.cast` recording feeds every format.

## Notes

- **asciicast v2, not v3:** `asciinema` 3.x records v3 by default, but `agg` and
  `svg-term` currently consume v2. `termcap rec` forces v2 so exports always work.
  If you have a v3 cast, run `asciinema convert` first.
- **macOS permissions:** `shot` / `shotwin` / `screenrec` need Screen Recording
  permission the first time (System Settings → Privacy & Security → Screen Recording).

## License

MIT — see [LICENSE](LICENSE).
