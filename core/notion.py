"""Reading Notion, in one place.

The portal and the MCP server each grew their own copy of these — the
portal's file even says "ported from the MCP server" — and they drifted. The
MCP's version had learned to read rollups, created_by, last_edited_by and
unique_id; the portal's had not. Merged here, so the next property type only
has to be taught once.

They also disagreed on what to do with a property type neither handles, and
that difference is deliberate rather than accidental:

- the portal drops unknown properties (`simplify_page` filters out None), so
  a new Notion field cannot put stray text on a page;
- the MCP server shows `[rollup]` so Claude can see something is there and
  say so rather than silently omitting it.

`on_unknown` keeps both behaviours instead of forcing one on the other.
"""

from datetime import date, datetime


def rich_text_to_str(rt_array) -> str:
    """Flatten a Notion rich-text array to a plain string."""
    return "".join(seg.get("plain_text", "") for seg in rt_array or [])


def _drop(_type):
    return None


def _show_type(prop_type):
    return f"[{prop_type}]"


def extract_property_value(prop, on_unknown=_drop):
    """A human-readable value for a Notion property.

    `on_unknown` is called with the property type when we don't handle it.
    Defaults to dropping it; pass `show_unknown_type` to surface a marker.
    """
    t = prop["type"]

    if t == "title":
        return rich_text_to_str(prop["title"])
    if t == "rich_text":
        return rich_text_to_str(prop["rich_text"])
    if t == "number":
        return str(prop["number"]) if prop["number"] is not None else None
    if t == "select":
        return prop["select"]["name"] if prop["select"] else None
    if t == "status":
        return prop["status"]["name"] if prop["status"] else None
    if t == "multi_select":
        return ", ".join(s["name"] for s in prop["multi_select"]) or None
    if t == "date":
        d = prop["date"]
        if not d:
            return None
        start, end = d.get("start", ""), d.get("end")
        return f"{start} to {end}" if end else start
    if t == "checkbox":
        return "Yes" if prop["checkbox"] else "No"
    if t == "url":
        return prop["url"]
    if t == "email":
        return prop["email"]
    if t == "phone_number":
        return prop["phone_number"]
    if t == "people":
        names = [p.get("name", "Unknown") for p in prop["people"]]
        return ", ".join(names) if names else None
    if t == "relation":
        n = len(prop["relation"])
        return f"({n} linked)" if n else None
    if t == "formula":
        f = prop["formula"]
        return str(f.get(f["type"]))
    if t == "rollup":
        r = prop["rollup"]
        rtype = r["type"]
        if rtype == "array":
            items = r.get("array", [])
            if not items:
                return None
            return ", ".join(str(extract_property_value(i, on_unknown)) for i in items if i)
        return str(r.get(rtype))
    if t == "created_time":
        return prop["created_time"]
    if t == "last_edited_time":
        return prop["last_edited_time"]
    if t == "created_by":
        return prop["created_by"].get("name", "Unknown")
    if t == "last_edited_by":
        return prop["last_edited_by"].get("name", "Unknown")
    if t == "unique_id":
        uid = prop["unique_id"]
        prefix, number = uid.get("prefix", ""), uid.get("number", "")
        return f"{prefix}-{number}" if prefix else str(number)

    return on_unknown(t)


# Pass as on_unknown= where an unhandled property should be visible rather
# than dropped — the MCP server wants this so Claude can see a field exists.
show_unknown_type = _show_type


def get_page_title(page) -> str:
    """The page's title property, or 'Untitled'."""
    for prop in page.get("properties", {}).values():
        if prop["type"] == "title":
            return rich_text_to_str(prop["title"]) or "Untitled"
    return "Untitled"


def get_date_prop(page, name: str) -> date | None:
    """The start of a date property as a date, or None."""
    prop = page.get("properties", {}).get(name)
    if not prop or prop.get("type") != "date" or not prop.get("date"):
        return None
    start = prop["date"].get("start", "")
    try:
        return datetime.fromisoformat(start.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def simplify_page(page) -> dict:
    """Flatten a page to {id, title, url, props} for templates.

    Properties with no value are omitted rather than rendered empty.
    """
    props = {}
    for name, prop in page.get("properties", {}).items():
        if prop["type"] == "title":
            continue
        value = extract_property_value(prop)
        if value is not None and str(value).strip():
            props[name] = value
    return {
        "id": page["id"],
        "title": get_page_title(page),
        "url": page.get("url"),
        "props": props,
    }


class DataSources:
    """Resolves and caches database -> data source ids.

    Notion v3 addresses data sources rather than databases: queries go to
    data_sources.query() and pages are parented to a data source. Database
    ids are stable, so one lookup per process is enough.
    """

    def __init__(self, client):
        self._client = client
        self._cache: dict[str, str] = {}

    def id_for(self, db_id: str) -> str:
        if db_id not in self._cache:
            db = self._client.databases.retrieve(database_id=db_id)
            self._cache[db_id] = db["data_sources"][0]["id"]
        return self._cache[db_id]

    def parent(self, db_id: str) -> dict:
        """The parent block for creating a page in a database."""
        return {"type": "data_source_id", "data_source_id": self.id_for(db_id)}
