# Characters

`slip/` — Slip, the Slipnote paper-note mascot, as SVG (editable) and transparent PNG (600 px wide).
Poses: idle, happy, wave, surprised, think, write, sleepy, sad, peek, cheer.
Regenerate: `python tools/make_slip.py && python tools/render_svgs.py assets/characters/slip`.
Add a pose by adding an entry to `POSES` in `tools/make_slip.py`.

`harsh/` — the real mascot (cut-outs of Harsh, WebP). `MANIFEST.md` lists every image with its original file name and what it shows.
Folders: `expressions/`, `mouths/` (7 mouth shapes), `face/` (non-speaking faces), `eyes/`, `gestures/`, `fullbody/` — still images; the expression, face and gesture
stills are used as reaction pops.
`talk_source/mascot_talking_calm.mp4` — the green-screen talking video (not lip-synced; plays at its own speed, `engine/render/talkclip.py`).
`reactions/*.mp4` — green-screen reaction videos (cheer, shocked, shrug, point_down), matched to the talker's size and cross-faded in.
Rebuild the stills: `python tools/prepare_mascot.py <unzipped dir> <loose png dir>`.
