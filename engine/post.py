"""Loading and validating post files in queue/<date>/<platform>[-n].yml."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from .config import QUEUE, ROOT, TZ, INBOX

PLATFORMS = {"linkedin", "instagram", "youtube"}
FORMATS = {
    "linkedin": {"text", "image", "carousel", "video"},
    "instagram": {"image", "carousel", "reel"},
    "youtube": {"short"},
}
VIDEO_KINDS = {"slides", "recording", "talking_head", "same_as"}
APPS = {"slipnote", "setalytix", "personal"}

# Hard limits from brand/founder.md. Each entry: (regex, message). Matches are errors.
FORBIDDEN = [
    (r"(?i)terms of service|privacy (notice|policy)|disclaimer|\bdpdp\b|\bgdpr\b|lawyer|\blegal\b", "legal topic — not allowed in posts for now"),
    (r"₹\s?[1-9]|(?i:\bper month\b|/month|subscription|\bpremium\b|\bpaywall\b|\bads\b)", "pricing/ads/premium — not until near launch"),
]



def blocked_terms() -> list[str]:
    """Names that must never appear in posts (e.g. competitor apps). Kept out of this public repo:
    read from the BLOCKED_TERMS secret (comma/newline separated) or a file at BLOCKED_TERMS_FILE."""
    raw = os.environ.get("BLOCKED_TERMS", "")
    path = os.environ.get("BLOCKED_TERMS_FILE")
    if path and Path(path).exists():
        raw += "\n" + Path(path).read_text(encoding="utf-8")
    return [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]


BANNED_PHRASES = [
    "delve", "game-changer", "game changer", "fast-paced world", "let's dive in",
    "here's the thing", "humbled to announce", "comment yes", "agree?",
]


@dataclass
class Post:
    path: Path
    data: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ---- identity -------------------------------------------------------
    @property
    def id(self) -> str:
        return self.path.relative_to(ROOT).with_suffix("").as_posix()

    @property
    def platform(self) -> str:
        return self.data.get("platform", "")

    @property
    def format(self) -> str:
        return self.data.get("format", "")

    @property
    def app(self) -> str:
        return self.data.get("app", "personal")

    @property
    def scheduled_at(self) -> datetime | None:
        raw = self.data.get("scheduled_at")
        if raw is None:
            return None
        if isinstance(raw, datetime):
            dt = raw
        else:
            dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt

    # ---- media ----------------------------------------------------------
    @property
    def asset_dir(self) -> Path:
        return self.path.parent / "assets" / self.path.stem

    @property
    def needs_images(self) -> bool:
        return self.format in {"image", "carousel"}

    @property
    def needs_video(self) -> bool:
        return self.format in {"video", "reel", "short"}

    @property
    def video_spec(self) -> dict:
        return self.data.get("video") or {}

    def images(self) -> list[Path]:
        return sorted(self.asset_dir.glob("slide-*.jpg"))

    def video_ref(self) -> dict | None:
        ref = self.asset_dir / "video.json"
        if ref.exists():
            return json.loads(ref.read_text())
        local = self.asset_dir / "video.mp4"
        if local.exists():
            return {"local": local.relative_to(ROOT).as_posix()}
        return None

    def video_source(self) -> Path | None:
        """Raw clip in inbox/ for recording/talking_head videos."""
        src = self.video_spec.get("source")
        if not src:
            return None
        # Accept "inbox/clip.mp4" or just "clip.mp4" (assumed to be in inbox/).
        return ROOT / src if "/" in src else INBOX / src

    def awaiting_recording(self) -> bool:
        kind = self.video_spec.get("kind")
        if not self.needs_video or kind not in {"recording", "talking_head"}:
            return False
        src = self.video_source()
        return src is None or not src.exists()

    def render_hash(self) -> str:
        """Changes when anything that affects rendered media changes."""
        relevant = {k: self.data.get(k) for k in ("format", "app", "slides", "video", "theme")}
        src = self.video_source()
        if src and src.exists():
            relevant["_src"] = [src.name, src.stat().st_size]
        blob = json.dumps(relevant, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def is_rendered(self) -> bool:
        if not (self.needs_images or self.needs_video):
            return True
        stamp = self.asset_dir / ".render-hash"
        if not stamp.exists() or stamp.read_text().strip() != self.render_hash():
            return False
        if self.needs_images and not self.images():
            return False
        if self.needs_video and not self.video_ref():
            return False
        return True

    # ---- text -----------------------------------------------------------
    @property
    def text(self) -> str:
        return (self.data.get("text") or "").strip()


def load(path: Path) -> Post:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    post = Post(path=path.resolve(), data=data)
    validate(post)
    return post


def all_posts(root: Path = QUEUE) -> list[Post]:
    files = [p for p in root.glob("*/*.yml") if not p.name.startswith("_")]
    return sorted((load(p) for p in files), key=lambda p: (p.scheduled_at or datetime.max.replace(tzinfo=TZ), p.id))


HASHTAG = re.compile(r"(?<!\w)#\w+")


def validate(post: Post) -> None:
    d, e, w = post.data, post.errors, post.warnings
    if post.platform not in PLATFORMS:
        e.append(f"platform must be one of {sorted(PLATFORMS)}")
        return
    if post.format not in FORMATS[post.platform]:
        e.append(f"format for {post.platform} must be one of {sorted(FORMATS[post.platform])}")
    if post.app not in APPS:
        e.append(f"app must be one of {sorted(APPS)}")
    try:
        if post.scheduled_at is None:
            e.append("scheduled_at is required")
    except ValueError:
        e.append("scheduled_at is not a valid ISO datetime")

    text = post.text
    if post.platform == "linkedin":
        if not text:
            e.append("text is required")
        if len(text) > 3000:
            e.append(f"LinkedIn text is {len(text)} chars (max 3000)")
        if len(HASHTAG.findall(text)) > 3:
            w.append("more than 3 hashtags on LinkedIn")
        if "http" in text:
            w.append("link in LinkedIn body — put it in first_comment for better reach")
    if post.platform == "instagram":
        if len(text) > 2200:
            e.append(f"Instagram caption is {len(text)} chars (max 2200)")
        if len(HASHTAG.findall(text)) > 30:
            e.append("more than 30 hashtags on Instagram")
    if post.platform == "youtube":
        yt = d.get("youtube") or {}
        title = yt.get("title", "")
        if not title:
            e.append("youtube.title is required")
        elif len(title) > 100:
            e.append(f"youtube.title is {len(title)} chars (max 100)")
        if len(yt.get("description", "")) > 5000:
            e.append("youtube.description over 5000 chars")
        if "<" in title or ">" in title:
            e.append("youtube.title can't contain < or >")

    if post.needs_images:
        slides = d.get("slides") or []
        if not slides:
            e.append(f"format '{post.format}' needs slides")
        if post.format == "image" and len(slides) != 1:
            e.append("format 'image' needs exactly 1 slide")
        if post.format == "carousel" and not (2 <= len(slides) <= 10):
            e.append("carousel needs 2–10 slides")
    if post.needs_video:
        kind = post.video_spec.get("kind")
        if kind not in VIDEO_KINDS:
            e.append(f"video.kind must be one of {sorted(VIDEO_KINDS)}")
        if kind == "slides" and not d.get("slides"):
            e.append("video.kind 'slides' needs slides")
        if kind in {"recording", "talking_head"} and not post.video_spec.get("source"):
            e.append("video.source (file in inbox/) is required for recording/talking_head")
        if kind == "talking_head" and not post.video_spec.get("script"):
            w.append("talking_head without video.script — Harsh won't know what to record")
        if kind == "same_as" and not post.video_spec.get("post"):
            e.append("video.post (sibling file name, e.g. instagram) required for same_as")

    everything = json.dumps({k: d.get(k) for k in ("text", "first_comment", "slides", "youtube")}, ensure_ascii=False)
    if "TODO" in everything:
        e.append("contains TODO — fill it in (or fill the matching TODO in brand/) before approving")

    for term in blocked_terms():
        if re.search(r"(?i)\b" + re.escape(term) + r"\b", everything):
            e.append("contains a blocked name (see BLOCKED_TERMS) — describe it generically instead")
    for pattern, message in FORBIDDEN:
        if re.search(pattern, everything):
            e.append(message)

    lowered = (text + " " + json.dumps(d.get("slides", []))).lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            w.append(f"banned phrase: '{phrase}'")
