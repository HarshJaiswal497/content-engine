"""Try the voiceover engines on GitHub Actions and save samples (used once to pick a voice)."""
import os, sys, time
import soundfile as sf

LINES = [
    "My app tells me exactly what to lift today.",
    "Did eight, eight and seven last time? Today it asks for nine, nine and eight. Same weight, one more rep.",
    "Hit every set? Then it's time to go heavier, by one small step.",
    "And warm-ups don't count. Only your working sets decide.",
    "It's called Setalytix, and it's free. Link's in the description.",
]
os.makedirs("samples", exist_ok=True)
engine = sys.argv[1]
t = time.time()
if engine == "chatterbox":
    from chatterbox.tts import ChatterboxTTS
    import torch, torchaudio
    m = ChatterboxTTS.from_pretrained(device="cpu")
    print("load", round(time.time() - t, 1), flush=True)
    for ex in (0.45, 0.65):
        t = time.time()
        wavs = [m.generate(l, exaggeration=ex, cfg_weight=0.4) for l in LINES]
        torchaudio.save(f"samples/chatterbox-ex{ex}.wav", torch.cat(wavs, dim=1), m.sr)
        print("chatterbox", ex, "gen", round(time.time() - t, 1), flush=True)
else:
    from kokoro import KPipeline
    import numpy as np
    p = KPipeline(lang_code=engine[0])  # 'a' american, 'b' british
    voices = {"a": ["am_michael", "am_fenrir", "af_heart"], "b": ["bm_george", "bm_fable"]}[engine[0]]
    print("load", round(time.time() - t, 1), flush=True)
    for v in voices:
        t = time.time()
        audio = np.concatenate([a for l in LINES for _, _, a in p(l, voice=v)])
        sf.write(f"samples/kokoro-{v}.wav", audio, 24000)
        print("kokoro", v, "gen", round(time.time() - t, 1), "len", round(len(audio) / 24000, 1), flush=True)
