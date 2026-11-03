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
        title = slide.get("title") or ""
        tokens = {
            "ID": f"s{i}", "LABEL": label, "HANDLE": handle, "N": n_point + 1,
            "TITLE_HTML": _title_html(title), "BODY": html.escape(slide.get("body") or ""),
            "TEXTURE": _texture(theme.texture, theme.ink), "GAP": 26,
            "BG": theme.bg, "INK": theme.ink, "ACCENT": theme.accent,
            "MUTED": theme.muted, "CARD": theme.card, "ON_ACCENT": theme.on_accent, "DIR": 1 if n_point % 2 == 0 else -1,
            "TITLE_SIZE": _title_size(title, kind in {"cover", "cta"}),
        }
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
