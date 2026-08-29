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


def cutout(img, tol=34):
    """Strip any flat background the model painted despite being told not to.

    Only removes background-colored pixels CONNECTED to the image border, so a
    cream petal in the middle of a bloom survives.
    """
    img = img.convert("RGBA")
    a = np.array(img)
    rgb = a[:, :, :3].astype(np.int16)

    # Corner pixels are background if anything is.
    h, w = rgb.shape[:2]
    corners = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
    bg = np.median(corners, axis=0)

    near_bg = (np.abs(rgb - bg).max(axis=2) <= tol) | (a[:, :, 3] < 24)

    labels, n = ndimage.label(near_bg)
    if n:
        edge = set(labels[0, :]) | set(labels[-1, :]) | \
               set(labels[:, 0]) | set(labels[:, -1])
        edge.discard(0)
        outside = np.isin(labels, list(edge))
    else:
        outside = np.zeros_like(near_bg)

    alpha = a[:, :, 3].copy()
    alpha[outside] = 0

    # Soften the cut by one pixel so edges don't look scissored.
    soft = ndimage.uniform_filter(alpha.astype(np.float32), size=3)
    alpha = np.minimum(alpha, soft.astype(np.uint8) + 8)

    a[:, :, 3] = alpha
    return Image.fromarray(a, "RGBA")


def recut_file(path):
    """Re-cut an already-saved PNG that still carries a painted background."""
    img = Image.open(path).convert("RGBA")
    transparent = (np.array(img)[:, :, 3] < 16).mean()
    if transparent > 0.12:
        return False                      # already cut out
    _trim(cutout(img)).save(path, "PNG")
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
