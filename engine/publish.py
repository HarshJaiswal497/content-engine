"""Publish every approved post that is due.

"Approved" means the post file is on the main branch — drafts only reach main when you merge
the weekly drafts pull request. Run:  python -m engine.publish [--dry-run] [--now ISO]
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

from . import state
from .config import calendar
from .github import close_issue, create_issue
from .platforms import instagram, linkedin, youtube
from .post import all_posts

PUBLISHERS = {"linkedin": linkedin, "instagram": instagram, "youtube": youtube}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't call any platform API or write the log")
    ap.add_argument("--now", help="pretend it is this time (ISO 8601)")
    ap.add_argument("--only", help="only this post id, e.g. queue/2026-10-26/linkedin")
    args = ap.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    max_late = timedelta(hours=calendar().get("max_late_hours", 36))
    log = state.load()
    lines, failures = [], 0

    for post in all_posts():
        if args.only and post.id != args.only:
            continue
        entry = log.get(post.id)
        if state.is_done(entry) or not post.scheduled_at or post.scheduled_at > now:
            continue
        if post.errors:
            lines.append(f"⛔ {post.id}: invalid — {'; '.join(post.errors)}")
            if not args.dry_run:
                state.record(post.id, "skipped", reason="; ".join(post.errors))
            continue
        if now - post.scheduled_at > max_late:
            lines.append(f"⌛ {post.id}: expired (scheduled {post.scheduled_at:%d %b %H:%M})")
            if not args.dry_run:
                state.record(post.id, "expired")
            continue

        if post.awaiting_recording():
            src = post.video_spec.get("source")
            lines.append(f"🎥 {post.id}: waiting for recording {src}")
            if not args.dry_run and not (entry or {}).get("reminder_issue"):
                script = post.video_spec.get("script", "").strip()
                num = create_issue(
                    f"🎥 Record today's clip → {src}",
                    f"`{post.id}.yml` is due but its clip isn't in the repo yet.\n\n"
                    f"Record it, upload it to **`{src}`** (GitHub → inbox → Add file → Upload), and it "
                    f"will be captioned and posted on the next run (within {max_late.total_seconds()/3600:.0f}h "
                    f"of the scheduled time).\n\n**Script**\n\n{script or '_no script_'}",
                    ["recording-needed"])
                state.record(post.id, "waiting", reminder_issue=num)
            continue

        if not post.is_rendered():
            lines.append(f"🖼️ {post.id}: media not rendered yet — will retry")
            continue

        try:
            result = PUBLISHERS[post.platform].publish(post, dry_run=args.dry_run)
        except Exception as exc:  # keep going with other posts
            failures += 1
            attempts = (entry or {}).get("attempts", 0) + 1
            msg = f"{type(exc).__name__}: {exc}"
            lines.append(f"❌ {post.id}: attempt {attempts}/{state.MAX_ATTEMPTS} — {msg}")
            traceback.print_exc()
            if not args.dry_run:
                state.record(post.id, "failed", attempts=attempts, error=msg[:800])
                if attempts >= state.MAX_ATTEMPTS:
                    create_issue(f"❌ Couldn't publish {post.id}",
                                 f"Gave up after {attempts} attempts.\n\n```\n{msg}\n```\n\n"
                                 "Fix the cause (often an expired token — see SETUP.md) then delete this "
                                 "post's last lines from `published/log.jsonl` to retry.", ["publish-failed"])
            continue

        icon = "✅" if result.status == "published" else "📲"
        lines.append(f"{icon} {post.id}: {result.status} {result.url or ''} {result.note or ''}".rstrip())
        if not args.dry_run:
            state.record(post.id, result.status, remote_id=result.remote_id, url=result.url,
                         note=result.note, attempts=(entry or {}).get("attempts", 0) + 1)
            if (entry or {}).get("reminder_issue"):
                close_issue(entry["reminder_issue"])

    report = "\n".join(lines) or "Nothing due."
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Publish run {now:%Y-%m-%d %H:%M} UTC\n\n" + "\n".join(f"- {l}" for l in lines or [report]) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
