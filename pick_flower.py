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

FIRST, KNOW THE BOOK. You have a web search tool. Unless you are certain what \
the book actually is — its plot, subject, register, reputation — search for it \
before choosing anything. Titles mislead. A book called "Whistler" might be a \
biography of the painter, a legal thriller, or a memoir. Guessing from a title \
produces a flower that fits an imaginary book, which is worse than no flower.

Search when you are unsure. Do not pretend to knowledge you don't have.

THEN CHOOSE. The reader's own notes, when present, are your most important \
input — they tell you what the book was like FOR THIS READER, and your flower \
should answer their reaction, not a generic summary. A reader who found a \
thriller implausible but fun deserves a flower that is itself a little \
unbelievable.

Choose a real, illustratable flowering plant. Earn the connection through some \
genuine property of the plant — how it grows, when it blooms, how long it \
lasts, its history, what people mistake it for. Avoid the obvious symbolic \
dictionary (red rose = love, lily = death).

VOICE. Write plainly. Gentle and straightforward, like a knowledgeable friend \
telling you something true, not like a poet performing. Specifically:
- No ornate or archaic diction. No "as if memory arrives before reason does."
- No rhetorical flourishes, inversions, or dramatic sentence rhythms.
- Say the concrete thing. "It blooms for one night" beats "its beauty is \
  categorical rather than decorative."
- Short words over long ones. Plain syntax.
- It is fine to be quiet and unremarkable. Better that than overwrought.

Return, in JSON only, no markdown fence:
{
  "summary": "One plain sentence: what this book actually is. Say if unsure.",
  "flower": "Common name",
  "latin": "Genus species",
  "line": "Under 20 words. Goes on a wallpaper under the illustration. \
Plain, concrete, no flourish. Don't start with the flower's name.",
  "adjectives": ["three", "mood", "words"],
  "reason": "1-2 plain sentences: why this flower for this book."
}"""


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
    """Pull our JSON object out of a reply that may also carry search prose.

    Search results bring their own braces, so take the last balanced object
    that actually looks like ours rather than the first one we trip over.
    """
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "flower" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    found, depth, start = [], 0, None
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(cleaned[start:i + 1])
                    if isinstance(obj, dict) and "flower" in obj:
                        found.append(obj)
                except json.JSONDecodeError:
                    pass
    if found:
        return found[-1]
    raise ValueError(f"No usable JSON in reply: {text[:300]!r}")


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
            "max_tokens": 3000,
            "system": SYSTEM,
            "messages": messages,
            "tools": [{"type": "web_search_20250305",
                       "name": "web_search",
                       "max_uses": 4}],
        },
        timeout=300,
    )
    r.raise_for_status()
    blocks = r.json()["content"]
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
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
                    "max_tokens": 3000,
                    "system": DESCRIBE_SYSTEM,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": [{"type": "web_search_20250305",
                               "name": "web_search",
                               "max_uses": 4}],
                },
                timeout=300,
            )
            r.raise_for_status()
            blocks = r.json()["content"]
            text = "".join(b.get("text", "") for b in blocks
                           if b.get("type") == "text")
            result = _extract_json(text)
            if result.get("line"):
                result["flower"] = flower_name
                return result
        except (ValueError, json.JSONDecodeError) as e:
            print(f"      (unparseable reply, retrying: {e})", flush=True)
    raise RuntimeError(f"Could not describe {flower_name} for {book['title']!r}")
