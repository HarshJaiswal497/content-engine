"""Cover thumbnails for Reels and Shorts, made at render time next to the video.

A post can say what it wants:

    cover:
      words: [Nobody likes, "*UGLY*", themes]     # one line each; *x* is the highlighted line
      layout: face | scene                        # face = your sticker cut-out (default), scene = you at your desk
      pose: surprised                             # a file in assets/people/harsh/ (face)
      scene: working-on-laptop-3                  # a file in assets/people/harsh/scenes/ (scene)
      screen: slipnote/theme-fridge               # optional real app screen
      mascot: slip:happy                          # optional slip|bo:<pose>
      kicker: so I rebuilt them                   # optional small line

Without a `cover:` the headline comes from the first slide's title (slides), the hook (talking head) or the story's
first beat. The result is cover.jpg (1080x1920) in the post's asset folder; Instagram gets it as the Reel cover and the
YouTube upload issue links it. Failure never blocks a post: no cover just means Instagram picks a frame."""
from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

from ..config import ROOT

POSES = ["happy-with-teeth", "thinking", "surprised", "simple-smile", "shocked", "normal"]
MASCOT = {"slipnote": "slip:happy", "setalytix": "bo:flex"}


def _maker():
    spec = importlib.util.spec_from_file_location("make_thumb", ROOT / "tools" / "make_thumb.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wrap(text: str, width: int = 11) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    # no orphans: a tiny last line ("to", "a") joins the line before it
    while len(lines) > 1 and len(lines[-1]) <= 3 and len(lines[-2]) + 1 + len(lines[-1]) <= 14:
        lines[-2] += " " + lines.pop()
    return lines


def words_from_title(title: str, max_lines: int = 3) -> list[str]:
    """'Slip had to *sit on a button*' -> ['Slip had to', '*sit on a*', '*button*'] (highlighted lines wrapped in *).
    At most 3 lines (the face needs room); with no highlight in the title the longest line gets one."""
    segs = [(seg.strip(), i % 2 == 1) for i, seg in enumerate(title.split("*")) if seg.strip()]
    for width in (11, 14, 18):
        out = [(ln, hl) for seg, hl in segs for ln in _wrap(seg, width)]
        if len(out) <= max_lines:
            break
    while len(out) > max_lines:               # still too long: drop plain trailing text first, then the tail
        k = next((j for j in range(len(out) - 1, -1, -1) if not out[j][1]), len(out) - 1)
        out.pop(k)
    if out and not any(hl for _, hl in out):
        k = max(range(len(out)), key=lambda j: len(out[j][0]))
        out[k] = (out[k][0], True)
    return [f"*{t}*" if hl else t for t, hl in out]


def _headline(post) -> str:
    v = post.video_spec
    for sl in post.data.get("slides") or []:
        if sl.get("title"):
            return str(sl["title"])
    if v.get("hook"):
        return str(v["hook"])
    if v.get("title"):
        return str(v["title"])
    for b in v.get("beats") or []:
        if b.get("head"):
            return str(b["head"])
    return ""


def cover_spec(post) -> dict | None:
    spec = dict(post.data.get("cover") or {})
    if not spec and post.video_spec.get("kind") == "same_as":     # a Short that reuses its sibling's video reuses its cover
        from ..post import load
        sib = load(post.path.parent / f"{post.video_spec['post']}.yml")
        spec = dict(sib.data.get("cover") or {})
        if not spec:
            return cover_spec(sib)
    if "words" not in spec:
        head = _headline(post)
        if not head:
            return None
        spec["words"] = words_from_title(head)
    spec.setdefault("app", post.app)
    spec.setdefault("size", "reel")
    spec.setdefault("layout", "face")
    if spec["layout"] == "face":
        h = int(hashlib.sha256(post.id.encode()).hexdigest(), 16)
        spec.setdefault("pose", POSES[h % len(POSES)])
        spec.setdefault("side", "left" if (h >> 8) % 2 else "right")
    if "mascot" not in spec and "mascot" not in (post.data.get("cover") or {}):
        spec["mascot"] = MASCOT.get(post.app)
    if "screen" not in spec:
        for sl in post.data.get("slides") or []:
            if sl.get("screen"):
                spec["screen"] = sl["screen"]
                break
        for b in post.video_spec.get("beats") or []:
            if b.get("screen") and "screen" not in spec:
                spec["screen"] = b["screen"]
    longest = max((len(re.sub(r"\*", "", w)) for w in spec["words"]), default=8)
    spec.setdefault("font", max(96, min(176, int(960 / (max(longest, 6) * 0.70)))))
    return spec


def make_cover(post) -> Path | None:
    spec = cover_spec(post)
    if not spec:
        return None
    from PIL import Image
    out = post.asset_dir / "cover.jpg"
    png = post.asset_dir / "cover.png"
    try:
        _maker().render(spec, png)
        Image.open(png).convert("RGB").save(out, "JPEG", quality=88)
    finally:
        png.unlink(missing_ok=True)
    return out
