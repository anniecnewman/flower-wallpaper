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

# Vertical zones, in pixels from the top.
CLOCK_ZONE_BOTTOM = 600      # iOS clock + date live here; keep it sparse
HERO_CENTER_Y = 1180         # center of the current-read flower
HERO_MAX_H = 760             # its max height
TEXT_TOP = 1620              # title / flower name / adjectives block
BOTTOM_UI_TOP = 2500         # plant almost to the edge now
BUTTON_ZONE_TOP = 2270       # flashlight / camera sit in the bottom corners
BUTTON_ZONE_W = 250          # ...within this much of each side

# Each flower is tipped slightly so the garden doesn't read as a grid.
MAX_TILT = 15                # degrees, left or right         # flashlight + camera buttons; keep it sparse

# Garden cluster: an ellipse the read-flowers scatter across.
CLUSTER_CX, CLUSTER_CY = CANVAS_W // 2, 1360
CLUSTER_RX, CLUSTER_RY = 520, 800

# Size falloff. Most recent read book is largest, earliest smallest.
GARDEN_MAX_H = 300
GARDEN_MIN_H = 165
GARDEN_MIN_ALPHA = 255       # no fading — the reference plate is fully painted
GARDEN_MAX_ALPHA = 255

# ---------------------------------------------------------------- style block
# Prepended to every image generation. Only species + mood words vary.
STYLE_BLOCK = (
    "Botanical illustration of a single flowering plant, in the manner of an "
    "English cottage-garden plate. Fine ink and pencil linework with watercolor "
    "and colored-pencil washes laid over it, hatching visible in the leaves. "
    "The color is TRUE AND VARIED, not muted: scarlet, cornflower blue, "
    "buttercup yellow, warm rose pink, deep violet, fresh leaf green. Clear and "
    "saturated like an English garden in June, though never neon or synthetic. "
    "The delicacy comes from fine linework and translucent washes, NOT from "
    "draining or greying the color. "
    "A single specimen: one stem, its leaves, one or two blooms, three-quarter "
    "view, growing upright. "
    "THE BACKGROUND MUST BE COMPLETELY EMPTY AND FULLY TRANSPARENT. Do not "
    "paint paper, parchment, card, texture, grain, a torn or ragged edge, a "
    "wash, a tint, a vignette, or any tone at all behind the plant. No ground, "
    "no soil, no shadow, no pot, no vase, no frame, no border, no text, no "
    "labels, no signature. Only the plant itself, floating on nothing. "
    "Scientific accuracy of form, painterly looseness of execution."
)

# Typography. Swap TITLE_FONT for another file in fonts/ to change the hand.
TITLE_FONT = "LaBelleAurore.ttf"
TITLE_SIZE = 82          # shrinks automatically if the title is long
TITLE_MIN_SIZE = 46
TITLE_MAX_W = 960        # px the title must fit inside

IMAGE_MODEL = "gpt-image-1"
IMAGE_SIZE = "1024x1536"
TEXT_MODEL = "claude-sonnet-4-6"
