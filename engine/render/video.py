"""Video building with ffmpeg (+ faster-whisper for captions). All output is 1080x1920, 30 fps, H.264/AAC."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import FONTS, ROOT

W, H, FPS = 1080, 1920, 30
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart"]
MAX_SECONDS = 180
MUSIC_DIR = ROOT / "assets" / "music"
MUSIC_CONFIG = ROOT / "brand" / "music.yml"
MUSIC_VOLUME = 0.6          # music alone (no voice)
MUSIC_WITH_VOICE = 0.45     # music bed before ducking; it ducks hard while the voice speaks
APP_MOOD = {"setalytix": "upbeat", "slipnote": "story"}


def mood_for(tone: str | None, app: str | None) -> str:
    return tone or APP_MOOD.get(app or "", "calm")


def pick_music(key: str, mood: str | None = None) -> Path | None:
    """A track from assets/music/ matching `mood` (see brand/music.yml), chosen by `key` so a video
    keeps the same track on re-renders. Falls back to any track."""
    d = Path(os.environ.get("MUSIC_DIR") or MUSIC_DIR)
    tracks = sorted(p for p in d.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")) if d.is_dir() else []
    if not tracks:
        return None
    if mood and MUSIC_CONFIG.exists() and not os.environ.get("MUSIC_DIR"):
        import yaml
        moods = {t["file"]: t.get("mood") for t in (yaml.safe_load(MUSIC_CONFIG.read_text()) or {}).get("tracks", [])}
        matching = [t for t in tracks if moods.get(t.name) == mood]
        tracks = matching or tracks
    import hashlib
    from datetime import date
    try:  # rotate by day, so videos on nearby days get different tracks
        n = date.fromisoformat(key[:10]).toordinal() + int(hashlib.sha1(key[10:].encode()).hexdigest(), 16) % 2
    except ValueError:
        n = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    return tracks[n % len(tracks)]


def _music_input(key: str, total: float, index: int, label: str = "aout",
                 volume: float = MUSIC_VOLUME, mood: str | None = None) -> tuple[list[str], str]:
    """ffmpeg inputs + filter for the music bed: quiet looped music with fades, or silence if there's none."""
    track = pick_music(key, mood)
    if not track:
        return (["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"],
                f"[{index}:a]atrim=0:{total:.3f}[{label}]")
    fade_out = max(total - 1.5, 0)
    return (["-stream_loop", "-1", "-i", str(track)],
            f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,volume={volume},atrim=0:{total:.3f},"
            f"afade=t=in:d=0.8,afade=t=out:st={fade_out:.3f}:d=1.5[{label}]")


def audio_seconds(path: Path) -> float:
    return probe(path)["duration"]


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
VOICE_LEAD, VOICE_TAIL = 0.25, 0.45   # pause before / after each spoken line


def slides_to_video(images: list[Path], out: Path, seconds: list[float] | float = 3.2, fade: float = 0.45,
                    voice: list[Path | None] | None = None, mood: str | None = None) -> Path:
    """Slides → vertical video. With `voice` (one clip or None per slide) each slide lasts as long as its
    line, the lines play over their slides, and the music sits quietly underneath."""
    if isinstance(seconds, (int, float)):
        seconds = [float(seconds)] * len(images)
    seconds = [max(s, fade + 0.5) for s in seconds]
    clips = list(voice or [])[:len(images)]
    clips += [None] * (len(images) - len(clips))
    if any(clips):  # let the narration set the pace
        seconds = [max(VOICE_LEAD + audio_seconds(c) + VOICE_TAIL + fade, 1.6) if c else min(s, 2.2)
                   for s, c in zip(seconds, clips)]
    cmd = ["ffmpeg", "-y", "-hide_banner"]
    for img, d in zip(images, seconds):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(img)]
    total = sum(seconds) - fade * (len(seconds) - 1)
    n = len(images)
    if any(clips):
        audio_in, music_f = _music_input("/".join(out.parts[-4:-1]), total, n, "music", MUSIC_WITH_VOICE, mood)
        cmd += audio_in
        parts, labels, start, idx = [music_f], [], 0.0, n + 1
        for i, c in enumerate(clips):
            if c:
                cmd += ["-i", str(c)]
                ms = int((start + VOICE_LEAD) * 1000)
                parts.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,loudnorm=I=-15:TP=-1.5,"
                             f"aresample=44100,adelay={ms}|{ms}[vo{i}]")
                labels.append(f"[vo{i}]")
                idx += 1
            start += seconds[i] - fade
        # all lines on one voice track; the music ducks under it (sidechain) and swells in the pauses
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                     f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},asplit=2[voice][key]")
        parts.append("[music][key]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=450:makeup=1[bed]")
        parts.append("[bed][voice]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]")
    else:
        audio_in, audio_f = _music_input("/".join(out.parts[-4:-1]), total, n, mood=mood)
        cmd += audio_in
        parts = [audio_f]
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
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]", "-map", "[aout]",
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


def transcribe(path: Path, script: str | None = None, fixes: dict | None = None) -> list[dict]:
    """Word-level timestamps via faster-whisper (CPU). Returns [{'word','start','end'}]."""
    from faster_whisper import WhisperModel  # imported lazily: heavy, CI-only

    cfg = caption_config()
    name = cfg.get("model") or os.environ.get("WHISPER_MODEL") or "large-v3-turbo"
    model = WhisperModel(name, device="cpu", compute_type="int8")
    # hotwords nudge spelling without the planned-script prompt (which made Whisper invent phrases);
    # not conditioning on previous text stops repeated-phrase loops.
    hot = " ".join(cfg.get("vocabulary") or []) or None
    segments, _ = model.transcribe(str(path), word_timestamps=True, vad_filter=True,
                                   language=os.environ.get("WHISPER_LANG") or "en", beam_size=5,
                                   condition_on_previous_text=False, hotwords=hot)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return fix_words(align_to_script(words, script), {**(cfg.get("fixes") or {}), **(fixes or {})})


CAPTIONS_CONFIG = ROOT / "brand" / "captions.yml"


def align_to_script(words: list[dict], script: str | None) -> list[dict]:
    """Harsh reads from a script, so where what Whisper heard is *close* to the script (e.g. "Slipknot"
    vs "Slipnote", "self-respect" vs "myself a spreadsheet"), use the script's words with the heard
    timings. Where he clearly said something else, keep what was heard. Script words he skipped are
    left out."""
    import difflib
    import re
    toks = (script or "").split()
    if not toks or not words:
        return words
    norm = lambda t: re.sub(r"[^\w]", "", t.lower())
    heard = [norm(w["word"]) for w in words]
    planned = [norm(t) for t in toks]
    out: list[dict] = []
    sm = difflib.SequenceMatcher(None, heard, planned, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out += [{**words[i], "word": toks[j]} for i, j in zip(range(i1, i2), range(j1, j2))]
        elif op == "replace":
            h, p = "".join(heard[i1:i2]), "".join(planned[j1:j2])
            n_h, n_p = i2 - i1, j2 - j1
            ratio = difflib.SequenceMatcher(None, h, p).ratio()
            close = (h == p                                     # "one -on -one" vs "one-on-one"
                     or (n_h == n_p == 1 and ratio >= 0.3)      # one word between matching words
                     or (ratio >= 0.4 and 0.5 <= n_p / n_h <= 2.5))
            if close:
                t0, t1 = words[i1]["start"], words[i2 - 1]["end"]
                step = (t1 - t0) / n_p
                out += [{"word": toks[j1 + k], "start": t0 + k * step, "end": t0 + (k + 1) * step} for k in range(n_p)]
            else:
                out += words[i1:i2]
        elif op == "delete":
            out += words[i1:i2]
    return out


def caption_config() -> dict:
    import yaml
    return (yaml.safe_load(CAPTIONS_CONFIG.read_text()) or {}) if CAPTIONS_CONFIG.exists() else {}


def fix_words(words: list[dict], fixes: dict) -> list[dict]:
    """Correct words the speech model gets wrong (e.g. 'Satellitics' → 'Setalytix'). Keys may be one
    to three words; matching ignores case and punctuation, and keeps the original punctuation.
    An empty replacement removes the words (e.g. a stumble)."""
    import re
    norm = lambda t: re.sub(r"[^\w']", "", t).lower()
    table = {tuple(k.lower().split()): v for k, v in fixes.items()}
    out, i = [], 0
    while i < len(words):
        for n in (3, 2, 1):
            key = tuple(norm(w["word"]) for w in words[i:i + n])
            if len(key) == n and key in table:
                tail = re.search(r"[^\w']*$", words[i + n - 1]["word"]).group(0)
                if table[key]:
                    out.append({"word": table[key] + tail, "start": words[i]["start"], "end": words[i + n - 1]["end"]})
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return out


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
                  captions: bool = True, words: list[dict] | None = None, mood: str | None = None,
                  script: str | None = None, fixes: dict | None = None) -> Path:
    info = probe(src)
    duration = min(info["duration"], MAX_SECONDS)
    if captions and info["has_audio"] and words is None:
        words = transcribe(src, script, fixes)
    chunks = chunk_words(words or []) if captions else []
    if words:
        (out.parent / "captions.txt").write_text(" ".join(w["word"] for w in words) + "\n", encoding="utf-8")

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
            # phone recordings are often quiet: bring speech up to a standard loudness
            cmd += ["-filter_complex", f"{graph};[0:a:0]loudnorm=I=-16:TP=-1.5,aresample=44100[aout]",
                    "-map", "[v]", "-map", "[aout]"]
        else:
            audio_in, audio_f = _music_input("/".join(out.parts[-4:-1]), duration, 1, mood=mood)
            cmd += [*audio_in, "-filter_complex", f"{graph};{audio_f}", "-map", "[v]", "-map", "[aout]"]
        cmd += ["-t", f"{duration:.3f}", *ENC, str(out)]
        _run(cmd)
    return out


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None
