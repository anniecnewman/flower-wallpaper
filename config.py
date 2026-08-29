"""Central configuration for the flower wallpaper."""

import os

# ---------------------------------------------------------------- credentials
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Your books database.
NOTION_DATABASE_ID = "168445e9-173e-81fc-ae0d-e6d91b73ecbc"

# Where the committed flower PNGs will be served from once the repo is public.
# Set GITHUB_REPOSITORY (owner/name) in the Action; falls back for local runs.
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "YOURNAME/flower-wallpaper")
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"

# ------------------------------------------------------------------- schema
# Property names the script reads. Matching is case-insensitive and ignores
# punctuation, so "thoughts?" and "Thoughts" both resolve.
P_TITLE = "title"
P_STATUS = "status"
P_RATING = "rating"
P_TAGS = "tags"
P_THOUGHTS = "thoughts"
P_COMPLETED = "completed"
P_AUTHOR = "author"
P_GENRE = "genre"

# Properties the script creates and writes to.
P_FLOWER = "flower"
P_FLOWER_NOTES = "flower notes"
P_FLOWER_REASON = "flower reason"
P_FLOWER_IMAGE = "flower image"

STATUS_READING = "reading"
STATUS_READ = "read"

# ------------------------------------------------------------------- canvas
# iPhone 15/16 Pro logical wallpaper size. Change if your device differs.
CANVAS_W, CANVAS_H = 1179, 2556
PAPER = (247, 243, 233)  # warm cream, matches the field-guide plate

# Some flowers come back with a flat wash painted behind them despite the
# prompt. Rather than cut it out — which risks eating pale petals — repaint it
# to exactly PAPER so it disappears into the canvas. Applied at render time;
# the saved PNGs are never modified. Set False to see the patches as they are.
HARMONIZE = True
HARMONIZE_TOL = 46           # how close to the wash colour counts as the wash
HARMONIZE_MAX_SAT = 62       # ...and it must be this unsaturated, so petals are safe

# Vertical zones, in pixels from the top.
CLOCK_ZONE_BOTTOM = 70       # plant right up to the top; the clock sits over it
HERO_CENTER_Y = 1275         # center of the current-read flower
HERO_MAX_H = 620             # its max height
TEXT_TOP = 1660              # title / flower name / adjectives block
BOTTOM_UI_TOP = 2500         # plant almost to the bottom edge
BUTTON_ZONE_TOP = 2270       # flashlight / camera sit in the bottom corners
BUTTON_ZONE_W = 250          # ...within this much of each side

# Each flower is tipped slightly so the garden doesn't read as a grid.
MAX_TILT = 22                # degrees, left or right


# Garden grid. Every flower gets an equal cell, so none can ever touch.
GARDEN_FLOWER_H = 225        # every garden flower is this tall. Fixed.
GARDEN_GAP = 16              # painted edges stay this far apart while there's room
GARDEN_MAY_OVERLAP = True    # once the garden is full, let flowers tuck behind
                             # each other rather than drop out of the year
SPACING_X = 104              # centre-to-centre spacing. Never changes with
SPACING_Y = 120              # ...the count, so the garden looks the same always.

# An invisible ellipse around the current read that no garden flower may enter.
# The masses above and below curve around it, leaving the flanks open too.
KEEPOUT_CY = 1420            # centre of the clear zone
KEEPOUT_RX = 560             # how far it reaches sideways
KEEPOUT_RY = 660             # ...and up and down
KEEPOUT_WOBBLE = 0.075       # irregularity, so the edge never reads as drawn
LABEL_GAP = 70               # 'reading now' sits this far inside the clear zone

TEXT_CLEARANCE = 300         # blank band kept around the type, in px

# ---------------------------------------------------------------- style block
# Prepended to every image generation. Only species + mood words vary.
STYLE_BLOCK = (
    "A hand-drawn botanical illustration of one flowering plant, in colored "
    "pencil and watercolor on paper. "
    "DRAWN, NOT RENDERED. The marks of the hand stay visible: fine ink or "
    "pencil outlines, pencil grain in the washes, hatching and line-work for "
    "the veining of leaves and petals. It should look like a page from an old "
    "field guide someone drew by hand. "
    "The color is complete — no area is left blank or white — but it is FLAT "
    "LOCAL COLOR, not modelled form. Do NOT airbrush. No smooth gradients "
    "standing for light and shade, no glossy highlights, no dark rims of "
    "shadow along an edge, no three-dimensional volume, no sheen, no cast "
    "shadow. A leaf is a green shape with drawn veins, not a shaded object. "
    "Where color does shift, it shifts because the flower itself is marked "
    "that way — a yellow throat bleeding into red petals, veining, a paler "
    "edge — never to suggest a light source. "
    "The palette is natural pigment on paper: soft scarlet, dusty crimson, "
    "cornflower blue, violet, buttercup yellow, rose pink, and sage or olive "
    "greens. True and varied, but slightly muted and matte — the color of "
    "watercolor on cotton paper, never screen-bright, neon, or printed. "
    "A single specimen: one stem, its leaves, one or two blooms, three-quarter "
    "view, growing upright, filling the frame. "
    "THE BACKGROUND MUST BE COMPLETELY EMPTY AND FULLY TRANSPARENT. Do not "
    "paint paper, parchment, card, texture, grain, a torn edge, a wash, a tint "
    "or a vignette behind the plant. No ground, no soil, no shadow, no pot, no "
    "vase, no frame, no border, no text, no labels. Only the plant, floating "
    "on nothing."
)

# Typography. Swap TITLE_FONT for another file in fonts/ to change the hand.
TITLE_FONT = "LaBelleAurore.ttf"
TITLE_SIZE = 82          # shrinks automatically if the title is long
TITLE_MIN_SIZE = 46
TITLE_MAX_W = 960        # px the title must fit inside

IMAGE_MODEL = "gpt-image-1"
IMAGE_SIZE = "1024x1536"
TEXT_MODEL = "claude-sonnet-4-6"
