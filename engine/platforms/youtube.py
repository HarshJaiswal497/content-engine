"""YouTube Shorts.

Two modes, set with the YOUTUBE_MODE repo variable:

- "handoff" (default): YouTube locks API uploads from unaudited Google Cloud projects to
  private, permanently. So as soon as a week's Shorts are rendered and approved, ONE GitHub issue
  lists every Short with its schedule time, video link and copy-ready title/description/tags; you
  upload and schedule them all in YouTube Studio in one sitting and close the issue.
- "api": once your project passes the YouTube API compliance audit, uploads go straight out.
  Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (from tools/auth_youtube.py).
"""
from __future__ import annotations

import json
from datetime import timedelta, timezone

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


IST = timezone(timedelta(hours=5, minutes=30))


def mode() -> str:
    return (env("YOUTUBE_MODE") or "handoff").lower()


def weekly_handoff(posts: list, dry_run: bool = False) -> tuple[int | None, list[str]]:
    """One GitHub issue for a whole batch of Shorts: for each, the schedule time, video link, title,
    description and tags, so they can all be uploaded and scheduled in YouTube Studio in one go.
    Returns (issue number, one log line per post)."""
    posts = sorted(posts, key=lambda p: p.scheduled_at)
    first, last = posts[0].scheduled_at.astimezone(IST), posts[-1].scheduled_at.astimezone(IST)
    span = f"{first:%d %b}" if first.date() == last.date() else f"{first:%d %b} – {last:%d %b}"
    parts = [f"""{len(posts)} Short{'s' if len(posts) != 1 else ''} are ready. Upload them in one sitting and **schedule** each one in YouTube Studio, then close this issue.

**How:** YouTube Studio → Create → Upload videos → pick the file → paste the title, description and tags below → *Audience: No, it's not made for kids* → **Visibility → Schedule** → set the date and time shown (India time) → Schedule. Tick each box as you go.

_Download links open the video file from this repo's release page (right-click → Save link as, or open and save)._
"""]
    for i, post in enumerate(posts, 1):
        m = _meta(post)
        ref = post.video_ref() or {}
        link = ref.get("url") or "(see the assets folder for this post)"
        when = post.scheduled_at.astimezone(IST)
        parts.append(f"""---
### {i}. {when:%a %d %b, %I:%M %p} IST — {m['title']}
- [ ] Uploaded and scheduled
- **Video:** {link}

**Title**
```
{m['title']}
```
**Description**
```
{m['description']}
```
**Tags** (Studio → Details → Show more)
```
{", ".join(m['tags'])}
```
_Post file: `{post.id}.yml`_
""")
    parts.append("_Once your Google project passes the YouTube audit, set the repo variable `YOUTUBE_MODE` to `api` and this step goes away._")
    title = f"📲 YouTube Shorts to schedule: {span} ({len(posts)})"
    if dry_run:
        return None, [f"📲 [dry-run] one YouTube issue for {len(posts)} Shorts: {title}"]
    number = create_issue(title, "\n".join(parts), ["youtube-upload"])
    return number, [f"📲 {p.id}: handoff (weekly issue #{number})" for p in posts]


def publish(post, dry_run: bool = False) -> Result:
    if dry_run:
        return Result("published", note=f"[dry-run] YouTube ({mode()}): {_meta(post)['title']}")
    return _upload(post) if mode() == "api" else _handoff(post)
