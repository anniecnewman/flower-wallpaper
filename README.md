# Flower wallpaper

A lock screen that grows a flower for every book you read. The book you're
currently reading blooms in the center; finished books settle into the garden
around it. Claude picks the species, an image model paints it, and a scheduled
job reassembles the whole thing daily.

---

## Setup

### 1. Make the repo and upload the files

On github.com, click **+** (top right) → **New repository**. Name it
`flower-wallpaper`. Set it to **Public** — your iPhone needs to fetch the
finished image without logging in. Check **Add a README file** so the repo
isn't empty. Create it.

Now upload. Unzip the folder on your Mac, then on the repo page click
**Add file** → **Upload files**, and drag in everything *inside* the
`flower-wallpaper` folder — the `.py` files, `README.md`, `requirements.txt`,
and the `fonts` and `.github` folders. Scroll down, click **Commit changes**.

That's what "pushing" means. You've done it.

> Finder hides the `.github` folder because its name starts with a dot. Press
> **Cmd + Shift + .** in Finder to show it, then drag it in with the rest. If it
> doesn't make it up, the daily schedule won't run.

### 2. Add your three keys

Repo → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**. Add all three, names exactly as written:

| Name | Where it came from |
|---|---|
| `NOTION_TOKEN` | Notion connection token, starts `ntn_` |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `OPENAI_API_KEY` | platform.openai.com |

### 3. See the flower picks before spending anything

Go to the **Actions** tab. If it asks you to enable workflows, do that. Click
**Build flower wallpaper** on the left, then **Run workflow** on the right.
**Tick the dry run box**, and run it.

It adds the three columns to Notion, picks a flower for each of this year's
books, writes them back, and prints the reasoning in the log. **No images are
drawn and nothing is charged.** Click into the run to read the picks.

If a pick is wrong, clear that book's `Flower` cell in Notion and run it again
— it'll choose differently, avoiding everything already taken.

### 4. Draw them

Same button, **dry run unticked**.

Roughly four cents per flower. Thirty books is about $1.20, once. The finished
`wallpaper.png` gets committed straight back to the repo — refresh and it's
there. Open it and look at it.

To redraw one flower you dislike, delete its PNG from the `flowers/` folder in
the repo and run again.

### 5. Turn on the schedule

Nothing more to do — the schedule is already in the workflow file. It runs
daily at 09:00 UTC (about 5am Eastern) and commits any new flowers. The
**Run workflow** button is there whenever you want it immediately, which is
handy right after you finish a book.

### 6. Point your Shortcut at it

Edit **Get Contents of URL** to:

```
https://raw.githubusercontent.com/YOURNAME/flower-wallpaper/main/wallpaper.png
```

Confirm **Show Preview** is off and **Crop to Subject** is off.

---

## Using it

Mark a book **reading** in Notion when you start it, and **read** when you
finish. That's the whole interface. The next run moves the old flower into the
garden and blooms a new one.

To see it change immediately rather than waiting for the schedule, hit **Run
workflow** in the Actions tab, wait for the green check, then run your Shortcut.

You never need a terminal for any of this.

## Tuning

Everything visual lives in `config.py`:

- `CANVAS_W/H` — set to your iPhone's resolution if it isn't 1179×2556
- `CLOCK_ZONE_BOTTOM` / `BOTTOM_UI_TOP` — the bands kept clear for iOS UI
- `HERO_MAX_H` — how big the current book's flower is
- `GARDEN_MAX_H` / `GARDEN_MIN_H` — newest and oldest garden flowers
- `GARDEN_MIN_ALPHA` — how far the earliest books fade back
- `STYLE_BLOCK` — the illustration style, applied to every flower
- `TITLE_FONT` — the book-title hand. Ships with Pinyon Script; drop any .ttf
  into `fonts/` and name it here. Long titles shrink automatically down to
  `TITLE_MIN_SIZE`.

If a year gets crowded, raise the grid in `compose.py` (`_slots(cols=, rows=)`).

## Notes

- Flower choice is never hardcoded. Every book runs through the same prompt.
- Species are unique across your entire library, enforced in code — the model
  is given the taken list and its answer is checked against it.
- A flower is drawn once and reused. Daily runs normally cost nothing.
- Running `python run.py --year 2025` locally builds a past year's garden,
  if you ever want one.
