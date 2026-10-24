"""Voiceover for slide videos: one audio clip per slide, from the slide's `say:` line.

Engines (set in brand/voice.yml):
  chatterbox  open-source (MIT). With a voice sample it speaks in YOUR voice: the sample is kept
              encrypted in assets/voice/reference.enc and unlocked with the VOICE_KEY secret.
              Without a sample it uses its default narrator.
  kokoro      open-source (Apache 2.0), fast preset narrators; `narrator:` picks one (e.g. am_michael).

Requires requirements-voice.txt (installed by the render workflow).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import ROOT

REFERENCE = ROOT / "assets" / "voice" / "reference.enc"
CONFIG = ROOT / "brand" / "voice.yml"
# How expressive the delivery is, per post tone (Chatterbox "exaggeration").
TONES = {"calm": 0.4, "story": 0.5, "upbeat": 0.65}


def config() -> dict:
    return (yaml.safe_load(CONFIG.read_text()) or {}) if CONFIG.exists() else {}


def engine() -> str:
    return str(config().get("engine") or "chatterbox").lower()


def _decrypt_reference(tmp: Path) -> Path | None:
    key = os.environ.get("VOICE_KEY")
    if not (key and REFERENCE.exists()):
        return None
    out = tmp / "reference.wav"
    subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-pass", "env:VOICE_KEY",
                    "-in", str(REFERENCE), "-out", str(out)], check=True, env={**os.environ, "VOICE_KEY": key})
    return out


@lru_cache(maxsize=1)
def _chatterbox():
    from chatterbox.tts import ChatterboxTTS
    return ChatterboxTTS.from_pretrained(device="cpu")


@lru_cache(maxsize=1)
def _kokoro():
    from kokoro import KPipeline
    voice = str(config().get("narrator") or "am_michael")
    return KPipeline(lang_code=voice[0]), voice


def synthesize(lines: list[str], out_dir: Path, tone: str = "story") -> list[Path | None]:
    """Write one WAV per non-empty line into out_dir; returns paths (None for empty lines)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path | None] = []
    with tempfile.TemporaryDirectory() as tmp:
        ref = _decrypt_reference(Path(tmp)) if engine() == "chatterbox" else None
        for i, line in enumerate(lines):
            line = (line or "").strip()
            if not line:
                paths.append(None)
                continue
            for word, spoken in (config().get("pronounce") or {}).items():
                line = re.sub(rf"\b{re.escape(word)}\b", spoken, line)
            out = out_dir / f"say-{i + 1}.wav"
            if engine() == "kokoro":
                import numpy as np
                import soundfile as sf
                pipe, voice = _kokoro()
                audio = np.concatenate([a for _, _, a in pipe(line, voice=voice)])
                sf.write(out, audio, 24000)
            else:
                import torchaudio
                model = _chatterbox()
                ex = config().get("exaggeration")  # a fixed delivery for every video, if set
                kw = {"exaggeration": float(ex) if ex is not None else TONES.get(tone, 0.5), "cfg_weight": 0.4}
                if ref:
                    kw["audio_prompt_path"] = str(ref)
                torchaudio.save(str(out), model.generate(line, **kw), model.sr)
            paths.append(out)
    return paths


def voice_fingerprint() -> str:
    """Part of the render hash, so changing engine, narrator or voice sample re-renders videos."""
    ref = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()[:8] if REFERENCE.exists() else "-"
    cfg = hashlib.sha256(CONFIG.read_bytes()).hexdigest()[:8] if CONFIG.exists() else "-"
    return f"{cfg}:{ref}"
