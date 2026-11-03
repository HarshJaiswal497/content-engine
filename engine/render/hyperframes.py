"""Motion videos with HyperFrames (HTML to video): kinetic titles, wipes between scenes.

Turns a post's `slides:` into scenes (cover / point / cta) from hf/promo/templates/, builds a throwaway
HyperFrames project, renders a silent 1080x1920 30 fps MP4, and returns it. The voiceover and music are
mixed afterwards by video.mux_audio, so the picture and the sound stay independent.

Needs Node 22+, ffmpeg and Chrome. Set HYPERFRAMES_BROWSER_PATH if Chrome is not found.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..config import ROOT
from .slides import APP_LABEL, THEMES, _words, handles

HF = ROOT / "hf"
W, H, FPS = 1080, 1920, 30
FADE = 0.45   # overlap between scenes (the next scene wipes in over the last)
LEAD, TAIL = 0.35, -0.15   # voice starts 0.35 s into its scene; the next scene wipes in 0.15 s before the line ends
HEX = re.compile(r"^#([0-9a-fA-F]{6})$")


def _rgba(hex_color: str, alpha: float) -> str:
    m = HEX.match(hex_color)
    if not m:
        return hex_color
    n = int(m.group(1), 16)
    return f"rgba({n >> 16},{(n >> 8) & 255},{n & 255},{alpha})"


def _title_size(text: str, big: bool) -> int:
    n = len(text.replace("*", ""))
    sizes = [(16, 150), (24, 128), (36, 108), (52, 92)] if big else [(20, 112), (34, 96), (52, 84)]
    for limit, size in sizes:
        if n <= limit:
            return size
    return 72 if big else 68


def screen_catalog() -> dict:
    import yaml
    p = ROOT / "brand" / "screens.yml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def resolve_screen(ref: str, app: str) -> tuple[str, str, dict]:
    """'today' (this post's app) or 'slipnote/composer' -> (app, slug, catalog entry). Raises if unknown."""
    ref = str(ref).strip()
    owner, slug = ref.split("/", 1) if "/" in ref else (app, ref)
    entry = (screen_catalog().get(owner) or {}).get(slug)
    if entry is None or not (ROOT / "assets" / "screens" / owner / f"{slug}.png").exists():
        raise ValueError(f"unknown screen '{ref}' (see brand/screens.yml)")
    return owner, slug, entry


def _focus_box(focus, entry: dict) -> dict | None:
    if not focus:
        return None
    box = (entry.get("regions") or {}).get(focus) if isinstance(focus, str) else focus
    if not isinstance(box, dict) or not {"x", "y", "w", "h"} <= set(box):
        raise ValueError(f"unknown focus '{focus}' (use a region name from brand/screens.yml or an {{x, y, w, h}} box)")
    return {k: float(box[k]) for k in ("x", "y", "w", "h")}


def _title_html(text: str) -> str:
    """Words as spans. Neighbouring *accent* words share one highlight pill (unless the phrase is long)."""
    items: list[tuple[str, bool]] = []
    for word in _words(text):
        if word[0][0] == "\n":
            items.append(("\n", False))
            continue
        items.append(("".join(t for t, _ in word), any(a for _, a in word)))
    groups: list[tuple[str, bool]] = []
    for label, acc in items:
        if groups and acc and groups[-1][1] and label != "\n" and groups[-1][0] != "\n" and len(groups[-1][0]) + len(label) < 16:
            groups[-1] = (groups[-1][0] + " " + label, True)
        else:
            groups.append((label, acc))
    out = []
    for label, acc in groups:
        if label == "\n":
            out.append('<span style="flex-basis:100%;height:0"></span>')
            continue
        hl = '<i class="hl"></i>' if acc else ""
        out.append(f'<span class="w{" acc" if acc else ""}">{html.escape(label)}{hl}</span>')
    return "".join(out)


def _phone_tokens(slide: dict, app: str, dur: float, out_dir: Path, title_size: int) -> dict:
    owner, slug, entry = resolve_screen(slide["screen"], app)
    dest = out_dir / "assets" / f"{owner}-{slug}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "assets" / "screens" / owner / f"{slug}.png", dest)
    box = _focus_box(slide.get("focus"), entry)
    top, pw, ph = 560.0, 540.0, 1169.0
    t = {"SCREEN_SRC": f"assets/{owner}-{slug}.png", "PHONE_TOP": int(top), "DUR": f"{dur:.2f}",
         "TITLE_SIZE": min(title_size, 92), "LABEL": html.escape(str(slide.get("label") or "")),
         "ZOOM": 1, "ZOOM_X": 0, "ZOOM_Y": 0, "FOCUS_ORIGIN": "50% 50%", "LABEL_ON": 0,
         "RING_L": 0, "RING_T": 0, "RING_W": 0, "RING_H": 0, "LABEL_X": 50, "LABEL_T": 0, "LABEL_TR": "-100%"}
    if box:
        cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
        zoom = min(2.1, max(1.15, 1.6 / max(box["w"], 0.2)), 880 / (max(box["h"], 0.05) * ph))
        t.update(ZOOM=round(zoom, 3), ZOOM_X=round(540 - (270 + cx * pw)), ZOOM_Y=round(860 - (top + cy * ph)),
                 FOCUS_ORIGIN=f"{cx * 100:.1f}% {cy * 100:.1f}%",
                 RING_L=round((box["x"] - 0.015) * 100, 2), RING_T=round((box["y"] - 0.008) * 100, 2),
                 RING_W=round((box["w"] + 0.03) * 100, 2), RING_H=round((box["h"] + 0.016) * 100, 2),
                 LABEL_X=round(cx * 100, 1), LABEL_ON=1 if t["LABEL"] else 0)
        if box["y"] < 0.1:
            t.update(LABEL_T=round((box["y"] + box["h"]) * 100 + 3.5, 2), LABEL_TR="0%")
        else:
            t.update(LABEL_T=round(box["y"] * 100 - 1.6, 2))
    return t


def _texture(kind: str, ink: str) -> str:
    if kind == "lines":
        return (f"background-image: repeating-linear-gradient(to bottom, transparent 0 62px, {_rgba('#B9A98A', .22)} 62px 64px);"
                " background-position: 0 160px;")
    if kind == "dots":
        return f"background-image: radial-gradient({_rgba(ink, .09)} 3px, transparent 3.5px); background-size: 48px 48px;"
    return ""


def _fill(template: str, tokens: dict[str, str]) -> str:
    for k, v in tokens.items():
        template = template.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[A-Z_]+\}\}", template)
    if left:
        raise ValueError(f"unfilled template tokens: {sorted(set(left))}")
    return template


def build_project(slides: list[dict], app: str, seconds: list[float], fade: float, out_dir: Path) -> Path:
    """Write a HyperFrames project for these slides into out_dir and return it."""
    theme = THEMES.get(app, THEMES["personal"])
    base_css = (HF / "promo" / "templates" / "base.css").read_text()
    label = APP_LABEL.get(app, app.upper())
    handle = (handles().get("handle") or "").strip()
    comps = out_dir / "compositions"
    comps.mkdir(parents=True, exist_ok=True)
    shutil.copy(HF / "shared" / "gsap.min.js", out_dir / "gsap.min.js")
    (out_dir / "hyperframes.json").write_text((HF / "promo" / "hyperframes.json").read_text())

    hosts, start, n_point = [], 0.0, 0
    for i, (slide, dur) in enumerate(zip(slides, seconds)):
        kind = slide.get("type") if slide.get("type") in {"cover", "point", "cta"} else "point"
        if i == 0:
            kind = "cover"
        if i == len(slides) - 1 and len(slides) > 1:
            kind = "cta"
        if kind == "point" and slide.get("screen"):
            kind = "phone"
        title = slide.get("title") or ""
        tokens = {
            "ID": f"s{i}", "LABEL": label, "HANDLE": handle, "N": n_point + 1,
            "TITLE_HTML": _title_html(title), "BODY": html.escape(slide.get("body") or ""),
            "TEXTURE": _texture(theme.texture, theme.ink), "GAP": 26,
            "BG": theme.bg, "INK": theme.ink, "ACCENT": theme.accent,
            "MUTED": theme.muted, "CARD": theme.card, "ON_ACCENT": theme.on_accent, "DIR": 1 if n_point % 2 == 0 else -1,
            "TITLE_SIZE": _title_size(title, kind in {"cover", "cta"}),
        }
        if kind == "phone":
            n_point += 1
            tokens.update(_phone_tokens(slide, app, dur, out_dir, tokens["TITLE_SIZE"]))
        if kind == "point":
            n_point += 1
            if n_point % 2 == 0:       # alternate the ground for rhythm
                tokens.update(BG=theme.card, CARD=theme.bg)
        if kind == "cta":
            tokens.update(BG=theme.accent, INK=theme.on_accent, ACCENT=theme.on_accent, ON_ACCENT=theme.accent,
                          MUTED=_rgba(theme.on_accent, .75), CARD=theme.on_accent)
        tokens["BASE_CSS"] = _fill(base_css, tokens)
        tpl = (HF / "promo" / "templates" / f"{kind}.html").read_text()
        (comps / f"s{i}.html").write_text(_fill(tpl, tokens))
        hosts.append(
            f'    <div id="s{i}" data-composition-id="s{i}" data-composition-src="compositions/s{i}.html" '
            f'data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="{i + 1}" data-track-kind="graphics" '
            f'data-width="{W}" data-height="{H}" style="z-index:{i + 1}"></div>')
        start += dur - fade
    total = start + fade
    (out_dir / "index.html").write_text(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: {theme.bg}; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
{chr(10).join(hosts)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    return out_dir


def render_project(project: Path, out: Path, quality: str = "looks") -> Path:
    env = dict(os.environ)
    cmd = ["npx", "--yes", "hyperframes@0.9.9", "render", str(project), "-o", str(out), "-q", quality,
           "--quiet", "--workers", env.get("HF_WORKERS", "2")]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"hyperframes render failed ({proc.returncode}):\n{(proc.stdout + proc.stderr)[-3000:]}")
    return out


def render_motion(slides: list[dict], app: str, seconds: list[float], fade: float, out: Path, work: Path,
                  quality: str = "looks") -> Path:
    proj = build_project(slides, app, seconds, fade, work / "hf-project")
    return render_project(proj, out, quality)


# ---------------------------------------------------------------- talking head

ZOOM_CYCLE = [1.0, 1.12, 1.0, 1.2]   # punch-in rhythm: wide, in, wide, closer


def _sentences(words: list[dict]) -> list[float]:
    """Start time of each sentence (a word after one ending . ? !)."""
    starts = [words[0]["start"]] if words else []
    for prev, w in zip(words, words[1:]):
        if prev["word"].endswith((".", "?", "!")):
            starts.append(w["start"])
    return starts


def _caption_chunks(words: list[dict], dur: float) -> list[dict]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= 3 or w["start"] - cur[-1]["end"] > 0.6 or cur[-1]["word"].endswith((".", "?", "!", ","))):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        s, e = c[0]["start"], max(c[-1]["end"], c[0]["start"] + 0.4)
        if i + 1 < len(chunks):   # hold through a short gap so captions do not flicker
            nxt = chunks[i + 1][0]["start"]
            e = min(max(e, nxt - 0.02), e + 0.35)
            e = min(e, nxt - 0.02) if nxt - 0.02 > s else e
        out.append({"s": round(s, 3), "e": round(min(e, dur), 3),
                    "w": [[round(w["start"], 3), round(max(w["end"], w["start"] + 0.1), 3), w["word"]] for w in c]})
    return out


def build_talking_project(src: Path, words: list[dict], hook: str | None, app: str, dur: float,
                          out_dir: Path, inserts: list[dict] | None = None, portrait: bool = True,
                          emphasis: list[str] | None = None) -> Path:
    """HyperFrames project for a talking-head clip: the clip (muted; audio is muxed later), word-highlight
    captions, punch-in zooms at sentence starts, a hook pill, and phone-screen inserts."""
    theme = THEMES.get(app, THEMES["personal"])
    comps = out_dir / "compositions"
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    comps.mkdir(parents=True, exist_ok=True)
    shutil.copy(HF / "shared" / "gsap.min.js", out_dir / "gsap.min.js")
    (out_dir / "hyperframes.json").write_text((HF / "talking-head" / "hyperframes.json").read_text())
    shutil.copy(src, out_dir / "assets" / "clip.mp4")

    chunks = _caption_chunks(words, dur)
    caps_html = []
    for i, c in enumerate(chunks):
        spans = "".join(f'<span class="cw" id="cap{i}w{j}">{html.escape(w[2])}</span>' for j, w in enumerate(c["w"]))
        caps_html.append(f'    <div class="cap" id="cap{i}">{spans}</div>')

    starts = _sentences(words)
    zooms = [[0, 1.0]]
    for k, t in enumerate(starts[1:], start=1):
        zooms.append([round(max(t - 0.05, 0), 3), ZOOM_CYCLE[k % len(ZOOM_CYCLE)]])
    emph = {re.sub(r"\W", "", e.lower()) for e in (emphasis or [])}
    for w in words:
        if re.sub(r"\W", "", w["word"].lower()) in emph:
            zooms.append([round(w["start"] - 0.05, 3), 1.26])
            zooms.append([round(w["end"] + 0.35, 3), 1.0])
    zooms.sort()

    ins_html, ins_data = [], []
    for i, ins in enumerate(inserts or []):
        owner, slug, entry = resolve_screen(ins["screen"], app)
        shutil.copy(ROOT / "assets" / "screens" / owner / f"{slug}.png", out_dir / "assets" / f"{owner}-{slug}.png")
        box = _focus_box(ins.get("focus"), entry)
        ring = lab = ""
        if box:
            ring = (f'<div class="ring" style="left:{(box["x"]-.015)*100:.2f}%;top:{(box["y"]-.008)*100:.2f}%;'
                    f'width:{(box["w"]+.03)*100:.2f}%;height:{(box["h"]+.016)*100:.2f}%"></div>')
            if ins.get("label"):
                lab = (f'<div class="lab" style="left:-8px;top:{max(box["y"]*100-2, 1):.1f}%">'
                       f'{html.escape(str(ins["label"]))}</div>')
        at = float(ins["at"])
        end = min(at + float(ins.get("dur", 3.5)), dur)
        ins_html.append(f'    <div class="ins" id="ins{i}"><div class="scr"><img src="assets/{owner}-{slug}.png" alt="">{ring}</div>{lab}</div>')
        ins_data.append({"s": round(at, 3), "e": round(end, 3), "ring": bool(box)})

    hook_end = 2.8
    tokens = {
        "BG": "#000000", "ACCENT": theme.accent, "ON_ACCENT": theme.on_accent,
        "VIDEO_SRC": "assets/clip.mp4", "VIDEO_TOP": 0 if portrait else 360, "VIDEO_H": 1920 if portrait else 1200,
        "CAP_TOP": 1120, "INS_TOP": 230,
        "HOOK": html.escape(hook or ""), "HOOK_ON": "true" if hook else "false", "HOOK_END": hook_end,
        "CAPS_HTML": "\n".join(caps_html), "INSERTS_HTML": "\n".join(ins_html),
        "ZOOMS": json.dumps(zooms), "CAPS": json.dumps(chunks), "INSERTS": json.dumps(ins_data),
    }
    (comps / "th.html").write_text(_fill((HF / "talking-head" / "templates" / "main.html").read_text(), tokens))
    (out_dir / "index.html").write_text(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="th" data-composition-id="th" data-composition-src="compositions/th.html" data-start="0" data-duration="{dur:.3f}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    return out_dir


def render_talking(src: Path, words: list[dict], hook: str | None, app: str, dur: float, out: Path, work: Path,
                   inserts: list[dict] | None = None, portrait: bool = True, emphasis: list[str] | None = None,
                   quality: str = "looks") -> Path:
    proj = build_talking_project(src, words, hook, app, dur, work / "hf-th", inserts, portrait, emphasis)
    return render_project(proj, out, quality)
