from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
INBOX = ROOT / "inbox"
BRAND = ROOT / "brand"
FONTS = ROOT / "assets" / "fonts"
LOG = ROOT / "published" / "log.jsonl"


def calendar() -> dict:
    with open(BRAND / "calendar.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


TZ = ZoneInfo(calendar().get("timezone", "Asia/Kolkata"))


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required secret/env: {name}")
    return val


def repo_slug() -> str | None:
    """owner/repo when running in GitHub Actions."""
    return os.environ.get("GITHUB_REPOSITORY")
