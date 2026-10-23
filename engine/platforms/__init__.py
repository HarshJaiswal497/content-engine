from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Result:
    status: str              # "published" | "handoff"
    remote_id: str | None = None
    url: str | None = None
    note: str | None = None


class PublishError(RuntimeError):
    pass
