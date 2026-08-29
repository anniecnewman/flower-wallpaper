"""Assemble the wallpaper: a hero flower for the current read, a cluster of
finished ones around it, and the type block underneath.

Placement is deterministic — seeded from each book's Notion id — so a flower
keeps its seat in the garden from one day to the next.
"""

import hashlib
import math
import os
import random

import numpy as np
from scipy import ndimage
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
def _harmonize(img):
    """Repaint a flat background wash to the canvas colour so it disappears.

    Deliberately non-destructive: it changes colour, never transparency. If the
    detection misfires the worst case is a pale flower going cream, not the
    ghost outlines that deleting pixels produced.
    """
    if not config.HARMONIZE:
        return img
    a = np.array(img.convert("RGBA"))
    rgb = a[:, :, :3].astype(np.int16)
    alpha = a[:, :, 3]

    clear = alpha < 24
    if clear.mean() < 0.02:              # no transparency to reason from
        return img

    # The wash shows up as opaque pixels sitting right against the empty area.
    ring = ndimage.binary_dilation(clear, iterations=3) & (alpha > 200)
    value = rgb.max(axis=2)
    sat = value - rgb.min(axis=2)
    ring &= (value >= 200) & (sat <= 55)
    if ring.sum() < 400:                 # nothing wash-like at the edges
        return img
    bg = np.median(rgb[ring], axis=0)

    near = (np.abs(rgb - bg).max(axis=2) <= config.HARMONIZE_TOL) & (alpha > 0)
    ink = ndimage.binary_closing(~(near | clear), structure=np.ones((7, 7)))

    labels, n = ndimage.label(~ink)
    if not n:
        return img
    seeds = set(np.unique(labels[clear]))
    seeds |= set(labels[0, :]) | set(labels[-1, :]) | \
             set(labels[:, 0]) | set(labels[:, -1])
    seeds.discard(0)
    if not seeds:
        return img

    wash = np.isin(labels, list(seeds)) & near
    opaque = (alpha > 128).sum()
    # A painted wash is legitimately most of the opaque area — the plant itself
    # is thin. Only refuse if it would repaint essentially everything.
    if not opaque or wash.sum() / opaque > 0.90:
        return img

    a[:, :, 0][wash] = config.PAPER[0]
    a[:, :, 1][wash] = config.PAPER[1]
    a[:, :, 2][wash] = config.PAPER[2]
    return Image.fromarray(a, "RGBA")


def _scaled(path, target_h, alpha=255):
    img = _harmonize(Image.open(path).convert("RGBA"))
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


def _poisson(seed=20260828, tries=30, density=0.5):
    """Organic scatter at a FIXED spacing, filling the garden's whole shape.

    Bridson's algorithm with an elliptical radius, so upright flowers sit
    closer side-to-side than head-to-toe. Spacing never varies with the number
    of books — a bigger year simply reaches further up the screen.
    """
    # A dense lattice of candidate positions. Actual separation is enforced
    # later against each flower's painted extents, so this only needs to offer
    # plenty of well-spread options to choose from.
    rx = config.SPACING_X * density
    ry = config.SPACING_Y * density
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

    while active and len(pts) < 900:
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


def _clear_of(box, placed, gap):
    """True if this rectangle keeps `gap` px from every placed flower."""
    x1, y1, x2, y2 = box
    for (px1, py1, px2, py2) in placed:
        if (x1 - gap < px2 and x2 + gap > px1
                and y1 - gap < py2 and y2 + gap > py1):
            return False
    return True


def _place_garden(canvas, garden):
    """garden: (book_id, png_path), OLDEST first — planted from the bottom up.

    Poisson spacing distributes the centres evenly, but a sprawling nasturtium
    and a narrow spike are very different widths at the same centre distance.
    So every flower is checked against the painted extents of the ones already
    down, and moved to the next free spot if it would touch.
    """
    if not garden:
        return
    spots = _poisson()
    t0, t1 = _text_band()
    placed = []
    used = set()

    for book_id, path in garden:
        rng = random.Random(int(hashlib.md5(book_id.encode()).hexdigest()[:8], 16))
        tilt = rng.uniform(-config.MAX_TILT, config.MAX_TILT)
        wobble = rng.uniform(0.94, 1.06)

        # If a flower can't find room at full size, let it grow a little
        # smaller rather than drop out of the garden entirely.
        for shrink in (1.0, 0.88, 0.76, 0.64):
            img = _scaled(path, config.GARDEN_FLOWER_H * wobble * shrink)
            img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
            bbox = img.getchannel("A").getbbox()
            if bbox:
                img = img.crop(bbox)

            spot = None
            for idx, (cx, cy) in enumerate(spots):
                if idx in used:
                    continue
                x = min(max(6, cx - img.width / 2), config.CANVAS_W - 6 - img.width)
                y = min(max(config.CLOCK_ZONE_BOTTOM + 20, cy - img.height / 2),
                        config.CANVAS_H - 6 - img.height)
                box = (x, y, x + img.width, y + img.height)

                if box[1] < t1 and box[3] > t0:
                    continue
                mid_x = box[0] + img.width / 2
                if _keepout(cx, cy) or _keepout(mid_x, box[1]) \
                        or _keepout(mid_x, box[3]):
                    continue
                if not _clear_of(box, placed, config.GARDEN_GAP):
                    continue
                spot = (idx, x, y, box)
                break

            if spot:
                idx, x, y, box = spot
                canvas.alpha_composite(img, (int(x), int(y)))
                placed.append(box)
                used.add(idx)
                break


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
