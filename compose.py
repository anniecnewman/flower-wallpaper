"""Assemble the wallpaper: a hero flower for the current read, a cluster of
finished ones around it, and the type block underneath.

Placement is deterministic — seeded from each book's Notion id — so a flower
keeps its seat in the garden from one day to the next.
"""

import hashlib
import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

HERE = os.path.dirname(__file__)
FONT_DIR = os.path.join(HERE, "fonts")


# ------------------------------------------------------------------- fonts
def _script(size):
    path = os.path.join(FONT_DIR, config.TITLE_FONT)
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return _font(italic=True, size=size)


def _fit_script(draw, text):
    """Largest script size that keeps the title inside TITLE_MAX_W."""
    size = config.TITLE_SIZE
    while size > config.TITLE_MIN_SIZE:
        f = _script(size)
        if draw.textlength(text, font=f) <= config.TITLE_MAX_W:
            return f
        size -= 3
    return _script(config.TITLE_MIN_SIZE)


def _font(italic=False, size=48, weight=400):
    name = "EBGaramond-Italic[wght].ttf" if italic else "EBGaramond[wght].ttf"
    path = os.path.join(FONT_DIR, name)
    try:
        f = ImageFont.truetype(path, size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        return f
    except OSError:
        return ImageFont.load_default(size)


def _text_w(draw, text, font, tracking=0):
    w = draw.textlength(text, font=font)
    return w + tracking * max(0, len(text) - 1)


def _centered(draw, y, text, font, fill, tracking=0):
    """Draw centered text, optionally letterspaced."""
    total = _text_w(draw, text, font, tracking)
    x = (config.CANVAS_W - total) / 2
    if tracking == 0:
        draw.text((x, y), text, font=font, fill=fill)
    else:
        for ch in text:
            draw.text((x, y), ch, font=font, fill=fill)
            x += draw.textlength(ch, font=font) + tracking
    return y + font.size * 1.25


# ------------------------------------------------------------------ layout
def _scaled(path, target_h, alpha=255):
    img = Image.open(path).convert("RGBA")
    ratio = target_h / img.height
    img = img.resize((max(1, int(img.width * ratio)), int(target_h)),
                     Image.LANCZOS)
    if alpha < 255:
        a = img.getchannel("A").point(lambda p: int(p * alpha / 255))
        img.putalpha(a)
    return img


def _overlap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix = max(0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    small = min((ax2 - ax1) * (ay2 - ay1), (bx2 - bx1) * (by2 - by1))
    return inter / small if small else 0


def _slots(cols=6, rows=8):
    """Jittered grid across the plantable area, minus the hero and text zones."""
    x0, x1 = 40, config.CANVAS_W - 40
    y0, y1 = config.CLOCK_ZONE_BOTTOM + 110, config.BOTTOM_UI_TOP  # +110 clears the 'reading now' line
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows

    hero = (config.CANVAS_W / 2 - 300, config.HERO_CENTER_Y - 340,
            config.CANVAS_W / 2 + 300, config.TEXT_TOP - 30)
    text = (40, config.TEXT_TOP - 40, config.CANVAS_W - 40, config.TEXT_TOP + 300)

    out = []
    for r in range(rows):
        for c in range(cols):
            rng = random.Random(r * 100 + c)
            cx = x0 + cw * (c + 0.5) + rng.uniform(-cw * 0.22, cw * 0.22)
            cy = y0 + ch * (r + 0.5) + rng.uniform(-ch * 0.22, ch * 0.22)
            if hero[0] < cx < hero[2] and hero[1] < cy < hero[3]:
                continue
            if text[0] < cx < text[2] and text[1] < cy < text[3]:
                continue
            out.append((cx, cy))

    # nearest the hero first, so the most recent finishes sit closest to it
    out.sort(key=lambda p: math.hypot(p[0] - config.CANVAS_W / 2,
                                      (p[1] - config.HERO_CENTER_Y) * 0.75))
    return out


def _place_garden(canvas, garden):
    """garden: list of (book_id, png_path), most recently finished first."""
    n = len(garden)
    if n == 0:
        return
    slots = _slots()
    if not slots:
        return

    # If the year outgrows the grid, subdivide it rather than stacking.
    if n > len(slots):
        slots = _slots(cols=7, rows=10)

    for i, (book_id, path) in enumerate(garden[:len(slots)]):
        t = i / max(1, n - 1)                      # 0 = newest, 1 = oldest
        h = config.GARDEN_MAX_H + t * (config.GARDEN_MIN_H - config.GARDEN_MAX_H)
        alpha = int(config.GARDEN_MAX_ALPHA +
                    t * (config.GARDEN_MIN_ALPHA - config.GARDEN_MAX_ALPHA))
        img = _scaled(path, h, alpha)

        rng = random.Random(int(hashlib.md5(book_id.encode()).hexdigest()[:8], 16))
        cx, cy = slots[i]
        cx += rng.uniform(-40, 40)
        cy += rng.uniform(-40, 40)

        x = int(min(max(20, cx - img.width / 2), config.CANVAS_W - 20 - img.width))
        y = int(min(max(config.CLOCK_ZONE_BOTTOM + 60, cy - img.height / 2),
                    config.BOTTOM_UI_TOP - img.height))
        canvas.alpha_composite(img, (x, y))


# ------------------------------------------------------------------- render
def build(current, garden, out_path):
    """current: dict with title / flower / adjectives / png path (or None).
       garden:  list of (book_id, png_path), newest finished first."""
    canvas = Image.new("RGBA", (config.CANVAS_W, config.CANVAS_H),
                       config.PAPER + (255,))

    _place_garden(canvas, garden)

    # Soft cream veil so type stays readable over a dense garden.
    # Built as a true radial falloff — a blurred hard ellipse leaves a halo.
    if current:
        gw, gh = 240, 120
        grad = Image.new("L", (gw, gh), 0)
        gd = ImageDraw.Draw(grad)
        steps = 60
        for i in range(steps):
            f = i / steps
            a = int(242 * f ** 1.25)   # opaque at the center, clear at the rim
            gd.ellipse([gw / 2 * f, gh / 2 * f,
                        gw - gw / 2 * f, gh - gh / 2 * f], fill=a)
        grad = grad.resize((config.CANVAS_W + 200, 620), Image.LANCZOS)
        grad = grad.filter(ImageFilter.GaussianBlur(20))
        veil = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        veil.paste(Image.new("RGBA", grad.size, config.PAPER + (255,)),
                   (-100, config.TEXT_TOP - 150), grad)
        canvas.alpha_composite(veil)

    ink = (58, 52, 44, 255)
    faded = (120, 110, 96, 255)
    draw = ImageDraw.Draw(canvas)

    if current:
        if current.get("png") and os.path.exists(current["png"]):
            hero = _scaled(current["png"], config.HERO_MAX_H)
            canvas.alpha_composite(hero, (
                int((config.CANVAS_W - hero.width) / 2),
                int(config.HERO_CENTER_Y - hero.height / 2),
            ))

        _centered(draw, config.CLOCK_ZONE_BOTTOM + 20, "reading now",
                  _font(italic=True, size=40), faded, tracking=6)

        y = config.TEXT_TOP
        tf = _fit_script(draw, current["title"])
        y = _centered(draw, y, current["title"], tf, ink)
        y = _centered(draw, y + 6, current["flower"].upper(),
                      _font(size=34, weight=500), faded, tracking=9)
        adjectives = " · ".join(a.lower() for a in current.get("adjectives", []))
        _centered(draw, y + 14, adjectives, _font(italic=True, size=36), ink)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
