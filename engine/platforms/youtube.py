"""YouTube Shorts.

Two modes, set with the YOUTUBE_MODE repo variable:

- "handoff" (default): YouTube locks API uploads from unaudited Google Cloud projects to
  private, permanently. So at the scheduled time we open a GitHub issue with the finished
  video and copy-ready title/description/tags; you upload it from the YouTube app (~30 s)
  and close the issue.
- "api": once your project passes the YouTube API compliance audit, uploads go straight out.
  Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (from tools/auth_youtube.py).
"""
from __future__ import annotations

import json

import requests

from ..config import env
from ..github import create_issue, resolve_video
from . import PublishError, Result

UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


def _meta(post) -> dict:
    yt = post.data.get("youtube") or {}
    title = yt["title"].strip()
    desc = (yt.get("description") or post.text or "").strip()
    if "#shorts" not in (title + desc).lower():
        desc = (desc + "\n\n#Shorts").strip()
    return {"title": title, "description": desc, "tags": yt.get("tags") or [],
            "category": str(yt.get("category_id", "28"))}  # 28 = Science & Technology


def _access_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": env("YT_CLIENT_ID", required=True),
        "client_secret": env("YT_CLIENT_SECRET", required=True),
        "refresh_token": env("YT_REFRESH_TOKEN", required=True),
        "grant_type": "refresh_token"})
    if r.status_code >= 400:
        raise PublishError(f"YouTube token refresh failed: {r.status_code} {r.text[:300]}")
    return r.json()["access_token"]


def _upload(post) -> Result:
    m = _meta(post)
    path = resolve_video(post)
    token = _access_token()
    body = {"snippet": {"title": m["title"], "description": m["description"], "tags": m["tags"],
                        "categoryId": m["category"]},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    init = requests.post(UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"}, timeout=60,
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                  "X-Upload-Content-Type": "video/mp4",
                                  "X-Upload-Content-Length": str(path.stat().st_size)},
                         data=json.dumps(body))
    if init.status_code >= 400:
        raise PublishError(f"YouTube upload init failed: {init.status_code} {init.text[:300]}")
    with open(path, "rb") as f:
        up = requests.put(init.headers["Location"], data=f, timeout=900,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
    if up.status_code >= 400:
        raise PublishError(f"YouTube upload failed: {up.status_code} {up.text[:300]}")
    data = up.json()
    vid = data["id"]
    privacy = data.get("status", {}).get("privacyStatus")
    note = None if privacy == "public" else (
        f"uploaded as {privacy} — your Google project is probably not audited yet; switch YOUTUBE_MODE back to handoff")
    return Result("published", vid, f"https://youtube.com/shorts/{vid}", note)


def _handoff(post) -> Result:
    m = _meta(post)
    ref = post.video_ref() or {}
    link = ref.get("url") or "(see the assets folder for this post)"
    tags = ", ".join(m["tags"])
    body = f"""Today's Short is ready. Upload it from the YouTube app, then close this issue.

**1. Download the video:** {link}

**2. Title**
```
{m['title']}
```
**3. Description**
```
{m['description']}
```
**4. Tags** (YouTube Studio → Details → Show more)
```
{tags}
```
Audience: *No, it's not made for kids.* Visibility: *Public*.

_Post file: `{post.id}.yml` — Once your Google project passes the YouTube audit, set the repo
variable `YOUTUBE_MODE` to `api` and this step goes away._"""
    number = create_issue(f"📲 Upload today's Short: {m['title']}", body, ["youtube-upload"])
    return Result("handoff", str(number) if number else None, note="manual upload issue opened")


def publish(post, dry_run: bool = False) -> Result:
    mode = (env("YOUTUBE_MODE") or "handoff").lower()
    if dry_run:
        return Result("published", note=f"[dry-run] YouTube ({mode}): {_meta(post)['title']}")
    return _upload(post) if mode == "api" else _handoff(post)
