"""Video building with ffmpeg (+ faster-whisper for captions). All output is 1080x1920, 30 fps, H.264/AAC."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import FONTS

W, H, FPS = 1080, 1920, 30
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart"]
MAX_SECONDS = 180


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-2000:]}")


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        rot = abs(int(sd.get("rotation", 0) or 0))
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    if rot in (90, 270):
        w, h = h, w
    return {"width": w, "height": h, "duration": float(info["format"].get("duration", 0)),
            "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


# ---- slides → motion video ---------------------------------------------------
def slides_to_video(images: list[Path], out: Path, seconds: list[float] | float = 3.2, fade: float = 0.45) -> Path:
    if isinstance(seconds, (int, float)):
        seconds = [float(seconds)] * len(images)
    seconds = [max(s, fade + 0.5) for s in seconds]
    cmd = ["ffmpeg", "-y", "-hide_banner"]
    for img, d in zip(images, seconds):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(img)]
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    parts = []
    for i, d in enumerate(seconds):
        frames = int(d * FPS)
        # slow push-in; upscale first so the zoom doesn't jitter
        parts.append(f"[{i}:v]scale={W * 2}:{H * 2},zoompan=z='min(1+0.0009*on,1.05)':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                     f"trim=end_frame={frames},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{i}]")
    last, offset = "v0", 0.0
    for i in range(1, len(seconds)):
        offset += seconds[i - 1] - fade
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        last = f"x{i}"
    total = sum(seconds) - fade * (len(seconds) - 1)
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]", "-map", f"{len(images)}:a",
            "-t", f"{total:.3f}", *ENC, str(out)]
    _run(cmd)
    return out


# ---- recordings → vertical, captioned ------------------------------------------
def _ass_time(t: float) -> str:
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def transcribe(path: Path) -> list[dict]:
    """Word-level timestamps via faster-whisper (CPU). Returns [{'word','start','end'}]."""
    from faster_whisper import WhisperModel  # imported lazily: heavy, CI-only

    model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), word_timestamps=True, vad_filter=True,
                                   language=os.environ.get("WHISPER_LANG") or None)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def chunk_words(words: list[dict], max_words: int = 3, max_gap: float = 0.6) -> list[dict]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap
                    or cur[-1]["word"].endswith((".", "?", "!", ","))):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return [{"text": " ".join(x["word"] for x in c), "start": c[0]["start"], "end": c[-1]["end"]} for c in chunks]


def build_ass(chunks: list[dict], hook: str | None, accent_hex: str) -> str:
    r, g, b = accent_hex[1:3], accent_hex[3:5], accent_hex[5:7]
    accent = f"&H00{b}{g}{r}".upper()
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Cap,Inter Display,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,560,1",
        f"Style: Hook,Inter Display,72,&H00FFFFFF,&H00FFFFFF,{accent},{accent},-1,0,0,0,100,100,0,0,3,18,0,8,90,90,240,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook:
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(2.8)},Hook,,0,0,0,,{_ass_escape(hook)}")
    for c in chunks:
        end = max(c["end"], c["start"] + 0.35)
        lines.append(f"Dialogue: 0,{_ass_time(c['start'])},{_ass_time(end)},Cap,,0,0,0,,"
                     f"{{\\fad(40,40)}}{_ass_escape(c['text'])}")
    return "\n".join(lines) + "\n"


def caption_video(src: Path, out: Path, hook: str | None = None, accent: str = "#7DD3FC",
                  captions: bool = True, words: list[dict] | None = None) -> Path:
    info = probe(src)
    duration = min(info["duration"], MAX_SECONDS)
    if captions and info["has_audio"] and words is None:
        words = transcribe(src)
    chunks = chunk_words(words or []) if captions else []

    with tempfile.TemporaryDirectory() as tmp:
        ass = Path(tmp) / "subs.ass"
        ass.write_text(build_ass(chunks, hook, accent), encoding="utf-8")
        portrait = info["height"] >= info["width"] * 1.6
        if portrait:  # fill the frame
            base = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[base]"
        else:  # landscape/square screen recording: sharp centre over a blurred fill
            base = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                    f"boxblur=30:4,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")
        fontsdir = str(FONTS).replace(":", r"\:")
        assp = str(ass).replace(":", r"\:")
        graph = f"{base};[base]ass='{assp}':fontsdir='{fontsdir}'[v]"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(src)]
        if info["has_audio"]:
            cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "0:a:0"]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-filter_complex", graph, "-map", "[v]", "-map", "1:a"]
        cmd += ["-t", f"{duration:.3f}", *ENC, str(out)]
        _run(cmd)
    return out


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None
