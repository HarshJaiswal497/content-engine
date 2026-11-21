"""Generate Bo (the Setalytix dumbbell mascot) as SVG poses, plus PNG renders. Same drawing style as Slip.
Usage: python tools/make_bo.py && python tools/render_svgs.py assets/characters/bo   (transparent PNGs, 600 px wide)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_slip as S

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "bo"
PLATE, PEDGE, SHADE, GRIP, GEDGE = "#F7C948", "#B8860B", "#EBB230", "#B9B4D6", "#6F69A0"
INK, BLUSH = S.INK, S.BLUSH
SW = 7

HEAD = (f'<rect x="64" y="10" width="192" height="122" rx="40" fill="{PLATE}" stroke="{PEDGE}" stroke-width="{SW}"/>'
        f'<path d="M92 26 Q150 18 214 26" stroke="#FFE69A" stroke-width="9" stroke-linecap="round" fill="none"/>')
HANDLE = (f'<rect x="140" y="128" width="40" height="100" rx="8" fill="{GRIP}" stroke="{GEDGE}" stroke-width="{SW}"/>'
          f'<path d="M148 164 H172 M148 176 H172 M148 188 H172" stroke="{GEDGE}" stroke-width="5" stroke-linecap="round" opacity=".7"/>'
          f'<rect x="116" y="122" width="88" height="18" rx="7" fill="{GRIP}" stroke="{GEDGE}" stroke-width="6"/>'
          f'<rect x="116" y="216" width="88" height="18" rx="7" fill="{GRIP}" stroke="{GEDGE}" stroke-width="6"/>')
BASE = (f'<rect x="64" y="228" width="192" height="106" rx="38" fill="{SHADE}" stroke="{PEDGE}" stroke-width="{SW}"/>'
        f'<text x="160" y="300" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="56" font-weight="900" fill="{PEDGE}">20</text>')
BLUSHES = f'<ellipse cx="94" cy="92" rx="14" ry="8" fill="{BLUSH}" opacity=".9"/><ellipse cx="206" cy="92" rx="14" ry="8" fill="{BLUSH}" opacity=".9"/>'


def hand(cx, cy, r=18):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PLATE}" stroke="{PEDGE}" stroke-width="{SW}"/>'


def feet(dy=0):
    return ""


POSES = {
    "idle":      dict(eyes=(0, 0), mouth="tiny", hands=[(110, 178), (210, 178)]),
    "happy":     dict(eyes="arc", mouth="open", hands=[(60, 150), (260, 150)]),
    "wave":      dict(eyes=(0, 0), mouth="smile", hands=[(110, 182), (270, 112)], extra=f'<path d="M290 96 q10 -8 18 0 M296 76 q12 -4 18 6" stroke="{PEDGE}" stroke-width="6" fill="none" stroke-linecap="round"/>', rot=-3),
    "flex":      dict(eyes="arc", mouth="open", hands=[(56, 110), (264, 110)], extra=f'<path d="M24 80 l12 -12 M296 80 l-12 -12 M160 4 v14" stroke="{PEDGE}" stroke-width="7" stroke-linecap="round"/>'),
    "surprised": dict(eyes=(0, 0, 33), mouth="o", hands=[(84, 168), (236, 168)], extra=f'<path d="M30 40 l14 14 M290 40 l-14 14" stroke="{PEDGE}" stroke-width="7" stroke-linecap="round"/>'),
    "think":     dict(eyes=(-9, -9), mouth="flat", hands=[(110, 182), (190, 196)], extra=f'<circle cx="282" cy="56" r="9" fill="{SHADE}" stroke="{PEDGE}" stroke-width="4"/><circle cx="298" cy="26" r="14" fill="{SHADE}" stroke="{PEDGE}" stroke-width="4"/>'),
    "tick":      dict(eyes=(4, 4), mouth="smile", hands=[(110, 182), (214, 186)], extra=f'<g transform="translate(214 150)"><rect x="0" y="0" width="64" height="64" rx="14" fill="#fff" stroke="{PEDGE}" stroke-width="6"/><path d="M14 34 L28 48 L52 16" fill="none" stroke="#2FA86B" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></g>'),
    "sleepy":    dict(eyes="line", mouth="tiny", hands=[(110, 196), (210, 196)], extra=f'<text x="262" y="40" font-family="Caveat, cursive" font-size="40" font-weight="700" fill="{PEDGE}">z</text><text x="290" y="16" font-family="Caveat, cursive" font-size="30" font-weight="700" fill="{PEDGE}">z</text>', rot=3),
    "sad":       dict(eyes=(0, 8, 31), mouth="sad", hands=[(110, 204), (210, 204)], extra='<path d="M88 88 q-6 18 0 26 q8 -8 0 -26 Z" fill="#8CC8F0"/>'),
    "cheer":     dict(eyes="arc", mouth="open", hands=[(50, 50), (270, 50)], extra='<g fill="#fff"><path d="M18 130 l6 12 12 6 -12 6 -6 12 -6 -12 -12 -6 12 -6z"/><path d="M296 160 l5 10 10 5 -10 5 -5 10 -5 -10 -10 -5 10 -5z"/></g>', feet=-8, rot=-2),
}


def build(p):
    eyes = p["eyes"]
    if isinstance(eyes, str):
        e = S.eye(112, 62, shut=eyes) + S.eye(188, 62, shut=eyes)
    else:
        r = eyes[2] if len(eyes) > 2 else 25
        e = S.eye(112, 62, eyes[0], eyes[1], r) + S.eye(188, 62, eyes[0], eyes[1], r)
    hands = "".join(hand(x, y) for x, y in p["hands"])
    inner = (f'<g transform="rotate({p.get("rot", 0)} 160 200)">' + feet(p.get("feet", 0)) + BASE + HANDLE + HEAD + BLUSHES + e
             + S.mouth(p["mouth"], 150, 104) + hands + "</g>" + p.get("extra", ""))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 340" width="320" height="340">{inner}</svg>\n'


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, p in POSES.items():
        (OUT / f"{n}.svg").write_text(build(p))
        for k, m in enumerate(S.LIP):    # talking frames for lip-sync
            (OUT / f"{n}-m{k}.svg").write_text(build({**p, "mouth": m}))
    print("wrote", len(POSES), "poses to", OUT)
