"""Run: python -m pytest -q   (no network; platform APIs are mocked)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from engine import post as post_mod, publish, state
from engine.platforms import instagram, linkedin, youtube
from engine.post import all_posts, load

ROOT = Path(__file__).resolve().parent.parent


class FakeResp:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data or {}, headers or {}
        self.ok = status < 400
        self.text = json.dumps(self._data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


def test_all_week_one_posts_parse():
    posts = all_posts()
    assert len(posts) >= 21
    bad = [p.id for p in posts if p.errors and "TODO" not in " ".join(p.errors)]
    assert not bad, bad


def test_little_text_escapes_and_keeps_hashtags():
    out = linkedin.to_little_text("Ship (fast) #buildinpublic @me")
    assert "\\(fast\\)" in out and "\\@me" in out
    assert "{hashtag|\\#|buildinpublic}" in out


def test_todo_is_an_error(tmp_path):
    f = tmp_path / "x.yml"
    f.write_text("platform: linkedin\nformat: text\nscheduled_at: 2030-01-01T09:00:00+05:30\ntext: hi\n"
                 "first_comment: 'TODO link'\n")
    assert any("TODO" in e for e in load(f).errors)


def test_dry_run_publishes_due_posts(capsys):
    rc = publish.main(["--dry-run", "--now", "2026-10-27T12:00:00+05:30"])
    out = capsys.readouterr().out
    assert "queue/2026-10-26/linkedin" in out and "queue/2026-10-27/linkedin" in out
    assert "queue/2026-10-27/instagram" not in out  # 19:30, not due yet
    assert rc == 0


def test_expired_and_waiting(capsys):
    publish.main(["--dry-run", "--now", "2026-10-28T20:00:00+05:30"])
    out = capsys.readouterr().out
    assert "waiting for recording inbox/2026-10-28-why-setalytix.mp4" in out
    assert "queue/2026-10-26/linkedin: expired" in out


def test_instagram_carousel_call_sequence(monkeypatch):
    p = load(ROOT / "queue/2026-10-27/instagram.yml")
    calls = []

    def fake_post(url, data=None, **kw):
        calls.append(("POST", url, data))
        if url.endswith("/media_publish"):
            return FakeResp(data={"id": "MEDIA1"})
        return FakeResp(data={"id": f"C{len(calls)}"})

    def fake_get(url, params=None, **kw):
        if "fields" in (params or {}) and "status_code" in params["fields"]:
            return FakeResp(data={"status_code": "FINISHED"})
        return FakeResp(data={"permalink": "https://instagram.com/p/x"})

    monkeypatch.setenv("IG_ACCESS_TOKEN", "t"); monkeypatch.setenv("IG_USER_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/content-engine"); monkeypatch.setenv("GITHUB_SHA", "abc")
    monkeypatch.setattr(instagram.requests, "post", fake_post)
    monkeypatch.setattr(instagram.requests, "get", fake_get)
    r = instagram.publish(p)
    children = [c for c in calls if c[2] and c[2].get("is_carousel_item")]
    assert len(children) == len(p.images()) == 6
    assert children[0][2]["image_url"].startswith("https://raw.githubusercontent.com/owner/content-engine/abc/queue/")
    parent = [c for c in calls if c[2] and c[2].get("media_type") == "CAROUSEL"][0]
    assert parent[2]["children"].count(",") == 5 and parent[2]["caption"].startswith("I was sitting at home")
    assert r.remote_id == "MEDIA1" and r.url


def test_linkedin_text_post_body(monkeypatch):
    p = load(ROOT / "queue/2026-10-31/linkedin.yml")
    sent = {}

    class S:
        headers = {}

        def post(self, url, json=None, **kw):
            if "url" not in sent:
                sent["url"], sent["json"] = url, json
            else:
                sent["comment"] = json
            return FakeResp(201, headers={"x-restli-id": "urn:li:share:1"})

    monkeypatch.setattr(linkedin, "_session", lambda: S())
    monkeypatch.setattr(linkedin.time, "sleep", lambda s: None)
    monkeypatch.setenv("LINKEDIN_PERSON_URN", "urn:li:person:abc")
    r = linkedin.publish(p)
    assert sent["url"].endswith("/rest/posts")
    assert sent["json"]["author"] == "urn:li:person:abc"
    assert "{hashtag|\\#|ainative}" in sent["json"]["commentary"]
    assert "content" not in sent["json"]
    assert r.url == "https://www.linkedin.com/feed/update/urn:li:share:1/"
    assert sent["comment"]["message"]["text"].startswith("Setalytix: https://app.setalytix.in")


def test_youtube_handoff_opens_issue(monkeypatch):
    p = load(ROOT / "queue/2026-10-26/youtube.yml")
    made = {}
    monkeypatch.setattr(youtube, "create_issue", lambda t, b, l: made.update(t=t, b=b) or 7)
    r = youtube.publish(p)
    assert r.status == "handoff" and r.remote_id == "7"
    assert "what to lift today" in made["t"] and "#Shorts" in made["b"]


def test_state_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "LOG", tmp_path / "log.jsonl")
    state.record("a", "failed", attempts=1)
    state.record("a", "failed", attempts=3)
    assert state.is_done(state.load()["a"])
    state.record("b", "waiting", reminder_issue=5)
    assert not state.is_done(state.load()["b"])


def test_hard_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOCKED_TERMS", "RivalApp, Other App")
    f = tmp_path / "x.yml"
    base = "platform: linkedin\nformat: text\nscheduled_at: 2030-01-01T09:00:00+05:30\ntext: "
    for bad in ["Better than RivalApp", "unlike other app", "Our privacy notice", "Only ₹99 a month", "no ads ever"]:
        f.write_text(base + repr(bad) + "\n")
        assert load(f).errors, bad
    f.write_text(base + "'Illegal invocation, a ₹0 stack'\n")
    assert not load(f).errors


def test_facebook_caption_drops_link_in_bio():
    from engine.platforms.facebook import caption_for_facebook
    out = caption_for_facebook("Free in your browser. Link in bio.\n\n#gym")
    assert "bio" not in out.lower() and out.startswith("Free in your browser.") and "#gym" in out


def test_facebook_carousel_and_mirror_after_instagram(monkeypatch, tmp_path):
    from engine.platforms import facebook
    p = load(ROOT / "queue/2026-10-27/instagram.yml")
    calls = []

    def fake_post(url, data=None, **kw):
        calls.append((url, data))
        if url.endswith("/feed"):
            return FakeResp(data={"id": "123_456"})
        return FakeResp(data={"id": f"P{len(calls)}"})

    monkeypatch.setenv("FB_PAGE_ID", "123"); monkeypatch.setenv("FB_PAGE_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/content-engine"); monkeypatch.setenv("GITHUB_SHA", "abc")
    monkeypatch.setattr(facebook.requests, "post", fake_post)
    r = facebook.publish(p)
    uploads = [c for c in calls if c[0].endswith("/photos")]
    assert len(uploads) == len(p.images()) and all(c[1]["published"] == "false" for c in uploads)
    feed = calls[-1][1]
    assert "attached_media[0]" in feed and "link in bio" not in feed["message"].lower()
    assert r.url == "https://www.facebook.com/123_456"

    # publish loop: Facebook copy only after Instagram is published, logged separately
    monkeypatch.setattr(state, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(instagram, "publish", lambda post, dry_run=False: __import__("engine.platforms", fromlist=["Result"]).Result("published", "IG1", "u"))
    for mod in (linkedin, youtube):
        monkeypatch.setattr(mod, "publish", lambda post, dry_run=False: __import__("engine.platforms", fromlist=["Result"]).Result("published"))
    publish.main(["--now", "2026-10-27T19:40:00+05:30", "--only", "queue/2026-10-27/instagram"])
    log = state.load()
    assert log["queue/2026-10-27/instagram"]["status"] == "published"
    assert log["queue/2026-10-27/instagram#facebook"]["status"] == "published"
