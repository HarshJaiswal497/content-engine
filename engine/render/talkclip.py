"""A talking clip of the real mascot, re-timed to any voice.

The source is one continuous green-screen video of the mascot talking (fast, 16.8 s). Cutting between stills makes the
head and ears jitter, so instead the *video* is played along a path through its own frames, chosen so the mouth opening
follows the loudness of our voice: slower and smoother than the source, head and neck moving as one piece.

  path   dynamic programme over (source position in quarter frames, speed): matches mouth openness to the voice,
         penalises speed changes, so the clip plays at 0..1.25x with no jumps.
  frames in-between positions are rendered with optical flow, not cross-fades.
  clip   1080x1920: the mascot over a glow of the app colour, reaction images (impact frames) popped in on cue.
"""
from __future__ import annotations
import subprocess, tempfile
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "characters" / "harsh" / "talk_source" / "mascot_talking_green.mp4"
CROP_X, SIZE = 420, 1080
ROI = (470, 540, 650, 670)
Q = 4                      # quarter-frame positions
FPS = 30


def key(rgb: np.ndarray) -> np.ndarray:
    """Remove the flat green background, suppress green spill on hair and skin edges. -> float32 premultiplied RGBA 0..1"""
    f = rgb.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    gd = g - np.maximum(r, b)
    a = 1.0 - np.clip((gd - 14.0) / 62.0, 0, 1)
    g2 = np.minimum(g, np.maximum(r, b) + 6.0)
    rgb = np.stack([r, g2, b], -1) / 255.0
    return np.dstack([rgb * a[..., None], a]).astype(np.float32)


class Source:
    def __init__(self, workdir: Path, video: Path = SOURCE):
        self.raw = workdir / "src.raw"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", f"crop={SIZE}:{SIZE}:{CROP_X}:0",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", str(self.raw)], check=True)
        self.n = self.raw.stat().st_size // (SIZE * SIZE * 3)
        self.mm = np.memmap(self.raw, np.uint8, "r", shape=(self.n, SIZE, SIZE, 3))
        self._keyed: dict[int, np.ndarray] = {}
        self._flow: dict[int, np.ndarray] = {}
        self.mouth = self._mouth_openness()
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)

    def _mouth_openness(self) -> np.ndarray:
        x0, y0, x1, y1 = ROI
        feats = np.array([cv2.resize(cv2.cvtColor(np.ascontiguousarray(self.mm[i, y0:y1, x0:x1]), cv2.COLOR_RGB2GRAY), (36, 26),
                                     interpolation=cv2.INTER_AREA).astype(np.float32).ravel() for i in range(self.n)])
        mean_luma = feats.mean(1)
        feats = feats - feats.mean(0)
        u, s, _ = np.linalg.svd(feats, full_matrices=False)
        m = u[:, 0] * s[0]
        if np.corrcoef(m, -mean_luma)[0, 1] < 0:   # the open mouth shows dark inside: more dark = more open
            m = -m
        lo, hi = np.percentile(m, 5), np.percentile(m, 95)
        return np.clip((m - lo) / (hi - lo + 1e-9), 0, 1)

    def keyed(self, i: int) -> np.ndarray:
        i = int(np.clip(i, 0, self.n - 1))
        if i not in self._keyed:
            if len(self._keyed) > 6:
                self._keyed.pop(next(iter(self._keyed)))
            self._keyed[i] = key(np.asarray(self.mm[i]))
        return self._keyed[i]

    def _flow_between(self, i: int) -> np.ndarray:
        if i not in self._flow:
            if len(self._flow) > 6:
                self._flow.pop(next(iter(self._flow)))
            g = lambda k: cv2.resize(cv2.cvtColor(np.asarray(self.mm[k]), cv2.COLOR_RGB2GRAY), (SIZE // 2, SIZE // 2), interpolation=cv2.INTER_AREA)
            f = self.dis.calc(g(i), g(i + 1), None)
            self._flow[i] = cv2.resize(f, (SIZE, SIZE)) * 2.0
        return self._flow[i]

    def frame_at(self, q: float) -> np.ndarray:
        """The source at fractional frame q (optical-flow interpolation between neighbours)."""
        q = float(np.clip(q, 0, self.n - 1))
        i = int(q)
        a = q - i
        if a < 1e-3 or i >= self.n - 1:
            return self.keyed(i)
        F = self._flow_between(i)
        gx, gy = np.meshgrid(np.arange(SIZE, dtype=np.float32), np.arange(SIZE, dtype=np.float32))
        A, B = self.keyed(i), self.keyed(i + 1)
        wa = cv2.remap(A, gx - a * F[..., 0], gy - a * F[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        wb = cv2.remap(B, gx + (1 - a) * F[..., 0], gy + (1 - a) * F[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return (1 - a) * wa + a * wb


def voice_openness(wav: Path, total: float, fps: int = FPS) -> np.ndarray:
    """Target mouth opening per frame (0 shut .. 1 wide) from the loudness of the voice."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 16000 // fps
    n = int(round(total * fps))
    x = np.pad(x, (0, max(n * hop - len(x), 0)))[: n * hop]
    rms = np.sqrt((x.reshape(n, hop) ** 2).mean(1))
    rms = np.convolve(rms, np.hanning(5) / np.hanning(5).sum(), mode="same")
    ref = np.percentile(rms[rms > rms.max() * .05], 90) if (rms > rms.max() * .05).any() else 1.0
    o = np.clip((rms / ref) ** .75, 0, 1)
    o[rms < rms.max() * .05] = 0
    return o


def plan_path(o: np.ndarray, mouth: np.ndarray, kmax: int = 5, pref: float = 2.0,
              lam_change: float = .004, lam_pref: float = .0012) -> np.ndarray:
    """Source position (in frames, fractional) for each output frame. Speed is 0..kmax quarter-frames per output frame."""
    n = len(mouth)
    P = (n - 1) * Q + 1
    ms = np.interp(np.arange(P) / Q, np.arange(n), mouth).astype(np.float32)
    T, K = len(o), kmax + 1
    ks = np.arange(K)
    pen = (np.abs(ks[:, None] - ks[None, :]) * lam_change + ((ks - pref) ** 2)[None, :] * lam_pref).astype(np.float32)
    INF = np.float32(1e9)
    dp = np.full((P, K), INF, np.float32)
    dp[: P // 3, :] = ((o[0] - ms[: P // 3]) ** 2)[:, None] + pen[int(pref)][None, :] * 0   # start in the first third
    back = np.zeros((T, P, K), np.int8)
    for j in range(1, T):
        tmp = dp[:, :, None] + pen[None]
        bp = tmp.argmin(1).astype(np.int8)
        bv = tmp.min(1)
        cost = ((o[j] - ms) ** 2).astype(np.float32)
        new = np.full((P, K), INF, np.float32)
        for k in range(K):
            new[k:, k] = bv[: P - k, k] + cost[k:]
            back[j][k:, k] = bp[: P - k, k]
        dp = new
    p, k = np.unravel_index(int(dp.argmin()), dp.shape)
    pos = np.zeros(T, np.int64)
    for j in range(T - 1, -1, -1):
        pos[j] = p
        if j:
            kp = back[j][p, k]
            p, k = p - k, int(kp)
    return pos / Q


def _bg(accent: str, shade: str) -> np.ndarray:
    """radial-gradient(circle at 50% 58%, accent, shade) at 1080x1920, premultiplied-ready float RGB 0..1"""
    h = lambda c: np.array([int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255
    W, H = 1080, 1920
    cx, cy = W * .5, H * .58
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    far = np.hypot(max(cx, W - cx), max(cy, H - cy))
    t = np.clip(np.hypot(gx - cx, gy - cy) / far, 0, 1)[..., None]
    return h(accent) * (1 - t) + h(shade) * t


def _back_out(u: float, s: float = 2.6) -> float:
    u = min(max(u, 0), 1) - 1
    return u * u * ((s + 1) * u + s) + 1


def render_clip(src: Source, pos: np.ndarray, out: Path, accent: str, shade: str,
                impacts: list[dict] | None = None, top: int = 840) -> Path:
    """impacts: [{t, d, image: Path}] reaction images popped in over the talker (with a flash and a small shake)."""
    impacts = impacts or []
    bg = _bg(accent, shade)
    imgs = {}
    for x in impacts:
        if x["image"] not in imgs:
            im = np.asarray(Image.open(x["image"]).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS), np.float32) / 255
            imgs[x["image"]] = np.dstack([im[..., :3] * im[..., 3:4], im[..., 3:]])
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                         stdin=subprocess.PIPE)
    T = len(pos)
    for j in range(T):
        t = j / FPS
        layer = src.frame_at(pos[j])
        flash, dx = 0.0, 0.0
        act = next((x for x in impacts if x["t"] <= t < x["t"] + x["d"]), None)
        # a gentle breathing scale so the stills between sentences are never frozen
        sc = 1.0 + .005 * np.sin(2 * np.pi * t / 3.4)
        rot = 0.0
        if act:
            layer = imgs[act["image"]]
            u = (t - act["t"]) / .32
            sc *= .86 + .14 * _back_out(u)
            rot = -3.0 * (1 - min(_back_out(u), 1))
        for x in impacts:   # flash and shake live a little longer than the pop
            dt = t - x["t"]
            if 0 <= dt < .34:
                dx += -14 * np.exp(-6 * dt) * np.cos(2 * np.pi * 2.2 * dt)
            if 0 <= dt < .22:
                flash = max(flash, .55 * (1 - dt / .22) ** 2)
        M = cv2.getRotationMatrix2D((SIZE / 2, SIZE), rot, sc)
        M[0, 2] += dx
        layer = cv2.warpAffine(layer, M, (SIZE, SIZE), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        frame = bg.copy()
        reg = frame[top:top + SIZE]
        reg[:] = layer[..., :3] + reg * (1 - layer[..., 3:4])
        if flash:
            frame = frame * (1 - flash) + flash
        p.stdin.write((frame.clip(0, 1) * 255 + .5).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return out
