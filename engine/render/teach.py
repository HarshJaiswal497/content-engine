"""Teaching Reels (video.kind: teach): faceless, the mascot talks in the lower window, one idea per beat.

Picture per beat: a segmented progress bar, a tag chip, a slamming heading, and a floating card (code, flow,
gauge, walkthrough video or the comment-word CTA) that shakes and flashes on every hit, which drops a water
ripple into a moving three.js gradient. Captions in white, the spoken word lit black on white.

Slide fields (see queue/_template.yml and hf/teach/example.yml):
  say, head ("Stop *leaking* keys"), tag ("THE MISTAKE"), react / react_at (mascot reaction), and `card:`.
  card.type: code | flow | gauge | video | comment | bio
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import ROOT

HF = ROOT / "hf"
LEAD = 0.2


def _typed(text: str, cls: str = "") -> str:
    return "".join(f'<span class="ch {cls}">{html.escape(c) if c != " " else "&nbsp;"}</span>' for c in text)


def _head_html(s: str) -> str:
    """Words as spans; *several words* share one highlight pill."""
    out = []
    for m in re.finditer(r"\*(.+?)\*([^\s*]*)|(\S+)", s):
        if m.group(1) is not None:
            out.append(f'<span class="hl">{html.escape(m.group(1))}</span>' + (f'<span class="hw">{html.escape(m.group(2))}</span>' if m.group(2) else ""))
        else:
            out.append(f'<span class="hw">{html.escape(m.group(3))}</span>')
    return " ".join(out)


MARK = re.compile(r"\[\[(bad|good):(.*?)\]\]")


def _code_html(code: str) -> tuple[str, bool]:
    """Escape, then turn [[bad:...]] / [[good:...]] into typed, highlighted spans. Returns (html, has_typed)."""
    out, pos, typed = "", 0, False
    for m in MARK.finditer(code):
        out += html.escape(code[pos:m.start()]).replace(" ", "&nbsp;")
        out += f'<span class="{m.group(1)}">{_typed(m.group(2))}</span>'
        pos, typed = m.end(), True
    out += html.escape(code[pos:]).replace(" ", "&nbsp;")
    return out, typed


def _card(i: int, beat_len: float, card: dict, spec_span: int, starts: list[float], ends: list[float]) -> tuple[str, str]:
    """(html, js) for the card shown on beat i. Offsets are seconds from the beat start, kept inside the beat."""
    t = card.get("type", "code")
    cid, B = f"c{i}", f"B[{i}]"
    cap = max(beat_len - 0.55, 1.0)
    at = lambda x: min(float(x), cap)
    last = i + spec_span - 1
    js = [f'card("#{cid}", {B}.s + .05, B[{last}].e{" + .3" if card.get("hold_out") else ""});']
    if t == "code":
        body, typed = _code_html(str(card.get("code", "")))
        extra = ""
        win = f'<div class="win"><i></i><i></i><i></i><span>{html.escape(str(card.get("file", "code")))}</span></div>'
        h = f'<div class="card" id="{cid}"><div class="cf"></div>{win}<pre class="code">{body}</pre>'
        if typed:
            js.append(f'typeIn("#{cid}", {B}.s + {at(.6)}, .06);')
        if card.get("stamp"):
            h += f'<div class="stamp" id="st{i}">{html.escape(str(card["stamp"]))}</div>'
            js.append(f'tl.fromTo("#st{i}", {{ opacity: 0, scale: 2.6, rotation: -22 }}, {{ opacity: 1, scale: 1, rotation: -8, duration: .25, ease: "power4.in" }}, {B}.s + {at(1.55)}); hit("#{cid}", {B}.s + {at(1.8)}, 1.3, [.72, .5]);')
        if card.get("pill"):
            h += f'<span class="pill g" id="pl{i}">{html.escape(str(card["pill"]))}</span>'
            js.append(f'tl.fromTo("#pl{i}", {{ opacity: 0, scale: .6 }}, {{ opacity: 1, scale: 1, duration: .35, ease: "back.out(3)" }}, {B}.s + {at(1.6)});')
        if card.get("big"):
            h += f'<div class="big" id="bg{i}">{html.escape(str(card["big"]))}</div>'
            js.append(f'tl.fromTo("#bg{i}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: .35 }}, {B}.s + {at(2.0)});')
        if card.get("sub"):
            h += f'<div class="sub" id="sb{i}">{html.escape(str(card["sub"]))}</div>'
            js.append(f'tl.fromTo("#sb{i}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: .35 }}, {B}.s + {at(3.4)});')
        cnt = card.get("count")
        if cnt:
            h += f'<div class="cnt" id="cnt{i}" style="opacity:0"><b id="cn{i}">0</b><span>{html.escape(str(cnt.get("label", "")))}</span></div>'
            js.append(f'tl.set("#cnt{i}", {{ opacity: 1 }}, {B}.s + {at(cnt.get("at", 2.6))}); count("#cn{i}", {int(cnt["to"])}, {B}.s + {at(cnt.get("at", 2.6))}, 1.0);')
        return h + "</div>", "\n".join(js)
    if t == "flow":
        nodes = (card.get("nodes") or [])[:3]
        parts = []
        for n, nd in enumerate(nodes):
            lk = " lk" if nd.get("lock") else ""
            parts.append(f'<div class="nd{lk}" id="nd{i}_{n}">{html.escape(str(nd.get("title", "")))}<small>{html.escape(str(nd.get("sub", "")))}</small></div>')
            if n < len(nodes) - 1:
                parts.append(f'<svg class="ar" viewBox="0 0 100 40"><path id="ap{i}_{n}" d="M4 20 H88 M72 6 L90 20 L72 34" fill="none" stroke="#ff8a3d" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="190" stroke-dashoffset="190"/></svg>')
        win = f'<div class="win"><i></i><i></i><i></i><span>{html.escape(str(card.get("file", "how it flows")))}</span></div>'
        h = f'<div class="card" id="{cid}"><div class="cf"></div>{win}<div class="flow">{"".join(parts)}</div>'
        if card.get("note"):
            h += f'<div class="sub" id="sb{i}" style="text-align:center;margin-top:34px">{html.escape(str(card["note"]))}</div>'
        h += "</div>"
        offs = [.7, 1.5, 2.6]
        for n in range(len(nodes)):
            o = at(offs[n] if n < 3 else 2.6)
            js.append(f'tl.fromTo("#nd{i}_{n}", {{ opacity: 0, scale: .75 }}, {{ opacity: 1, scale: 1, duration: .4, ease: "back.out(2.4)" }}, {B}.s + {o});')
            if n < len(nodes) - 1:
                js.append(f'tl.to("#ap{i}_{n}", {{ strokeDashoffset: 0, duration: .45, ease: "power2.inOut" }}, {B}.s + {at(o + .4)});')
        if card.get("note"):
            js.append(f'tl.fromTo("#sb{i}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: .35 }}, {B}.s + {at(3.6)});')
        return h, "\n".join(js)
    if t == "gauge":
        win = f'<div class="win"><i></i><i></i><i></i><span>{html.escape(str(card.get("file", "result")))}</span></div>'
        gs = []
        for n, it in enumerate((card.get("items") or [])[:2]):
            col = html.escape(str(it.get("color", "#3ddc97")))
            gs.append(f'<div class="ga"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" fill="none" stroke="#2a1a12" stroke-width="12"/>'
                      f'<circle id="gr{i}_{n}" cx="60" cy="60" r="52" fill="none" stroke="{col}" stroke-width="12" stroke-linecap="round" '
                      f'stroke-dasharray="327" stroke-dashoffset="327" transform="rotate(-90 60 60)"/></svg><b id="gn{i}_{n}">0</b>'
                      f'<span>{html.escape(str(it.get("label", "")))}</span></div>')
            v = max(0, min(100, int(it.get("value", 0))))
            js.append(f'tl.to("#gr{i}_{n}", {{ strokeDashoffset: {327 * (1 - v / 100):.1f}, duration: 1.3, ease: "power2.out" }}, {B}.s + {at(.7 + .3 * n)}); count("#gn{i}_{n}", {v}, {B}.s + {at(.7 + .3 * n)}, 1.3);')
        h = f'<div class="card" id="{cid}"><div class="cf"></div>{win}<div class="gg">{"".join(gs)}</div>'
        if card.get("note"):
            h += f'<div class="sub" id="sb{i}" style="text-align:center;margin-top:18px">{html.escape(str(card["note"]))}</div>'
            js.append(f'tl.set("#sb{i}", {{ opacity: 1 }}, {B}.s + {at(2.4)});')
        return h + "</div>", "\n".join(js)
    if t == "video":
        chips = card.get("chips") or []
        ch = "".join(f'<span class="chp" id="ch{i}_{n}"><b id="cn{i}_{n}">0</b> {html.escape(str(c.get("label", "")))}</span>' for n, c in enumerate(chips))
        h = (f'<div class="card vid" id="{cid}"><div class="cf"></div>'
             f'<video id="wv{i}" class="clip" src="walk{i}.mp4" muted playsinline data-start="{starts[i]:.3f}" '
             f'data-duration="{ends[last] - starts[i]:.3f}" data-track-index="3"></video><div class="chips">{ch}</div></div>')
        for n, c in enumerate(chips):
            o = float(c.get("at", 0.9 + .6 * n))
            js.append(f'tl.fromTo("#ch{i}_{n}", {{ opacity: 0, y: 20, scale: .7 }}, {{ opacity: 1, y: 0, scale: 1, duration: .3, ease: "back.out(2.4)" }}, B[{i + int(c.get("beat", 0))}].s + {o}); '
                      f'count("#cn{i}_{n}", {int(c["to"])}, B[{i + int(c.get("beat", 0))}].s + {o + .05}, .9);')
        if chips:
            js.append(f'tl.to("#ch{i}_0, #ch{i}_{len(chips) - 1}", {{ opacity: 0, duration: .2 }}, B[{i + int(chips[-1].get("beat", 0))}].e - .1);')
        return h, "\n".join(js)
    if t in ("comment", "bio"):
        # comment: the comment-word offer. bio: "free guides, link in bio" (no word to type; title is the typed label)
        word = str(card.get("word", "GUIDE")).upper() if t == "comment" else str(card.get("title", "FREE GUIDES")).upper()
        label = "comments" if t == "comment" else "my profile"
        h = (f'<div class="card" id="{cid}"><div class="cf"></div><div class="win"><i></i><i></i><i></i><span>{label}</span></div>'
             f'<div class="bub" id="bb{i}"><span class="ty">{_typed(word)}</span></div><br/>'
             f'<div class="dm" id="dm{i}">{html.escape(str(card.get("reply", "Sent ✓")))}</div></div>')
        js = [f'card("#{cid}", {B}.s + .05, {B}.e + .3);',
              f'tl.fromTo("#bb{i}", {{ opacity: 0, scale: .4 }}, {{ opacity: 1, scale: 1, duration: .35, ease: "back.out(2.4)" }}, {B}.s + {at(.8)}); typeIn("#bb{i}", {B}.s + {at(1.0)}, .1);',
              f'tl.fromTo("#dm{i}", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: .35 }}, {B}.s + {at(1.9)});']
        return h, "\n".join(js)
    raise ValueError(f"unknown card type '{t}'")


def check_slides(slides: list[dict]) -> list[str]:
    e = []
    kinds = {"code", "flow", "gauge", "video", "comment", "bio"}
    span_end = 0   # last slide number covered by a video card's span
    for n, s in enumerate(slides, 1):
        s = s or {}
        _c = s.get("card")
        if _c:
            if _c.get("type") == "video":
                span_end = max(span_end, n + int(_c.get("span", 1)) - 1)
            else:
                span_end = max(span_end, n)
        elif n > span_end:
            e.append(f"teach slide {n}: needs a card (the renderer fails on a slide with no card and no video card spanning it)")
        if not s.get("say"):
            e.append(f"teach slide {n}: needs say")
        if not s.get("head"):
            e.append(f"teach slide {n}: needs head")
        c = s.get("card")
        if c and c.get("type", "code") not in kinds:
            e.append(f"teach slide {n}: card.type must be one of {sorted(kinds)}")
        if c and c.get("type") == "video":
            if not c.get("src") or not c.get("cuts"):
                e.append(f"teach slide {n}: video card needs src and cuts")
    if len(slides) > 8:
        e.append("teach: more than 8 slides; keep Reels under about 45 s")
    if slides and not any(((s or {}).get("card") or {}).get("type") in ("comment", "bio") for s in slides):
        e.append("teach: the last slide should be a bio card (free guide, link in bio) or a comment card (word + reply)")
    return e


def build_project(slides: list[dict], total: float, starts: list[float], ends: list[float], words: list[dict],
                  work: Path) -> Path:
    proj = work / "hf-teach"
    (proj / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy(HF / "shared" / "gsap.min.js", proj / "gsap.min.js")
    shutil.copy(HF / "shared" / "three.min.js", proj / "three.min.js")
    shutil.copy(HF / "promo" / "hyperframes.json", proj / "hyperframes.json")
    shutil.copy(ROOT / "assets" / "fonts" / "DejaVuSansMono.ttf", proj / "assets" / "fonts" / "DejaVuSansMono.ttf")
    shutil.copy(work / "talk.mp4", proj / "talk.mp4")
    n = len(slides)
    cards_html, cards_js, cardof, land = [], [], [], []
    cur, span_end = None, -1
    for i, s in enumerate(slides):
        c = (s or {}).get("card")
        if c:
            span = int(c.get("span", 1)) if c.get("type") == "video" else 1
            if c.get("type") == "video":
                src = ROOT / str(c["src"])
                if not src.exists():
                    raise FileNotFoundError(f"teach slide {i + 1}: {c['src']} not found")
                cuts = [float(x) for x in c["cuts"]]
                parts = []
                for k, st in enumerate(cuts[:span]):
                    seg = work / f"seg{i}_{k}.mp4"
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{st:.3f}", "-t", f"{ends[i + k] - starts[i + k]:.3f}",
                                    "-i", str(src), "-an", "-vf", "scale=940:529:force_original_aspect_ratio=increase,crop=940:529,fps=30",
                                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(seg)], check=True)
                    parts.append(seg)
                lst = work / f"seg{i}.txt"
                lst.write_text("".join(f"file '{p}'\n" for p in parts))
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                                str(proj / f"walk{i}.mp4")], check=True)
                cur, span_end = i, i + span - 1
                land_t = .12
            else:
                cur, span_end, land_t = i, i, .65
            h, j = _card(i, ends[i] - starts[i], c, span, starts, ends)
            cards_html.append(h)
            cards_js.append(j)
        elif cur is None or i > span_end:
            raise ValueError(f"teach slide {i + 1} has no card and no video card spanning it")
        else:
            land_t = .12
        cardof.append(f"#c{cur}")
        land.append(land_t)
    # words -> chunks of up to 3, breaking at punctuation and at the end of each spoken line
    line_of = []
    for w in words:
        k = max(j for j in range(n) if starts[j] <= w["start"] + 1e-6) if words else 0
        line_of.append(k)
    chunks, cur_c = [], []
    for wi, w in enumerate(words):
        cur_c.append(wi)
        end_line = wi + 1 == len(words) or line_of[wi + 1] != line_of[wi]
        if len(cur_c) >= 3 or end_line or re.search(r"[.,?!]$", w["word"]):
            chunks.append(cur_c); cur_c = []
    cap_html = "".join(f'<div class="cc" id="cc{ci}">' + "".join(f'<span class="cw" id="w{wi}">{html.escape(words[wi]["word"])}</span>' for wi in ch) + "</div>"
                       for ci, ch in enumerate(chunks))
    segs = "".join(f'<i class="sg"><u id="sg{i}"></u></i>' for i in range(n))
    tags = "".join(f'<span class="tg" id="tg{i}"><b>{i + 1}</b>{html.escape(str((s or {}).get("tag") or ""))}</span>' for i, s in enumerate(slides))
    heads = "".join(f'<div class="hd" id="hd{i}">{_head_html(str(s["head"]))}</div>' for i, s in enumerate(slides))
    D = {"name": "teach", "total": round(total, 2), "cardof": cardof, "land": land,
         "beats": [{"s": round(starts[i], 3), "e": round(ends[i], 3)} for i in range(n)],
         "words": [{"s": round(w["start"], 3), "e": round(w["end"], 3)} for w in words], "chunks": chunks}
    head = (HF / "teach" / "head.js").read_text().replace("%%D%%", json.dumps(D))
    js = head + "\n" + "\n".join(cards_js) + "\n" + (HF / "teach" / "gl.js").read_text()
    css = (HF / "teach" / "teach.css").read_text()
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=1080, height=1920"/>
<script src="gsap.min.js"></script><script src="three.min.js"></script><style>{css}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{round(total, 2)}" data-width="1080" data-height="1920" data-fps="30">
 <div id="stage" style="position:absolute;inset:0">
  <canvas id="gl" class="bgc"></canvas>
  <div class="sgs">{segs}</div>
  <div class="tags">{tags}</div>
  <div class="heads">{heads}</div>
  <div class="cz">{"".join(cards_html)}</div>
  <div class="win2"><video id="tv" class="clip" src="talk.mp4" muted playsinline data-start="0" data-duration="{round(total, 2)}" data-track-index="1"></video><div class="caps">{cap_html}</div></div>
 </div>
</div>
<script>{js}</script>
</body></html>'''
    (proj / "index.html").write_text(page)
    return proj


def teach_video(slides: list[dict], app: str, out: Path, mood: str | None, fixes: dict | None = None) -> Path:
    """The mascot teaches in your voice. Same voice, captions-from-words, mascot talk clip and sound as the story reels."""
    from . import talkclip
    from .hyperframes import THEMES, _shade, impact_file, render_project
    from .tts import synthesize
    from .video import _impacts, _run, mux_audio, plan_seconds, transcribe
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        lines = [str(s.get("say") or "") for s in slides]
        voice = synthesize(lines, tmp_p / "voice", "story")
        secs = plan_seconds(len(slides), [float(s.get("seconds") or 4.0) for s in slides], voice, 0.0, LEAD, 0.2)
        total = sum(secs)
        starts, t = [], 0.0
        for d in secs:
            starts.append(t); t += d
        cmd = ["ffmpeg", "-y", "-hide_banner"]
        parts, labels, idx = [], [], 0
        for i, c in enumerate(voice):
            if c:
                cmd += ["-i", str(c)]
                ms = int((starts[i] + LEAD) * 1000)
                parts.append(f"[{idx}:a]aresample=44100,aformat=channel_layouts=mono,adelay={ms}|{ms}[v{i}]")
                labels.append(f"[v{i}]"); idx += 1
        vall = tmp_p / "voice_all.wav"
        parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad=whole_dur={total:.3f},atrim=0:{total:.3f}[o]")
        _run(cmd + ["-filter_complex", ";".join(parts), "-map", "[o]", str(vall)])
        words = transcribe(vall, " ".join(l for l in lines if l.strip()), fixes)
        th = THEMES.get(app, THEMES["personal"])
        imp, extra = _impacts(slides, starts, secs, words, "harsh", LEAD)
        src = talkclip.Source(tmp_p)
        o = talkclip.voice_openness(vall, total)
        pos = talkclip.plan_natural(o, src.mouth, speed=25 / 30)
        talkclip.render_clip(src, pos, tmp_p / "talk.mp4", "#ff8a3d", _shade("#ff8a3d", .55),
                             [{"t": x["t"], "d": x["d"], "image": impact_file("harsh", x["name"]), "video": talkclip.reaction_video(x["name"])} for x in imp])
        ends = [s0 + d for s0, d in zip(starts, secs)]
        proj = build_project(slides, total, [s0 - 0.0 for s0 in starts], ends, words, tmp_p)
        silent = tmp_p / "picture.mp4"
        render_project(proj, silent, "looks")
        key = "/".join(out.parts[-4:-1])
        mux_audio(silent, out, secs, 0.0, voice, mood, key, lead=LEAD, sfx=True, extra_cues=extra)
    return out
