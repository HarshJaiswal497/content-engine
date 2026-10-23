"""Instagram publishing via the official Instagram API with Instagram Login (graph.instagram.com).

No Facebook Page needed. Requires an Instagram Professional (Creator/Business) account and a
Meta developer app with the Instagram product. Secrets: IG_ACCESS_TOKEN (long-lived, refreshed
weekly by the refresh-tokens workflow), IG_USER_ID (optional; looked up if missing).

Images must be JPEG at a public URL — rendered slides are committed to this (public) repo and
served from raw.githubusercontent.com. Reels are uploaded directly (resumable upload).
"""
from __future__ import annotations

import time

import requests

from ..config import env
from ..github import raw_url, resolve_video
from . import PublishError, Result

VERSION = "v23.0"


def _base() -> str:
    return f"https://graph.instagram.com/{env('IG_API_VERSION') or VERSION}"


def _token() -> str:
    return env("IG_ACCESS_TOKEN", required=True)


def _check(r: requests.Response, what: str) -> dict:
    if r.status_code >= 400:
        raise PublishError(f"Instagram {what} failed: {r.status_code} {r.text[:500]}")
    return r.json()


def user_id() -> str:
    uid = env("IG_USER_ID")
    if uid:
        return uid
    data = _check(requests.get(f"{_base()}/me", params={"fields": "user_id,username", "access_token": _token()},
                               timeout=30), "me")
    return data["user_id"]


def _container(uid: str, **params) -> str:
    data = _check(requests.post(f"{_base()}/{uid}/media", data={**params, "access_token": _token()},
                                timeout=60), "create container")
    return data["id"]


def _wait(container_id: str, minutes: int = 10) -> None:
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        data = _check(requests.get(f"{_base()}/{container_id}",
                                   params={"fields": "status_code,status", "access_token": _token()},
                                   timeout=30), "container status")
        code = data.get("status_code")
        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagram container {container_id} {code}: {data.get('status')}")
        time.sleep(8)
    raise PublishError(f"Instagram container {container_id} not ready after {minutes} min")


def _publish(uid: str, container_id: str) -> str:
    _wait(container_id)
    data = _check(requests.post(f"{_base()}/{uid}/media_publish",
                                data={"creation_id": container_id, "access_token": _token()}, timeout=60),
                  "media_publish")
    return data["id"]


def _reel_container(uid: str, caption: str, video_path) -> str:
    size = video_path.stat().st_size
    data = _check(requests.post(f"{_base()}/{uid}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "access_token": _token()}), "reel container")
    cid, upload_uri = data["id"], data.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{env('IG_API_VERSION') or VERSION}/{data['id']}"
    with open(video_path, "rb") as f:
        r = requests.post(upload_uri, data=f, timeout=600, headers={
            "Authorization": f"OAuth {_token()}", "offset": "0", "file_size": str(size)})
    _check(r, "reel upload")
    return cid


def publish(post, dry_run: bool = False) -> Result:
    caption = post.text
    if dry_run:
        n = len(post.images()) if post.needs_images else 1
        return Result("published", note=f"[dry-run] Instagram {post.format}, caption {len(caption)} chars, {n} media")

    uid = user_id()
    if post.format == "image":
        cid = _container(uid, image_url=raw_url(post.images()[0]), caption=caption)
    elif post.format == "carousel":
        children = []
        for img in post.images():
            child = _container(uid, image_url=raw_url(img), is_carousel_item="true")
            _wait(child, minutes=3)
            children.append(child)
        cid = _container(uid, media_type="CAROUSEL", children=",".join(children), caption=caption)
    elif post.format == "reel":
        cid = _reel_container(uid, caption, resolve_video(post))
    else:
        raise PublishError(f"unsupported Instagram format {post.format}")

    media_id = _publish(uid, cid)
    link = None
    try:
        link = requests.get(f"{_base()}/{media_id}", params={"fields": "permalink", "access_token": _token()},
                            timeout=30).json().get("permalink")
    except Exception:  # permalink is a nice-to-have
        pass

    comment = (post.data.get("first_comment") or "").strip()
    note = None
    if comment:
        cr = requests.post(f"{_base()}/{media_id}/comments", data={"message": comment, "access_token": _token()},
                           timeout=30)
        if cr.status_code >= 400:
            note = f"first comment failed: {cr.status_code}"
    return Result("published", media_id, link, note)


def refresh_token(token: str) -> tuple[str, int]:
    """Exchange a long-lived token for a fresh 60-day one. Token must be at least 24h old."""
    data = _check(requests.get("https://graph.instagram.com/refresh_access_token",
                               params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30),
                  "token refresh")
    return data["access_token"], int(data.get("expires_in", 0))
