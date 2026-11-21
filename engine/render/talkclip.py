"""The talking mascot clip for story Reels.

The source is one calm green-screen video of the mascot talking (assets/characters/harsh/talk_source). It is not lip-synced:
it plays at its own speed while the voice is on and settles to a shut mouth in pauses (plan_natural), which looks calm and
keeps the head, neck and ears in one piece. Reaction videos (assets/characters/harsh/reactions) are matched to the
talker's head size and place and cross-faded in on cue; reaction stills pop in instead.

  clip   1080x1920: the mascot over a glow of the app colour, with flash and shake on each reaction.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "characters" / "harsh" / "talk_source" / "mascot_talking_calm.mp4"
SIZE = 1080
# the calm source (1664x928): a 928 square from x=368, scaled to 1080. Mouth sits near (550, 640) in that square.
CROP = "crop=928:928:368:0,scale=1080:1080"
CROP_X = 420           # the 1920x1080 reaction videos: a 1080 square from x=420
ROI = (460, 560, 640, 720)
TALK_SCALE = .62       # the calm source is a close-up; bring its head to the size of the reaction videos
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
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", CROP,
                        "-f", "rawvideo", "-pix_fmt", "rgb24", str(self.raw)], check=True)
        self.n = self.raw.stat().st_size // (SIZE * SIZE * 3)
        self.mm = np.memmap(self.raw, np.uint8, "r", shape=(self.n, SIZE, SIZE, 3))
        self._keyed: dict[int, np.ndarray] = {}
        self.mouth = self._mouth_openness()

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

    def frame_at(self, q: float) -> np.ndarray:
        """The nearest whole source frame (blending in-between frames softens the lips)."""
        return self.keyed(int(round(float(np.clip(q, 0, self.n - 1)))))


REACT_DIR = ROOT / "assets" / "characters" / "harsh" / "reactions"
REACT_SECONDS = 1.25     # one gesture cycle of the reaction videos (they loop seamlessly)


def reaction_video(name: str) -> Path | None:
    f = REACT_DIR / f"{name}.mp4"
    return f if f.exists() else None


class Reaction:
    """A green-screen reaction video played 1:1 (same crop and key as the talking source)."""
    def __init__(self, workdir: Path, video: Path):
        raw = workdir / f"react-{video.stem}.raw"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", f"crop={SIZE}:{SIZE}:{CROP_X}:0",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)], check=True)
        n = raw.stat().st_size // (SIZE * SIZE * 3)
        self.mm = np.memmap(raw, np.uint8, "r", shape=(n, SIZE, SIZE, 3))
        self.n = n

    def frame(self, i: int) -> np.ndarray:
        return key(np.asarray(self.mm[int(np.clip(i, 0, self.n - 1))]))


def head_metrics(rgba: np.ndarray) -> tuple[float, float, float]:
    """(top of the hair, hair width, hair centre x) of a keyed 1080 square: what makes two clips the same size."""
    a = rgba[..., 3] > .5
    top = int(np.flatnonzero(a.any(1))[0])
    best, cx = 0, 0.0
    for y in range(top, min(top + 250, a.shape[0])):
        xs = np.flatnonzero(a[y])
        if len(xs) and xs[-1] - xs[0] > best:
            best, cx = xs[-1] - xs[0], (xs[-1] + xs[0]) / 2
    return float(top), float(best), float(cx)


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


def plan_natural(o: np.ndarray, mouth: np.ndarray, speed: float = .5, gap: float = .35) -> np.ndarray:
    """Not lip-sync: ordinary speaking, slow and smooth. The source plays at a constant `speed` (source frames per output
    frame) while the voice is on; a pause longer than `gap` seconds lets the mouth settle shut and hold until the next
    phrase. The path reflects at the ends of the source so there is never a jump."""
    T, n = len(o), len(mouth)
    on = o > .06
    k = int(gap * FPS)
    idx = np.flatnonzero(on)
    talk = np.zeros(T, bool)
    for a, b in zip(idx[:-1], idx[1:]):   # bridge short gaps
        if b - a <= k:
            talk[a:b + 1] = True
    talk[idx] = True
    closed = mouth < .12
    pos = np.zeros(T)
    p, d = float(np.argmax(closed[: n // 3])), 1.0   # start on a shut mouth
    settling = False
    for j in range(T):
        pos[j] = p
        want = talk[j] or (j + 1 < T and talk[j + 1])
        if want:
            settling = False
        elif not settling and j > 0 and talk[j - 1]:
            settling = True
        if want or settling:
            if settling and closed[int(round(p)) % n] and mouth[int(round(p))] < .12 and not want:
                continue   # settled: hold
            p += d * speed
            if p >= n - 1: p, d = n - 1.0, -1.0
            if p <= 0: p, d = 0.0, 1.0
    return pos


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
    imgs, vids = {}, {}
    for x in impacts:
        if x.get("video"):
            if x["video"] not in vids:
                vids[x["video"]] = Reaction(out.parent, x["video"])
        elif x["image"] not in imgs:
            im = np.asarray(Image.open(x["image"]).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS), np.float32) / 255
            imgs[x["image"]] = np.dstack([im[..., :3] * im[..., 3:4], im[..., 3:]])
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                         stdin=subprocess.PIPE)
    T = len(pos)
    tm = head_metrics(src.keyed(100))
    cache: dict = {}

    def align_to_talk(layer, key_):
        """3x3 that puts a reaction's head where the talker's head is (same size, same top, same centre)."""
        if key_ not in cache:
            top_r, w_r, cx_r = head_metrics(layer)
            s_ = TALK_SCALE * tm[1] / w_r
            cx_t = 540 + (tm[2] - 540) * TALK_SCALE
            top_t = 1080 - (1080 - tm[0]) * TALK_SCALE
            cache[key_] = np.array([[s_, 0, cx_t - s_ * cx_r], [0, s_, top_t - s_ * top_r], [0, 0, 1]], np.float64)
        return cache[key_]

    def pop(sc, rot, dx):
        M = np.vstack([cv2.getRotationMatrix2D((SIZE / 2, SIZE), rot, sc), [0, 0, 1]])
        M[0, 2] += dx
        return M

    FADE = .12
    for j in range(T):
        t = j / FPS
        flash, dx = 0.0, 0.0
        act = next((x for x in impacts if x["t"] - 1e-6 <= t < x["t"] + x["d"]), None)
        for x in impacts:   # flash and shake live a little longer than the pop
            dt = t - x["t"]
            if 0 <= dt < .34:
                dx += -14 * np.exp(-6 * dt) * np.cos(2 * np.pi * 2.2 * dt)
            if 0 <= dt < .22:
                flash = max(flash, .55 * (1 - dt / .22) ** 2)
        breath = 1.0 + .005 * np.sin(2 * np.pi * t / 3.4)   # the stills between sentences are never frozen
        Tt = np.array([[TALK_SCALE, 0, 540 * (1 - TALK_SCALE)], [0, TALK_SCALE, 1080 * (1 - TALK_SCALE)], [0, 0, 1]])
        talk = cv2.warpAffine(src.frame_at(pos[j]), (pop(breath, 0, dx) @ Tt)[:2], (SIZE, SIZE), flags=cv2.INTER_LINEAR)
        layer = talk
        if act:
            u = t - act["t"]
            w = min(1.0, u / FADE, (act["t"] + act["d"] - t) / FADE)
            w = float(np.clip(w, 0, 1)); w = w * w * (3 - 2 * w)
            if act.get("video"):   # plays as video, aligned to the talker; cross-fades in and out
                raw = vids[act["video"]].frame(int(u * FPS)); psc, rot = 1.0, 0.0
                A = align_to_talk(vids[act["video"]].frame(0), act["video"])
            else:
                raw = imgs[act["image"]]; q = u / .32
                psc, rot = .9 + .1 * _back_out(q), -3.0 * (1 - min(_back_out(q), 1))
                A = align_to_talk(raw, act["image"])
            react = cv2.warpAffine(raw, (pop(psc * breath, rot, dx) @ A)[:2], (SIZE, SIZE), flags=cv2.INTER_LINEAR)
            layer = talk * (1 - w) + react * w
        frame = bg.copy()
        reg = frame[top:top + SIZE]
        reg[:] = layer[..., :3] + reg * (1 - layer[..., 3:4])
        if flash:
            frame = frame * (1 - flash) + flash
        p.stdin.write((frame.clip(0, 1) * 255 + .5).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return out
