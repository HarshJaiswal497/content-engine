"""One-off (CI): ways to make Slip's af_heart voice cuter and more excited. Usage: python tools/slip_voices.py <out_dir>"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import subprocess
from pathlib import Path
import numpy as np, soundfile as sf

LINES = ["Hi! I'm Slip! Let's fix that!", "Don't text! Doodle!", "It lands on their home screen! No interrupting!", "In development! Waitlist in bio!"]
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
gap = np.zeros(int(24000 * 0.5), dtype="float32")


def kokoro_lines(speed):
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="a")
    return [np.concatenate([a for _, _, a in pipe(l, voice="af_heart", speed=speed)]) for l in LINES]


def save(name, parts, pitch=None):
    p = out / f"{name}.wav"
    sf.write(p, np.concatenate([x for a in parts for x in (a, gap)]), 24000)
    if pitch:
        t = out / "t.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-af", f"asetrate={int(24000*pitch)},aresample=24000,atempo={1/pitch:.4f}", str(t)], check=True)
        t.replace(p)


try:
    base = kokoro_lines(1.15)
    save("A-heart-fast-excited", base)
    save("B-heart-fast-pitch-up-8pct", base, 1.08)
except Exception as e:
    print("kokoro failed", e, flush=True)

try:   # Chatterbox, copying the af_heart voice, with a lively delivery
    import torchaudio
    from chatterbox.tts import ChatterboxTTS
    ref = out / "ref.wav"
    sf.write(ref, np.concatenate(kokoro_lines(1.05)[:2]), 24000)
    model = ChatterboxTTS.from_pretrained(device="cpu")
    for name, ex in (("C-chatterbox-heart-lively", 0.85), ("D-chatterbox-heart-very-excited", 1.1)):
        parts = []
        for l in LINES:
            w = model.generate(l, audio_prompt_path=str(ref), exaggeration=ex, cfg_weight=0.3)
            parts.append(w.squeeze().numpy())
        sf.write(out / f"{name}.wav", np.concatenate([x for a in parts for x in (a, np.zeros(int(model.sr * 0.5), dtype="float32"))]), model.sr)
    ref.unlink()
except Exception as e:
    print("chatterbox failed", e, flush=True)
