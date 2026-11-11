"""Impact-style thumbnails for clips: 9:16 Shorts cover and 16:9 YouTube thumb.

Frames are picked by sharpness and face size; text is drawn with ffmpeg
drawtext (big condensed font, thick black outline). Words wrapped in
*asterisks* make their line yellow; without any, the last line is yellow.
"""

from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path

import cv2

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "Anton-Regular.ttf"
FORMATS = {"shorts": (1080, 1920), "youtube": (1280, 720)}
YELLOW = "0xFFE500"


def _face_cascade():
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def candidate_frames(clip_path: Path, count: int = 3, samples: int = 24) -> list[float]:
    """Seconds of the sharpest frames with the biggest faces, at least 2s apart."""
    capture = cv2.VideoCapture(str(clip_path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    duration = (capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps
    if duration <= 0:
        capture.release()
        return [0.0]
    cascade = _face_cascade()
    scored = []
    for i in range(samples):
        t = 0.5 + (duration - 1.0) * i / max(1, samples - 1)
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(cv2.resize(frame, (360, int(360 * frame.shape[0] / frame.shape[1]))), cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(30, 30))
        face_area = max((w * h for _, _, w, h in faces), default=0) / (gray.shape[0] * gray.shape[1])
        scored.append((min(sharpness, 1500) / 1500 + face_area * 8, t))
    capture.release()
    picked: list[float] = []
    for _, t in sorted(scored, reverse=True):
        if all(abs(t - other) >= 2 for other in picked):
            picked.append(round(t, 2))
        if len(picked) == count:
            break
    return sorted(picked) or [0.0]


def extract_frame(clip_path: Path, seconds: float, out_path: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{max(0.0, seconds):.2f}", "-i", str(clip_path),
         "-frames:v", "1", "-q:v", "3", "-vf", "scale=360:-2", str(out_path)],
        check=True, capture_output=True, text=True,
    )
    return out_path


def _lines(text: str, width: int) -> list[tuple[str, bool]]:
    text = " ".join(text.upper().split())
    wrapped = textwrap.wrap(text, width=width, break_long_words=False) or [""]
    lines = [(line.replace("*", "").strip(), "*" in line) for line in wrapped]
    lines = [(line, hot) for line, hot in lines if line]
    if lines and not any(hot for _, hot in lines):
        lines[-1] = (lines[-1][0], True)
    return lines[:4]


def render_thumbnail(clip_path: Path, seconds: float, text: str, fmt: str, out_path: Path) -> Path:
    width, height = FORMATS[fmt]
    font = str(FONT_PATH).replace("\\", "/").replace(":", "\\:")
    with tempfile.TemporaryDirectory() as work:
        if fmt == "shorts":
            lines, size, x, max_w = _lines(text, 14), 128, "(w-text_w)/2", width - 80
            top = int(height * 0.12)
            graph = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                "eq=contrast=1.15:saturation=1.35:brightness=0.02,"
                f"drawbox=x=0:y=0:w=iw:h={int(height * 0.42)}:color=black@0.45:t=fill"
            )
        else:
            fg_w = int(height * 9 / 16) + 40
            lines, size, x, max_w = _lines(text, 12), 104, "48", width - fg_w - 28 - 80
            top = int((height - len(_lines(text, 12)) * 116) / 2)
            graph = (
                f"[0:v]split[a][b];"
                f"[a]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                f"boxblur=24:2,eq=brightness=-0.25:saturation=1.3[bg];"
                f"[b]scale=-2:{height},eq=contrast=1.15:saturation=1.35[fg];"
                f"[bg][fg]overlay=W-w-24:0,"
                f"drawbox=x=iw-{fg_w}-28:y=0:w=8:h=ih:color=0xE50914:t=fill"
            )
        y = top
        for index, (line, hot) in enumerate(lines):
            # Anton caps are about 0.48em wide; shrink long lines to fit.
            line_size = min(size, int(max_w / (0.48 * max(1, len(line)))))
            line_file = Path(work) / f"line_{index}.txt"
            line_file.write_text(line, encoding="utf-8")
            textfile = str(line_file).replace("\\", "/").replace(":", "\\:")
            graph += (
                f",drawtext=fontfile='{font}':textfile='{textfile}':fontsize={line_size}"
                f":fontcolor={YELLOW if hot else 'white'}:borderw={max(6, line_size // 14)}:bordercolor=black"
                f":shadowx=0:shadowy=6:shadowcolor=black@0.6:x={x}:y={y}"
            )
            y += int(line_size * 1.12)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{max(0.0, seconds):.2f}", "-i", str(clip_path),
             "-frames:v", "1", "-filter_complex", graph, "-q:v", "2", str(out_path)],
            check=True, capture_output=True, text=True,
        )
    return out_path
