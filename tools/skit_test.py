"""One-off: render hf/skit/example.yml with real voices (run in CI). Usage: python tools/skit_test.py <out.mp4>"""
import sys
from pathlib import Path
import yaml
from engine.render.video import skit_video

spec = yaml.safe_load((Path(__file__).resolve().parent.parent / "hf" / "skit" / "example.yml").read_text())["video"]
out = Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True)
skit_video(spec["beats"], "slipnote", out, spec.get("tone"))
print("done", out.stat().st_size)
