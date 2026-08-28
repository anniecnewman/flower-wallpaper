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
BOTTOM_UI_TOP = 2230         # flashlight + camera buttons; keep it sparse

# Garden cluster: an ellipse the read-flowers scatter across.
CLUSTER_CX, CLUSTER_CY = CANVAS_W // 2, 1360
CLUSTER_RX, CLUSTER_RY = 520, 800

# Size falloff. Most recent read book is largest, earliest smallest.
GARDEN_MAX_H = 330
GARDEN_MIN_H = 150
GARDEN_MIN_ALPHA = 150       # earliest books fade back like distant specimens
GARDEN_MAX_ALPHA = 255

# ---------------------------------------------------------------- style block
# Prepended to every image generation. Only species + mood words vary.
STYLE_BLOCK = (
    "Botanical field-guide illustration in the style of a 19th-century "
    "naturalist's plate. Fine ink linework in warm sepia-black, filled with "
    "loose watercolor washes that occasionally break past the lines. Muted "
    "naturalistic palette: earth tones, dusty blues, sage, ochre, soft rust. "
    "Visible paper grain and pigment pooling. A single specimen: one stem, "
    "its leaves, one or two blooms, in three-quarter view. Isolated on a plain "
    "transparent background. No scene, no ground, no shadow, no vase, no pot, "
    "no border, no text, no labels. Scientific accuracy of form, painterly "
    "imperfection of execution."
)

# Typography. Swap TITLE_FONT for another file in fonts/ to change the hand.
TITLE_FONT = "PinyonScript-Regular.ttf"
TITLE_SIZE = 96          # shrinks automatically if the title is long
TITLE_MIN_SIZE = 52
TITLE_MAX_W = 980        # px the title must fit inside

IMAGE_MODEL = "gpt-image-1"
IMAGE_SIZE = "1024x1536"
TEXT_MODEL = "claude-sonnet-4-6"
