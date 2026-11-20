"""Build lip-sync frames for the real mascot.
The mouth images are independent generations (hair and head differ slightly), so swapping whole images would make the
head jitter. Instead each mouth is aligned to a base pose (ECC on the glasses/nose area) and only a feathered patch
around the mouth and beard is pasted onto the base. Everything outside the patch stays pixel-identical across frames.

  python tools/build_talk.py            -> assets/characters/harsh/talk/<pose>-v0..v6.webp + talk/meta.json
Visemes v0..v6: closed, slight_open, small_open, wide_open, round, teeth_on_lip, wide_smile.
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "harsh"
VIS = ["closed", "slight_open", "small_open", "wide_open", "round", "teeth_on_lip", "wide_smile"]
# poses that can talk: name -> source image (relative to ROOT)
TALKERS = {
    "front": "mouths/closed.webp",
    "neutral": "expressions/neutral_talking.webp",
    "crossed": "gestures/arms_crossed.webp",
    "shrug": "gestures/shrug.webp",
    "present": "gestures/present_phone.webp",
    "wave": "gestures/wave.webp",
    "point_right": "gestures/point_right.webp",
    "happy": "expressions/happy.webp",
}


def load(p):
    return np.array(Image.open(ROOT / p).convert("RGBA"))


def align(src, dst):
    """Warp src onto dst with an affine ECC fit on the eyes/nose region (the part that doesn't move when talking)."""
    h, w = dst.shape[:2]
    g1 = cv2.cvtColor(dst[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(src[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    mask = np.zeros((h, w), np.uint8)
    mask[int(h * .30):int(h * .52), int(w * .30):int(w * .72)] = 255
    cc = warp = None
    for motion in (cv2.MOTION_AFFINE, cv2.MOTION_EUCLIDEAN, cv2.MOTION_TRANSLATION):
        try:
            warp = np.eye(2, 3, dtype=np.float32)
            cc, warp = cv2.findTransformECC(cv2.GaussianBlur(g1, (0, 0), 2), cv2.GaussianBlur(g2, (0, 0), 2), warp, motion,
                                            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), mask, 5)
            break
        except cv2.error:
            warp = None
    if warp is None:
        return None, 0.0
    out = cv2.warpAffine(src, warp, (w, h), flags=cv2.INTER_LANCZOS4 + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    return out, float(cc)


def mouth_mask(shape, aligned_vis, base_closed):
    """Where the mouths differ from each other: union of differences to the closed mouth, grown and feathered."""
    h, w = shape[:2]
    acc = np.zeros((h, w), np.float32)
    ref = cv2.cvtColor(base_closed[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
    for v in aligned_vis:
        d = np.abs(cv2.cvtColor(v[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) - ref)
        acc = np.maximum(acc, cv2.GaussianBlur(d, (0, 0), 3))
    lower = np.zeros((h, w), np.float32)
    lower[int(h * .47):int(h * .86), int(w * .30):int(w * .70)] = 1   # nose-bottom to below the chin, between the ears
    m = ((acc > 14) & (lower > 0)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((41, 41), np.uint8))
    m = cv2.dilate(m, np.ones((31, 31), np.uint8))
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 14)
    return np.clip(m * 1.6, 0, 1)


def main():
    vis_src = [load(f"mouths/{v}.webp") for v in VIS]
    out_dir = ROOT / "talk"
    out_dir.mkdir(exist_ok=True)
    meta = {}
    # one mask from the mouth set, aligned to its own closed mouth
    closed = vis_src[0]
    al = [align(v, closed)[0] if i else v for i, v in enumerate(vis_src)]
    mask = mouth_mask(closed.shape, al[1:], closed)
    Image.fromarray((mask * 255).astype(np.uint8)).save(out_dir / "_mask.png")
    for name, rel in TALKERS.items():
        base = load(rel)
        frames, scores = [], []
        for i, v in enumerate(vis_src):
            a, cc = (align(v, base) if (name != "front" or i) else (v, 1.0))
            scores.append(round(cc, 3))
            if a is None:
                break
            a_rgb = a[..., :3].astype(np.float32)
            b_rgb = base[..., :3].astype(np.float32)
            # match the patch colour to the base around the seam so skin tones agree
            ring = ((mask > .02) & (mask < .6))[..., None]
            if ring.any():
                off = (b_rgb[ring[..., 0]].mean(0) - a_rgb[ring[..., 0]].mean(0))
                a_rgb = a_rgb + off * .8
            m = mask[..., None]
            rgb = b_rgb * (1 - m) + a_rgb * m
            alpha = base[..., 3:4].astype(np.float32)
            out = np.concatenate([rgb, alpha], 2).clip(0, 255).astype(np.uint8)
            Image.fromarray(out, "RGBA").save(out_dir / f"{name}-v{i}.webp", "WEBP", quality=90, alpha_quality=100, method=4)
        if len(scores) < len(vis_src) or a is None:
            print(name, "skipped: could not align", scores)
            continue
        meta[name] = {"source": rel, "align_cc": scores}
        print(name, scores)
    (out_dir / "meta.json").write_text(json.dumps({"visemes": VIS, "poses": meta}, indent=1))


if __name__ == "__main__":
    main()
