"""Append-only publish log at published/log.jsonl. The latest entry per post id wins."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import LOG

FINAL = {"published", "handoff", "expired", "skipped"}
MAX_ATTEMPTS = 3


def load() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                prev = latest.get(entry["id"], {})
                entry.setdefault("attempts", prev.get("attempts", 0))
                entry.setdefault("reminder_issue", prev.get("reminder_issue"))
                latest[entry["id"]] = entry
    return latest


def record(post_id: str, status: str, **fields) -> dict:
    entry = {"id": post_id, "status": status, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def is_done(entry: dict | None) -> bool:
    if not entry:
        return False
    if entry["status"] in FINAL:
        return True
    return entry["status"] == "failed" and entry.get("attempts", 0) >= MAX_ATTEMPTS
