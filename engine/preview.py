"""Build the review comment for a drafts PR: every post with its text, slides, video and checks.

python -m engine.preview --ref <commit-sha> [--out preview.md] [paths...]
Exits 1 if any post has errors, so the PR check goes red.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import repo_slug
from .github import raw_url
from .post import all_posts, load

ICON = {"linkedin": "💼", "instagram": "📸", "youtube": "▶️"}


def render_md(posts, ref: str) -> tuple[str, int]:
    errors = 0
    rows = ["| When (IST) | Platform | Format | App | Pillar | Status |", "|---|---|---|---|---|---|"]
    blocks = []
    for p in posts:
        status = "⛔ errors" if p.errors else ("⚠️ warnings" if p.warnings else "✅")
        if p.awaiting_recording():
            status += " · 🎥 needs recording"
        errors += bool(p.errors)
        when = f"{p.scheduled_at:%a %d %b %H:%M}" if p.scheduled_at else "?"
        rows.append(f"| {when} | {ICON.get(p.platform, '')} {p.platform} | {p.format} | {p.app} | "
                    f"{p.data.get('pillar', '')} | {status} |")

        b = [f"### {ICON.get(p.platform, '')} {when} · {p.platform} {p.format}", f"`{p.id}.yml`", ""]
        if p.data.get("review_note"):
            b.append(f"> 📝 **Check:** {p.data['review_note']}")
        for e in p.errors:
            b.append(f"> ⛔ {e}")
        for w in p.warnings:
            b.append(f"> ⚠️ {w}")
        if p.platform == "youtube":
            yt = p.data.get("youtube") or {}
            b += [f"**Title:** {yt.get('title', '')}", ""]
        if p.text:
            b += ["<details open><summary>Text</summary>", "", "```text", p.text, "```", "</details>", ""]
        if p.data.get("first_comment"):
            b += [f"**First comment:** {p.data['first_comment']}", ""]
        imgs = p.images()
        if imgs and repo_slug():
            b.append(" ".join(f'<img src="{raw_url(i, ref)}" width="180">' for i in imgs))
            b.append("")
        ref_v = p.video_ref()
        spec = p.video_spec
        if ref_v:
            url = ref_v.get("url") or (raw_url(Path(ref_v["local"]), ref) if "local" in ref_v else "")
            b += [f"🎬 **Video:** [watch / download]({url})", ""]
        if spec.get("kind") == "talking_head":
            b += [f"🎥 **Record and upload to `{spec.get('source')}`**", "", "<details><summary>Script</summary>", "",
                  spec.get("script", ""), "", "</details>", ""]
        blocks.append("\n".join(b))

    md = ["## 🗓️ Drafts for review", "",
          "**Merge this PR to approve everything.** To change a post, edit its `.yml` in this PR "
          "(media re-renders automatically). To drop a post, delete its file. Close the PR to reject the week.",
          "", *rows, "", "---", "", "\n\n---\n\n".join(blocks)]
    return "\n".join(md), errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    posts = [load(Path(p)) for p in args.paths if Path(p).exists()] if args.paths else all_posts()
    posts.sort(key=lambda p: (p.scheduled_at.isoformat() if p.scheduled_at else "", p.platform))
    md, errors = render_md(posts, args.ref)
    if len(md) > 64000:  # GitHub comment limit is 65536
        md = md[:63500] + "\n\n…(truncated — see the files in this PR)"
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
