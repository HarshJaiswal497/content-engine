"""Store the two full-body mascot images: the desk scene (opaque illustration, edge noise cropped) and the standing
presenter (cut out of the glow with rembg). Usage: python tools/prepare_fullbody.py <desk png> <standing png>"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "harsh" / "fullbody"


def main(desk, standing):
    from rembg import new_session, remove
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(desk).convert("RGBA")
    bg = Image.new("RGBA", im.size, (24, 20, 30, 255)); bg.alpha_composite(im)
    w, h = bg.size
    bg.convert("RGB").crop((22, 22, w - 22, h - 22)).save(OUT / "desk_coding_scene.webp", "WEBP", quality=92, method=6)
    im = Image.open(standing).convert("RGBA")
    flat = Image.new("RGBA", im.size, (128, 128, 128, 255)); flat.alpha_composite(im)
    m = np.array(remove(flat.convert("RGB"), session=new_session("u2net_human_seg"), only_mask=True)).astype(np.float32)
    idx = ndi.distance_transform_edt(~(m >= 200), return_distances=False, return_indices=True)
    rgb = np.array(flat.convert("RGB")).astype(np.float32)[idx[0], idx[1]]
    m = ndi.gaussian_filter(ndi.grey_erosion(m, size=(3, 3)), .8); m[m < 12] = 0
    out = Image.fromarray(np.dstack([rgb, m]).clip(0, 255).astype(np.uint8), "RGBA")
    out.crop(out.getbbox()).save(OUT / "presenter_standing.webp", "WEBP", quality=92, alpha_quality=100, method=6)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
