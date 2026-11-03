# hf/: HyperFrames video templates

HyperFrames turns HTML into video (frame-exact, free, runs in GitHub Actions). Each folder here is one template.

| Folder | What | Status |
|---|---|---|
| `shared/` | Files every template uses (GSAP animation library) | in use |
| `promo/` | Faceless Reels/Shorts from a post's `slides:`: kinetic titles, filled highlight pills, wipes between scenes, iris into the end card. Templates are in `promo/templates/` (`cover`, `point`, `cta`, `base.css`). | built; off by default |
| `talking-head/` | Your clip with styled captions, punch-in zooms, titles | planned |
| `skit/` | Original characters, speech bubbles, sound effects | planned |

## How a post uses it
Nothing changes in a post file. A `video: {kind: slides}` post is rendered by `promo/` when its style is `motion`:
- globally: `slides_style: motion` in `brand/video-styles.yml`
- per post: `video: {style: motion}` (or `style: slides` to keep the classic look)

The bridge is `engine/render/hyperframes.py`: it fills the templates from the slides (colours from the app theme in `engine/render/slides.py`), writes a throwaway HyperFrames project, renders a silent 1080x1920 30 fps video, and `engine/render/video.py` (`mux_audio`) adds the voiceover and music exactly as before.

## Editing a template
Edit the `.html`/`.css` in `promo/templates/`. `{{TOKENS}}` are filled by the bridge. Rules that matter: every scene builds one paused GSAP timeline, no `Math.random`/`Date.now`, ids are prefixed with the scene id (`{{ID}}-…`), key content stays inside y 168-1330 (Instagram's UI covers the rest).

## Try it locally
Needs Node 22+, ffmpeg and Chrome (`HYPERFRAMES_BROWSER_PATH`). `pip install -r requirements.txt`, then call `engine.render.hyperframes.render_motion(...)` (see `tests/test_engine.py` for the project builder).

## Talking-head (hf/talking-head/)

Clips (`kind: talking_head` / `recording`) get word-highlight captions, punch-in zooms at each sentence start,
a hook pill and optional phone-screen inserts. On from `motion_from` in `brand/video-styles.yml` (or `video.style: motion`);
any failure falls back to the classic burn-in. Optional post fields under `video:`:

- `inserts: [{at: 8, dur: 3.5, screen: today, focus: start-button, label: Resume}]` (screens from `brand/screens.yml`)
- `emphasis: [closed, free]` extra zoom while those words are spoken

## Skit (hf/skit/)

`video.kind: skit` — Slip and a human talk in speech bubbles, with a music bed and tiny sound effects. Characters live in
`assets/characters/` (see its README). Beats:

```yaml
video:
  kind: skit
  title: optional
  beats:
    - {who: human, pose: phone, text: "My workout *vanished*?!", seconds: 3, other_pose: surprised, sfx: dun}
    - {who: slip, pose: wave, text: "Hi, I'm Slip."}      # sfx: pop (default) | ping | dun | none
```
`*word*` gets the accent highlight. Slip poses: idle happy wave surprised think write sleepy sad peek cheer.
Human poses: idle talk shocked happy sad phone think. Skits are not date-gated: a post opts in with `kind: skit`.
