"""Tests for the shared Notion helpers.

The portal and the MCP server had diverged copies of these. The point of most
of what follows is to pin the behaviours that differed, so a future tidy-up
does not quietly collapse them into one and change what a caller sees.
"""

from datetime import date

from core.notion import (
    DataSources,
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
