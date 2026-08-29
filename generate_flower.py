"""Generate one flower illustration as a transparent PNG."""

import base64
import io
import os
import re
import numpy as np
import requests
from scipy import ndimage
from PIL import Image

import config

FLOWER_DIR = os.path.join(os.path.dirname(__file__), "flowers")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60]


def asset_key(title, book_id):
    """Unique per Notion page — two books can share a title."""
    return f"{slug(title)}-{book_id.replace('-', '')[:8]}"


def build_prompt(flower):
    """Style block first, then only what varies: species and mood."""
    mood = ", ".join(flower.get("adjectives", [])[:3])
    latin = flower.get("latin", "")
    subject = f"{flower['flower']}" + (f" ({latin})" if latin else "")
    return (
        f"{config.STYLE_BLOCK}\n\n"
        f"Specimen: {subject}.\n"
        f"Let the mood of the painting be: {mood}. Allow that mood to steer "
        f"the color temperature, the openness of the bloom, and the energy of "
        f"the linework — but never the composition, which stays a single "
        f"centered specimen on transparent background."
    )


def _alpha_share(img):
    return float((np.array(img.convert("RGBA"))[:, :, 3] < 16).mean())


def cutout(img, seal=5):
    """Remove flat pale background the model painted, however it's arranged.

    The failure this fixes: the model returns a properly transparent image but
    paints a cream wash directly behind the plant, inside the transparent area.
    So "does this image have transparency?" is the wrong question. What counts
    as background is a pale, unsaturated region that connects either to the
    image border or to already-transparent pixels.

    The drawing's ink is sealed with a morphological closing first, so the fill
    can't leak through a gap in an outline and hollow out the flower.
    """
    img = img.convert("RGBA")
    a = np.array(img)
    rgb = a[:, :, :3].astype(np.int16)
    alpha = a[:, :, 3]

    value = rgb.max(axis=2)
    sat = value - rgb.min(axis=2)
    pale = (value >= 205) & (sat <= 42)          # cream, ivory, white, pale grey
    clear = alpha < 24

    background_like = pale | clear
    ink = ndimage.binary_closing(~background_like, structure=np.ones((seal, seal)))

    labels, n = ndimage.label(~ink)
    if not n:
        return img

    # Seeds: anything touching the frame, plus anything already transparent.
    seeds = set(labels[0, :]) | set(labels[-1, :]) | \
            set(labels[:, 0]) | set(labels[:, -1])
    seeds |= set(np.unique(labels[clear]))
    seeds.discard(0)
    if not seeds:
        return img

    outside = np.isin(labels, list(seeds)) & background_like

    new_alpha = alpha.copy()
    new_alpha[outside] = 0

    # Safety: if this would erase most of the picture, it misfired — keep the
    # original rather than return a ghost.
    was = (alpha > 128).sum()
    now = (new_alpha > 128).sum()
    if was and now / was < 0.45:
        return img

    soft = ndimage.uniform_filter(new_alpha.astype(np.float32), size=3)
    new_alpha = np.minimum(new_alpha, soft.astype(np.uint8) + 8)
    a[:, :, 3] = new_alpha
    return Image.fromarray(a, "RGBA")


def recut_file(path):
    """Re-cut a saved PNG. Runs on every build, so a background that slipped
    through gets cleaned up without paying to redraw the flower."""
    img = Image.open(path).convert("RGBA")
    before = _alpha_share(img)
    cut = cutout(img)
    if _alpha_share(cut) - before < 0.01:        # nothing to remove
        return False
    _trim(cut).save(path, "PNG")
    return True


def _trim(img, pad=8):
    """Crop to the visible flower so scaling is predictable."""
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(img.width, r + pad), min(img.height, b + pad)
    return img.crop((l, t, r, b))


def generate(flower, book_title, book_id):
    """Returns the local path of the saved PNG, or an existing one."""
    os.makedirs(FLOWER_DIR, exist_ok=True)
    path = os.path.join(FLOWER_DIR, f"{asset_key(book_title, book_id)}.png")
    if os.path.exists(path):
        return path

    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.IMAGE_MODEL,
            "prompt": build_prompt(flower),
            "size": config.IMAGE_SIZE,
            "background": "transparent",
            "output_format": "png",
            "quality": "high",
            "n": 1,
        },
        timeout=300,
    )
    r.raise_for_status()
    raw = base64.b64decode(r.json()["data"][0]["b64_json"])

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    _trim(cutout(img)).save(path, "PNG")
    return path
