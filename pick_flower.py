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

Then write ONE sentence, UNDER 20 WORDS, that goes on a wallpaper beneath the \
illustration. It should land the connection between book and flower in a single \
stroke — concrete, a little surprising, no clichés, no hedging. It is read at a \
glance on a lock screen, so it must work without any other context. Do not \
begin it with the flower's name. Never unkind about a book the reader rated \
highly.

Also give three adjectives. These are NOT displayed — they steer the painting's \
mood — so make them evocative of color and energy.

Finally, write the full reasoning in 1-2 sentences: why this flower, for this \
book, for this reader.

Return ONLY valid JSON, no markdown fence:
{"flower": "Common name", "latin": "Genus species", \
"line": "Under twenty words.", "adjectives": ["one", "two", "three"], \
"reason": "1-2 sentences."}"""


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


def _extract_json(text):
    """Pull the first JSON object out of a reply that may carry prose."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, depth = cleaned.find("{"), 0
    if start == -1:
        raise ValueError(f"No JSON in reply: {text[:200]!r}")
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])
    raise ValueError(f"Unterminated JSON: {text[:200]!r}")


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
            "max_tokens": 900,
            "system": SYSTEM,
            "messages": messages,
        },
        timeout=90,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    return _extract_json(text)


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

    for attempt in range(5):
        try:
            result = _call(messages)
        except (ValueError, json.JSONDecodeError) as e:
            # A malformed reply shouldn't cost us the whole run.
            print(f"      (unparseable reply, retrying: {e})", flush=True)
            continue
        name = result.get("flower", "")
        if not name or not result.get("line"):
            continue
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


DESCRIBE_SYSTEM = SYSTEM + """

In this mode the flower has ALREADY been chosen for this book. Do not choose a \
different one. Keep the given flower and write its line, adjectives and \
reasoning."""


def describe(book, flower_name):
    """Write the line and reasoning for a flower that's already assigned.

    Used to backfill books picked before the sentence existed, without
    discarding a good pick.
    """
    prompt = (
        f"{_describe(book)}\n\n"
        f"The flower already assigned to this book is: {flower_name}.\n"
        f"Keep it. Return the same JSON shape, with \"flower\" set to "
        f"{flower_name!r}."
    )
    for _ in range(4):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config.TEXT_MODEL,
                    "max_tokens": 900,
                    "system": DESCRIBE_SYSTEM,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=90,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"])
            result = _extract_json(text)
            if result.get("line"):
                result["flower"] = flower_name
                return result
        except (ValueError, json.JSONDecodeError) as e:
            print(f"      (unparseable reply, retrying: {e})", flush=True)
    raise RuntimeError(f"Could not describe {flower_name} for {book['title']!r}")
