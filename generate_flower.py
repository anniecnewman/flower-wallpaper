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


def cutout(img, tol=22, seal=7):
    """Strip a flat background the model painted instead of leaving it empty.

    Deliberately conservative. An earlier version treated "pale and
    unsaturated" as background, which is also an exact description of a
    colored-pencil wash — it deleted the flowers and left ghost outlines. So
    this only removes colour that closely matches the actual corner colour AND
    reaches the frame, and it refuses to run at all if the model already
    returned real transparency.
    """
    img = img.convert("RGBA")
    if _alpha_share(img) > 0.20:          # already transparent — leave it alone
        return img

    a = np.array(img)
    rgb = a[:, :, :3].astype(np.int16)
    alpha = a[:, :, 3]

    h, w = rgb.shape[:2]
    corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
    if corners.std(axis=0).max() > 18:    # corners disagree; not a flat ground
        return img
    bg = np.median(corners, axis=0)

    near_bg = (np.abs(rgb - bg).max(axis=2) <= tol) | (alpha < 24)
    ink = ndimage.binary_closing(~near_bg, structure=np.ones((seal, seal)))

    labels, n = ndimage.label(~ink)
    if not n:
        return img
    edge = set(labels[0, :]) | set(labels[-1, :]) | \
           set(labels[:, 0]) | set(labels[:, -1])
    edge.discard(0)
    if not edge:
        return img
    outside = np.isin(labels, list(edge)) & near_bg

    new_alpha = alpha.copy()
    new_alpha[outside] = 0

    # Hard guard: this should shave a margin, never gut the picture.
    was = (alpha > 128).sum()
    now = (new_alpha > 128).sum()
    if was and now / was < 0.70:
        return img

    soft = ndimage.uniform_filter(new_alpha.astype(np.float32), size=3)
    new_alpha = np.minimum(new_alpha, soft.astype(np.uint8) + 8)
    a[:, :, 3] = new_alpha
    return Image.fromarray(a, "RGBA")


def recut_file(path):
    """Disabled. Re-processing finished art is how the ghost-outline bug got
    into the garden twice; a bad flower is cheaper to redraw than to repair."""
    return False


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
