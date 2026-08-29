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


def _text_band():
    """Vertical span kept clear so the type has air around it."""
    return (config.TEXT_TOP - 70, config.TEXT_TOP + config.TEXT_CLEARANCE)


def _keepout(cx, cy):
    """Inside the clear zone around the current read?

    A plain ellipse would leave a visibly drawn arc, so the boundary is warped
    by a couple of slow sine terms — the edge stays roughly circular but reads
    as something that grew rather than something ruled.
    """
    dx = (cx - config.CANVAS_W / 2) / config.KEEPOUT_RX
    dy = (cy - config.KEEPOUT_CY) / config.KEEPOUT_RY
    d = math.hypot(dx, dy)
    if d == 0:
        return True
    ang = math.atan2(dy, dx)
    wobble = (1
              + config.KEEPOUT_WOBBLE * math.sin(3 * ang + 0.9)
              + config.KEEPOUT_WOBBLE * 0.6 * math.sin(5 * ang - 2.1))
    return d < wobble


def _in_garden(cx, cy):
    """True where a flower may grow: anywhere but the clear zone, the type,
    the clock, and the two bottom-corner buttons."""
    if cy < config.CLOCK_ZONE_BOTTOM + 40 or cy > config.BOTTOM_UI_TOP:
        return False
    if cy > config.BUTTON_ZONE_TOP and (cx < config.BUTTON_ZONE_W
                                        or cx > config.CANVAS_W - config.BUTTON_ZONE_W):
        return False
    t0, t1 = _text_band()
    if t0 < cy < t1:
        return False
    return not _keepout(cx, cy)


def _poisson(seed=20260828, tries=30):
    """Organic scatter at a FIXED spacing, filling the garden's whole shape.

    Bridson's algorithm with an elliptical radius, so upright flowers sit
    closer side-to-side than head-to-toe. Spacing never varies with the number
    of books — a bigger year simply reaches further up the screen.
    """
    rx, ry = config.SPACING_X, config.SPACING_Y
    rng = random.Random(seed)

    def far_enough(p, pts):
        for q in pts:
            dx = (p[0] - q[0]) / rx
            dy = (p[1] - q[1]) / ry
            if dx * dx + dy * dy < 1.0:
                return False
        return True

    # Seed both masses, and both flanks of each, or the scatter can't spread.
    cx = config.CANVAS_W / 2
    seeds = [(cx, config.BOTTOM_UI_TOP - ry * 0.5),
             (150, config.CANVAS_H - 260), (config.CANVAS_W - 150, config.CANVAS_H - 260),
             (cx, config.CLOCK_ZONE_BOTTOM + 120),
             (170, config.CLOCK_ZONE_BOTTOM + 120),
             (config.CANVAS_W - 170, config.CLOCK_ZONE_BOTTOM + 120),
             (90, config.KEEPOUT_CY), (config.CANVAS_W - 90, config.KEEPOUT_CY)]

    pts, active = [], []
    for p in seeds:
        if _in_garden(*p) and far_enough(p, pts):
            pts.append(p)
            active.append(p)

    while active and len(pts) < 400:
        i = rng.randrange(len(active))
        base = active[i]
        placed = False
        for _ in range(tries):
            ang = rng.uniform(0, 2 * math.pi)
            rad = rng.uniform(1.0, 1.85)
            p = (base[0] + math.cos(ang) * rx * rad,
                 base[1] + math.sin(ang) * ry * rad)
            if not (20 < p[0] < config.CANVAS_W - 20):
                continue
            if not _in_garden(*p):
                continue
            if far_enough(p, pts):
                pts.append(p)
                active.append(p)
                placed = True
                break
        if not placed:
            active.pop(i)

    # Planted from the bottom middle outward and upward.
    pts.sort(key=lambda p: (-round(p[1] / (ry * 0.75)),
                            abs(p[0] - config.CANVAS_W / 2)))
    return pts


def _place_garden(canvas, garden):
    """garden: (book_id, png_path), OLDEST first — planted from the bottom up."""
    if not garden:
        return
    pts = _poisson()
    t0, t1 = _text_band()

    for (book_id, path), (cx, cy) in zip(garden, pts):
        rng = random.Random(int(hashlib.md5(book_id.encode()).hexdigest()[:8], 16))
        tilt = rng.uniform(-config.MAX_TILT, config.MAX_TILT)

        img = _scaled(path, config.GARDEN_FLOWER_H * rng.uniform(0.95, 1.05))
        max_w = config.SPACING_X * 1.75
        if img.width > max_w:
            img = _scaled(path, config.GARDEN_FLOWER_H * max_w / img.width)
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)

        x = int(min(max(4, cx - img.width / 2), config.CANVAS_W - 4 - img.width))
        y = int(min(max(config.CLOCK_ZONE_BOTTOM + 20, cy - img.height / 2),
                    config.CANVAS_H - 4 - img.height))

        if y < t1 and y + img.height > t0:      # tall stem reaching into the type
            y = int(t0 - img.height - 10) if cy < (t0 + t1) / 2 else int(t1 + 10)
            if y < config.CLOCK_ZONE_BOTTOM or y + img.height > config.CANVAS_H:
                continue

        canvas.alpha_composite(img, (x, y))


# ------------------------------------------------------------------- render
def build(current, garden, out_path):
    """current: dict with title / flower / adjectives / png path (or None).
       garden:  list of (book_id, png_path), newest finished first."""
    canvas = Image.new("RGBA", (config.CANVAS_W, config.CANVAS_H),
                       config.PAPER + (255,))

    _place_garden(canvas, garden)

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

        # Inside the clear zone, just above the flower it refers to.
        label_y = config.KEEPOUT_CY - config.KEEPOUT_RY + config.LABEL_GAP
        _centered(draw, label_y, "reading now",
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
