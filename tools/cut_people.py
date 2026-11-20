"""Cut the photos in inbox/photos-style folders out of their background.

    python tools/cut_people.py inbox assets/people/harsh

Uses rembg (u2net_human_seg). Writes <slug>.png (transparent, cropped to the person) and <slug>-sticker.png
(the same with a thick white sticker outline), 900 px tall at most. Slugs come from the file names."""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from rembg import new_session, remove

SKIP = ("working corner", "workig corner", "laptop")   # whole-scene photos stay as photos


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s.replace("me-holding-my-hand-out-acting-like-im-holding-a-phone", "phone")


def sticker(rgba: Image.Image, px: int = 26) -> Image.Image:
    a = rgba.split()[3]
    pad = px * 2
    big = Image.new("L", (a.width + pad * 2, a.height + pad * 2), 0)
    big.paste(a, (pad, pad))
    grown = big.filter(ImageFilter.MaxFilter(px * 2 + 1)).filter(ImageFilter.GaussianBlur(2))
    grown = grown.point(lambda v: 255 if v > 110 else 0)
    out = Image.new("RGBA", big.size, (255, 255, 255, 0))
    out.paste(Image.new("RGBA", big.size, (255, 255, 255, 255)), mask=grown)
    layer = Image.new("RGBA", big.size, (0, 0, 0, 0))
    layer.paste(rgba, (pad, pad))
    out.alpha_composite(layer)
    return out


def main(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    sess = new_session("u2net_human_seg")
    for f in sorted(src.glob("*.jp*g")):
        if any(k in f.name.lower() for k in SKIP):
            continue
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        cut = remove(im, session=sess, alpha_matting=False)
        a = np.array(cut.split()[3])
        # wall showing between curls: drop pixels that still look like the wall (colour taken from outside the mask)
        rgb = np.array(im).astype(float)
        outside = (a < 10).astype(np.float32)
        if outside.sum() > 500:
            import cv2
            # the wall is not one colour (vignette), so estimate it locally from the pixels outside the mask
            num = cv2.GaussianBlur(rgb.astype(np.float32) * outside[..., None], (0, 0), 45)
            den = cv2.GaussianBlur(outside, (0, 0), 45)[..., None] + 1e-4
            wall = num / den
            dist = np.sqrt(((rgb - wall) ** 2).sum(axis=2))
            keep = np.clip((dist - 22) / 30, 0, 1)
            h = a.shape[0]
            wd = a.shape[1]
            zone = np.zeros(a.shape, bool)
            zone[: int(h * 0.45)] = True                                   # head zone only
            zone[int(h * 0.17): int(h * 0.45), int(wd * 0.30): int(wd * 0.70)] = False   # but never the face (glasses are clear)
            keep[~zone] = 1.0                                              # nothing below: shirt, neck, arms, hands
            a = (a * keep).astype("uint8")
        a = np.where(a > 200, 255, np.where(a < 40, 0, a)).astype("uint8")   # firm up the matte
        cut.putalpha(Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8)))
        cut = cut.crop(cut.getbbox())
        if cut.height > 1100:
            cut = cut.resize((round(cut.width * 1100 / cut.height), 1100), Image.LANCZOS)
        n = slug(f.stem)
        cut.save(dst / f"{n}.png")
        sticker(cut).save(dst / f"{n}-sticker.png")
        print(n, cut.size)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
