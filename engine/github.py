"""Small GitHub REST helpers: issues, the 'media' release that stores videos, raw URLs."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import requests

from .config import ROOT, repo_slug

API = "https://api.github.com"
MEDIA_TAG = "media"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") and repo_slug())


def raw_url(path: Path, ref: str | None = None) -> str:
    """Public URL for a committed file. Uses the current commit so the URL never changes under us."""
    ref = ref or os.environ.get("GITHUB_SHA", "main")
    rel = path.resolve().relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{repo_slug()}/{ref}/{quote(rel)}"


def blob_url(path: Path, ref: str = "main") -> str:
    rel = path.resolve().relative_to(ROOT).as_posix()
    return f"https://github.com/{repo_slug()}/blob/{ref}/{quote(rel)}"


# ---- issues ---------------------------------------------------------------
def create_issue(title: str, body: str, labels: list[str] | None = None) -> int | None:
    if not available():
        print(f"[issue] {title}\n{body}\n")
        return None
    r = requests.post(f"{API}/repos/{repo_slug()}/issues", headers=_headers(),
                      json={"title": title, "body": body, "labels": labels or []}, timeout=30)
    r.raise_for_status()
    return r.json()["number"]


def comment_issue(number: int, body: str) -> None:
    if not available():
        print(f"[issue #{number} comment] {body}")
        return
    requests.post(f"{API}/repos/{repo_slug()}/issues/{number}/comments", headers=_headers(),
                  json={"body": body}, timeout=30).raise_for_status()


def close_issue(number: int) -> None:
    if available():
        requests.patch(f"{API}/repos/{repo_slug()}/issues/{number}", headers=_headers(),
                       json={"state": "closed"}, timeout=30)


# ---- media release (keeps big videos out of git history) -------------------
def _media_release() -> dict:
    s = requests.Session()
    s.headers.update(_headers())
    r = s.get(f"{API}/repos/{repo_slug()}/releases/tags/{MEDIA_TAG}", timeout=30)
    if r.status_code == 404:
        r = s.post(f"{API}/repos/{repo_slug()}/releases", timeout=30, json={
            "tag_name": MEDIA_TAG, "name": "Rendered media",
            "body": "Videos rendered by content-engine. Managed automatically — don't edit.",
            "prerelease": True})
    r.raise_for_status()
    return r.json()


def upload_media(path: Path, name: str) -> dict:
    rel = _media_release()
    for asset in rel.get("assets", []):
        if asset["name"] == name:
            requests.delete(asset["url"], headers=_headers(), timeout=30).raise_for_status()
    upload = rel["upload_url"].split("{")[0]
    with open(path, "rb") as f:
        r = requests.post(upload, params={"name": name}, data=f, timeout=600,
                          headers={**_headers(), "Content-Type": "video/mp4"})
    r.raise_for_status()
    a = r.json()
    return {"release_asset": name, "url": a["browser_download_url"], "api_url": a["url"], "size": a["size"]}


def download_media(ref: dict, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(ref["api_url"], headers={**_headers(), "Accept": "application/octet-stream"},
                      stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return dest


def resolve_video(post) -> Path:
    """Local path to a post's rendered video, downloading it from the media release if needed."""
    ref = post.video_ref()
    if not ref:
        raise RuntimeError(f"{post.id}: video not rendered")
    if "local" in ref:
        return ROOT / ref["local"]
    cache = ROOT / ".cache" / ref["release_asset"]
    if not cache.exists():
        download_media(ref, cache)
    return cache
