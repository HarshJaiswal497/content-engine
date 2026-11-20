"""Thumbnail maker: you (sticker cutout), a huge headline with one highlighted word, a real app screen, a mascot.

    python tools/make_thumb.py spec.yml out.png
    python tools/make_thumb.py --demo out_dir          # three sample thumbnails

spec.yml:
    size: reel            # reel = 1080x1920 (Instagram cover, key content inside the middle 1080x1350)
                          # yt = 1280x720 (YouTube)
    app: slipnote         # colours: slipnote | setalytix | personal
    layout: scene         # scene (you at your desk, the default and the house style) | face (sticker cut-out, not used)
    words: [Nobody likes, "*UGLY*", themes]     # one *highlighted* word; one line per entry
    pose: surprised       # a file in assets/people/harsh/ (without -sticker.png): surprised, shocked, thinking, ...
    side: left            # which side you stand on (face layout)
    screen: slipnote/theme-fridge               # optional real app screen (brand/screens.yml)
    mascot: slip:happy    # optional: slip|bo:<pose>
    kicker: build in public                      # optional small script line
Render needs playwright + chromium."""
from __future__ import annotations

import base64
import html
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
THEMES = {
    "slipnote": {"bg": "#FFFBF1", "ink": "#1C1B2E", "accent": "#1F3A93", "hl": "#E5353B", "hl_text": "#FFFFFF", "grid": "rgba(31,58,147,.10)"},
    "setalytix": {"bg": "#1D1147", "ink": "#FFFFFF", "accent": "#FFD23F", "hl": "#FFD23F", "hl_text": "#1D1147", "grid": "rgba(255,255,255,.09)"},
    "personal": {"bg": "#101827", "ink": "#F8FAFC", "accent": "#7DD3FC", "hl": "#7DD3FC", "hl_text": "#0B1220", "grid": "rgba(255,255,255,.07)"},
}
SIZES = {"reel": (1080, 1920), "yt": (1280, 720)}


def _uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def _screen_png(ref: str, app: str) -> Path:
    owner, slug = ref.split("/", 1) if "/" in ref else (app, ref)
    p = ROOT / "assets" / "screens" / owner / f"{slug}.png"
    if not p.exists():
        raise SystemExit(f"unknown screen {ref}")
    return p


def build_html(spec: dict) -> tuple[str, int, int]:
    app = spec.get("app", "slipnote")
    t = THEMES[app]
    w, h = SIZES[spec.get("size", "reel")]
    land = w > h
    layout = spec.get("layout", "scene")
    side = spec.get("side", "left")
    words = spec.get("words") or []
    lines = []
    for ln in words:
        m = re.fullmatch(r"\*(.+)\*", str(ln).strip())
        lines.append(f'<div class="ln hl"><span>{html.escape(m.group(1))}</span></div>' if m
                     else f'<div class="ln"><span>{html.escape(str(ln))}</span></div>')
    person = ""
    scene = spec.get("scene", "working-on-laptop-3")
    if layout == "scene":
        sp = ROOT / "assets" / "people" / "harsh" / "scenes" / f"{scene}.png"
        if not sp.exists():
            raise SystemExit(f"no such scene {sp.name} (tools/make_scenes.py makes them)")
        pos = spec.get("scene_pos", "30% 50%")
        person = f'<img class="scenebg" src="{_uri(sp)}" style="object-position:{pos}">'
    if layout == "face":
        p = ROOT / "assets" / "people" / "harsh" / f"{spec.get('pose', 'normal')}-sticker.png"
        if not p.exists():
            raise SystemExit(f"no such pose {p.name}")
        person = f'<img class="person" src="{_uri(p)}">'
    scr = ""
    if spec.get("screen"):
        scr = (f'<div class="phone"><div class="scr"><img src="{_uri(_screen_png(spec["screen"], app))}"></div></div>')
    mas = ""
    if spec.get("mascot"):
        who, _, pose = str(spec["mascot"]).partition(":")
        mp = ROOT / "assets" / "characters" / who / f"{pose or 'idle'}.png"
        mas = f'<img class="mascot {"big" if layout == "mascot" else ""}" src="{_uri(mp)}">'
    kicker = f'<div class="kicker"><span>{html.escape(spec["kicker"])}</span></div>' if spec.get("kicker") else ""
    font = _uri_font()
    # sizes per orientation
    if land:
        css_pos = f"""
        .words {{ left: 50px; top: 70px; width: {w * 0.58:.0f}px; }}
        .ln {{ font-size: 150px; }}
        .person {{ height: 690px; bottom: -30px; {side if side != 'left' else 'right'}: -10px; }}
        .phone {{ width: 250px; height: 540px; {'left' if side != 'left' else 'right'}: {w * 0.36:.0f}px; bottom: 60px; transform: rotate(-6deg); }}
        .mascot {{ width: 190px; left: 40px; bottom: 30px; }}
        .mascot.big {{ width: 480px; right: 60px; bottom: 20px; left: auto; }}
        .kicker {{ left: 56px; bottom: 54px; font-size: 44px; }}
        """
        if layout == "mascot":
            css_pos += ".phone { right: 60px; left: auto; bottom: 40px; }"
        if layout == "scene":
            css_pos += ".mascot { left: 560px; bottom: 24px; width: 170px; } .kicker { left: 56px; }"
    else:
        css_pos = f"""
        .words {{ left: 50px; right: 50px; top: 230px; }}
        .ln {{ font-size: {150 if layout == 'scene' else 176}px; }}
        .person {{ height: 960px; bottom: 270px; {'left' if side == 'left' else 'right'}: -40px; }}
        .phone {{ width: 330px; height: 710px; {'right' if side == 'left' else 'left'}: 34px; bottom: 330px; transform: rotate(7deg); }}
        .mascot {{ width: 250px; {'right' if side == 'left' else 'left'}: 60px; top: 1500px; }}
        .mascot.big {{ width: 620px; left: 230px; bottom: 300px; top: auto; right: auto; }}
        .kicker {{ left: 0; right: 0; text-align: center; bottom: 190px; font-size: 58px; }}
        """
    page = f"""<!doctype html><meta charset=utf-8><body class="{'sc' if layout == 'scene' else ''}"><style>
    @font-face {{ font-family: TF; src: url({font}); font-weight: 800; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ width: {w}px; height: {h}px; overflow: hidden; background: {'#0c0c14' if layout == 'scene' else t['bg']}; font-family: TF, Inter, sans-serif; }}
    .bg {{ position: absolute; inset: 0; background-image: linear-gradient({t['grid']} 2px, transparent 2px), linear-gradient(90deg, {t['grid']} 2px, transparent 2px); background-size: 64px 64px; }}
    .glow {{ position: absolute; width: {w * 0.9:.0f}px; height: {w * 0.9:.0f}px; border-radius: 50%; left: {w * 0.05:.0f}px; top: {h * 0.3:.0f}px; background: radial-gradient(circle, {t['accent']}33, transparent 66%); }}
    .words {{ position: absolute; z-index: 5; }}
    .ln {{ font-weight: 800; line-height: .98; letter-spacing: -.02em; text-transform: uppercase; margin-bottom: 8px; color: {t['accent']}; }}
    .ln span {{ display: inline-block; -webkit-text-stroke: 16px #fff; paint-order: stroke fill; filter: drop-shadow(0 10px 0 rgba(0,0,0,.22)); padding: 0 6px; }}
    .ln.hl span {{ color: {t['hl_text']}; background: {t['hl']}; -webkit-text-stroke: 0; filter: drop-shadow(0 10px 0 rgba(0,0,0,.25)); padding: 0 26px 10px; border-radius: 16px; transform: rotate(-2deg); }}
    .sc, .sc html {{ background: #0c0c14; }}
    .scenebg {{ position: absolute; z-index: 1; display: block; {'right: 0; top: 0; height: 100%; width: auto; -webkit-mask-image: linear-gradient(to right, transparent, #000 28%);' if land else 'left: 0; bottom: 0; width: 100%; height: auto; -webkit-mask-image: linear-gradient(to bottom, transparent, #000 22%);'} }}
    .shade {{ display: none; }}
    .sc .ln {{ color: #fff; }}
    .sc .ln span {{ -webkit-text-stroke: 16px #111; }}
    .sc .ln.hl span {{ -webkit-text-stroke: 0; color: {t['hl_text']}; }}
    .person {{ position: absolute; z-index: 3; filter: drop-shadow(0 14px 22px rgba(0,0,0,.35)); }}
    .phone {{ position: absolute; z-index: 4; border-radius: 46px; background: #0d0d10; padding: 9px; border: 12px solid #fff; box-shadow: 0 20px 40px rgba(0,0,0,.4); }}
    .scr {{ width: 100%; height: 100%; border-radius: 30px; overflow: hidden; }}
    .scr img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .mascot {{ position: absolute; z-index: 6; filter: drop-shadow(0 0 0 #fff) drop-shadow(0 8px 0 rgba(0,0,0,.18)); }}
    .kicker {{ position: absolute; z-index: 7; font-weight: 800; font-style: italic; color: {t['ink']}; }}
    .kicker span {{ background: #fff; color: #111; padding: 6px 30px 12px; border-radius: 999px; box-shadow: 0 8px 0 rgba(0,0,0,.18); }}
    {css_pos}
    </style><div class="bg"></div><div class=glow></div>
    {person}{'<div class=shade></div>' if layout == 'scene' else ''}{scr}{mas}<div class=words>{''.join(lines)}</div>{kicker}"""
    return page, w, h


def _uri_font() -> str:
    f = ROOT / "assets" / "fonts" / "InterDisplay-ExtraBold.otf"
    return "data:font/otf;base64," + base64.b64encode(f.read_bytes()).decode()


def render(spec: dict, out: Path) -> Path:
    from playwright.sync_api import sync_playwright
    page, w, h = build_html(spec)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.set_content(page)
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(out))
        b.close()
    return out


DEMOS = {
    "at-my-desk": {"app": "slipnote", "layout": "scene", "scene": "working-on-laptop-3", "words": ["I built this", "*WHOLE APP*", "alone"],
                   "screen": "slipnote/theme-love-letter", "mascot": "slip:cheer", "kicker": "from this corner"},
    "yt-desk": {"app": "setalytix", "size": "yt", "layout": "scene", "scene": "working-on-laptop-2-me-looking-at-camera-2",
                "scene_pos": "50% 30%", "words": ["I built a", "*FREE*", "gym app"], "mascot": "bo:flex", "side": "right"},
}

if __name__ == "__main__":
    if sys.argv[1] == "--demo":
        out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
        for k, s in DEMOS.items():
            print(render(s, out / f"{k}.png"))
    else:
        render(yaml.safe_load(Path(sys.argv[1]).read_text()), Path(sys.argv[2]))
