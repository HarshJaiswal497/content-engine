"""Add app screens to assets/screens/<app>/ (2x upscaled and lightly sharpened so they stay crisp in video).

python tools/add_screens.py <app> <slug>=<source.png> [<slug>=<source.png> ...]

Only add screens that show features Harsh has cleared for sharing (see the fact sheets in the private repo):
this folder is public. Then describe each screen in brand/screens.yml so the drafter can pick it.
If you have 2x or 3x exports from the design tool, use those instead: pass --raw to copy them as they are.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> None:
    raw = "--raw" in argv
    argv = [a for a in argv if a != "--raw"]
    app, pairs = argv[0], argv[1:]
    out = ROOT / "assets" / "screens" / app
    out.mkdir(parents=True, exist_ok=True)
    for pair in pairs:
        slug, src = pair.split("=", 1)
        dest = out / f"{slug}.png"
        if raw:
            shutil.copy(src, dest)
            continue
        im = Image.open(src).convert("RGB")
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
        im.save(dest, optimize=True)
        print(dest.relative_to(ROOT), im.size)


if __name__ == "__main__":
    main(sys.argv[1:])
