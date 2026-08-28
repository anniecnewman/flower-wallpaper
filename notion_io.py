"""Reading books out of Notion and writing flowers back in.

Property names are matched loosely (case- and punctuation-insensitive) so the
script keeps working if you rename "thoughts?" to "Thoughts" one day.
"""

import re
import requests

import config

API = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {config.NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _find_prop(props, wanted, types=None):
    """Return the real property name matching `wanted`, or None.

    `types` restricts the match to Notion property types — without it, a
    checkbox called "Completed" can shadow the date you actually wanted.
    """
    target = _norm(wanted)

    def ok(name):
        if not types:
            return True
        entry = props.get(name) or {}
        return entry.get("type") in types

    for name in props:                       # exact name, right type
        if _norm(name) == target and ok(name):
            return name
    for name in props:                       # prefix, right type
        if _norm(name).startswith(target) and ok(name):
            return name
    for name in props:                       # right type, name contains target
        if target in _norm(name) and ok(name):
            return name
    if types:                                # only one of that type? take it
        candidates = [n for n in props if ok(n)]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _plain(prop):
    """Flatten any Notion property into a plain Python value."""
    if prop is None:
        return None
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v).strip() or None
    if t == "select":
        return (v or {}).get("name")
    if t == "status":
        return (v or {}).get("name")
    if t == "multi_select":
        return [x["name"] for x in (v or [])]
    if t == "date":
        return (v or {}).get("start")
    if t in ("number", "checkbox", "url"):
        return v
    if t == "formula":
        return v.get(v.get("type"))
    if t == "rollup":
        return None
    if t == "relation":
        return [x["id"] for x in (v or [])]
    return None


def get_schema():
    r = requests.get(f"{API}/databases/{config.NOTION_DATABASE_ID}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["properties"]


def ensure_schema():
    """Add flower / flower notes / flower image columns if they're missing."""
    props = get_schema()
    to_add = {}
    for name, spec in (
        (config.P_FLOWER, {"rich_text": {}}),
        (config.P_FLOWER_NOTES, {"rich_text": {}}),
        (config.P_FLOWER_IMAGE, {"url": {}}),
    ):
        want_type = ("url",) if name == config.P_FLOWER_IMAGE else ("rich_text",)
        if _find_prop(props, name, want_type) is None:
            to_add[name.title()] = spec
    if not to_add:
        return []
    r = requests.patch(
        f"{API}/databases/{config.NOTION_DATABASE_ID}",
        headers=HEADERS,
        json={"properties": to_add},
        timeout=30,
    )
    r.raise_for_status()
    return list(to_add)


def _resolve_relation_titles(page_ids):
    """Relations store page ids; fetch their titles (author names, genres)."""
    names = []
    for pid in page_ids or []:
        try:
            r = requests.get(f"{API}/pages/{pid}", headers=HEADERS, timeout=30)
            r.raise_for_status()
            for prop in r.json()["properties"].values():
                if prop.get("type") == "title":
                    names.append(_plain(prop))
                    break
        except requests.RequestException:
            continue
    return [n for n in names if n]


def fetch_books(year=None):
    """Return every book, normalized. Optionally only those completed in `year`."""
    books, cursor = [], None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
            f"{API}/databases/{config.NOTION_DATABASE_ID}/query",
            headers=HEADERS, json=payload, timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        for page in data["results"]:
            props = page["properties"]

            def g(wanted, types=None):
                key = _find_prop(props, wanted, types)
                return _plain(props[key]) if key else None

            completed = g(config.P_COMPLETED, ("date",))
            if not isinstance(completed, str):
                completed = None
            book = {
                "id": page["id"],
                "title": g(config.P_TITLE, ("title",)),
                "status": (g(config.P_STATUS, ("status", "select")) or "").lower(),
                "rating": g(config.P_RATING, ("select", "number", "rich_text",
                                              "multi_select", "formula")),
                "tags": g(config.P_TAGS, ("multi_select",)) or [],
                "thoughts": g(config.P_THOUGHTS, ("rich_text",)),
                "completed": completed,
                "author_ids": g(config.P_AUTHOR, ("relation",)) or [],
                "genre_ids": g(config.P_GENRE, ("relation",)) or [],
                "flower": g(config.P_FLOWER, ("rich_text",)),
                "flower_notes": g(config.P_FLOWER_NOTES, ("rich_text",)),
                "flower_image": g(config.P_FLOWER_IMAGE, ("url",)),
            }
            if isinstance(book["rating"], list):
                book["rating"] = ", ".join(book["rating"]) or None
            if not book["title"]:
                continue
            if year and book["status"] == config.STATUS_READ:
                if not completed or not completed.startswith(str(year)):
                    continue
            books.append(book)

        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]

    return books


def enrich(book):
    """Attach author and genre names. Only called for books needing a flower."""
    book["authors"] = _resolve_relation_titles(book["author_ids"])
    book["genres"] = _resolve_relation_titles(book["genre_ids"])
    return book


def write_flower(page_id, flower=None, notes=None, image_url=None):
    props = get_schema()
    payload = {}
    if flower is not None:
        key = _find_prop(props, config.P_FLOWER, ("rich_text",))
        payload[key] = {"rich_text": [{"text": {"content": flower}}]}
    if notes is not None:
        key = _find_prop(props, config.P_FLOWER_NOTES, ("rich_text",))
        payload[key] = {"rich_text": [{"text": {"content": notes}}]}
    if image_url is not None:
        key = _find_prop(props, config.P_FLOWER_IMAGE, ("url",))
        payload[key] = {"url": image_url}
    if not payload:
        return
    r = requests.patch(
        f"{API}/pages/{page_id}", headers=HEADERS,
        json={"properties": payload}, timeout=30,
    )
    r.raise_for_status()
