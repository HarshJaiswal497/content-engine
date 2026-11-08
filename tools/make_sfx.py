"""Render the engine's small sound-effect library with earshot (https://github.com/Leonxlnx/earshot).

earshot's film sound bank is pure code: no models, no network, no licences to track. Run this once locally
(`uv tool install "earshot[mcp] @ git+https://github.com/Leonxlnx/earshot"`), commit assets/sfx/*.wav and
brand/sfx.yml. CI never needs earshot; the renderer just reads the committed files."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "sfx"
ROLES = {
    "hit":    ["pro_impact/short", "pro_impact/air", "cut_hit/punch"],              # frame 0 / big reveal
    "whoosh": ["swipe/flick", "whoosh_fast/tight", "swipe/cloth", "whoosh_fast/crisp"],  # scene changes
    "pop":    ["pro_pop_in/airy", "ui_pop/blip", "pro_pop/bloop", "pro_pop_in/round"],     # something appears
    "ping":   ["pro_notify/ding_1930", "pro_notify/ding_2167"],                      # happy / success
    "dun":    ["pro_sub_drop/quick", "pro_sub_drop/soft"],                            # sad / shock
    "tick":   ["pro_typing_key/tick", "pro_hover_tick/soft", "pro_typing_key/soft"], # text arriving
    "tap":    ["pro_tap/finger", "pro_tap/soft"],                                     # a tap on screen
    "riser":  ["pro_riser/roll"],                                                     # build to the payoff
    "sting":  ["pro_logo_sting/taps_tone", "pro_logo_sting/zap_bloom"],             # end card
}
manifest: dict[str, list[dict]] = {}
for role, ids in ROLES.items():
    for i, sid in enumerate(ids):
        name = f"{role}{i}.wav"
        p = subprocess.run(["earshot", "sfx", "render", sid, "-o", str(OUT / name)], capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"{sid}: {p.stderr[-300:]}")
        peak = float(re.search(r"peak at ([\d.]+) s", p.stdout).group(1))
        dur = float(re.search(r": ([\d.]+) s, onset", p.stdout).group(1))
        manifest.setdefault(role, []).append({"file": name, "peak": peak, "dur": dur, "from": sid})
(ROOT / "brand" / "sfx.json").write_text(json.dumps(manifest, indent=1) + "\n")
print({k: len(v) for k, v in manifest.items()})
