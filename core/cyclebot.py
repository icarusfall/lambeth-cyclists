"""CycleBot: the read-only Notion agent, in one place.

This is the agent itself — the tools, the system prompt and the conversation
loop — kept separate from any one way of reaching it. It began as the MCP
server's ten tools, which the portal's chat page reached over the network:

    portal -> Anthropic API -> (public internet) -> Railway MCP server -> Notion

The MCP connector means Anthropic's servers call the tools, not ours, so the
MCP server had to be publicly reachable and needed a bearer key to stop the
whole workspace being readable by anyone with the URL. For a chat page in a
service that can already reach Notion directly, that is a long way round.

What actually wants sharing between the chat page and any later surface (a
WhatsApp bot, say) is the agent, not the transport. So it lives here as a
plain function, and the surfaces are thin:

    portal chat       core.cyclebot.answer(history, surface=...)
    WhatsApp (later)  core.cyclebot.answer(history, surface=...)
    mcp/server.py     registers TOOLS with FastMCP, for MCP clients

The MCP server is now a facade over these same functions rather than the only
way in, so third-party MCP clients stay possible without the chat page paying
for them.

Read-only by construction: nothing here writes to Notion.
"""

import os
import inspect
import logging
from functools import lru_cache

import anthropic
from notion_client import Client

from core.claude import MODEL, response_text_of
from core.notion import (
    extract_property_value as _extract,
    get_page_title,
    rich_text_to_str,
    show_unknown_type,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration — database IDs and their data source IDs
# To add a new database: retrieve it, grab the data_sources[0].id, add here.
# ---------------------------------------------------------------------------
def _db(key, default_db, default_ds, label):
    """Database config, overridable per-deployment via NOTION_<KEY>_DB/_DS env vars."""
    return {
        "db_id": os.environ.get(f"NOTION_{key.upper()}_DB", default_db),
        "ds_id": os.environ.get(f"NOTION_{key.upper()}_DS", default_ds),
        "label": label,
    }


DATABASES = {
    "meetings": _db("meetings", "2e42d7a24378803fb811d2f6ed029137",
                    "2e42d7a2-4378-80b4-bba9-000bfdd54b95", "Meetings"),
    "wards": _db("wards", "3002d7a24378814ba99cf54d0664ab1c",
                 "3002d7a2-4378-81f4-85f6-000b48c100c1", "Wards"),
    "councillors": _db("councillors", "3002d7a24378814388effd4357a003d3",
                       "3002d7a2-4378-81d8-8f0e-000be42cf371", "Councillors & Candidates"),
    "items": _db("items", "2e32d7a2437880298c81f1af94c441a0",
                 "2e32d7a2-4378-80c7-ab8b-000b859cd636", "Items"),
    "projects": _db("projects", "2e42d7a2437880d686e8ff554556b0c1",
                    "2e42d7a2-4378-80f3-bafd-000baf137869", "Projects"),
}


_notion_client = None


def use_notion_client(client) -> None:
    """Supply the Notion client instead of building one from the environment.

    The MCP server runs straight off os.environ and can build its own. The
    portal cannot: it loads config with pydantic-settings from its .env, which
    populates a Settings object and never touches os.environ — so it hands
    over the client it already has.
    """
    global _notion_client
    _notion_client = client


def _notion() -> Client:
    """The Notion client, built on first use if nobody supplied one.

    Lazy so that importing this module — which the MCP server, the portal and
    the tests all do — does not require NOTION_API_TOKEN to be set.
    """
    global _notion_client
    if _notion_client is None:
        _notion_client = Client(auth=os.environ["NOTION_API_TOKEN"])
    return _notion_client


# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------


def extract_property_value(prop):
    """A readable value for a Notion property.

    Unhandled types surface as "[type]" rather than being dropped, so Claude
    can see a field exists and say so instead of silently omitting it. The
    portal's own page rendering wants the opposite — see core.notion.
    """
    return _extract(prop, on_unknown=show_unknown_type)


def format_properties(page):
    """Format all properties of a page as markdown."""
    lines = []
    title = get_page_title(page)
    lines.append(f"### {title}")

    for name, prop in sorted(page.get("properties", {}).items()):
        if prop["type"] == "title":
            continue
        value = extract_property_value(prop)
        if value is not None and str(value).strip():
            lines.append(f"- **{name}**: {value}")

    url = page.get("url")
    if url:
        lines.append(f"- [Open in Notion]({url})")

    # Include page ID for drill-down with get_page_detail
    lines.append(f"- *Page ID*: `{page['id']}`")

    return "\n".join(lines)


def blocks_to_markdown(blocks):
    """Convert Notion blocks to markdown text."""
    lines = []
    for block in blocks:
        bt = block["type"]
        if bt == "paragraph":
            text = rich_text_to_str(block["paragraph"]["rich_text"])
            if text:
                lines.append(text)
        elif bt == "heading_1":
            lines.append(f"# {rich_text_to_str(block['heading_1']['rich_text'])}")
        elif bt == "heading_2":
            lines.append(f"## {rich_text_to_str(block['heading_2']['rich_text'])}")
        elif bt == "heading_3":
            lines.append(f"### {rich_text_to_str(block['heading_3']['rich_text'])}")
        elif bt == "bulleted_list_item":
            lines.append(
                f"- {rich_text_to_str(block['bulleted_list_item']['rich_text'])}"
            )
        elif bt == "numbered_list_item":
            lines.append(
                f"1. {rich_text_to_str(block['numbered_list_item']['rich_text'])}"
            )
        elif bt == "to_do":
            text = rich_text_to_str(block["to_do"]["rich_text"])
            checked = "x" if block["to_do"].get("checked") else " "
            lines.append(f"- [{checked}] {text}")
        elif bt == "toggle":
            lines.append(
                f"<details><summary>{rich_text_to_str(block['toggle']['rich_text'])}</summary></details>"
            )
        elif bt == "divider":
            lines.append("---")
        elif bt == "callout":
            text = rich_text_to_str(block["callout"]["rich_text"])
            emoji = block["callout"].get("icon", {}).get("emoji", "")
            lines.append(f"> {emoji} {text}")
        elif bt == "quote":
            lines.append(f"> {rich_text_to_str(block['quote']['rich_text'])}")
        elif bt == "code":
            text = rich_text_to_str(block["code"]["rich_text"])
            lang = block["code"].get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif bt == "table_row":
            cells = block.get("table_row", {}).get("cells", [])
            row = " | ".join(rich_text_to_str(cell) for cell in cells)
            lines.append(f"| {row} |")
        elif bt == "child_page":
            lines.append(
                f"**{block['child_page'].get('title', 'Untitled')}** (sub-page)"
            )
        elif bt == "child_database":
            lines.append(
                f"**{block['child_database'].get('title', 'Untitled')}** (database)"
            )
    return "\n\n".join(lines)


def get_page_content(page_id):
    """Fetch all blocks from a page and return as markdown."""
    all_blocks = []
    cursor = None

    while True:
        kwargs = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        try:
            response = _notion().blocks.children.list(**kwargs)
        except Exception as e:
            logger.error("Error fetching blocks for %s: %s", page_id, e)
            return ""
        all_blocks.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return blocks_to_markdown(all_blocks)


def query_database(db_key, filter_obj=None, sorts=None, limit=None):
    """Query a Notion database via data_sources.query().

    Returns a list of pages or an error string.
    """
    db_conf = DATABASES.get(db_key)
    if not db_conf:
        return f"Unknown database '{db_key}'. Available: {', '.join(DATABASES.keys())}"

    kwargs = {"data_source_id": db_conf["ds_id"]}
    if filter_obj:
        kwargs["filter"] = filter_obj
    if sorts:
        kwargs["sorts"] = sorts
    if limit:
        kwargs["page_size"] = min(limit, 100)

    try:
        response = _notion().data_sources.query(**kwargs)
        return response.get("results", [])
    except Exception as e:
        logger.error("Error querying %s: %s", db_key, e)
        return f"Error querying {db_key}: {e}"


def get_data_source_info(db_key):
    """Retrieve data source metadata (title, properties) for a database."""
    db_conf = DATABASES.get(db_key)
    if not db_conf:
        return None
    try:
        return _notion().data_sources.retrieve(data_source_id=db_conf["ds_id"])
    except Exception as e:
        logger.error("Error retrieving data source for %s: %s", db_key, e)
        return None


# ---------------------------------------------------------------------------
# The tool registry
#
# One decorator, two facades. `anthropic_tools()` builds the tool specs for a
# direct messages.create() call; mcp/server.py hands the same functions to
# FastMCP. Both take the description from the docstring and the schema from
# the signature, so a tool cannot describe itself differently depending on
# which way it is reached.
# ---------------------------------------------------------------------------
TOOLS = {}

_JSON_TYPES = {str: "string", int: "integer", bool: "boolean"}


def tool(fn):
    """Register a function as one of CycleBot's tools.

    The schema is built here rather than lazily so that a tool missing a type
    hint or a docstring fails at import, where the mistake is, instead of
    halfway through someone's conversation.
    """
    if not inspect.getdoc(fn):
        raise TypeError(
            f"Tool {fn.__name__} needs a docstring — it is what tells the "
            "model when to use the tool."
        )
    _input_schema(fn)
    TOOLS[fn.__name__] = fn
    return fn


def _input_schema(fn):
    """A JSON schema for fn's parameters, from its annotations."""
    properties, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        if param.annotation not in _JSON_TYPES:
            raise TypeError(
                f"Tool {fn.__name__} parameter '{name}' needs one of "
                f"{', '.join(t.__name__ for t in _JSON_TYPES)} as its type "
                f"hint, not {param.annotation!r}."
            )
        properties[name] = {"type": _JSON_TYPES[param.annotation]}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def describe(fn) -> str:
    """What the model is told about a tool.

    inspect.getdoc rather than fn.__doc__ so the docstring arrives dedented
    and stripped. Both facades go through here, so an MCP client and a direct
    call get the same text rather than the same text differently indented.
    """
    return inspect.getdoc(fn)


def anthropic_tools():
    """The tool specs for a messages.create() call."""
    return [
        {
            "name": name,
            "description": describe(fn),
            "input_schema": _input_schema(fn),
        }
        for name, fn in TOOLS.items()
    ]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def search_all(query: str) -> str:
    """Search across all Lambeth Cyclists Notion content.

    Use this for broad queries when you don't know which database to look in,
    or when the user asks a general question.

    Examples of when to use this tool:
    - "anything about bike lanes on Brixton Road"
    - "what do we know about John Smith"
    - "cycle parking"
    """
    try:
        response = _notion().search(query=query, page_size=10)
        results = response.get("results", [])
    except Exception as e:
        return f"Search error: {e}"

    if not results:
        return (
            f"No results found for '{query}'. Try different keywords, "
            "or use a specific tool like list_meetings() or get_ward_data()."
        )

    parts = [f"## Search results for '{query}'\n"]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def list_meetings(limit: int = 10) -> str:
    """List recent Lambeth Cyclists meetings.

    Returns meetings sorted by date (most recent first). Each result includes
    the meeting title, date, type, and other metadata.

    Use get_meeting_agenda() to get the full content of a specific meeting.

    Examples:
    - list_meetings() — 10 most recent meetings
    - list_meetings(limit=3) — just the latest 3

    Meeting types: regular_committee, special, planning, emergency
    """
    results = query_database(
        "meetings",
        sorts=[{"property": "Meeting Date", "direction": "descending"}],
        limit=limit,
    )
    if isinstance(results, str):
        return results
    if not results:
        return "No meetings found."

    parts = [f"## Meetings (showing {len(results)})\n"]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_meeting_agenda(date: str = "", title_search: str = "") -> str:
    """Get the full agenda or minutes for a specific meeting.

    Looks up a meeting by date or title keyword, then returns its properties
    AND full page content (agenda items, minutes, notes, etc.).

    Args:
        date: Date string like "2026-03-05" or partial like "2026-03".
              Matches against the "Meeting Date" property.
        title_search: Keyword(s) to match in the meeting title, e.g. "AGM".

    Examples:
    - get_meeting_agenda(date="2026-03-05")
    - get_meeting_agenda(title_search="AGM")
    - get_meeting_agenda(date="2026-02") — any meeting in Feb 2026
    """
    # If exact date given, try server-side filter first
    filter_obj = None
    if date and len(date) == 10:  # YYYY-MM-DD
        filter_obj = {
            "property": "Meeting Date",
            "date": {"equals": date},
        }

    results = query_database(
        "meetings",
        filter_obj=filter_obj,
        sorts=[{"property": "Meeting Date", "direction": "descending"}],
        limit=20,
    )
    if isinstance(results, str):
        return results
    if not results and filter_obj:
        # Exact date didn't match — fall back to fetching all and filtering
        results = query_database(
            "meetings",
            sorts=[{"property": "Meeting Date", "direction": "descending"}],
            limit=20,
        )
        if isinstance(results, str):
            return results

    if not results:
        return "No meetings found. Try list_meetings() to see what's available."

    # Client-side filter by partial date (e.g. "2026-02")
    if date and len(date) < 10:
        date_matched = []
        for page in results:
            meeting_date = page.get("properties", {}).get("Meeting Date", {})
            if meeting_date.get("type") == "date" and meeting_date.get("date"):
                if meeting_date["date"].get("start", "").startswith(date):
                    date_matched.append(page)
        if date_matched:
            results = date_matched

    # Filter by title keyword
    if title_search:
        title_matched = [
            p for p in results
            if title_search.lower() in get_page_title(p).lower()
        ]
        if title_matched:
            results = title_matched

    if not results:
        return (
            f"No meetings matched date='{date}' title='{title_search}'. "
            "Try list_meetings() to see available meetings."
        )

    # Return the best match with full page content
    page = results[0]
    parts = [format_properties(page), "\n---\n"]

    content = get_page_content(page["id"])
    parts.append(content if content else "*(No page content found)*")

    if len(results) > 1:
        parts.append(
            f"\n---\n*{len(results) - 1} other meeting(s) also matched. "
            "Showing the most recent.*"
        )
    return "\n".join(parts)


@tool
def get_action_items(status: str = "all", assignee: str = "") -> str:
    """Get action items from the Items database.

    The Items database contains emails, consultations, and action items
    received by Lambeth Cyclists.

    Args:
        status: Filter by status — "all" for everything, or one of:
                "new", "reviewed", "response_drafted", "submitted",
                "monitoring", "closed"
        assignee: Filter by person name (case-insensitive partial match).

    Examples:
    - get_action_items() — everything
    - get_action_items(status="new") — new/unprocessed items
    - get_action_items(status="monitoring") — items being monitored
    """
    filter_obj = None
    if status and status.lower() != "all":
        filter_obj = {
            "property": "Status",
            "select": {"equals": status},
        }

    results = query_database(
        "items",
        filter_obj=filter_obj,
        sorts=[{"property": "Date Received", "direction": "descending"}],
    )
    if isinstance(results, str):
        return results

    # Client-side filter for assignee
    if assignee and results:
        filtered = [
            p for p in results
            if assignee.lower() in format_properties(p).lower()
        ]
        if not filtered:
            return f"No items found for '{assignee}'."
        results = filtered

    if not results:
        msg = "No items found"
        if status and status.lower() != "all":
            msg += f" with status '{status}'"
        return msg + "."

    parts = [f"## Items ({len(results)} found)\n"]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_ward_data(ward_name: str = "") -> str:
    """Get ward-level data from the Wards database.

    Returns ward information including election analysis for the May 2026
    Lambeth council elections. Data includes competitiveness, 2022 margin,
    priority level, cycling issues, and engagement status.

    Args:
        ward_name: Optional ward name (case-insensitive partial match).
                   Leave empty to get all wards.

    Competitiveness values: Safe Labour, Labour-Green, Labour-LD, Three-way
    Priority values: High, Medium, Low
    Status values: Research, Outreach, Engaged, Committed, No response

    Examples:
    - get_ward_data() — all wards
    - get_ward_data("Brixton") — wards matching "Brixton"
    - get_ward_data("Herne Hill") — Herne Hill ward
    """
    results = query_database("wards")
    if isinstance(results, str):
        return results
    if not results:
        return "No ward data found."

    if ward_name:
        filtered = [
            p for p in results
            if ward_name.lower() in get_page_title(p).lower()
        ]
        if not filtered:
            all_names = [get_page_title(p) for p in results]
            return (
                f"No ward matching '{ward_name}'. "
                f"Available wards: {', '.join(sorted(all_names))}"
            )
        results = filtered

    parts = [
        f"## Ward Data ({len(results)} ward{'s' if len(results) != 1 else ''})\n"
    ]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_councillor_data(
    ward_name: str = "",
    councillor_name: str = "",
    party: str = "",
) -> str:
    """Get councillor and candidate information.

    The Councillors & Candidates database tracks current councillors and
    declared/potential candidates for the May 2026 Lambeth elections,
    including their party, ward, position on cycling, and engagement level.

    Args:
        ward_name: Filter by ward (case-insensitive partial match).
        councillor_name: Filter by name (case-insensitive partial match).
        party: Filter by party — "Labour", "Green", "Liberal Democrat",
               or "Conservative".

    Status values: Current Councillor, Declared Candidate, Potential Candidate,
                   2026 Candidate, Departed
    Engagement values: Not contacted, Contacted, Meeting scheduled, Supportive,
                       Committed, Opposed

    Examples:
    - get_councillor_data() — all councillors and candidates
    - get_councillor_data(party="Green")
    - get_councillor_data(councillor_name="Smith")
    - get_councillor_data(ward_name="Brixton")
    """
    filter_obj = None
    if party:
        filter_obj = {
            "property": "Party",
            "select": {"equals": party},
        }

    results = query_database("councillors", filter_obj=filter_obj)
    if isinstance(results, str):
        return results
    if not results:
        return "No councillor data found."

    if councillor_name:
        results = [
            p for p in results
            if councillor_name.lower() in get_page_title(p).lower()
        ]
    if ward_name:
        results = [
            p for p in results
            if ward_name.lower() in format_properties(p).lower()
        ]

    if not results:
        return "No councillors found matching those criteria."

    parts = [f"## Councillors & Candidates ({len(results)} found)\n"]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_battleground_wards() -> str:
    """Get wards that are competitive for the May 2026 Lambeth elections.

    Returns wards where the Competitiveness is NOT "Safe Labour" — i.e.,
    wards classified as Labour-Green, Labour-LD, or Three-way marginals.
    Also includes any wards with Priority set to "High".
    """
    results = query_database("wards")
    if isinstance(results, str):
        return results
    if not results:
        return "No ward data found."

    battleground = []
    for page in results:
        props = page.get("properties", {})

        # Check Competitiveness
        comp = props.get("Competitiveness", {})
        if comp.get("type") == "select" and comp.get("select"):
            comp_val = comp["select"]["name"]
            if comp_val != "Safe Labour":
                battleground.append(page)
                continue

        # Check Priority
        priority = props.get("Priority", {})
        if priority.get("type") == "select" and priority.get("select"):
            if priority["select"]["name"] == "High":
                battleground.append(page)
                continue

    if not battleground:
        return (
            "No battleground wards found. All wards may be classified as "
            "Safe Labour, or competitiveness data hasn't been entered yet. "
            "Use get_ward_data() to see all ward data."
        )

    parts = [f"## Battleground Wards ({len(battleground)} found)\n"]
    for page in battleground:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_projects(status: str = "all") -> str:
    """Get projects from the Projects database.

    Lambeth Cyclists' campaigns and projects, including infrastructure
    campaigns, partnerships, research, and ongoing monitoring.

    Args:
        status: "all" for everything, or one of:
                "planning", "active", "paused", "completed", "archived"

    Project types: infrastructure_campaign, campaigning, research,
                   partnership, ongoing_monitoring, membership

    Examples:
    - get_projects() — all projects
    - get_projects("active") — only active projects
    - get_projects("planning") — projects in planning phase
    """
    filter_obj = None
    if status and status.lower() != "all":
        filter_obj = {
            "property": "Status",
            "select": {"equals": status},
        }

    results = query_database(
        "projects",
        filter_obj=filter_obj,
        sorts=[{"property": "Start Date", "direction": "descending"}],
    )
    if isinstance(results, str):
        return results
    if not results:
        msg = "No projects found"
        if status and status.lower() != "all":
            msg += f" with status '{status}'"
        return msg + "."

    parts = [f"## Projects ({len(results)} found)\n"]
    for page in results:
        parts.append(format_properties(page))
        parts.append("")
    return "\n".join(parts)


@tool
def get_page_detail(page_id: str) -> str:
    """Get the full content of any Notion page by its ID.

    Use this to drill into a specific page when other tools return summaries
    and you need the full content (meeting minutes, detailed ward notes, etc.).

    The page ID is included in results from other tools (listed as 'Page ID').

    Args:
        page_id: The Notion page ID string.
    """
    try:
        page = _notion().pages.retrieve(page_id=page_id)
    except Exception as e:
        return f"Error retrieving page: {e}"

    parts = [format_properties(page), "\n---\n"]
    content = get_page_content(page_id)
    parts.append(content if content else "*(No page content)*")
    return "\n".join(parts)


@tool
def list_databases() -> str:
    """List all available Notion databases and their property schemas.

    Use this to discover what data is available, what each database is called,
    and what property names/types it has. Helpful for understanding the data
    model or debugging when queries don't return expected results.
    """
    parts = ["## Available Databases\n"]

    for key, db_conf in DATABASES.items():
        ds_info = get_data_source_info(key)
        if ds_info:
            title = rich_text_to_str(ds_info.get("title", []))
            parts.append(f"### {title or db_conf['label']}")
            parts.append(f"- **Key**: `{key}`")

            props = ds_info.get("properties", {})
            if props:
                parts.append(f"- **Properties** ({len(props)}):")
                for prop_name, prop_info in sorted(props.items()):
                    ptype = prop_info["type"]
                    extra = ""
                    if ptype == "select":
                        opts = [
                            o["name"]
                            for o in prop_info.get("select", {}).get(
                                "options", []
                            )
                        ]
                        if opts:
                            extra = f" — options: {', '.join(opts)}"
                    parts.append(f"  - {prop_name} (`{ptype}`){extra}")
        else:
            parts.append(f"### {db_conf['label']}")
            parts.append(f"- **Key**: `{key}`")
            parts.append("- *(Could not retrieve database info)*")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------
SYSTEM = (
    "You are CycleBot, the assistant for Lambeth Cyclists — the Lambeth branch "
    "of the London Cycling Campaign, a friendly volunteer-run cycling advocacy "
    "group in South London. "
    "Use the Notion tools to look things up before answering — never guess or "
    "make up data. You can summarise anything in the databases (all filed "
    "emails and items, meetings, projects, ward and councillor research), "
    "including things that weren't picked for the newsletter. "
    "Keep answers concise and practical; the people asking are busy volunteers. "
    "Be studiously apolitical: report on council and TfL plans factually. "
    "You have read-only access — for edits, point people at Notion or the "
    "newsletter builder. If you can't find something, say so honestly."
)


def run_tool(name: str, arguments: dict) -> str:
    """Run one tool by name. Never raises — the model sees the error instead."""
    fn = TOOLS.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. Available: {', '.join(TOOLS)}"
    try:
        return fn(**arguments)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return f"Error running {name}: {e}"


# The two services read their key through pydantic settings, which accept
# either name. This is the one reader that does not go through them, and it
# used to index os.environ directly — so a deployment set up from the docs,
# which said CLAUDE_API_KEY, ran a working processor and a working portal
# with a chat page that died on a bare KeyError.
_KEY_NAMES = ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")


@lru_cache
def _anthropic() -> anthropic.Anthropic:
    for name in _KEY_NAMES:
        key = os.environ.get(name)
        if key:
            return anthropic.Anthropic(api_key=key)
    raise RuntimeError(
        "CycleBot needs an Anthropic key: set " + " or ".join(_KEY_NAMES) + "."
    )


def answer(
    messages: list[dict],
    *,
    surface: str = "",
    client: anthropic.Anthropic | None = None,
    max_turns: int = 8,
) -> str:
    """One CycleBot turn. `messages` is the full [{role, content}] history.

    `surface` is appended to the system prompt to say where the conversation is
    happening — the members' portal, a WhatsApp group, whatever comes next.
    Everything that should be the same everywhere lives in SYSTEM; only the
    genuine differences go here. Note that surfaces differ in who can read
    them: the portal is behind a login, so anything more public wants a
    narrower view of the databases than "all of it".

    The tools run in this process, so the loop is ours: keep going while the
    model asks for tools, and stop at max_turns so a confused model cannot
    bill indefinitely. (There is no pause_turn to handle here — that belongs
    to server-side tools like web_search, not local ones.)
    """
    api = client or _anthropic()
    system = f"{SYSTEM} {surface}".strip()
    convo = list(messages)
    response = None

    for _ in range(max_turns):
        response = api.with_options(timeout=120.0).messages.create(
            model=MODEL,
            max_tokens=4096,
            output_config={"effort": "medium"},
            system=system,
            tools=anthropic_tools(),
            messages=convo,
        )
        if response.stop_reason != "tool_use":
            return response_text_of(response)

        convo.append({"role": "assistant", "content": response.content})
        convo.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run_tool(block.name, block.input),
                }
                for block in response.content
                if block.type == "tool_use"
            ],
        })

    logger.warning("CycleBot hit max_turns=%d without finishing", max_turns)
    return response_text_of(response) or (
        "Sorry — I couldn't finish looking that up. Try asking more narrowly."
    )
