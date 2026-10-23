"""LinkedIn personal-profile publishing via the official Posts API.

Needs a LinkedIn developer app with the self-serve products "Share on LinkedIn" and
"Sign In with LinkedIn using OpenID Connect" (scopes: openid profile w_member_social).
Secrets: LINKEDIN_ACCESS_TOKEN (60-day token from tools/auth_linkedin.py).
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

from ..config import env
from ..github import resolve_video
from . import PublishError, Result

API = "https://api.linkedin.com"
RESERVED = r"\|{}@[]()<>#*_~"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {env('LINKEDIN_ACCESS_TOKEN', required=True)}",
        # LinkedIn versions are YYYYMM and each is supported for ~1 year. Bump via the
        # LINKEDIN_VERSION repo variable if posts start failing with a version error.
        "LinkedIn-Version": env("LINKEDIN_VERSION") or "202601",
        "X-Restli-Protocol-Version": "2.0.0",
    })
    return s


def _check(r: requests.Response, what: str) -> requests.Response:
    if r.status_code >= 400:
        raise PublishError(f"LinkedIn {what} failed: {r.status_code} {r.text[:500]}")
    return r


def author_urn(s: requests.Session) -> str:
    urn = env("LINKEDIN_PERSON_URN")
    if urn:
        return urn
    r = _check(s.get(f"{API}/v2/userinfo", timeout=30), "userinfo")
    return f"urn:li:person:{r.json()['sub']}"


def to_little_text(text: str) -> str:
    """Escape LinkedIn 'little text' reserved chars, keeping #hashtags as real hashtags."""
    tags: list[str] = []

    def keep(m: re.Match) -> str:
        tags.append(m.group(1))
        return f"\x00{len(tags) - 1}\x00"

    text = re.sub(r"(?<!\w)#(\w+)", keep, text)
    text = "".join("\\" + c if c in RESERVED else c for c in text)
    return re.sub(r"\x00(\d+)\x00", lambda m: "{hashtag|\\#|" + tags[int(m.group(1))] + "}", text)


def upload_image(s: requests.Session, owner: str, path: Path) -> str:
    r = _check(s.post(f"{API}/rest/images?action=initializeUpload", timeout=30,
                      json={"initializeUploadRequest": {"owner": owner}}), "image init")
    v = r.json()["value"]
    with open(path, "rb") as f:
        _check(requests.put(v["uploadUrl"], data=f, timeout=120,
                            headers={"Authorization": s.headers["Authorization"]}), "image upload")
    return v["image"]


def upload_video(s: requests.Session, owner: str, path: Path) -> str:
    size = path.stat().st_size
    r = _check(s.post(f"{API}/rest/videos?action=initializeUpload", timeout=30, json={
        "initializeUploadRequest": {"owner": owner, "fileSizeBytes": size,
                                    "uploadCaptions": False, "uploadThumbnail": False}}), "video init")
    v = r.json()["value"]
    etags = []
    with open(path, "rb") as f:
        for part in v["uploadInstructions"]:
            f.seek(part["firstByte"])
            chunk = f.read(part["lastByte"] - part["firstByte"] + 1)
            up = _check(requests.put(part["uploadUrl"], data=chunk, timeout=300,
                                     headers={"Content-Type": "application/octet-stream"}), "video part")
            etags.append(up.headers.get("ETag") or up.headers.get("etag"))
    _check(s.post(f"{API}/rest/videos?action=finalizeUpload", timeout=60, json={
        "finalizeUploadRequest": {"video": v["video"], "uploadToken": v.get("uploadToken", ""),
                                  "uploadedPartIds": etags}}), "video finalize")
    for _ in range(60):  # wait up to ~10 min for processing
        st = s.get(f"{API}/rest/videos/{quote(v['video'], safe='')}", timeout=30)
        if st.ok and st.json().get("status") == "AVAILABLE":
            break
        if st.ok and st.json().get("status") == "PROCESSING_FAILED":
            raise PublishError("LinkedIn video processing failed")
        time.sleep(10)
    return v["video"]


def publish(post, dry_run: bool = False) -> Result:
    if dry_run:
        n = len(post.images()) if post.needs_images else (1 if post.needs_video else 0)
        return Result("published", note=f"[dry-run] LinkedIn {post.format}, {len(post.text)} chars, {n} media")

    s = _session()
    author = author_urn(s)
    alt = [sl.get("alt") or sl.get("title", "") for sl in post.data.get("slides") or []]
    content = None
    if post.format == "image":
        content = {"media": {"id": upload_image(s, author, post.images()[0]), "altText": alt[0][:300] if alt else ""}}
    elif post.format == "carousel":
        imgs = [{"id": upload_image(s, author, p), "altText": (alt[i] if i < len(alt) else "")[:300]}
                for i, p in enumerate(post.images())]
        content = {"multiImage": {"images": imgs}}
    elif post.format == "video":
        vid = upload_video(s, author, resolve_video(post))
        content = {"media": {"id": vid, "title": (post.data.get("video") or {}).get("title", "")[:200]}}

    body = {
        "author": author,
        "commentary": to_little_text(post.text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if content:
        body["content"] = content
    r = _check(s.post(f"{API}/rest/posts", json=body, timeout=60), "create post")
    urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id")
    url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else None

    comment = (post.data.get("first_comment") or "").strip()
    if comment and urn:
        time.sleep(3)
        cr = s.post(f"{API}/rest/socialActions/{quote(urn, safe='')}/comments", timeout=30, json={
            "actor": author, "object": urn, "message": {"text": comment}})
        if cr.status_code >= 400:
            return Result("published", urn, url, note=f"first comment failed: {cr.status_code}")
    return Result("published", urn, url)
