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
                          emphasis: list[str] | None = None, zoom: bool = True) -> Path:
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
    if not zoom:          # `zoom: false` on the post: the speaker never punches in; only the screens move
        zooms = []

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
        # the screen slowly pushes in on what matters: the focus box, else the top of the screen (where the note is)
        fx, fy = (box["x"] + box["w"] / 2, box["y"] + box["h"] / 2) if box else (.5, .33)
        zs = min(1.6, max(1.25, 0.55 / max(box['w'], box['h']))) if box else 1.22
        ins_data.append({"s": round(at, 3), "e": round(end, 3), "ring": bool(box),
                         "ox": round(fx * 100, 1), "oy": round(fy * 100, 1), "z": round(zs, 3)})

    hook_end = 2.8
    tokens = {
        "BG": "#000000", "ACCENT": theme.accent, "ON_ACCENT": theme.on_accent,
        "VIDEO_SRC": "assets/clip.mp4", "VIDEO_TOP": 0 if portrait else 360, "VIDEO_H": 1920 if portrait else 1200,
        "CAP_TOP": 1120, "INS_TOP": 230,
        "HOOK": html.escape(hook or ""), "HOOK_ON": "true" if hook else "false", "HOOK_END": hook_end,
        "CAPS_HTML": "\n".join(caps_html), "INSERTS_HTML": "\n".join(ins_html),
        "ZOOMS": json.dumps(zooms), "ZOOM_ON": "true" if zoom else "false", "CAPS": json.dumps(chunks), "INSERTS": json.dumps(ins_data),
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
                   quality: str = "looks", zoom: bool = True) -> Path:
    proj = build_talking_project(src, words, hook, app, dur, work / "hf-th", inserts, portrait, emphasis, zoom)
    return render_project(proj, out, quality)


# ---------------------------------------------------------------- skit (Slip + a human, speech bubbles)

CHARS = ROOT / "assets" / "characters"
SKIT_LAYOUT = {   # left, top, width (px) of each character on the 1080x1920 frame
    "slip": (0, 880, 560),
    "human": (580, 830, 480),
}


def _bubble_html(text: str) -> str:
    parts = []
    for w in _words(text):
        if w[0][0] == "\n":
            parts.append('<span style="flex-basis:100%;height:0"></span>')
            continue
        label = html.escape("".join(t for t, _ in w))
        parts.append(f'<span class="bw{" em" if any(a for _, a in w) else ""}">{label}</span>')
    return "".join(parts)


def skit_beats_ok(beats: list[dict]) -> list[str]:
    errs = []
    for n, b in enumerate(beats or [], 1):
        who = (b or {}).get("who")
        if who not in SKIT_LAYOUT:
            errs.append(f"beat {n}: who must be one of {sorted(SKIT_LAYOUT)}")
            continue
        other = "human" if who == "slip" else "slip"
        for key, owner in (("pose", who), ("other_pose", other)):
            if b.get(key) and not (CHARS / owner / f"{b[key]}.png").exists():
                errs.append(f"beat {n}: unknown {key} '{b[key]}' for {owner}")
        if not str(b.get("text") or "").strip():
            errs.append(f"beat {n}: text is required")
    return errs


def build_skit_project(beats: list[dict], app: str, out_dir: Path, title: str | None = None) -> tuple[Path, list[float]]:
    theme = THEMES.get(app, THEMES["personal"])
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    (out_dir / "compositions").mkdir(parents=True, exist_ok=True)
    shutil.copy(HF / "shared" / "gsap.min.js", out_dir / "gsap.min.js")
    (out_dir / "hyperframes.json").write_text((HF / "skit" / "hyperframes.json").read_text())
    errs = skit_beats_ok(beats)
    if errs:
        raise ValueError("; ".join(errs))

    durs = [float(b.get("seconds") or max(1.8, 0.35 + 0.34 * len(str(b["text"]).split()) + 0.5)) for b in beats]
    starts, t = [], 0.0
    for d in durs:
        starts.append(round(t, 3)); t += d
    total = t + 0.4

    # which poses each character shows, and when
    state = {"slip": "idle", "human": "idle"}
    timeline: list[dict] = []   # per beat: {who, poses: {slip, human}}
    used: dict[str, set] = {"slip": {"idle"}, "human": {"idle"}}
    for b in beats:
        who = b["who"]
        other = "human" if who == "slip" else "slip"
        state[who] = b.get("pose") or ("wave" if who == "slip" and not timeline else "idle" if who == "slip" else "talk")
        if b.get("other_pose"):
            state[other] = b["other_pose"]
        used["slip"].add(state["slip"]); used["human"].add(state["human"])
        timeline.append(dict(state))

    imgs = []
    for ch, poses in used.items():
        left, top, width = SKIT_LAYOUT[ch]
        for p in sorted(poses):
            src = CHARS / ch / f"{p}.png"
            shutil.copy(src, out_dir / "assets" / f"{ch}-{p}.png")
            imgs.append(f'      <img class="pose {ch}" id="{ch}-{p}" src="assets/{ch}-{p}.png" alt="">')
    bubbles = []
    for i, b in enumerate(beats):
        left_tail = 24 if b["who"] == "slip" else 74
        bubbles.append(f'    <div class="bubble {b["who"]}" id="b{i}"><div class="card">{_bubble_html(str(b["text"]))}</div>'
                       f'<i class="tail" style="left:{left_tail}%"></i></div>')
    data = {"starts": starts, "durs": [round(x, 3) for x in durs], "who": [b["who"] for b in beats], "poses": timeline, "total": round(total, 3)}
    page = (HF / "skit" / "main.html").read_text()
    tokens = {"BG": theme.bg, "INK": theme.ink, "ACCENT": theme.accent, "ON_ACCENT": theme.on_accent, "CARD": theme.card,
              "TEXTURE": _texture(theme.texture, theme.ink), "LABEL": html.escape(APP_LABEL.get(app, app.upper())),
              "TITLE": html.escape(title or ""), "TITLE_ON": "true" if title else "false",
              "IMGS_SLIP": "\n".join(i for i in imgs if " slip" in i), "IMGS_HUMAN": "\n".join(i for i in imgs if " human" in i), "BUBBLES": "\n".join(bubbles), "DATA": json.dumps(data),
              "SLIP_L": SKIT_LAYOUT["slip"][0], "SLIP_T": SKIT_LAYOUT["slip"][1], "SLIP_W": SKIT_LAYOUT["slip"][2],
              "HUMAN_L": SKIT_LAYOUT["human"][0], "HUMAN_T": SKIT_LAYOUT["human"][1], "HUMAN_W": SKIT_LAYOUT["human"][2]}
    (out_dir / "compositions" / "skit.html").write_text(_fill(page, tokens))
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
      <div id="skit" data-composition-id="skit" data-composition-src="compositions/skit.html" data-start="0" data-duration="{total:.3f}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    return out_dir, starts + [round(total - 0.4, 3)]


def render_skit(beats: list[dict], app: str, out: Path, work: Path, title: str | None = None,
                quality: str = "looks") -> tuple[Path, list[float]]:
    proj, marks = build_skit_project(beats, app, work / "hf-skit", title)
    return render_project(proj, out, quality), marks


# ---------------------------------------------------------------- story ("I built X": steps, real screens, speaker window, mascot)

MASCOT_POSES = {"slip": ["idle", "happy", "wave", "surprised", "think", "write", "sleepy", "sad", "peek", "cheer"],
                "bo": ["idle", "happy", "wave", "flex", "surprised", "think", "tick", "sleepy", "sad", "cheer"],
                "harsh-cartoon": ["idle", "happy", "wave", "surprised", "think", "sad", "cheer"],
                "harsh": ["idle", "happy", "wave", "think", "cheer", "front", "neutral", "point_right"]}   # the real mascot

# the real mascot talks in aligned frames (tools/build_talk.py): a beat's pose picks which of its talking sets is used
REAL_TALK = {"idle": "front", "think": "neutral", "wave": "happy", "cheer": "happy", "happy": "happy",
             "front": "front", "neutral": "neutral", "point_right": "point_right"}
REAL_VISEMES = 7


IMPACT_GROUPS = ("expressions", "face", "gestures")
# sound for an impact frame: strong reactions hit, bad moments thud, happy ones pop
IMPACT_SFX = {"shocked": "hit", "surprised": "hit", "oh_gasp": "hit", "confused": "dun", "frown": "dun", "hand_on_forehead": "dun",
              "gritted_teeth": "dun", "shrug": "dun", "yawn": "dun", "flat": "dun"}


def impact_file(mascot: str, name: str) -> Path | None:
    for g in IMPACT_GROUPS:
        f = CHARS / mascot / g / f"{name}.webp"
        if f.exists():
            return f
    return None


def talker(mascot: str | None, pose: str) -> str:
    """The name of the image set a beat's pose shows (the real mascot maps several poses onto its few talking sets)."""
    return REAL_TALK.get(pose, "front") if mascot == "harsh" else pose


def _story_words(text: str) -> list[tuple[str, bool]]:
    """'Nobody likes *ugly* themes' -> [(Nobody, False), (likes, False), (ugly, True), (themes, False)]. Neighbouring
    *accent* words stay separate pills (they animate one after the other)."""
    out = []
    for word in _words(text):
        if word[0][0] == "\n":
            continue
        out.append(("".join(t for t, _ in word), any(a for _, a in word)))
    return out


def story_beats_ok(beats: list[dict], app: str, mascot: str | None = None) -> list[str]:
    errs = []
    if not beats:
        return ["story needs beats"]
    for i, b in enumerate(beats, 1):
        if not str(b.get("head") or "").strip():
            errs.append(f"beat {i}: head is empty")
        if b.get("layout") not in (None, "full", "stack"):
            errs.append(f"beat {i}: layout must be 'full' or 'stack'")
        if b.get("layout") == "full" and (b.get("screen") or b.get("big")):
            errs.append(f"beat {i}: a full-screen beat shows only you (screens and big words need layout: stack)")
        if b.get("react") and mascot == "harsh" and not impact_file(mascot, str(b["react"])):
            errs.append(f"beat {i}: react '{b['react']}' is not one of the mascot's expression/face/gesture images")
        if b.get("screen"):
            try:
                resolve_screen(b["screen"], app)
            except ValueError as e:
                errs.append(f"beat {i}: {e}")
    return errs


def _cap_accent(theme) -> str:
    """Caption highlight: the app accent, or a warm yellow when the accent is too dark to read on the outline."""
    h = theme.accent.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return theme.accent if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#FFD23F"


# the mascot as the presenter: sits in the band (stack) or fills the screen (full); no speaker clip, no scrims
MASCOT_LAY = {"stack": {"mx": 319, "my": 1090, "ms": .8, "sc": 0, "cap": 1528},
              "full": {"mx": 319, "my": 735, "ms": 1.85, "sc": 0, "cap": 1560}}


# the real mascot is a square cut-out of head and torso: the bust sits in the band, large and cropped on the full beats
MASCOT_LAY_REAL = {"stack": {"mx": 319, "my": 1170, "ms": 1.086, "sc": 0, "cap": 1005},
                   "full": {"mx": 319, "my": 1179, "ms": 2.443, "sc": 0, "cap": 640}}


def _shade(hexcolor: str, k: float) -> str:
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{int(r * k):02x}{int(g * k):02x}{int(b * k):02x}"


def beats_from_slides(slides: list[dict], app: str) -> list[dict]:
    """Story beats from a post's slides, for a mascot that presents: each slide's title is the headline, a slide with
    a screen gets the stack layout (mascot in the band, the app above), the rest fill the screen with the mascot."""
    out, n = [], len(slides)
    for i, sl in enumerate(slides):
        kind = sl.get("type") or ""
        screen = sl.get("screen")
        b = {"tag": "intro" if i == 0 else ("try it" if kind == "cta" or i == n - 1 else f"{i}/{n - 2}" if n > 2 else ""),
             "head": sl.get("title") or sl.get("head") or "", "say": sl.get("say") or "",
             "layout": "stack" if screen else "full",
             "pose": sl.get("pose") or ("wave" if i == 0 else "cheer" if i == n - 1 else "think" if i % 2 else "idle")}
        if screen:
            b["screen"] = screen
            for k in ("focus", "label"):
                if sl.get(k):
                    b[k] = sl[k]
        if sl.get("big"):
            b["big"] = sl["big"]; b["layout"] = "stack"
        for k in ("react", "react_at", "react_for"):
            if sl.get(k) is not None:
                b[k] = sl[k]
        out.append(b)
    return out


def build_story_project(beats: list[dict], app: str, out_dir: Path, mascot: str | None = "slip",
                        speaker: Path | None = None, words: list[dict] | None = None,
                        emphasis: list[str] | None = None, lip: list | None = None,
                        presenter: bool = False, imp: list[dict] | None = None,
                        lay: dict | None = None) -> tuple[Path, float]:
    """HyperFrames project for a story video. Two layouts that morph into each other:
    `full` (you fill the screen) and `stack` (a framed band of you at the bottom, motion above: a real app screen
    that pushes in on the focus box, a big word). The numbered progress bar and the headline stay on screen in both.
    Captions follow your words; the mascot changes pose per beat. Returns (project, total seconds). Picture only."""
    errs = story_beats_ok(beats, app)
    if errs:
        raise ValueError("; ".join(errs))
    theme = THEMES.get(app, THEMES["personal"])
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    (out_dir / "compositions").mkdir(parents=True, exist_ok=True)
    shutil.copy(HF / "shared" / "gsap.min.js", out_dir / "gsap.min.js")
    (out_dir / "hyperframes.json").write_text((HF / "story" / "hyperframes.json").read_text())

    durs = [float(b.get("seconds") or 4.0) for b in beats]
    starts, t = [], 0.0
    for d in durs:
        starts.append(round(t, 3)); t += d
    total = round(t, 3)
    n = len(beats)

    html_beats, data, used = [], [], []
    for i, b in enumerate(beats):
        step = b.get("step", i + 1)
        tag = html.escape(str(b.get("tag") or "").upper())
        hw = _story_words(str(b["head"]))
        wspans = "".join(f'<span class="hw{" em" if em else ""}" id="bt{i}w{j}">{"<i class=pill></i>" if em else ""}{html.escape(w)}</span>'
                         for j, (w, em) in enumerate(hw))
        layout = b.get("layout") or ("stack" if (b.get("screen") or b.get("big")) else "full")
        if not speaker and not presenter:
            layout = "stack"
        phone = big = ""
        d = {"s": starts[i], "e": round(starts[i] + durs[i], 3), "screen": False, "em": [em for _, em in hw],
             "ring": False, "ox": 50, "oy": 33, "z": 1.2, "big": False, "layout": layout}
        if b.get("screen"):
            owner, slug, entry = resolve_screen(b["screen"], app)
            shutil.copy(ROOT / "assets" / "screens" / owner / f"{slug}.png", out_dir / "assets" / f"{owner}-{slug}.png")
            box = _focus_box(b.get("focus"), entry)
            ring = lab = ""
            if box:
                ring = (f'<div class="ring" style="left:{(box["x"]-.015)*100:.2f}%;top:{(box["y"]-.008)*100:.2f}%;'
                        f'width:{(box["w"]+.03)*100:.2f}%;height:{(box["h"]+.016)*100:.2f}%"></div>')
                if b.get("label"):
                    lab = f'<div class="lab" style="top:{max(box["y"]*100-2, 1):.1f}%">{html.escape(str(b["label"]))}</div>'
                d.update(ring=True, ox=round((box["x"] + box["w"] / 2) * 100, 1), oy=round((box["y"] + box["h"] / 2) * 100, 1),
                         z=round(min(1.6, max(1.25, 0.55 / max(box["w"], box["h"]))), 3))
            else:
                d["z"] = 1.18
            phone = f'<div class="ph"><div class="scr"><img src="assets/{owner}-{slug}.png" alt="">{ring}</div>{lab}</div>'
            d["screen"] = True
        if b.get("big"):
            big = f'<div class="big">{html.escape(str(b["big"]))}</div>'
            d["big"] = True
        cls = "full" if layout == "full" else ("" if b.get("screen") else "solo")
        html_beats.append(f'    <div class="beat {cls}" id="bt{i}"><div class="badge"><span class="num">{html.escape(str(step))}</span>'
                          f'{"<span class=tag>" + tag + "</span>" if tag else ""}</div><div class="head">{wspans}</div>{phone}{big}</div>')
        pose = b.get("pose") or ("wave" if i == 0 else "happy" if i == n - 1 else "think" if i % 2 else "idle")
        if mascot and mascot != "none" and pose not in MASCOT_POSES.get(mascot, []):
            raise ValueError(f"beat {i+1}: {mascot} has no pose '{pose}' ({', '.join(MASCOT_POSES[mascot])})")
        pose = talker(mascot, pose)
        d["mp"] = pose
        used.append(pose); data.append(d)

    mascot_html, poses = "", []
    if mascot and mascot != "none":
        poses = sorted(set(used) | ({"front"} if mascot == "harsh" else {"idle"}))
        for k, p in enumerate(poses):
            if presenter and mascot == "harsh":   # real mascot: seven mouth frames per set
                for m in range(REAL_VISEMES):
                    shutil.copy(CHARS / mascot / "talk" / f"{p}-v{m}.webp", out_dir / "assets" / f"mascot-{p}-m{m}.webp")
                    mascot_html += (f'      <img{" class=first" if (k == 0 and m == 0) else ""} id="mp{p}m{m}" '
                                    f'src="assets/mascot-{p}-m{m}.webp" alt="">\n')
                continue
            if presenter:   # talking frames: shut / half / open mouth, swapped by the voice loudness
                for m in range(3):
                    shutil.copy(CHARS / mascot / f"{p}-m{m}.png", out_dir / "assets" / f"mascot-{p}-m{m}.png")
                    mascot_html += (f'      <img{" class=first" if (k == 0 and m == 0) else ""} id="mp{p}m{m}" '
                                    f'src="assets/mascot-{p}-m{m}.png" alt="">\n')
                continue
            shutil.copy(CHARS / mascot / f"{p}.png", out_dir / "assets" / f"mascot-{p}.png")
            mascot_html += f'      <img{" class=first" if k == 0 else ""} id="mp{p}" src="assets/mascot-{p}.png" alt="">\n'

    imp = imp or []
    if presenter and mascot == "harsh":
        for nm in sorted({x["name"] for x in imp}):
            f = impact_file(mascot, nm)
            shutil.copy(f, out_dir / "assets" / f"imp-{nm}.webp")
            mascot_html += f'      <img class="ip" id="ip{nm}" src="assets/imp-{nm}.webp" alt="">\n'
    spk_inner = ""
    if speaker:
        shutil.copy(speaker, out_dir / "assets" / "speaker.mp4")
        spk_inner = ('<video id="spb" src="assets/speaker.mp4" muted playsinline></video>'
                     '<video id="spv" src="assets/speaker.mp4" muted playsinline></video>')
    _norm = lambda x: re.sub(r"\W", "", x.lower())
    emph = {_norm(e) for e in (emphasis or [])}
    chunks = _caption_chunks(words or [], total) if (speaker or presenter) else []
    caps_html = []
    for i, c in enumerate(chunks):
        spans = "".join(f'<span class="cw{" emph" if _norm(w[2]) in emph else ""}" id="cap{i}w{j}">{html.escape(w[2])}</span>'
                        for j, w in enumerate(c["w"]))
        caps_html.append(f'      <div class="cap" id="cap{i}">{spans}</div>')
    prog = "".join(f'<i><b id="pg{i}"></b></i>' for i in range(n))
    tokens = {"BG": theme.bg, "INK": theme.ink, "ACCENT": theme.accent, "ON_ACCENT": theme.on_accent, "CARD": theme.card,
              "ACCENT_CAP": _cap_accent(theme), "BAND_BG": "#15151c" if theme.bg.lower() > "#888888" else theme.card,
              "TEXTURE": _texture(theme.texture, theme.ink), "PROG": prog, "BEATS": "\n".join(html_beats),
              "CAPS_HTML": "\n".join(caps_html), "MASCOT": mascot_html,
              "MODE": "m-mascot" if presenter else ("m-spk" if speaker else "m-nospk"), "SPK_INNER": spk_inner,
              "MAS_W": 442 if presenter else 300, "M_INK": theme.on_accent, "M_BG": theme.accent,
              "DATA": json.dumps({"beats": data, "total": total, "poses": poses, "caps": chunks, "lipev": lip or [], "imp": [[x["t"], x["d"], "ip" + x["name"]] for x in imp],
                                  "lay": lay if lay is not None else ((MASCOT_LAY_REAL if mascot == "harsh" else MASCOT_LAY) if presenter else {})})}
    if presenter:   # the band and the full screen are a glow of the app colour behind the mascot
        tokens["BAND_BG"] = f"radial-gradient(circle at 50% 58%, {theme.accent} 0%, {_shade(theme.accent, .55)} 100%)"
    (out_dir / "compositions" / "story.html").write_text(_fill((HF / "story" / "templates" / "main.html").read_text(), tokens))
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
      <div id="story" data-composition-id="story" data-composition-src="compositions/story.html" data-start="0" data-duration="{total:.3f}" data-track-index="1" data-track-kind="graphics" data-width="{W}" data-height="{H}"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
""")
    return out_dir, total


def render_story(beats: list[dict], app: str, out: Path, work: Path, mascot: str | None = "slip",
                 speaker: Path | None = None, quality: str = "looks", words: list[dict] | None = None,
                 emphasis: list[str] | None = None, lip: list | None = None, presenter: bool = False,
                 imp: list[dict] | None = None, lay: dict | None = None) -> float:
    proj, total = build_story_project(beats, app, work / "hf-story", mascot, speaker, words, emphasis, lip, presenter, imp, lay)
    render_project(proj, out, quality)
    return total


# the retimed talking clip (1080x1920, mascot bottom-aligned, glow baked in) shown in the band and full screen
TALKCLIP_LAY = {"stack": {"vx": 197, "vy": -560, "vs": .56, "bo": 0, "bx": 0, "by": 0, "bs": 1},
                "full": {"vx": -135, "vy": -480, "vs": 1.25, "bo": 0}}
