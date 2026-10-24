"""Facebook Page publishing: mirrors each published Instagram post to your Facebook Page.

Uses the official Graph API with a Page access token (pages_manage_posts). Secrets:
FB_PAGE_ID and FB_PAGE_TOKEN, from tools/facebook_page_token.py. If they aren't set,
mirroring is simply skipped.
"""
from __future__ import annotations

import json
import re

import requests

from ..config import env
from ..github import raw_url, resolve_video
from . import PublishError, Result

VERSION = "v23.0"


def configured() -> bool:
    return bool(env("FB_PAGE_ID") and env("FB_PAGE_TOKEN"))


def _base(host: str = "graph.facebook.com") -> str:
    return f"https://{host}/{env('FB_API_VERSION') or VERSION}"


def _check(r: requests.Response, what: str) -> dict:
    if r.status_code >= 400:
        raise PublishError(f"Facebook {what} failed: {r.status_code} {r.text[:500]}")
    return r.json()


def caption_for_facebook(text: str) -> str:
    """Instagram captions say 'link in bio'; on a Page that makes no sense, so drop those phrases."""
    text = re.sub(r"(?i)\s*[·•\-–—(]*\s*link in (my )?bio\.?\)?", "", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def publish(post, dry_run: bool = False) -> Result:
    page, token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    caption = caption_for_facebook(post.text)
    if dry_run:
        return Result("published", note=f"[dry-run] Facebook Page {post.format}, {len(caption)} chars")
    if not (page and token):
        raise PublishError("FB_PAGE_ID / FB_PAGE_TOKEN not set")

    if post.format == "image":
        data = _check(requests.post(f"{_base()}/{page}/photos", timeout=120, data={
            "url": raw_url(post.images()[0]), "caption": caption, "published": "true",
            "access_token": token}), "photo")
        post_id = data.get("post_id") or data["id"]
    elif post.format == "carousel":
        media = []
        for img in post.images():
            d = _check(requests.post(f"{_base()}/{page}/photos", timeout=120, data={
                "url": raw_url(img), "published": "false", "access_token": token}), "photo upload")
            media.append(json.dumps({"media_fbid": d["id"]}))
        form = {"message": caption, "access_token": token}
        form.update({f"attached_media[{i}]": m for i, m in enumerate(media)})
        post_id = _check(requests.post(f"{_base()}/{page}/feed", data=form, timeout=120), "multi-photo post")["id"]
    elif post.format == "reel":
        path = resolve_video(post)
        with open(path, "rb") as f:
            d = _check(requests.post(f"{_base('graph-video.facebook.com')}/{page}/videos", timeout=900,
                                     data={"description": caption, "access_token": token},
                                     files={"source": (path.name, f, "video/mp4")}), "video upload")
        post_id = d["id"]
    else:
        raise PublishError(f"unsupported format for Facebook: {post.format}")

    return Result("published", post_id, f"https://www.facebook.com/{post_id}")


def check_token() -> tuple[bool, str]:
    page, token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    if not (page and token):
        return True, "not configured"
    r = requests.get(f"{_base()}/{page}", params={"fields": "name", "access_token": token}, timeout=30)
    if r.ok:
        return True, f"valid for Page '{r.json().get('name')}'"
    return False, f"{r.status_code} {r.text[:200]}"
