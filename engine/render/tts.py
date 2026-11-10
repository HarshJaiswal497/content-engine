"""Voiceover for slide videos: one audio clip per slide, from the slide's `say:` line.

Engines (set in brand/voice.yml):
  chatterbox  open-source (MIT). With a voice sample it speaks in YOUR voice: the sample is kept
              encrypted in assets/voice/ and unlocked with the VOICE_PRIVATE_KEY secret.
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
REFERENCE_KEY = ROOT / "assets" / "voice" / "reference.key.enc"
CONFIG = ROOT / "brand" / "voice.yml"
# How expressive the delivery is, per post tone (Chatterbox "exaggeration").
TONES = {"calm": 0.4, "story": 0.5, "upbeat": 0.65}


def config() -> dict:
    return (yaml.safe_load(CONFIG.read_text()) or {}) if CONFIG.exists() else {}


def engine() -> str:
    return str(config().get("engine") or "chatterbox").lower()


def _decrypt_reference(tmp: Path) -> Path | None:
    """Unlock the voice sample. reference.enc is AES-encrypted; its AES key (reference.key.enc) is locked
    with assets/voice/public.pem, whose private half exists only in the VOICE_PRIVATE_KEY secret."""
    priv = os.environ.get("VOICE_PRIVATE_KEY")
    if not (priv and REFERENCE.exists() and REFERENCE_KEY.exists()):
        return None
    pem = tmp / "voice.pem"
    pem.write_text(priv)
    pem.chmod(0o600)
    aes = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(pem), "-pkeyopt", "rsa_padding_mode:oaep",
                          "-in", str(REFERENCE_KEY)], check=True, capture_output=True).stdout.decode().strip()
    pem.unlink()
    out = tmp / "reference.wav"
    subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-pass", "env:VOICE_AES",
                    "-in", str(REFERENCE), "-out", str(out)], check=True, env={**os.environ, "VOICE_AES": aes})
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


def _trim_silence(path: Path) -> None:
    """Cut the silence the voice model leaves before and after a line, so lines can follow each other naturally."""
    tmp = path.with_suffix(".trim.wav")
    cut = "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af", f"{cut},areverse,{cut},areverse", str(tmp)],
                       capture_output=True)
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1000:
        tmp.replace(path)
    tmp.unlink(missing_ok=True)


def synthesize(lines: list[str], out_dir: Path, tone: str = "story") -> list[Path | None]:
    """Write one WAV per non-empty line into out_dir; returns paths (None for empty lines)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path | None] = []
    with tempfile.TemporaryDirectory() as tmp:
        ref = _decrypt_reference(Path(tmp)) if engine() == "chatterbox" else None
        print(f"voiceover: {engine()}, {'Harsh’s voice sample' if ref else 'default narrator'}", flush=True)
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
            _trim_silence(out)
            paths.append(out)
    return paths


def voice_fingerprint() -> str:
    """Part of the render hash, so changing engine, narrator or voice sample re-renders videos."""
    ref = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()[:8] if REFERENCE.exists() else "-"
    cfg = hashlib.sha256(CONFIG.read_bytes()).hexdigest()[:8] if CONFIG.exists() else "-"
    return f"{cfg}:{ref}"


def _cute(path: Path, pitch: float, speed: float) -> None:
    if pitch == 1.0 and speed == 1.0:
        return
    """Make a voice smaller and sweeter: raise pitch (asetrate), keep it light on speed."""
    tmp = path.with_suffix(".cute.wav")
    sr = 24000
    af = f"asetrate={int(sr * pitch)},aresample=24000,atempo={speed / pitch:.4f}"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af", af, str(tmp)], capture_output=True)
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1000:
        tmp.replace(path)
    tmp.unlink(missing_ok=True)


SLIP_REF_LINES = ["Hi! I'm Slip! Let's fix that!", "Don't text! Doodle!"]


def _slip_reference(tmp: Path, voice: str) -> Path:
    """A short clip of Kokoro's preset girl voice, used as the sound for Chatterbox to copy."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipe = KPipeline(lang_code=voice[0])
    audio = np.concatenate([a for line in SLIP_REF_LINES for _, _, a in pipe(line, voice=voice, speed=1.05)])
    ref = tmp / "slip-ref.wav"
    sf.write(ref, audio, 24000)
    return ref


def skit_voices(beats: list[dict], out_dir: Path) -> list[Path | None]:
    """One WAV per beat. The human speaks in Harsh's cloned voice. Slip is Chatterbox copying Kokoro's sweet
    `af_heart` voice with a lively, excited delivery (picked by Harsh, 4 Nov: "C chatterbox heart lively").
    Tune in brand/voice.yml -> slip: {voice, exaggeration}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = config()
    slip = {"voice": "af_heart", "exaggeration": 0.85, "cfg_weight": 0.3, **(cfg.get("slip") or {})}
    human_ex = float(cfg.get("exaggeration") if cfg.get("exaggeration") is not None else 0.5)
    paths: list[Path | None] = []
    import torchaudio
    with tempfile.TemporaryDirectory() as tmp:
        ref = _decrypt_reference(Path(tmp))
        slip_ref = _slip_reference(Path(tmp), str(slip["voice"])) if any(b.get("who") == "slip" for b in beats) else None
        print(f"skit voices: human={'Harsh’s voice sample' if ref else 'default'}, slip=chatterbox copying {slip['voice']}", flush=True)
        model = _chatterbox()
        for i, b in enumerate(beats):
            line = re.sub(r"[*_]", "", str(b.get("say") or b.get("text") or "")).strip()
            if not line or b.get("voice") is False:
                paths.append(None)
                continue
            for word, spoken in (cfg.get("pronounce") or {}).items():
                line = re.sub(rf"\b{re.escape(word)}\b", spoken, line)
            out = out_dir / f"beat-{i + 1}.wav"
            if b.get("who") == "slip":
                line = re.sub(r"\.(\s|$)", r"!\1", line)   # Slip is excited: full stops become exclamations
                wav = model.generate(line, audio_prompt_path=str(slip_ref), exaggeration=float(slip["exaggeration"]),
                                     cfg_weight=float(slip["cfg_weight"]))
            else:
                kw = {"exaggeration": human_ex, "cfg_weight": 0.4}
                if ref:
                    kw["audio_prompt_path"] = str(ref)
                wav = model.generate(line, **kw)
            torchaudio.save(str(out), wav, model.sr)
            _trim_silence(out)
            paths.append(out)
    return paths
