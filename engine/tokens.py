"""Token upkeep, run weekly by .github/workflows/tokens.yml.

python -m engine.tokens ig-refresh --out new_token.txt
python -m engine.tokens linkedin-check
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import requests

from .config import env
from .github import _headers, available, create_issue, repo_slug
from .platforms.instagram import refresh_token


def _open_issue_once(title: str, body: str, label: str) -> None:
    if available():
        r = requests.get(f"https://api.github.com/repos/{repo_slug()}/issues", headers=_headers(),
                         params={"labels": label, "state": "open"}, timeout=30)
        if r.ok and r.json():
            return
    create_issue(title, body, [label])


def ig_refresh(out: str) -> int:
    token = env("IG_ACCESS_TOKEN")
    if not token:
        print("IG_ACCESS_TOKEN not set; skipping")
        return 0
    new, expires_in = refresh_token(token)
    with open(out, "w") as f:
        f.write(new)
    os.chmod(out, 0o600)
    print(f"Instagram token refreshed; valid for {expires_in // 86400} days")
    return 0


def linkedin_check() -> int:
    token = env("LINKEDIN_ACCESS_TOKEN")
    if not token:
        print("LINKEDIN_ACCESS_TOKEN not set; skipping")
        return 0
    days_left = None
    cid, secret = env("LINKEDIN_CLIENT_ID"), env("LINKEDIN_CLIENT_SECRET")
    if cid and secret:
        r = requests.post("https://www.linkedin.com/oauth/v2/introspectToken", timeout=30,
                          data={"client_id": cid, "client_secret": secret, "token": token})
        if r.ok and r.json().get("active"):
            days_left = (r.json().get("expires_at", 0) - time.time()) / 86400
        elif r.ok:
            days_left = 0
    if days_left is None:
        r = requests.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        days_left = 999 if r.ok else 0
    print(f"LinkedIn token: {'~%d days left' % days_left if days_left < 999 else 'valid'}")
    if days_left <= 10:
        _open_issue_once(
            "🔑 LinkedIn token expires soon — re-authorise (2 min)",
            f"Your LinkedIn access token has about **{max(days_left, 0):.0f} days** left. LinkedIn doesn't "
            "give personal apps refresh tokens, so every ~60 days:\n\n"
            "1. On your laptop run `python tools/auth_linkedin.py`\n"
            "2. Copy the new token into the repo secret `LINKEDIN_ACCESS_TOKEN` "
            "(Settings → Secrets and variables → Actions)\n3. Close this issue.",
            "token-expiring")
    return 0


def facebook_check() -> int:
    from .platforms import facebook
    ok, msg = facebook.check_token()
    print(f"Facebook Page token: {msg}")
    if not ok:
        _open_issue_once("🔑 Facebook Page token stopped working — re-create it (5 min)",
                         f"Mirroring Instagram posts to your Facebook Page is failing:\n\n`{msg}`\n\n"
                         "This happens if you changed your Facebook password or removed the app. Re-run "
                         "`python tools/facebook_page_token.py` and update the FB_PAGE_TOKEN secret, then close this issue.",
                         "token-expiring")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ig-refresh"); a.add_argument("--out", required=True)
    sub.add_parser("linkedin-check")
    sub.add_parser("facebook-check")
    args = ap.parse_args(argv)
    if args.cmd == "ig-refresh":
        return ig_refresh(args.out)
    return facebook_check() if args.cmd == "facebook-check" else linkedin_check()


if __name__ == "__main__":
    sys.exit(main())
