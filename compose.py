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
# Fonts may live in fonts/ or sit beside the scripts — check both.
FONT_DIRS = [os.path.join(HERE, "fonts"), HERE]


def _font_path(filename):
    for d in FONT_DIRS:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return os.path.join(FONT_DIRS[0], filename)


# ------------------------------------------------------------------- fonts
def _script(size):
    path = _font_path(config.TITLE_FONT)
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
    path = _font_path(name)
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


def _wrap(draw, text, font, max_w):
    """Break a sentence into centered rows that fit the canvas."""
    words, rows, row = (text or "").split(), [], ""
    for w in words:
        trial = f"{row} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not row:
            row = trial
        else:
            rows.append(row)
            row = w
    if row:
        rows.append(row)
    return rows[:3]


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


def _blocked(cx, cy):
    """Zones a flower may not sit in: the hero, the type, the iOS buttons."""
    if (config.CANVAS_W / 2 - 300 < cx < config.CANVAS_W / 2 + 300
            and config.HERO_CENTER_Y - 340 < cy < config.TEXT_TOP - 30):
        return True
    if (40 < cx < config.CANVAS_W - 40
            and config.TEXT_TOP - 40 < cy < config.TEXT_TOP + 300):
        return True
    if cy > config.BUTTON_ZONE_TOP and (cx < config.BUTTON_ZONE_W
                                        or cx > config.CANVAS_W - config.BUTTON_ZONE_W):
        return True
    return False


def _seats(cols=6, rows=11):
    """Planting order: bottom center first, then outward and upward.

    Rows fill from the bottom of the screen up. Within a row, seats nearest
    the middle are taken first. As the bottom fills, later books climb the
    sides past the hero and finally arch over the top — which is how the
    garden grows over a year.
    """
    x0, x1 = 30, config.CANVAS_W - 30
    y0, y1 = config.CLOCK_ZONE_BOTTOM + 110, config.BOTTOM_UI_TOP
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows

    seats = []
    for r in range(rows):
        for c in range(cols):
            rng = random.Random(r * 137 + c * 31)
            cx = x0 + cw * (c + 0.5) + rng.uniform(-cw * 0.26, cw * 0.26)
            cy = y0 + ch * (r + 0.5) + rng.uniform(-ch * 0.24, ch * 0.24)
            if _blocked(cx, cy):
                continue
            seats.append((r, abs(cx - config.CANVAS_W / 2), cx, cy))

    # bottom rows first (high r), and within a row the middle first
    seats.sort(key=lambda s: (-s[0], s[1]))
    return [(cx, cy) for _, _, cx, cy in seats]


def _place_garden(canvas, garden):
    """garden: (book_id, png_path), OLDEST first — the first planted."""
    n = len(garden)
    if n == 0:
        return
    seats = _seats()
    if n > len(seats):
        seats = _seats(cols=7, rows=13)

    hero_x, hero_y = config.CANVAS_W / 2, config.HERO_CENTER_Y
    far = math.hypot(config.CANVAS_W / 2, config.CANVAS_H / 2)

    for (book_id, path), (cx, cy) in zip(garden, seats):
        rng = random.Random(int(hashlib.md5(book_id.encode()).hexdigest()[:8], 16))

        # Nearer the hero reads as nearer the viewer, so it's drawn larger.
        d = math.hypot(cx - hero_x, (cy - hero_y) * 0.8) / far
        h = config.GARDEN_MAX_H - (config.GARDEN_MAX_H - config.GARDEN_MIN_H) * min(1, d)
        h *= rng.uniform(0.92, 1.08)

        img = _scaled(path, h)
        tilt = rng.uniform(-config.MAX_TILT, config.MAX_TILT)
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)

        x = int(min(max(10, cx - img.width / 2), config.CANVAS_W - 10 - img.width))
        y = int(min(max(config.CLOCK_ZONE_BOTTOM + 40, cy - img.height / 2),
                    config.CANVAS_H - 10 - img.height))
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
        line_font = _font(italic=True, size=38)
        y += 14
        for row in _wrap(draw, current.get("line", ""), line_font, 900):
            y = _centered(draw, y, row, line_font, ink)

    canvas.convert("RGB").save(out_path, "PNG")
    return out_path
