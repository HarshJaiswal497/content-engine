"""Generate Slip (the Slipnote paper-note mascot) as SVG poses, plus PNG renders.
Usage: python tools/make_slip.py  -> assets/characters/slip/<pose>.svg and .png (transparent, 600 px wide)."""
from pathlib import Path
import subprocess, sys

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "slip"
PAPER, EDGE, FOLD, BLUSH, INK = "#FDF6E6", "#C9B27E", "#EADBB4", "#F4A9B4", "#3B2F2A"
SW = 7


def eye(cx, cy, px=0, py=0, r=30, shut=None, squint=False):
    if shut == "arc":   # happy closed eye ^
        return f'<path d="M{cx-r+4} {cy+6} Q{cx} {cy-r+2} {cx+r-4} {cy+6}" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
    if shut == "line":  # sleepy
        return f'<path d="M{cx-r+4} {cy+2} Q{cx} {cy+12} {cx+r-4} {cy+2}" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
    s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{EDGE}" stroke-width="4"/>'
    s += f'<circle cx="{cx+px}" cy="{cy+py}" r="{r*0.52:.1f}" fill="{INK}"/>'
    s += f'<circle cx="{cx+px+5}" cy="{cy+py-6}" r="{r*0.17:.1f}" fill="#fff"/>'
    if squint:
        s += f'<path d="M{cx-r} {cy-r*0.15} L{cx+r} {cy-r*0.15} L{cx+r} {cy-r-4} L{cx-r} {cy-r-4} Z" fill="{PAPER}" opacity="0"/>'
    return s


def mouth(kind, cx=150, cy=196):
    m = {
        "tiny": f'<ellipse cx="{cx}" cy="{cy}" rx="5" ry="6" fill="{INK}"/>',
        "smile": f'<path d="M{cx-14} {cy-4} Q{cx} {cy+14} {cx+14} {cy-4}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
        "open": f'<path d="M{cx-17} {cy-6} Q{cx} {cy+30} {cx+17} {cy-6} Z" fill="{INK}"/><path d="M{cx-9} {cy+8} Q{cx} {cy+18} {cx+9} {cy+8} Z" fill="{BLUSH}"/>',
        "o": f'<ellipse cx="{cx}" cy="{cy+2}" rx="9" ry="12" fill="{INK}"/>',
        "sad": f'<path d="M{cx-12} {cy+8} Q{cx} {cy-6} {cx+12} {cy+8}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
        "flat": f'<path d="M{cx-10} {cy} L{cx+10} {cy}" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>',
    }
    return m[kind]


def bump(cx, cy, r=19):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PAPER}" stroke="{EDGE}" stroke-width="{SW}"/>'


BODY = (f'<path d="M62 46 H196 L242 92 V268 Q242 282 228 282 H76 Q62 282 62 268 Z" fill="{PAPER}" stroke="{EDGE}" stroke-width="{SW}" stroke-linejoin="round"/>'
        f'<path d="M196 46 V80 Q196 92 208 92 H242 Z" fill="{FOLD}" stroke="{EDGE}" stroke-width="{SW}" stroke-linejoin="round"/>')
BLUSHES = f'<ellipse cx="96" cy="176" rx="15" ry="9" fill="{BLUSH}" opacity=".85"/><ellipse cx="204" cy="176" rx="15" ry="9" fill="{BLUSH}" opacity=".85"/>'
FEET = lambda dy=0: bump(112, 290 + dy, 18) + bump(188, 290 + dy, 18)

# pose: eyes, mouth, hands (list of (x,y)), extra svg, body transform, feet dy
POSES = {
    "idle":      dict(eyes=(0, 0), mouth="tiny", hands=[(52, 214), (252, 214)]),
    "happy":     dict(eyes="arc", mouth="open", hands=[(48, 150), (256, 150)]),
    "wave":      dict(eyes=(0, 0), mouth="smile", hands=[(52, 214), (262, 112)], extra=f'<path d="M286 86 q10 -8 18 0 M292 66 q12 -4 18 6" stroke="{EDGE}" stroke-width="6" fill="none" stroke-linecap="round"/>', rot=-3),
    "surprised": dict(eyes=(0, 0, 36), mouth="o", hands=[(50, 120), (254, 120)], extra=f'<path d="M30 40 l14 14 M270 40 l-14 14 M150 12 v20" stroke="{EDGE}" stroke-width="7" stroke-linecap="round"/>'),
    "think":     dict(eyes=(-9, -9), mouth="flat", hands=[(52, 214), (206, 226)], extra=f'<circle cx="262" cy="52" r="9" fill="{FOLD}" stroke="{EDGE}" stroke-width="4"/><circle cx="280" cy="24" r="14" fill="{FOLD}" stroke="{EDGE}" stroke-width="4"/>'),
    "write":     dict(eyes=(0, 10), mouth="smile", hands=[(52, 214), (178, 262)], extra='<g transform="rotate(35 196 266)"><rect x="190" y="206" width="16" height="64" rx="3" fill="#203C96"/><path d="M190 270 L198 292 L206 270 Z" fill="#203C96"/></g><path d="M96 252 q20 -14 40 0 t40 0" fill="none" stroke="#203C96" stroke-width="6" stroke-linecap="round"/>'),
    "sleepy":    dict(eyes="line", mouth="tiny", hands=[(52, 224), (252, 224)], extra=f'<text x="244" y="48" font-family="Caveat, cursive" font-size="40" font-weight="700" fill="{EDGE}">z</text><text x="270" y="18" font-family="Caveat, cursive" font-size="30" font-weight="700" fill="{EDGE}">z</text>', rot=4),
    "sad":       dict(eyes=(0, 8, 32), mouth="sad", hands=[(60, 240), (244, 240)], extra=f'<path d="M92 214 q-6 18 0 26 q8 -8 0 -26 Z" fill="#8CC8F0"/>'),
    "peek":      dict(eyes=(8, 6), mouth="tiny", hands=[(86, 70), (214, 70)], clip=True),
    "cheer":     dict(eyes="arc", mouth="open", hands=[(40, 60), (264, 60)], extra=f'<g fill="#F3C65D"><path d="M20 130 l6 12 12 6 -12 6 -6 12 -6 -12 -12 -6 12 -6z"/><path d="M286 160 l5 10 10 5 -10 5 -5 10 -5 -10 -10 -5 10 -5z"/></g>', feet=-8, rot=-2),
}


def build(name, p):
    eyes = p["eyes"]
    if isinstance(eyes, str):
        e = eye(112, 138, shut=eyes) + eye(188, 138, shut=eyes)
    else:
        r = eyes[2] if len(eyes) > 2 else 30
        e = eye(112, 138, eyes[0], eyes[1], r) + eye(188, 138, eyes[0], eyes[1], r)
    hands = "".join(bump(x, y) for x, y in p["hands"])
    rot = p.get("rot", 0)
    inner = (f'<g transform="rotate({rot} 150 200)">' + FEET(p.get("feet", 0)) + BODY + BLUSHES + e + mouth(p["mouth"]) + hands + "</g>" + p.get("extra", ""))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 340" width="320" height="340">{inner}</svg>\n'


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, p in POSES.items():
        (OUT / f"{n}.svg").write_text(build(n, p))
    from PIL import Image  # noqa
    import io
    try:
        import cairosvg
        for n in POSES:
            cairosvg.svg2png(url=str(OUT / f"{n}.svg"), write_to=str(OUT / f"{n}.png"), output_width=600)
    except ImportError:
        print("cairosvg missing; SVGs only", file=sys.stderr)
    print("poses:", ", ".join(POSES))
