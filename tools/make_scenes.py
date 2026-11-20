"""'Working at my desk' scenes: your photo with the room tidied up (shelf clutter and the boxes under the desk fade out).

    python tools/make_scenes.py inbox assets/people/harsh/scenes

Photos with 'laptop' in the name that were shot from the same spot as the 'corner' photo (same size, camera not moved:
skip any with '_1' in the name) get soft, darkened, tinted patches over the busy parts of the wall and under the desk;
you, the chair, the desk and the laptop stay untouched. Writes <slug>.png (same size as the photo)."""
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# (x0, y0, x1, y1) as fractions of the frame, blur, brightness
PATCHES = [
    ((0.50, 0.00, 1.00, 0.37), 16, 0.50),    # shelves, plant, bottles
    ((0.58, 0.70, 0.96, 0.94), 12, 0.55),    # boxes and bag under the desk
]
TINT = (40, 58, 140)


def tidy(im: Image.Image, person: Image.Image | None = None) -> Image.Image:
    w, h = im.size
    out = im.copy()
    keep = None
    if person is not None:   # never soften you
        keep = person.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
    for (x0, y0, x1, y1), blur, bright in PATCHES:
        patch = im.filter(ImageFilter.GaussianBlur(blur))
        patch = ImageEnhance.Brightness(patch).enhance(bright)
        arr = np.array(patch).astype(float) * 0.86 + np.array(TINT, float) * 0.14
        patch = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
        m = Image.new("L", (w, h), 0)
        m.paste(255, (int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        m = m.filter(ImageFilter.GaussianBlur(w * 0.04))
        if keep is not None:
            m = Image.fromarray((np.array(m).astype(float) * (1 - np.array(keep).astype(float) / 255)).astype("uint8"))
        out = Image.composite(patch, out, m)
    arr = np.array(ImageEnhance.Contrast(out).enhance(1.08)).astype(float)
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - 0.38 * (((xx - w / 2) / (w / 1.25)) ** 2 + ((yy - h / 2) / (h / 1.25)) ** 2)
    return Image.fromarray(np.clip(arr * v[..., None], 0, 255).astype("uint8"))


def main(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.jp*g"))
    plate_f = next((f for f in files if "corner" in f.name.lower()), None)
    from rembg import new_session, remove
    sess = new_session("u2net_human_seg")
    size = ImageOps.exif_transpose(Image.open(plate_f)).size if plate_f else None
    for f in files:
        if "laptop" not in f.name.lower() or "_1" in f.name:
            continue
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        if size and im.size != size:
            continue
        name = re.sub(r"[^a-z0-9]+", "-", f.stem.lower()).strip("-")
        person = remove(im, session=sess).split()[3]
        tidy(im, person).save(dst / f"{name}.png")
        print(name)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
