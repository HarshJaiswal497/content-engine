"""One-off (CI): Slip lines in several Kokoro preset voices. Usage: python tools/slip_voices.py <out_dir>"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from pathlib import Path
import numpy as np, soundfile as sf
from kokoro import KPipeline

LINES = ["Hi! I'm Slip. Let's fix that.", "Don't text. Doodle!", "It lands on their home screen. No interrupting.", "In development. Waitlist in bio!"]
VOICES = ["af_heart", "af_bella", "af_nicole", "af_sky", "af_sarah", "af_nova", "bf_lily", "bf_emma"]
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for v in VOICES:
    try:
        pipe = KPipeline(lang_code=v[0])
        gap = np.zeros(int(24000 * 0.5), dtype="float32")
        parts = []
        for line in LINES:
            parts += [np.concatenate([a for _, _, a in pipe(line, voice=v, speed=1.05)]), gap]
        sf.write(out / f"slip-{v}.wav", np.concatenate(parts), 24000)
        print("ok", v, flush=True)
    except Exception as e:
        print("failed", v, e, flush=True)
