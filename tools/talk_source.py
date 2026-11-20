"""Prepare the green-screen talking video of the mascot for lip-sync re-timing.

  python tools/talk_source.py <video.mp4> <out dir>

Writes <out>/rgba/0000.png.. (1080x1080 cut-outs, green removed with spill suppression) and <out>/analysis.npz:
  mouth  per-frame mouth openness 0..1 (PCA of the mouth region, sign set by the audio loudness)
  audio  per-frame loudness 0..1 of the video's own voice
  fps, n
"""
import subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

CROP_X, SIZE = 420, 1080            # the character sits in x 428..1485 of the 1920x1080 frame
BG = np.array([35, 176, 74], np.float32)
ROI = (470, 540, 650, 670)          # mouth region (x0, y0, x1, y1) in the 1080 crop


def key(rgb: np.ndarray):
    f = rgb.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    gd = g - np.maximum(r, b)
    a = 1.0 - np.clip((gd - 14.0) / 62.0, 0, 1)
    # spill: pull green down to the other channels where it leaks into hair/skin edges
    g2 = np.minimum(g, np.maximum(r, b) + 6.0)
    out = np.stack([r, g2, b], -1)
    return np.dstack([out, a * 255]).clip(0, 255).astype(np.uint8)


def main(video: str, out: str):
    out = Path(out); (out / "rgba").mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"crop={SIZE}:{SIZE}:{CROP_X}:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    feats, i = [], 0
    n_bytes = SIZE * SIZE * 3
    while True:
        buf = p.stdout.read(n_bytes)
        if len(buf) < n_bytes:
            break
        rgb = np.frombuffer(buf, np.uint8).reshape(SIZE, SIZE, 3)
        Image.fromarray(key(rgb), "RGBA").save(out / "rgba" / f"{i:04d}.png", compress_level=1)
        x0, y0, x1, y1 = ROI
        g = np.asarray(Image.fromarray(rgb[y0:y1, x0:x1]).convert("L").resize((36, 26)), np.float32)
        feats.append(g.ravel())
        i += 1
    F = np.array(feats)
    F -= F.mean(0)
    u, s, vt = np.linalg.svd(F, full_matrices=False)
    m = u[:, 0] * s[0]
    # audio loudness per video frame
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 16000 // 30
    k = min(len(x) // hop, i)
    rms = np.sqrt((x[:k * hop].reshape(k, hop) ** 2).mean(1))
    rms = np.pad(rms, (0, i - k))
    # sign and lag: the mouth curve that correlates best with loudness (lag within +-6 frames) says which way is "open"
    def nz(v):
        v = (v - np.percentile(v, 5)) / (np.percentile(v, 95) - np.percentile(v, 5) + 1e-9)
        return np.clip(v, 0, 1)
    best = (-2, 1, 0)
    for sign in (1, -1):
        for lag in range(-6, 7):
            c = np.corrcoef(np.roll(nz(sign * m), lag)[10:-10], nz(rms)[10:-10])[0, 1]
            if c > best[0]:
                best = (c, sign, lag)
    print("frames", i, "mouth/audio correlation", round(best[0], 3), "sign", best[1], "lag", best[2])
    np.savez(out / "analysis.npz", mouth=nz(best[1] * m), audio=nz(rms), fps=30.0, n=i)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
