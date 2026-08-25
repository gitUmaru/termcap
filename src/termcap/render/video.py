"""MP4 rendering via ffmpeg.

We render frames with the raster backend, pipe them to ffmpeg as a PNG image
sequence, and let ffmpeg encode H.264. ffmpeg is the one external runtime
dependency for video (encoding H.264 in pure Python is impractical).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from termcap.cast import Cast
from termcap.render.frames import sample_frames
from termcap.render.raster import _cell_metrics, _frames_to_images, _load_font


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def render_mp4(
    cast: Cast,
    out_path: str,
    *,
    fps: float = 10.0,
    font_size: int = 16,
    padding: int = 10,
    idle_limit: float = 2.0,
    speed: float = 1.0,
) -> None:
    if not have_ffmpeg():
        raise RuntimeError(
            "ffmpeg not found on PATH; install it (brew install ffmpeg) for MP4 output"
        )

    frames = sample_frames(cast, fps=fps, idle_limit=idle_limit, speed=speed)
    images, durations = _frames_to_images(frames, font_size, padding, show_cursor=True)
    if not images:
        raise ValueError("nothing to render")

    # Expand variable-delay frames into a constant-rate PNG sequence.
    out_fps = max(2, int(round(fps)))
    frame_period_ms = 1000.0 / out_fps

    tmpdir = tempfile.mkdtemp(prefix="termcap-mp4-")
    try:
        n = 0
        for img, dur_ms in zip(images, durations):
            reps = max(1, int(round(dur_ms / frame_period_ms)))
            for _ in range(reps):
                img.save(os.path.join(tmpdir, f"{n:06d}.png"))
                n += 1

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(out_fps),
            "-i",
            os.path.join(tmpdir, "%06d.png"),
            "-movflags",
            "+faststart",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            out_path,
        ]
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg failed:\n" + proc.stderr.decode("utf-8", "replace")[-2000:]
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
