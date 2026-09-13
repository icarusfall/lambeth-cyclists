"""Tests for the shared Notion helpers.

The portal and the MCP server had diverged copies of these. The point of most
of what follows is to pin the behaviours that differed, so a future tidy-up
does not quietly collapse them into one and change what a caller sees.
"""

from datetime import date

from core.notion import (
    TEXT_LIMIT,
    DataSources,
    clip_text,
    split_text,
    extract_property_value,
    get_date_prop,
    get_page_title,
    rich_text_to_str,
    show_unknown_type,
    simplify_page,
)


def rt(text):
    return [{"plain_text": text}]


def test_rich_text_joins_segments():
    assert rich_text_to_str(rt("a") + rt("b")) == "ab"
    assert rich_text_to_str([]) == ""
    assert rich_text_to_str(None) == ""


def test_the_types_both_copies_agreed_on():
    cases = [
        ({"type": "select", "select": {"name": "high"}}, "high"),
        ({"type": "select", "select": None}, None),
        ({"type": "multi_select", "multi_select": [{"name": "a"}, {"name": "b"}]}, "a, b"),
        ({"type": "checkbox", "checkbox": True}, "Yes"),
        ({"type": "url", "url": "https://example.org"}, "https://example.org"),
        ({"type": "date", "date": {"start": "2026-08-30"}}, "2026-08-30"),
        ({"type": "date", "date": {"start": "2026-08-01", "end": "2026-08-30"}},
         "2026-08-01 to 2026-08-30"),
        ({"type": "relation", "relation": [{"id": "x"}, {"id": "y"}]}, "(2 linked)"),
        ({"type": "relation", "relation": []}, None),
    ]
    for prop, expected in cases:
        assert extract_property_value(prop) == expected, prop["type"]


def test_types_only_the_mcp_copy_understood():
    """These were dropped by the portal's copy; the merged one reads them."""
    assert extract_property_value(
        {"type": "created_by", "created_by": {"name": "Colin"}}) == "Colin"
    assert extract_property_value(
        {"type": "unique_id", "unique_id": {"prefix": "ITEM", "number": 12}}) == "ITEM-12"
    assert extract_property_value(
        {"type": "unique_id", "unique_id": {"prefix": "", "number": 7}}) == "7"
    assert extract_property_value({
        "type": "rollup",
        "rollup": {"type": "array", "array": [
            {"type": "select", "select": {"name": "one"}},
            {"type": "select", "select": {"name": "two"}},
        ]},
    }) == "one, two"


def test_unknown_property_behaviour_differs_on_purpose():
    """The portal drops what it cannot read; the MCP server says so.

    Collapsing these would either put stray '[type]' text into portal pages
    or make CycleBot silently omit a field it can see exists.
    """
    unknown = {"type": "verification", "verification": {}}
    assert extract_property_value(unknown) is None
    assert extract_property_value(unknown, on_unknown=show_unknown_type) == "[verification]"


def test_page_title_and_dates():
    page = {"properties": {
        "Title": {"type": "title", "title": rt("Acre Lane")},
        "Received": {"type": "date", "date": {"start": "2026-08-30T13:00:00.000+00:00"}},
        "Missing": {"type": "date", "date": None},
    }}
    assert get_page_title(page) == "Acre Lane"
    assert get_page_title({"properties": {}}) == "Untitled"
    assert get_date_prop(page, "Received") == date(2026, 8, 30)
    assert get_date_prop(page, "Missing") is None
    assert get_date_prop(page, "Absent") is None


def test_simplify_page_omits_empties_and_the_title():
    page = {
        "id": "abc",
        "url": "https://notion.so/abc",
        "properties": {
            "Title": {"type": "title", "title": rt("A thing")},
            "Status": {"type": "select", "select": {"name": "new"}},
            "Owner": {"type": "select", "select": None},
            "Tags": {"type": "multi_select", "multi_select": []},
        },
    }
    out = simplify_page(page)
    assert out["title"] == "A thing"
    assert out["props"] == {"Status": "new"}


class FakeClient:
    """Stands in for notion_client.Client, counting lookups."""

    def __init__(self):
        self.calls = 0
        self.databases = self

    def retrieve(self, database_id):
        self.calls += 1
        return {"data_sources": [{"id": f"ds_of_{database_id}"}]}


def test_data_source_lookup_is_cached_and_shapes_the_parent():
    client = FakeClient()
    ds = DataSources(client)
    assert ds.id_for("db1") == "ds_of_db1"
    assert ds.id_for("db1") == "ds_of_db1"
    assert client.calls == 1, "database ids are stable; look them up once"
    assert ds.parent("db2") == {"type": "data_source_id", "data_source_id": "ds_of_db2"}


# ---------------------------------------------------------------------------
# Fitting text inside Notion's limit
# ---------------------------------------------------------------------------
# Notion counts UTF-16 units. These pin that, because the obvious `[:2000]`
# passes every test written in plain ASCII and fails in production the first
# time somebody pastes an announcement with emoji in it.

BIKE = "🚲"  # one character to Python, two units to Notion


def units(text):
    return len(text.encode("utf-16-le")) // 2


def test_the_bug_this_exists_for():
    # The newsletter that would not save: five emoji in the first 2000.
    body = BIKE * 5 + "a" * 3000
    assert units(body[:TEXT_LIMIT]) == 2005  # what slicing used to send
    assert units(clip_text(body)) <= TEXT_LIMIT
    assert all(units(c) <= TEXT_LIMIT for c in split_text(body))


def test_clip_never_cuts_an_emoji_in_half():
    text = "a" * 1999 + BIKE + "b"
    clipped = clip_text(text)
    assert clipped == "a" * 1999
    assert units(clipped) <= TEXT_LIMIT


def test_clip_leaves_short_text_alone():
    assert clip_text("Acre Lane " + BIKE) == "Acre Lane " + BIKE
    assert clip_text("") == ""
    assert clip_text(None) == ""


def test_clip_honours_a_smaller_limit():
    assert units(clip_text(BIKE * 1000, 1900)) <= 1900


def test_split_loses_nothing():
    for body in (BIKE * 1500, "x" * 4500, "a" * 1999 + BIKE + "b" * 10):
        pieces = split_text(body)
        assert "".join(pieces) == body
        assert all(units(p) <= TEXT_LIMIT for p in pieces)


def test_split_of_nothing_is_one_empty_piece():
    # Notion wants at least one rich-text run in a code block.
    assert split_text("") == [""]
    assert split_text(None) == [""]
