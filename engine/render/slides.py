"""Render slide dicts to JPEGs with Pillow (no browser needed, identical locally and in CI).

Slide types (set with `type:`; default is `point`):
  cover  – kicker, title, subtitle
  point  – optional number, title, body
  big    – one large statement (title)
  code   – title + code
  image  – screenshot from inbox/ (`image:`), title/caption
  cta    – title, body; handle is added automatically
Wrap words in *asterisks* to colour them with the app's accent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import BRAND, FONTS, ROOT

SIZES = {"feed": (1080, 1350), "vertical": (1080, 1920)}


@dataclass(frozen=True)
class Theme:
    bg: str
    ink: str
    accent: str
    muted: str
    card: str
    on_accent: str
    texture: str  # "lines" | "dots" | "none"


THEMES = {
    # Slipnote "Paper & Ink": cream card, navy ink accent
    "slipnote": Theme("#FFFBF1", "#1C1B2E", "#1F3A93", "#6B6A7E", "#FFF4D6", "#FFFFFF", "lines"),
    # Setalytix "Streak": deep indigo, yellow
    "setalytix": Theme("#1D1147", "#FFFFFF", "#FFD23F", "#B7AEDC", "#2A1D63", "#1D1147", "dots"),
    "personal": Theme("#101827", "#F8FAFC", "#7DD3FC", "#94A3B8", "#1B2537", "#0B1220", "none"),
}
APP_LABEL = {"slipnote": "SLIPNOTE", "setalytix": "SETALYTIX", "personal": "BUILD LOG"}


@lru_cache(maxsize=None)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"display": "InterDisplay-ExtraBold.otf", "bold": "InterDisplay-Bold.otf",
             "semi": "Inter-SemiBold.otf", "regular": "Inter-Regular.otf", "mono": "DejaVuSansMono.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), size)


@lru_cache(maxsize=1)
def handles() -> dict:
    p = BRAND / "handles.yml"
    return yaml.safe_load(p.read_text()) if p.exists() else {}


# ---- rich text: *accent* words --------------------------------------------
def _words(text: str) -> list[list[tuple[str, bool]]]:
    """Split into words; each word is a list of (segment, is_accent) so "*Slipnote*?" keeps its "?"."""
    words: list[list[tuple[str, bool]]] = []
    acc = False
    for raw in re.split(r"( +|\n)", text):
        if raw == "\n":
            words.append([("\n", False)])
            continue
        if not raw or raw.isspace():
            continue
        segs = []
        for i, part in enumerate(raw.split("*")):
            if i:
                acc = not acc
            if part:
                segs.append((part, acc))
        if segs:
            words.append(segs)
    return words


def _wlen(word, fnt) -> float:
    return sum(fnt.getlength(t) for t, _ in word)


def _layout(text: str, fnt, width: int) -> list[list[list[tuple[str, bool]]]]:
    lines, line, x = [], [], 0.0
    space = fnt.getlength(" ")
    for word in _words(text):
        if word[0][0] == "\n":
            lines.append(line); line, x = [], 0.0
            continue
        w = _wlen(word, fnt)
        if line and x + space + w > width:
            lines.append(line); line, x = [], 0.0
        x += (space if line else 0) + w
        line.append(word)
    if line:
        lines.append(line)
    return lines


def _text_block(draw, text, family, box, theme, color, max_size, min_size=28, leading=1.18, align="left"):
    """Draw text auto-sized to fit box=(x, y, w, h). Returns bottom y."""
    x, y, w, h = box
    for size in range(max_size, min_size - 1, -2):
        f = font(family, size)
        lines = _layout(text, f, w)
        lh = int(size * leading)
        if len(lines) * lh <= h:
            break
    space = f.getlength(" ")
    for line in lines:
        lw = sum(_wlen(wd, f) for wd in line) + space * (len(line) - 1)
        cx = x + (w - lw) / 2 if align == "center" else x
        for word in line:
            for seg, acc in word:
                draw.text((cx, y), seg, font=f, fill=theme.accent if acc else color)
                cx += f.getlength(seg)
            cx += space
        y += lh
    return y


def _texture(img: Image.Image, theme: Theme) -> None:
    d = ImageDraw.Draw(img)
    W, H = img.size
    if theme.texture == "lines":
        for yy in range(160, H, 64):
            d.line([(0, yy), (W, yy)], fill="#EFE8D8", width=2)
        d.line([(72, 0), (72, H)], fill="#F2C4C4", width=3)
    elif theme.texture == "dots":
        for yy in range(40, H, 48):
            for xx in range(40, W, 48):
                d.ellipse([xx - 2, yy - 2, xx + 2, yy + 2], fill="#2B1F5E")


def _chrome(d: ImageDraw.ImageDraw, img, theme, app, idx, total, M, video=False):
    W, H = img.size
    label = APP_LABEL.get(app, "BUILD LOG")
    f = font("semi", 26)
    pw = f.getlength(label) + 44
    d.rounded_rectangle([M, M, M + pw, M + 52], radius=26, fill=theme.accent)
    d.text((M + 22, M + 11), label, font=f, fill=theme.on_accent)
    if total > 1 and not video:
        t = f"{idx + 1}/{total}"
        d.text((W - M - f.getlength(t), M + 11), t, font=f, fill=theme.muted)
    fb = font("semi", 28)
    d.text((M, H - M - 30), handles().get("handle", ""), font=fb, fill=theme.muted)
    if total > 1 and idx < total - 1 and not video:
        s = "swipe →"
        d.text((W - M - fb.getlength(s), H - M - 30), s, font=fb, fill=theme.accent)


def _paste_screenshot(img, path: Path, box, theme):
    x, y, w, h = box
    shot = Image.open(path).convert("RGB")
    shot.thumbnail((w, h))
    sw, sh = shot.size
    ox, oy = x + (w - sw) // 2, y + (h - sh) // 2
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw, sh], radius=36, fill=255)
    shadow = Image.new("RGBA", (sw + 80, sh + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 50, sw + 40, sh + 50], radius=36, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.paste(shadow, (ox - 40, oy - 40), shadow)
    img.paste(shot, (ox, oy), mask)


def render_slide(slide: dict, app: str, idx: int, total: int, size: str = "feed") -> Image.Image:
    theme = THEMES.get(app, THEMES["personal"])
    W, H = SIZES[size]
    img = Image.new("RGB", (W, H), theme.bg)
    _texture(img, theme)
    d = ImageDraw.Draw(img)
    M = 96
    _chrome(d, img, theme, app, idx, total, M, video=size == "vertical")
    top, bottom = M + 120, H - M - 90
    cw = W - 2 * M
    kind = slide.get("type", "point")
    title, body = slide.get("title", ""), slide.get("body", "")
    vert = size == "vertical"

    avail = bottom - top

    k = 1.22 if vert else 1.0

    def flow(dr, y):
        """Draw a vertically flowing slide starting at y; returns the end y."""
        if kind == "cover":
            if slide.get("kicker"):
                dr.text((M, y), slide["kicker"].upper(), font=font("semi", 34), fill=theme.accent)
                y += 70
            y = _text_block(dr, title, "display", (M, y, cw, int(avail * 0.6)), theme, theme.ink, int(132 * k), 60, 1.06)
            if slide.get("subtitle"):
                y = _text_block(dr, slide["subtitle"], "regular", (M, y + 36, cw, int(avail * 0.25)), theme, theme.muted, int(46 * k), 30, 1.3)
            return y
        if kind == "big":
            return _text_block(dr, title, "display", (M, y, cw, int(avail * 0.8)), theme, theme.ink, int(120 * k), 54, 1.08)
        if kind == "cta":
            y = _text_block(dr, title, "display", (M, y, cw, 420), theme, theme.ink, int(104 * k), 52, 1.08) + 40
            if body:
                y = _text_block(dr, body, "regular", (M, y, cw, 300), theme, theme.muted, int(46 * k), 30, 1.3) + 50
            h = handles().get("handle", "")
            f = font("bold", 46)
            bw = f.getlength(f"Follow {h}") + 80
            dr.rounded_rectangle([M, y, M + bw, y + 96], radius=48, fill=theme.accent)
            dr.text((M + 40, y + 22), f"Follow {h}", font=f, fill=theme.on_accent)
            return y + 96
        # point
        numbered = slide.get("number") is not None
        if numbered:
            dr.text((M, y - 20), str(slide["number"]).zfill(2), font=font("display", 160), fill=theme.accent)
            y += 200
        y = _text_block(dr, title, "bold", (M, y, cw, 330), theme, theme.ink, int((84 if numbered else 104) * k), 44, 1.1) + 34
        if body:
            y = _text_block(dr, body, "regular", (M, y, cw, int(avail * 0.45)), theme, theme.muted,
                            int((46 if numbered else 54) * k), 28, 1.35)
        return y

    if kind in {"cover", "big", "cta", "point"}:
        scratch = ImageDraw.Draw(Image.new("RGB", (W, H)))
        height = flow(scratch, 0)
        flow(d, top + max(0, int((avail - height) * 0.42)))
        return img

    if kind == "code":
        code = slide.get("code", "").rstrip("\n").split("\n")
        longest = max((len(l) for l in code), default=1)
        inner = cw - 72
        size_px = max(20, min(int(38 * (1.15 if vert else 1)), int(inner / (0.61 * longest))))
        f = font("mono", size_px)
        lh = int(size_px * 1.5)
        box_h = 84 + lh * len(code) + 44
        scratch = ImageDraw.Draw(Image.new("RGB", (W, H)))
        title_h = _text_block(scratch, title, "bold", (M, 0, cw, 260), theme, theme.ink, int(72 * k), 36, 1.12) + 40
        body_h = (_text_block(scratch, body, "regular", (M, 0, cw, 200), theme, theme.muted, 44, 28, 1.3) + 36) if body else 0
        y = top + max(0, int((avail - title_h - box_h - body_h) * 0.42))
        y = _text_block(d, title, "bold", (M, y, cw, 260), theme, theme.ink, int(72 * k), 36, 1.12) + 40
        d.rounded_rectangle([M, y, W - M, y + box_h], radius=28, fill="#0B0F14")
        for i, c in enumerate(["#FF5F57", "#FEBC2E", "#28C840"]):
            d.ellipse([M + 32 + i * 34, y + 30, M + 52 + i * 34, y + 50], fill=c)
        cy = y + 84
        for line in code:
            d.text((M + 36, cy), line, font=f, fill="#E6EDF3")
            cy += lh
        if body:
            _text_block(d, body, "regular", (M, y + box_h + 36, cw, 200), theme, theme.muted, 44, 28, 1.3)
    elif kind == "image":
        y = top
        if title:
            y = _text_block(d, title, "bold", (M, top, cw, 200), theme, theme.ink, 60, 34, 1.12) + 24
        cap_h = 110 if body else 0
        src = ROOT / slide["image"] if "/" in slide.get("image", "") else ROOT / "inbox" / slide.get("image", "")
        if src.exists():
            _paste_screenshot(img, src, (M, y, cw, bottom - y - cap_h), theme)
        else:
            d.rounded_rectangle([M, y, W - M, bottom - cap_h], radius=36, outline=theme.muted, width=4)
            _text_block(d, f"missing image:\n{slide.get('image')}", "semi", (M + 40, y + 40, cw - 80, 200), theme, theme.muted, 36)
        if body:
            _text_block(d, body, "regular", (M, bottom - cap_h + 20, cw, cap_h), theme, theme.muted, 38, 26, 1.25, "center")
    return img


def render_post_slides(slides: list[dict], app: str, out_dir: Path, size: str = "feed", prefix: str = "slide") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, s in enumerate(slides):
        p = out_dir / f"{prefix}-{i + 1:02d}.jpg"
        render_slide(s, app, i, len(slides), size).save(p, "JPEG", quality=90, optimize=True, progressive=True)
        paths.append(p)
    return paths
