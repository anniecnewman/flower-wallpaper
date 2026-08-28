"""Ask Claude to choose a flower for a book, and hold it to a unique species.

Uniqueness is enforced twice: the taken list goes into the prompt, and the
response is checked against that list in code. Prompts drift; the check doesn't.
"""

import json
import re
import requests

import config

SYSTEM = """You assign a flower to a book, the way a 19th-century florist would \
have — by resemblance of character, not by decoration.

You will be given a book: title, author, genre, tags, the reader's star rating, \
and sometimes a line of the reader's own notes about it. When those notes exist \
they are the most important input you have. They tell you what the book was \
like FOR THIS READER, and your flower should answer their reaction, not a \
generic summary of the book. A reader who found a thriller implausible but fun \
deserves a flower that is itself a little unbelievable.

Choose a real, illustratable flowering plant. The connection should be earned \
through some genuine property of the plant — how it grows, when it blooms, how \
long it lasts, its history, its folklore, what people mistake it for. Avoid the \
obvious symbolic dictionary (red rose = love, lily = death). Reach for the \
specific.

Then give exactly three adjectives that describe the book and the flower at \
once. They appear on a wallpaper under the illustration, so they should be \
concrete and a little surprising. No clichés. Never unkind about a book the \
reader rated highly.

Return ONLY valid JSON, no markdown fence:
{"flower": "Common name", "latin": "Genus species", \
"adjectives": ["one", "two", "three"], "reason": "1-2 sentences."}"""


def _describe(book):
    bits = [f"Title: {book['title']}"]
    if book.get("authors"):
        bits.append(f"Author: {', '.join(book['authors'])}")
    if book.get("genres"):
        bits.append(f"Genre: {', '.join(book['genres'])}")
    if book.get("tags"):
        bits.append(f"Tags: {', '.join(book['tags'])}")
    if book.get("rating"):
        bits.append(f"Reader's rating: {book['rating']}")
    if book.get("thoughts"):
        bits.append(f"Reader's own notes: \"{book['thoughts']}\"")
    else:
        bits.append("Reader's own notes: (none — judge from the book itself)")
    return "\n".join(bits)


def _norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _call(messages):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.TEXT_MODEL,
            "max_tokens": 500,
            "system": SYSTEM,
            "messages": messages,
        },
        timeout=90,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    return json.loads(re.sub(r"```(json)?", "", text).strip())


def pick(book, taken):
    """Return a flower dict whose species is not already in `taken`."""
    taken_norm = {_norm(t) for t in taken}
    excluded = ", ".join(sorted(taken)) if taken else "(none yet)"

    prompt = (
        f"{_describe(book)}\n\n"
        f"These flowers are already assigned to other books and are "
        f"UNAVAILABLE. Do not choose any of them, or a trivial variant:\n"
        f"{excluded}"
    )
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(4):
        result = _call(messages)
        name = result.get("flower", "")
        if _norm(name) not in taken_norm:
            return result
        # Collision. Name it and make it try again.
        messages += [
            {"role": "assistant", "content": json.dumps(result)},
            {"role": "user", "content":
                f"'{name}' is already taken by another book. Choose a "
                f"genuinely different species and return JSON only."},
        ]

    raise RuntimeError(f"Could not find a unique flower for {book['title']!r}")
