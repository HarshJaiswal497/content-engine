"""Generate the skit human (Harsh-style: curly hair, glasses, cream shirt with maroon sleeves) as SVG poses.
Usage: python tools/make_human.py && python tools/render_svgs.py assets/characters/human"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "human"
SKIN, HAIR, SHIRT, SLEEVE, INK, LINE = "#E8B48A", "#2A211E", "#F6EDDA", "#7A2A33", "#2B211D", "#B99A6B"


def brows(kind):
    return {"neutral": f'<path d="M108 112 q14 -8 28 0 M184 112 q14 -8 28 0"',
            "up": f'<path d="M106 96 q14 -12 30 -2 M184 94 q16 -10 30 2"',
            "sad": f'<path d="M108 108 q14 -2 28 -12 M212 108 q-14 -2 -28 -12"',
            "down": f'<path d="M108 100 q14 8 30 8 M212 100 q-14 8 -30 8"'}[kind] + f' fill="none" stroke="{HAIR}" stroke-width="7" stroke-linecap="round"/>'


def mouth(kind):
    return {"smile": f'<path d="M136 188 Q160 212 184 188" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>',
            "talk": f'<path d="M138 186 Q160 224 182 186 Z" fill="{INK}"/><path d="M148 204 Q160 214 172 204 Z" fill="#E88A94"/>',
            "o": f'<ellipse cx="160" cy="196" rx="13" ry="17" fill="{INK}"/>',
            "sad": f'<path d="M138 200 Q160 180 182 200" fill="none" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>',
            "flat": f'<path d="M142 194 H178" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>'}[kind]


def person(brow, mth, eyes=(0, 0), arms="down", extra="", big=False):
    r = 17 if big else 12
    glasses = "".join(f'<circle cx="{cx}" cy="144" r="30" fill="#fff" fill-opacity=".55" stroke="{INK}" stroke-width="6"/>'
                      f'<circle cx="{cx+eyes[0]}" cy="{144+eyes[1]}" r="{r}" fill="{INK}"/><circle cx="{cx+eyes[0]+4}" cy="{144+eyes[1]-5}" r="4" fill="#fff"/>' for cx in (122, 198))
    glasses += f'<path d="M152 142 H168" stroke="{INK}" stroke-width="6"/>'
    arm_svg = {
        "down": f'<path d="M92 300 Q60 340 66 420" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><path d="M228 300 Q260 340 254 420" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><circle cx="66" cy="432" r="22" fill="{SKIN}"/><circle cx="254" cy="432" r="22" fill="{SKIN}"/>',
        "up": f'<path d="M92 300 Q40 260 40 190" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><path d="M228 300 Q280 260 280 190" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><circle cx="40" cy="170" r="22" fill="{SKIN}"/><circle cx="280" cy="170" r="22" fill="{SKIN}"/>',
        "phone": f'<path d="M92 300 Q60 340 66 420" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><circle cx="66" cy="432" r="22" fill="{SKIN}"/><path d="M228 300 Q270 330 214 350" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><rect x="190" y="290" width="62" height="104" rx="10" fill="#1d1d24" stroke="#555" stroke-width="4" transform="rotate(-10 220 340)"/><rect x="196" y="298" width="50" height="88" rx="6" fill="#FFD84D" transform="rotate(-10 220 340)"/><circle cx="214" cy="352" r="20" fill="{SKIN}"/>',
        "head": f'<path d="M92 300 Q60 340 66 420" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><circle cx="66" cy="432" r="22" fill="{SKIN}"/><path d="M228 300 Q286 250 232 176" stroke="{SLEEVE}" stroke-width="44" fill="none" stroke-linecap="round"/><circle cx="226" cy="166" r="22" fill="{SKIN}"/>',
    }[arms]
    hair = "".join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{HAIR}"/>' for x, y, rr in
                   [(100, 84, 30), (132, 62, 34), (170, 56, 34), (206, 66, 34), (232, 92, 30), (96, 122, 22), (232, 124, 22)])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 460" width="320" height="460">'
            f'<rect x="80" y="262" width="160" height="200" rx="40" fill="{SHIRT}" stroke="{LINE}" stroke-width="5"/>'
            f'<rect x="146" y="226" width="28" height="44" fill="{SKIN}"/>'
            f'{arm_svg}{hair}'
            f'<ellipse cx="160" cy="150" rx="76" ry="84" fill="{SKIN}"/>'
            f'<ellipse cx="86" cy="156" rx="12" ry="20" fill="{SKIN}"/><ellipse cx="234" cy="156" rx="12" ry="20" fill="{SKIN}"/>'
            f'{hair.split("<circle")[1] and "".join(f"<circle cx=%d cy=%d r=%d fill=%s />" % (x, y, rr, chr(34)+HAIR+chr(34)) for x, y, rr in [(112, 80, 26), (150, 66, 30), (190, 68, 30), (222, 86, 26)])}'
            f'{glasses}{brows(brow)}{mouth(mth)}{extra}</svg>\n')


POSES = {
    "idle": person("neutral", "smile"),
    "talk": person("neutral", "talk"),
    "shocked": person("up", "o", big=True, arms="up"),
    "happy": person("up", "smile", arms="up"),
    "sad": person("sad", "sad", eyes=(0, 6)),
    "phone": person("neutral", "flat", eyes=(10, 14), arms="phone"),
    "think": person("down", "flat", eyes=(-10, -10), arms="head"),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, s in POSES.items():
        s = s.replace('width="320" height="460"', 'width="320" height="460"')
        (OUT / f"{n}.svg").write_text(s)
    print("poses:", ", ".join(POSES))
