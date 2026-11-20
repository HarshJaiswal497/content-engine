"""Render media for every unpublished post whose content changed.

python -m engine.render [--upload] [--force] [paths...]
  --upload  push videos to the repo's 'media' release instead of keeping them in git (CI uses this)
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from .. import github, state
from ..post import Post, all_posts, load
from .slides import THEMES, render_post_slides
from .video import caption_video, caption_video_motion, skit_video, story_video, mood_for, mux_audio, plan_seconds, slides_to_video, video_style


def _clean(asset_dir: Path) -> None:
    for p in list(asset_dir.glob("slide-*.jpg")) + [asset_dir / "video.mp4", asset_dir / "video.json", asset_dir / "captions.txt",
                                                     asset_dir / "cover.jpg", asset_dir / ".render-hash"]:
        p.unlink(missing_ok=True)


def _finish_video(post: Post, mp4: Path, upload: bool) -> None:
    if upload:
        date = post.path.parent.name
        ref = github.upload_media(mp4, f"{date}__{post.path.stem}__{post.render_hash()}.mp4")
        (post.asset_dir / "video.json").write_text(__import__("json").dumps(ref, indent=2))
        mp4.unlink(missing_ok=True)


def render(post: Post, upload: bool, force: bool, seen: set[str]) -> str:
    if post.id in seen:
        return "already done"
    seen.add(post.id)
    if post.errors:
        return "invalid: " + "; ".join(post.errors)
    if post.is_rendered() and not force:
        return "up to date"
    if not (post.needs_images or post.needs_video):
        return "no media"

    spec = post.video_spec
    kind = spec.get("kind")
    if post.needs_video and kind in {"recording", "talking_head"} and post.awaiting_recording():
        return f"waiting for {spec.get('source')}"

    post.asset_dir.mkdir(parents=True, exist_ok=True)
    _clean(post.asset_dir)
    slides = post.data.get("slides") or []

    if post.needs_images:
        render_post_slides(slides, post.app, post.asset_dir, "feed")

    if post.needs_video:
        mp4 = post.asset_dir / "video.mp4"
        if kind == "slides":
            with tempfile.TemporaryDirectory() as tmp:
                secs = [float(s.get("seconds", spec.get("seconds_per_slide", 3.2))) for s in slides]
                lines = [str(s.get("say") or "") for s in slides]
                voice = None
                if any(lines) and spec.get("voice", True):
                    from .tts import synthesize
                    voice = synthesize(lines, Path(tmp) / "voice", spec.get("tone", "story"))
                done = False
                if video_style(spec, post.path.parent.name) == "motion":   # HyperFrames picture + the same voice and music
                    try:
                        from .hyperframes import FADE, LEAD, TAIL, render_motion
                        mseconds = plan_seconds(len(slides), secs, voice, FADE, LEAD, TAIL)
                        silent = Path(tmp) / "picture.mp4"
                        render_motion(slides, post.app, mseconds, FADE, silent, Path(tmp))
                        mux_audio(silent, mp4, mseconds, FADE, voice, mood_for(spec.get("tone"), post.app),
                                  "/".join(mp4.parts[-4:-1]), lead=LEAD, sfx=True)
                        done = True
                    except Exception:   # never lose a post over the fancy renderer: fall back to the classic look
                        print(f"{post.id}: motion render failed, using classic slides\n{traceback.format_exc()[-1500:]}", flush=True)
                if not done:
                    imgs = render_post_slides(slides, post.app, Path(tmp), "vertical")
                    slides_to_video(imgs, mp4, secs, voice=voice, mood=mood_for(spec.get("tone"), post.app))
            _finish_video(post, mp4, upload)
        elif kind == "voice":   # your cloned voice reading the slides' `say` lines: an audio-only file to drive talking clips
            import subprocess
            from .tts import synthesize
            with tempfile.TemporaryDirectory() as tmp:
                voice = [v for v in synthesize([str(s.get("say") or "") for s in slides], Path(tmp) / "voice", spec.get("tone", "calm")) if v]
                cmd, parts = ["ffmpeg", "-y", "-hide_banner", "-v", "error"], []
                for i, v in enumerate(voice):
                    cmd += ["-i", str(v)]
                    parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur=0.6[a{i}]")
                chain = "".join(f"[a{i}]" for i in range(len(voice)))
                parts.append(f"{chain}concat=n={len(voice)}:v=0:a=1,highpass=f=85,loudnorm=I=-16:TP=-1.5[o]")
                subprocess.run(cmd + ["-filter_complex", ";".join(parts), "-map", "[o]", "-c:a", "aac", "-b:a", "192k", str(mp4)], check=True)
            _finish_video(post, mp4, upload)
        elif kind == "skit":
            skit_video(spec.get("beats") or [], post.app, mp4, mood_for(spec.get("tone"), post.app), spec.get("title"),
                       voices=spec.get("voice", True))
            _finish_video(post, mp4, upload)
        elif kind == "story":
            sp = None
            beats = spec.get("beats") or []
            if spec.get("speaker") == "mascot":   # the mascot presents: beats come from the slides unless given
                from .hyperframes import beats_from_slides
                sp = "mascot"
                beats = beats or beats_from_slides(slides, post.app)
            elif spec.get("speaker"):
                from ..config import ROOT
                sp = ROOT / spec["speaker"]
                if not sp.exists():
                    return f"waiting for the speaker clip {spec['speaker']}"
            story_video(beats, post.app, mp4, mood_for(spec.get("tone"), post.app),
                        spec.get("mascot", "slip" if post.app == "slipnote" else "bo"), sp, voices=spec.get("voice", True),
                        script=spec.get("script"), fixes=spec.get("caption_fixes"), emphasis=spec.get("emphasis"))
            _finish_video(post, mp4, upload)
        elif kind in {"recording", "talking_head"}:
            accent = THEMES.get(post.app, THEMES["personal"]).accent
            done = False
            if spec.get("captions", True) and video_style(spec, post.path.parent.name) == "motion":
                try:
                    caption_video_motion(post.video_source(), mp4, post.app, hook=spec.get("hook"),
                                         mood=mood_for(spec.get("tone"), post.app), script=spec.get("script"),
                                         fixes=spec.get("caption_fixes"), inserts=spec.get("inserts"),
                                         emphasis=spec.get("emphasis"), zoom=spec.get("zoom", True))
                    done = True
                except Exception:   # fall back to the classic caption burn-in
                    print(f"{post.id}: motion captions failed, using classic\n{traceback.format_exc()[-1500:]}", flush=True)
            if not done:
                caption_video(post.video_source(), mp4, hook=spec.get("hook"), accent=accent,
                              captions=spec.get("captions", True), mood=mood_for(spec.get("tone"), post.app),
                              script=spec.get("script"), fixes=spec.get("caption_fixes"))
            _finish_video(post, mp4, upload)
        elif kind == "same_as":
            sib_path = post.path.parent / f"{spec['post']}.yml"
            sib = load(sib_path)
            msg = render(sib, upload, False, seen)
            if not sib.is_rendered():
                return f"waiting for sibling {sib.id} ({msg})"
            for name in ("video.json", "video.mp4"):
                if (sib.asset_dir / name).exists():
                    shutil.copy(sib.asset_dir / name, post.asset_dir / name)

    if post.format in {"reel", "short"}:   # a cover for the Reel / the YouTube upload; never blocks the post
        try:
            from .cover import make_cover
            make_cover(post)
        except Exception:
            print(f"{post.id}: cover failed, Instagram will pick a frame\n{traceback.format_exc()[-1200:]}", flush=True)

    (post.asset_dir / ".render-hash").write_text(post.render_hash())
    return "rendered"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    log = state.load()
    posts = [load(Path(p)) for p in args.paths] if args.paths else all_posts()
    seen: set[str] = set()
    errors = 0
    for post in posts:
        if state.is_done(log.get(post.id)):
            continue
        try:
            msg = render(post, args.upload, args.force, seen)
        except Exception as exc:
            errors += 1
            traceback.print_exc()
            msg = f"ERROR {exc}"
        print(f"{post.id}: {msg}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
