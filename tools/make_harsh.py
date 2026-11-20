"""Generate the cartoon Harsh (curly hair, clear glasses, beard, black tee) as SVG poses plus PNG renders, same drawing
style as Slip and Bo. Talking frames <pose>-m0|1|2 (shut, half, wide open) for lip-sync.
Usage: python tools/make_harsh.py  -> assets/characters/harsh/<pose>.svg / .png (transparent, 600 px wide)."""
from pathlib import Path
import math, sys

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "harsh"
SKIN, SEDGE, HAIR, HEDGE = "#E0AA7E", "#8A5733", "#3A2A24", "#1A100D"
TEE, TEDGE, GLASS, INK, BLUSH = "#2D2D36", "#14141A", "#93A8C0", "#2A1B16", "#E0795F"
SW = 7
LIP = ["tiny", "mid", "open"]


def curls(cx, cy, rx, ry, a0, a1, n, r):
    out = []
    for k in range(n):
        a = math.radians(a0 + (a1 - a0) * k / (n - 1))
        out.append((cx + rx * math.cos(a), cy + ry * math.sin(a), r))
    return out


def blob(cs):
    s = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{HAIR}" stroke="{HEDGE}" stroke-width="{SW}"/>' for x, y, r in cs)
    return s + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r - 2}" fill="{HAIR}"/>' for x, y, r in cs)


def _lock(d):
    return f'<path d="{d}" fill="{HAIR}" stroke="{HEDGE}" stroke-width="{SW}" stroke-linejoin="round"/>' + f'<path d="{d}" fill="{HAIR}"/>'


HAIR_BACK = (
    # side and back lengths down to the jaw, flicking out at the ends
    _lock("M92 70 Q62 110 68 190 Q70 210 86 206 Q96 160 104 112 Z")
    + _lock("M228 70 Q258 110 252 190 Q250 210 234 206 Q224 160 216 112 Z")
    + blob([(66, 204, 14), (52, 194, 10), (254, 204, 14), (268, 194, 10)])
    + blob(curls(160, 94, 78, 70, 168, 372, 11, 26) + [(80, 60, 22), (240, 58, 22), (120, 22, 22), (160, 14, 24), (204, 22, 22)])
)
HAIR_FRONT = (
    # layered wolf fringe: wispy pieces sweeping across the forehead, tips curling
    _lock("M104 50 Q90 80 106 90 Q122 80 134 54 Z")
    + _lock("M128 44 Q116 74 134 84 Q150 74 156 46 Z")
    + _lock("M152 44 Q150 72 168 80 Q184 68 184 44 Z")
    + _lock("M178 46 Q186 74 204 80 Q220 70 216 50 Z")
    + _lock("M206 54 Q214 80 228 86 Q240 72 232 58 Z")
)


def eye(cx, cy, px=0, py=0, shut=None, r=13):
    if shut == "arc":
        return f'<path d="M{cx-r} {cy+3} Q{cx} {cy-r-2} {cx+r} {cy+3}" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r+1}" fill="#fff"/><circle cx="{cx+px}" cy="{cy+py}" r="{r*.55:.1f}" fill="{INK}"/>'
            f'<circle cx="{cx+px+2}" cy="{cy+py-2}" r="2.4" fill="#fff"/>')


def glasses():
    def lens(x):
        return (f'<rect x="{x}" y="104" width="56" height="46" rx="14" fill="#FFFFFF" fill-opacity=".07" stroke="#8A97A6" stroke-width="9"/>'
                f'<rect x="{x}" y="104" width="56" height="46" rx="14" fill="none" stroke="#FFFFFF" stroke-width="5.5"/>'
                f'<path d="M{x+10} {106+34} L{x+26} {106+10}" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".55"/>')
    return (lens(96) + lens(168) + f'<path d="M152 122 H168" stroke="#8A97A6" stroke-width="8"/><path d="M152 122 H168" stroke="#fff" stroke-width="4.5"/>')


def brows(kind):
    y = {"up": 94, "flat": 100, "sad": 98}.get(kind, 98)
    if kind == "sad":
        return (f'<path d="M100 {y+6} L146 {y-4}" stroke="{HEDGE}" stroke-width="7" stroke-linecap="round"/>'
                f'<path d="M220 {y+6} L174 {y-4}" stroke="{HEDGE}" stroke-width="7" stroke-linecap="round"/>')
    return (f'<path d="M100 {y} Q124 {y-9} 148 {y}" fill="none" stroke="{HEDGE}" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M172 {y} Q196 {y-9} 220 {y}" fill="none" stroke="{HEDGE}" stroke-width="7" stroke-linecap="round"/>')


def mouth(kind, cx=160, cy=204):
    m = {
        "tiny": f'<path d="M{cx-15} {cy-2} Q{cx} {cy+10} {cx+15} {cy-2}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
        "mid": f'<path d="M{cx-17} {cy-3} Q{cx} {cy+19} {cx+17} {cy-3} Z" fill="{INK}"/><path d="M{cx-14} {cy-2} H{cx+14} V{cy+3} H{cx-14} Z" fill="#fff"/>',
        "open": (f'<path d="M{cx-20} {cy-4} Q{cx} {cy+34} {cx+20} {cy-4} Z" fill="{INK}"/>'
                 f'<path d="M{cx-17} {cy-3} H{cx+17} V{cy+4} H{cx-17} Z" fill="#fff"/>'
                 f'<path d="M{cx-10} {cy+16} Q{cx} {cy+8} {cx+10} {cy+16} Q{cx} {cy+26} {cx-10} {cy+16} Z" fill="{BLUSH}"/>'),
        "smile": f'<path d="M{cx-18} {cy-3} Q{cx} {cy+16} {cx+18} {cy-3}" fill="none" stroke="{INK}" stroke-width="5.5" stroke-linecap="round"/>',
        "o": f'<ellipse cx="{cx}" cy="{cy+4}" rx="10" ry="13" fill="{INK}"/>',
        "flat": f'<path d="M{cx-12} {cy+2} H{cx+12}" stroke="{INK}" stroke-width="5.5" stroke-linecap="round"/>',
        "sad": f'<path d="M{cx-14} {cy+8} Q{cx} {cy-4} {cx+14} {cy+8}" fill="none" stroke="{INK}" stroke-width="5.5" stroke-linecap="round"/>',
    }
    return m[kind]


def _strands(pts):
    return "".join(f'<path d="M{x} {y} l{dx} {dy}" stroke="#5B433A" stroke-width="2.6" stroke-linecap="round" opacity=".8"/>' for x, y, dx, dy in pts)


BEARD = (
    # fuller jaw-and-chin beard, joined to the sideburns
    f'<path d="M90 146 Q90 224 160 240 Q230 224 230 146 Q220 160 212 172 Q196 212 160 216 Q124 212 108 172 Q100 160 90 146 Z" fill="{HAIR}" stroke="{HEDGE}" stroke-width="{SW}" stroke-linejoin="round"/>'
    + _strands([(104, 190, 4, 10), (116, 206, 4, 10), (132, 222, 3, 11), (150, 232, 1, 10), (170, 232, -1, 10), (188, 222, -3, 11), (204, 206, -4, 10), (216, 190, -4, 10), (96, 168, 3, 12), (224, 168, -3, 12)])
    # moustache angled down and out, pointed ends, strand detail
    + f'<path d="M160 176 Q146 168 128 172 Q112 176 106 196 Q126 188 144 188 Q154 188 160 184 Q166 188 176 188 Q194 188 214 196 Q208 176 192 172 Q174 168 160 176 Z" fill="{HAIR}" stroke="{HEDGE}" stroke-width="4" stroke-linejoin="round"/>'
    + _strands([(150, 176, -8, 6), (138, 178, -8, 7), (126, 182, -7, 8), (170, 176, 8, 6), (182, 178, 8, 7), (194, 182, 7, 8)])
)
STACHE_PATCH = ''
LIPS = f'<ellipse cx="160" cy="204" rx="26" ry="14" fill="{SKIN}"/>'
FACE = f'<ellipse cx="160" cy="138" rx="74" ry="80" fill="{SKIN}" stroke="{SEDGE}" stroke-width="{SW}"/>'
EARS = (f'<ellipse cx="86" cy="140" rx="11" ry="17" fill="{SKIN}" stroke="{SEDGE}" stroke-width="5"/>'
        f'<ellipse cx="234" cy="140" rx="11" ry="17" fill="{SKIN}" stroke="{SEDGE}" stroke-width="5"/>')
NECK = f'<rect x="132" y="210" width="56" height="40" fill="{SKIN}" stroke="{SEDGE}" stroke-width="{SW}"/>'
TORSO = (f'<path d="M46 340 Q46 262 112 244 Q160 262 208 244 Q274 262 274 340 Z" fill="{TEE}" stroke="{TEDGE}" '
         f'stroke-width="{SW}" stroke-linejoin="round"/>')


def arm(sx, sy, hx, hy):
    return (f'<path d="M{sx} {sy} L{hx} {hy}" stroke="{TEDGE}" stroke-width="40" stroke-linecap="round"/>'
            f'<path d="M{sx} {sy} L{hx} {hy}" stroke="{TEE}" stroke-width="30" stroke-linecap="round"/>'
            f'<circle cx="{hx}" cy="{hy}" r="19" fill="{SKIN}" stroke="{SEDGE}" stroke-width="{SW}"/>')


POSES = {
    "idle":      dict(eyes=(0, 0), brow="flat", mouth="tiny", arms=[((64, 290), (58, 326)), ((256, 290), (262, 326))]),
    "happy":     dict(eyes="arc", brow="up", mouth="open", arms=[((64, 286), (40, 232)), ((256, 286), (280, 232))]),
    "wave":      dict(eyes=(0, 0), brow="up", mouth="smile", arms=[((64, 290), (58, 326)), ((256, 286), (284, 216))],
                      extra=f'<path d="M300 196 q8 -8 16 0 M302 176 q12 -4 16 6" stroke="{SEDGE}" stroke-width="6" fill="none" stroke-linecap="round"/>', rot=-2),
    "surprised": dict(eyes=(0, 0, 14), brow="up", mouth="o", arms=[((64, 286), (36, 230)), ((256, 286), (284, 230))]),
    "think":     dict(eyes=(-6, -6), brow="flat", mouth="flat", arms=[((64, 290), (58, 326)), ((256, 286), (210, 252))],
                      extra=f'<circle cx="284" cy="52" r="9" fill="#fff" stroke="{GLASS}" stroke-width="4"/><circle cx="300" cy="24" r="14" fill="#fff" stroke="{GLASS}" stroke-width="4"/>'),
    "cheer":     dict(eyes="arc", brow="up", mouth="open", arms=[((64, 280), (34, 190)), ((256, 280), (286, 190))],
                      extra='<g fill="#F3C65D"><path d="M16 120 l6 12 12 6 -12 6 -6 12 -6 -12 -12 -6 12 -6z"/><path d="M296 128 l5 10 10 5 -10 5 -5 10 -5 -10 -10 -5 10 -5z"/></g>', rot=-1),
    "sad":       dict(eyes=(0, 6), brow="sad", mouth="sad", arms=[((64, 290), (66, 330)), ((256, 290), (254, 330))]),
}


def build(p):
    eyes = p["eyes"]
    if isinstance(eyes, str):
        e = eye(124, 127, shut=eyes) + eye(196, 127, shut=eyes)
    else:
        r = eyes[2] if len(eyes) > 2 else 13
        e = eye(124, 127, eyes[0], eyes[1], r=r) + eye(196, 127, eyes[0], eyes[1], r=r)
    arms = "".join(arm(*a, *b) for a, b in p["arms"])
    inner = (f'<g transform="rotate({p.get("rot", 0)} 160 250)">' + HAIR_BACK + TORSO + NECK + EARS + FACE + BEARD + LIPS
             + f'<ellipse cx="104" cy="170" rx="13" ry="8" fill="{BLUSH}" opacity=".45"/><ellipse cx="216" cy="170" rx="13" ry="8" fill="{BLUSH}" opacity=".45"/>' + glasses() + e + brows(p["brow"]) + mouth(p["mouth"]) + HAIR_FRONT + arms + "</g>" + p.get("extra", ""))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 340" width="320" height="340">{inner}</svg>\n'


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, p in POSES.items():
        for name, q in [(n, p)] + [(f"{n}-m{k}", {**p, "mouth": m}) for k, m in enumerate(LIP)]:
            (OUT / f"{name}.svg").write_text(build(q))
    print("now: python tools/render_svgs.py assets/characters/harsh")
    print("poses:", ", ".join(POSES))
