#!/usr/bin/env python3
"""Advisory check for a drafted week: score each Reel's hook and how machine-written each text reads.

  python tools/draftcheck.py queue/2026-11-23 [queue/2026-11-24 ...]

Hook score (tools/draftcheck/hookscore.py): the first spoken line of every Reel/Short. Human score
(tools/draftcheck/detect.py): captions and LinkedIn text. Both are local heuristics, not predictions: use them
to catch greetings, vague hooks, em dashes and stock AI words, then fix the draft. Rewrite anything WEAK/FLAGGED.
The scripts are MIT licensed (see tools/draftcheck/LICENSE.txt).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent / "draftcheck"))
import detect  # noqa: E402
import hookscore  # noqa: E402

LEX = json.loads((Path(__file__).parent / "draftcheck" / "slop.json").read_text())


NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
       "fourteen": 14, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100}


def digits(text: str) -> str:
    """Spoken lines spell numbers out for the voice; the scorer wants to see them as digits."""
    def one(m):
        w = m.group(0).lower().split("-")
        return str(sum(NUM[x] for x in w)) if all(x in NUM for x in w) else m.group(0)
    return re.sub(r"\b[A-Za-z]+(?:-[A-Za-z]+)?\b", one, text)


def hook_of(d: dict) -> str | None:
    v = d.get("video") or {}
    if v.get("script"):
        return str(v["script"]).strip().split(". ")[0].split("\n")[0]
    for s in d.get("slides") or []:
        if (s or {}).get("say"):
            parts = str(s["say"]).strip().split(". ")
            return parts[0] if len(parts[0].split()) >= 6 else ". ".join(parts[:2])
    return None


def main(argv: list[str]) -> int:
    files = []
    for a in argv or ["queue"]:
        p = Path(a)
        files += sorted(p.rglob("*.yml")) if p.is_dir() else [p]
    bad = 0
    for f in files:
        if f.name.startswith("_"):
            continue
        try:
            d = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as ex:
            print(f"{f}\n  YAML error: {str(ex)[:120]}"); bad += 1; continue
        if not isinstance(d, dict) or "platform" not in d:
            continue
        rows = []
        h = hook_of(d) if d.get("format") in {"reel", "short"} else None
        if h:
            _, ov, verdict, flags = hookscore.run(digits(h))
            rows.append(f"hook {ov:4.0f} {verdict:6} {h!r}" + (f"  !! {'; '.join(flags)}" if flags else ""))
            bad += verdict == "WEAK"
        t = d.get("text") or ""
        if len(t.split()) >= 25:
            _, ov, verdict = detect.run(t, LEX)
            rows.append(f"human {ov:3.0f} {verdict}")
            bad += verdict == "FLAGGED"
        if rows:
            print(f"{f}\n  " + "\n  ".join(rows))
    print(f"\n{bad} to rewrite" if bad else "\nall clear")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
