"""Clean, rename and store the real mascot (cut-out images of Harsh) from the generated zips and PNGs.
For every image: stray red/white edge pixels are removed (edge colours are taken from the nearest solid pixel,
near-invisible alpha is dropped), then it is saved as a 1000 px lossless-alpha-friendly WebP.
Writes assets/characters/harsh/<group>/<name>.webp, manifest.json (old name -> new name, what it shows, notes) and MANIFEST.md.

Usage: python tools/prepare_mascot.py <dir with the unzipped folders> <dir with the loose PNGs>
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

OUT = Path(__file__).resolve().parent.parent / "assets" / "characters" / "harsh"
SIZE = 1000

E, M, N, G, X = ("mascot_emotions_reference_quality_7", "mascot_lips_individual_complete_7",
                 "mascot_non_speaking_corrected_labels/non_speaking", "mascot_gestures_arms_phone_typing_individual",
                 "mascot_eyes_brows_PARTIAL_8")
P = "mascot_pointing_left_right_verified"
# group, new name, source (folder/file or loose:<file>), what it shows, note
ITEMS = [
    ("expressions", "neutral_talking", f"{E}/01_neutral_talking.png", "front, relaxed, mouth slightly open as if mid-sentence", ""),
    ("expressions", "happy", f"{E}/02_happy.png", "front, big open smile with teeth", ""),
    ("expressions", "excited", f"{E}/03_excited.png", "front, brows up, wide open grin", ""),
    ("expressions", "thinking", f"{E}/04_thinking.png", "hand on chin, eyes looking aside, closed mouth", ""),
    ("expressions", "surprised", f"{E}/05_surprised.png", "front, brows up, small round mouth", ""),
    ("expressions", "shocked", f"{E}/06_shocked.png", "front, huge eyes, jaw dropped", ""),
    ("expressions", "confused", f"{E}/07_confused.png", "eyes aside, one brow down, mouth twisted", "white halo around the hair in the source; cleaned here"),
    ("mouths", "closed", f"{M}/01_closed.png", "mouth shape: closed (m, b, p)", "front, neutral face; the base for lip-sync"),
    ("mouths", "slight_open", f"{M}/02_neutral_slight_open.png", "mouth shape: neutral, slightly open", ""),
    ("mouths", "small_open", f"{M}/03_small_open.png", "mouth shape: small open (e, i)", ""),
    ("mouths", "wide_open", f"{M}/04_wide_open.png", "mouth shape: wide open (a)", ""),
    ("mouths", "round", f"{M}/05_round.png", "mouth shape: round (o, u, w)", ""),
    ("mouths", "teeth_on_lip", f"{M}/06_teeth_on_lip.png", "mouth shape: upper teeth showing (f, v)", "teeth do not clearly rest on the lip; usable as an f/v approximation"),
    ("mouths", "wide_smile", f"{M}/07_wide_smile.png", "mouth shape: wide smile with teeth (ee, s)", "the zip README says this one is missing; it is there"),
    ("face", "smirk", f"{N}/01_smile.png", "closed-mouth smile pulled up on one side", "was named 01_smile; it is a smirk"),
    ("face", "big_grin", f"{N}/02_big_grin.png", "wide grin with teeth", ""),
    ("face", "open_mouth", f"{N}/03_smirk.png", "mouth open, brows slightly up, mid-word", "was named 03_smirk; it shows an open mouth, not a smirk"),
    ("face", "frown", f"{N}/04_frown.png", "downturned mouth, unhappy", ""),
    ("face", "pout", f"{N}/05_pout.png", "lips pushed forward (duck/kiss pout)", ""),
    ("face", "flat", f"{N}/06_flat.png", "flat mouth, deadpan", ""),
    ("face", "gritted_teeth", f"{N}/07_gritted_teeth.png", "teeth clenched, brows down, frustrated", ""),
    ("face", "laugh_eyes_closed", f"{N}/08_laugh_eyes_closed.png", "laughing, eyes squeezed shut", ""),
    ("face", "yawn", f"{N}/09_yawn.png", "yawning with a hand over the mouth", ""),
    ("face", "tongue_out", f"{N}/10_tongue_out.png", "tongue out, one eye winking", ""),
    ("face", "oh_gasp", f"{N}/11_oh_gasp.png", "wide eyes, small round mouth", ""),
    ("eyes", "blink_open", f"{X}/blink/01_open.png", "eyes open", "different framing: head is smaller, body wider; not aligned with the other sets"),
    ("eyes", "blink_half", f"{X}/blink/02_half_open.png", "eyes half closed", "different framing"),
    ("eyes", "blink_closed", f"{X}/blink/03_closed.png", "eyes closed", "different framing"),
    ("eyes", "gaze_camera", f"{X}/gaze/01_camera.png", "looking at the camera", "different framing"),
    ("eyes", "gaze_left", f"{X}/gaze/02_left.png", "looking to the left of the frame", "different framing"),
    ("eyes", "gaze_right", f"{X}/gaze/03_right.png", "looking to the right of the frame", "different framing"),
    ("eyes", "gaze_up", f"{X}/gaze/04_up.png", "looking up", "different framing"),
    ("eyes", "happy_arcs", f"{X}/special/01_happy_arcs.png", "eyes as happy arcs, small smile", "source canvas 1199x1312; fitted to a square"),
    ("gestures", "arms_crossed", f"{G}/01_arms_crossed.png", "arms crossed, calm smirk", ""),
    ("gestures", "holding_phone", f"{G}/02_holding_phone.png", "looking down at a phone in both hands", ""),
    ("gestures", "typing_laptop", f"{G}/03_typing_laptop.png", "typing on a laptop, glancing at the screen", ""),
    ("gestures", "point_left", f"{P}/point_left.png", "pointing to the left of the frame, looking that way", ""),
    ("gestures", "point_right", f"{P}/point_right.png", "pointing to the right of the frame, looking at the camera", ""),
    ("gestures", "present_phone", "loose:Enthusiastic_Smartphone_Presentation.png", "holding a phone toward the camera and pointing at it, excited", "blank black phone screen: put the app on it"),
    ("gestures", "cheer", "loose:cheer.png", "both fists up, open-mouth joy", ""),
    ("gestures", "hand_on_forehead", "loose:face_palm.png", "hand on forehead, eyes shut, wincing", "was face_palm; the hand is on the forehead, not over the face"),
    ("gestures", "shrug", "loose:shrug.png", "both palms up, questioning look", ""),
    ("gestures", "point_down", "loose:pointing_down.png", "looking down and pointing down, mouth open", ""),
    ("gestures", "point_up", "loose:pointing_up.png", "looking up and pointing up with one finger", ""),
    ("gestures", "wave", "loose:Joyful_Wave_in_Black_Hoodie.png", "waving, big smile", ""),
]


def clean(im: Image.Image, defringe_hair: bool = False) -> Image.Image:
    im = im.convert("RGBA")
    a = np.array(im)
    al = a[..., 3].astype(np.float32)
    rgb = a[..., :3].astype(np.float32)
    al[al < 10] = 0
    solid = al >= 250
    if defringe_hair:   # bright halo on the hair of one source: drop bright pixels near the edge of the head zone
        dist = ndi.distance_transform_edt(al > 0)
        luma = rgb @ np.array([.299, .587, .114])
        h = al.shape[0]
        zone = np.zeros_like(al, bool); zone[: int(h * .55)] = True
        bad = zone & (dist <= 18) & (luma > 150)
        al[bad] = 0
        solid = al >= 250
    # edge colours come from the nearest solid pixel, so no red/white/green fringe survives
    idx = ndi.distance_transform_edt(~solid, return_distances=False, return_indices=True)
    rgb = rgb[idx[0], idx[1]]
    # pull the matte in by about one pixel and soften it
    al = ndi.grey_erosion(al, size=(3, 3))
    al = ndi.gaussian_filter(al, .7)
    al[al < 14] = 0
    out = np.dstack([rgb, al]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def fit_square(im: Image.Image, size: int) -> Image.Image:
    if im.width != im.height:
        s = max(im.size)
        c = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        c.paste(im, ((s - im.width) // 2, s - im.height))   # bottom-aligned, centred
        im = c
    return im.resize((size, size), Image.LANCZOS)


def main(zips: Path, loose: Path):
    man = []
    for group, name, src, shows, note in ITEMS:
        f = (loose / src[6:]) if src.startswith("loose:") else (zips / src)
        im = fit_square(clean(Image.open(f), defringe_hair=(name == "confused")), SIZE)
        d = OUT / group
        d.mkdir(parents=True, exist_ok=True)
        im.save(d / f"{name}.webp", "WEBP", quality=92, alpha_quality=100, method=6)
        man.append({"group": group, "name": name, "file": f"{group}/{name}.webp", "original": src.replace("loose:", "(attached) "),
                    "shows": shows, "note": note})
        print(f"{group}/{name}")
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False))
    lines = ["# Harsh mascot: stored images", "", "Cleaned (edge fringe removed), 1000 px WebP with transparency. "
             "`tools/prepare_mascot.py` rebuilds this folder from the zips. Images are independent generations: faces and hair differ slightly between files.", "",
             "| File | Original name | What it shows | Note |", "|---|---|---|---|"]
    lines += [f"| `{m['file']}` | {m['original'].split('/')[-1]} | {m['shows']} | {m['note']} |" for m in man]
    (OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
