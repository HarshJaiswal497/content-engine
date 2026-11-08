"""Sound effects placed on the timeline automatically.

The clips in assets/sfx are rendered once with earshot (tools/make_sfx.py), so CI needs nothing extra.
`manifest` knows where each clip peaks; `place()` delays a clip so that peak lands on the cue time.
Cues come from the structure of the video (hook at frame 0, scene changes, beats, the end), not by hand.
Takes rotate so the same whoosh does not play on every cut."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIR = ROOT / "assets" / "sfx"
MANIFEST = ROOT / "brand" / "sfx.json"
LIGHT_AFTER_SOUND = 0.033        # the sound lands one frame after the picture


def manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text())
    except (OSError, ValueError):
        return {}


def pick(role: str, n: int = 0) -> dict | None:
    takes = manifest().get(role) or []
    if not takes:
        return None
    t = takes[n % len(takes)]
    return t if (DIR / t["file"]).exists() else None


def cues_for_scenes(starts: list[float], total: float, hook: bool = True, sting: bool = False) -> list[dict]:
    """hit on frame 0, a whoosh into every later scene, optional end sting."""
    cues = []
    if hook:
        cues.append({"role": "hit", "t": 0.0, "gain": 0.7})
    for i, s in enumerate(starts[1:]):
        cues.append({"role": "whoosh", "t": s, "n": i, "gain": 0.5})
    if sting and total > 4:
        cues.append({"role": "sting", "t": max(total - 1.3, 0), "gain": 0.45})
    return cues


def add_to_graph(cues: list[dict], first_input: int, total: float) -> tuple[list[str], list[str], list[str]]:
    """Returns (ffmpeg -i args, filter parts, mix labels) for the cues that have a file."""
    args, parts, labels = [], [], []
    idx = first_input
    for k, c in enumerate(cues):
        take = pick(c["role"], c.get("n", 0))
        if not take:
            continue
        # place the clip's peak on the cue (one frame late), never before 0
        start = max(c["t"] + LIGHT_AFTER_SOUND - take["peak"], 0.0)
        ms = int(start * 1000)
        args += ["-i", str(DIR / take["file"])]
        parts.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=stereo,volume={c.get('gain', 0.5)},"
                     f"adelay={ms}|{ms}[sf{k}]")
        labels.append(f"[sf{k}]")
        idx += 1
    return args, parts, labels
