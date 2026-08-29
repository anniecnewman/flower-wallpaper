"""Build today's wallpaper.

    python run.py            # current year's garden
    python run.py --year 2025
    python run.py --dry-run  # pick flowers, skip image generation

Flowers are picked and drawn once, then reused forever. A normal daily run
usually generates nothing at all and just re-composes.
"""

import argparse
import datetime as dt
import os
import sys

import config
import notion_io
import pick_flower
import generate_flower
import compose

OUT = os.path.join(os.path.dirname(__file__), "wallpaper.png")


def log(msg):
    print(msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=dt.date.today().year)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for name, val in (("NOTION_TOKEN", config.NOTION_TOKEN),
                      ("ANTHROPIC_API_KEY", config.ANTHROPIC_API_KEY),
                      ("OPENAI_API_KEY", config.OPENAI_API_KEY)):
        if not val and not (args.dry_run and name == "OPENAI_API_KEY"):
            sys.exit(f"Missing {name}. See README.")

    added = notion_io.ensure_schema()
    if added:
        log(f"Added columns to Notion: {', '.join(added)}")

    all_books = notion_io.fetch_books()
    year_books = [
        b for b in all_books
        if b["status"] == config.STATUS_READ
        and (b["completed"] or "").startswith(str(args.year))
    ]
    reading = [b for b in all_books if b["status"] == config.STATUS_READING]

    if not reading:
        log("Nothing marked 'reading' — the center will be empty. "
            "Mark a book as reading in Notion.")
    elif len(reading) > 1:
        reading.sort(key=lambda b: b["title"])
        log(f"{len(reading)} books marked 'reading'; featuring "
            f"{reading[0]['title']!r}.")

    current = reading[0] if reading else None
    needed = year_books + ([current] if current else [])

    # Every flower ever assigned is off the table, not just this year's.
    taken = {b["flower"] for b in all_books if b["flower"]}

    for book in needed:
        # Three cases: no flower yet, a flower picked before the sentence
        # existed, or fully described already.
        if not book["flower"] or not book["flower_reason"]:
            book_full = notion_io.enrich(book)
            try:
                if book["flower"]:
                    result = pick_flower.describe(book_full, book["flower"])
                else:
                    result = pick_flower.pick(book_full, taken)
            except Exception as e:
                log(f"  !! skipped {book['title']}: {e}")
                continue
            book["flower"] = result["flower"]
            book["flower_notes"] = result["line"]
            book["flower_reason"] = result.get("reason", "")
            book["_adjectives"] = result.get("adjectives", [])
            book["_latin"] = result.get("latin", "")
            taken.add(result["flower"])
            notion_io.write_flower(book["id"], flower=result["flower"],
                                   notes=result["line"],
                                   reason=book["flower_reason"])
            log(f"  {book['title']}  ->  {result['flower']}")
            if result.get("summary"):
                log(f"      [book] {result['summary']}")
            log(f"      \u201c{result['line']}\u201d")
            log(f"      {book['flower_reason']}")

        if args.dry_run:
            continue

        key = generate_flower.asset_key(book["title"], book["id"])
        local = os.path.join(generate_flower.FLOWER_DIR, f"{key}.png")
        if not os.path.exists(local):
            spec = {
                "flower": book["flower"],
                "latin": book.get("_latin", ""),
                "adjectives": book.get("_adjectives") or [],
            }
            try:
                local = generate_flower.generate(spec, book["title"], book["id"])
            except Exception as e:
                log(f"  !! could not draw {book['flower']}: {e}")
                continue
            log(f"  drew {book['flower']}")
            url = f"{config.RAW_BASE}/flowers/{key}.png"
            notion_io.write_flower(book["id"], image_url=url)
        if generate_flower.recut_file(local):
            log(f"  re-cut background off {os.path.basename(local)}")
        book["_png"] = local

    if args.dry_run:
        log("Dry run complete — no images drawn, no wallpaper built.")
        return

    # Oldest first: the earliest books of the year are planted at the bottom.
    year_books.sort(key=lambda b: b["completed"] or "")
    garden = [(b["id"], b["_png"]) for b in year_books if b.get("_png")]

    hero = None
    if current and current.get("_png"):
        hero = {
            "title": current["title"],
            "flower": current["flower"],
            "line": current["flower_notes"] or "",
            "png": current["_png"],
        }

    compose.build(hero, garden, OUT)
    log(f"Wrote {OUT} — {len(garden)} in the garden, "
        f"{'hero: ' + hero['title'] if hero else 'no current read'}")


if __name__ == "__main__":
    main()
