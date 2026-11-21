# Characters

`slip/` — Slip, the Slipnote paper-note mascot, as SVG (editable) and transparent PNG (600 px wide).
Poses: idle, happy, wave, surprised, think, write, sleepy, sad, peek, cheer.
Regenerate: `python tools/make_slip.py && python tools/render_svgs.py assets/characters/slip`.
Add a pose by adding an entry to `POSES` in `tools/make_slip.py`.

`harsh/` — the real mascot (cut-outs of Harsh, WebP). `MANIFEST.md` lists every image with its original file name and what it shows.
Folders: `expressions/`, `mouths/` (7 mouth shapes), `face/` (non-speaking faces), `eyes/`, `gestures/`, `talk/` (generated lip-sync frames).
Rebuild: `python tools/prepare_mascot.py <unzipped dir> <loose png dir>` then `python tools/build_talk.py`.
`talk/<set>-v0..v6.webp` are the base pose with only the mouth patch swapped (aligned), so the head never jitters.
`harsh-cartoon/` — the earlier drawn cartoon version (`tools/make_harsh.py`); not used by default.
