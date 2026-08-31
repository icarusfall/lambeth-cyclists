"""On-demand AI actions (no daemons — every call here is a button press in the UI).

Model: claude-sonnet-5 with adaptive thinking (the default). Effort is kept at
low/medium to hold costs to pennies per newsletter.
"""

import logging
from datetime import date
from typing import Literal
from functools import lru_cache

import anthropic
from pydantic import BaseModel, Field

from app.config import get_settings
from app.notion import client as notion_client
from core import cyclebot
from core.claude import MODEL, parse_resuming

logger = logging.getLogger(__name__)



class Story(BaseModel):
    headline: str
    summary: str = Field(description="2-3 friendly sentences for a community newsletter")
    source: str = Field(description="Where this came from, e.g. 'Notion: <item title>' or a news site name")
    url: str | None = Field(default=None, description="Link for readers, if available")


class StoryList(BaseModel):
    stories: list[Story]


@lru_cache
def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def _parse_resuming(**kwargs):
    """messages.parse(), resumed across pause_turn. See core.claude."""
    return parse_resuming(client(), **kwargs)


VOICE = (
    "Lambeth Cyclists is the Lambeth branch of the London Cycling Campaign, a "
    "friendly volunteer-run advocacy group in South London. The newsletter voice is "
    "warm, brief and practical — community noticeboard, not press release. "
    "Studiously apolitical: report on council/TfL plans factually."
)


def suggest_stories(
    items_md: str, projects_md: str, existing_headlines: list[str] | None = None
) -> list[Story]:
    """Turn recent Notion items + active projects into candidate newsletter stories."""
    already = ""
    if existing_headlines:
        already = (
            "\n\nWe already have story cards on these — skip anything that covers "
            "the same ground:\n"
            + "\n".join(f"- {h}" for h in existing_headlines)
        )
    response = _parse_resuming(
        model=MODEL,
        max_tokens=4096,
        output_config={"effort": "low"},
        system=VOICE,
        messages=[
            {
                "role": "user",
                "content": (
                    "Below are recent items (mostly filed emails about consultations, "
                    "traffic orders and infrastructure) and active projects from our "
                    "Notion databases.\n\n"
                    f"## Recent items\n{items_md}\n\n## Active projects\n{projects_md}\n\n"
                    "Pick the 4-8 things a Lambeth cyclist would actually want to read "
                    "about this month and write each up as a newsletter story. Skip "
                    "admin noise, duplicates, and anything with no reader interest. "
                    "Mention consultation deadlines where they exist — encouraging "
                    "members to respond to consultations is a core purpose."
                    f"{already}"
                ),
            }
        ],
        output_format=StoryList,
    )
    return response.parsed_output.stories


def news_scan(existing_headlines: list[str]) -> list[Story]:
    """Web-search for recent Lambeth cycling news not already covered by our items."""
    already = "\n".join(f"- {h}" for h in existing_headlines) or "(none)"
    response = _parse_resuming(
        model=MODEL,
        max_tokens=8000,
        output_config={"effort": "medium"},
        system=VOICE,
        tools=[
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 6,
                "user_location": {
                    "type": "approximate",
                    "city": "London",
                    "region": "England",
                    "country": "GB",
                    "timezone": "Europe/London",
                },
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}. Search for news from the "
                    "last ~6 weeks relevant to cycling in the London Borough of "
                    "Lambeth: infrastructure changes, road schemes, consultations, "
                    "events, incidents with policy relevance. Good sources include "
                    "Brixton Buzz, Lambeth Council news, London Cycling Campaign, "
                    "853, Southwark News, local press.\n\n"
                    "We already have stories on these, so skip anything covered:\n"
                    f"{already}\n\n"
                    "Return up to 5 genuinely new stories with the source URL. If "
                    "nothing new turns up, return an empty list — do not pad."
                ),
            }
        ],
        output_format=StoryList,
    )
    return response.parsed_output.stories


# What is different about this surface. Everything CycleBot always does — who
# it is, look things up before answering, read-only, say so when it can't find
# something — lives in core.cyclebot.SYSTEM, so the portal and any later
# surface behave the same without being kept in step by hand.
CHAT_SURFACE = (
    "You are talking to a committee member inside the members' portal. The "
    "portal is behind a login, so you can discuss anything in the databases "
    "freely."
)


def chat_reply(messages: list[dict]) -> str:
    """One portal-chat turn. `messages` is the full [{role, content}] history.

    The tools run in this process — see core.cyclebot. This used to go out
    through the Anthropic MCP connector to the CycleBot server on Railway,
    which meant Anthropic's servers called our tools over the public internet;
    that is why the MCP server needed a bearer key. Same tools, no round trip.
    """
    cyclebot.use_notion_client(notion_client())
    return cyclebot.answer(messages, surface=CHAT_SURFACE, client=client())


def draft_newsletter(
    stories_md: str, meetings_md: str, month_label: str
) -> str:
    """Draft the full newsletter in markdown from the selected stories + meetings."""
    response = client().messages.create(
        model=MODEL,
        max_tokens=4096,
        output_config={"effort": "medium"},
        system=VOICE,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Draft our {month_label} newsletter in markdown.\n\n"
                    f"## Selected stories (use all of these, edited text is final-ish)\n"
                    f"{stories_md}\n\n"
                    f"## Upcoming meetings (always include a 'Get involved' section "
                    f"with these)\n{meetings_md}\n\n"
                    "Structure: a one-paragraph friendly intro, the stories with "
                    "short ## headings, then 'Get involved' with meeting details and "
                    "a line inviting people to reply if they'd like to help out. "
                    "Keep the whole thing readable in under 3 minutes on a phone. "
                    "Include story links where given. Do not invent facts beyond "
                    "what's provided. Return ONLY the newsletter markdown — no "
                    "preamble or commentary."
                ),
            }
        ],
    )
    return next(b.text for b in response.content if b.type == "text").strip()


# ---------------------------------------------------------------------------
# Adding something by hand
# ---------------------------------------------------------------------------
# Not everything arrives by email. Someone mentions a scheme in a meeting or
# on WhatsApp, and we want it on the list without anyone opening Notion.
# The member pastes links; Claude reads them and proposes the fields.

PROJECT_TYPES = ("traffic_order", "consultation", "infrastructure_project", "event", "other")
ACTIONS = ("response_needed", "information_only", "monitoring", "urgent_action")
PRIORITIES = ("critical", "high", "medium", "low")


class ItemSuggestion(BaseModel):
    title: str = Field(description="Short, specific, how a committee member would refer to it")
    summary: str = Field(description="2-3 sentences: what it is and why it matters for cycling in Lambeth")
    project_type: Literal[PROJECT_TYPES]
    action_required: Literal[ACTIONS] = Field(
        description="response_needed only if there is a consultation we can actually respond to; "
        "monitoring if it is a scheme to keep an eye on; information_only if purely for the record"
    )
    priority: Literal[PRIORITIES]
    tags: list[str] = Field(description="Reuse the existing tag vocabulary given below wherever one fits")
    locations: list[str] = Field(
        description="The specific streets, junctions or areas involved. Always "
        "name the actual street, even if it is not already in the list below"
    )
    key_points: str = Field(description="Markdown bullet list, one '- ' per line, of the things worth knowing")
    why_we_care: str = Field(description="One or two sentences on what Lambeth Cyclists should watch for")
    deadline: str | None = Field(default=None, description="ISO date (YYYY-MM-DD) of any consultation deadline, else null")
    main_link: str | None = Field(default=None, description="The most useful of the supplied links for a reader")
    unreachable: list[str] = Field(default_factory=list, description="Any supplied links you could not read")


def suggest_item_fields(
    links: list[str],
    note: str,
    tag_vocabulary: list[str],
    location_vocabulary: list[str],
) -> ItemSuggestion:
    """Read the supplied links and propose Notion field values for a new item.

    web_fetch only retrieves URLs already present in the conversation, so the
    pasted links are the whole of its reach — it cannot wander.
    """
    listed = "\n".join(f"- {u}" for u in links) or "(none supplied)"
    response = _parse_resuming(
        model=MODEL,
        max_tokens=8000,
        output_config={"effort": "medium"},
        system=VOICE,
        tools=[
            {
                "type": "web_fetch_20260209",
                "name": "web_fetch",
                "max_uses": 8,
                "max_content_tokens": 30000,
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}.\n\n"
                    "A committee member is adding something to our tracker by hand — it "
                    "did not arrive by email. Read the links below and propose the field "
                    "values for the new entry.\n\n"
                    f"## Links\n{listed}\n\n"
                    f"## What they told us\n{note or '(nothing beyond the links)'}\n\n"
                    f"## Existing tags — reuse these rather than inventing new ones unless nothing fits\n"
                    f"{', '.join(tag_vocabulary)}\n\n"
                    f"## Location names already in use - match these spellings where they "
                    f"apply, but add the specific street or junction if it is not listed\n"
                    f"{', '.join(location_vocabulary[:150])}\n\n"
                    "Fetch each link before judging it. If a link cannot be read, list it "
                    "in `unreachable` and work from the others — do not guess at its "
                    "contents. Base every field on what the pages actually say plus what "
                    "the member told you; if something is genuinely unclear, keep the "
                    "summary cautious rather than inventing detail. Set action_required "
                    "to response_needed only where there is a live consultation we could "
                    "actually reply to."
                ),
            }
        ],
        output_format=ItemSuggestion,
    )
    suggestion = response.parsed_output

    # A paused or otherwise unfinished turn can still satisfy the schema, with
    # stub text in the free-form fields. That is worse than an error, because
    # it looks like an answer and would be written to Notion as one.
    stubs = {"placeholder", "todo", "n/a", "none", "unknown", "tbc", ""}
    if suggestion.title.strip().lower() in stubs or suggestion.summary.strip().lower() in stubs:
        raise RuntimeError(
            "The model did not finish reading those pages (it returned stub text). "
            "Try again, or add a line of your own about what this is."
        )

    # You cannot respond to a consultation that has closed. The model reads the
    # deadline correctly and still calls it response_needed — telling it not to
    # in the prompt is less reliable than checking the date it just gave us.
    if suggestion.deadline and suggestion.action_required in ("response_needed", "urgent_action"):
        try:
            if date.fromisoformat(suggestion.deadline) < date.today():
                suggestion.action_required = "monitoring"
        except ValueError:
            pass  # unparseable date: leave the model's judgement alone

    return suggestion


# ---------------------------------------------------------------------------
# Triage: turning a pile of filed items into projects
# ---------------------------------------------------------------------------
# Items are leads. Projects are the work. Nothing currently carries a lead
# across that gap, which is why 49 items sat at status "new" for months.
#
# Deliberately one call over the whole backlog rather than one per item: the
# useful judgement is that five separate emails are the same scheme, and a
# per-item pass cannot see that.

PROJECT_KINDS = (
    "infrastructure_campaign", "campaigning", "research",
    "partnership", "ongoing_monitoring", "membership",
)
SCOPES = ("single_street", "neighbourhood", "borough_wide", "cross_borough")
PROJECT_PRIORITIES = ("strategic", "high", "medium", "low")


class ProjectProposal(BaseModel):
    title: str = Field(description="What the committee would call this, e.g. 'Acre Lane bus priority'")
    description: str = Field(description="3-4 sentences: what it is, where it stands, why we are tracking it")
    project_type: Literal[PROJECT_KINDS]
    geographic_scope: Literal[SCOPES]
    priority: Literal[PROJECT_PRIORITIES]
    primary_locations: list[str]
    next_action: str = Field(description="The single most useful next thing a volunteer could do")
    item_numbers: list[int] = Field(description="Numbers of the listed items that belong to this project")
    matches_existing: str | None = Field(
        default=None,
        description="Exact title of an existing project if these items belong to it, else null",
    )


class TriageResult(BaseModel):
    proposals: list[ProjectProposal]
    not_relevant: list[int] = Field(
        description="Item numbers that are genuinely just for the record and need no project"
    )
    reasoning: str = Field(description="Two or three sentences on how you grouped things")


def propose_projects(items: list[dict], projects: list[dict]) -> TriageResult:
    """Group filed items into projects worth tracking.

    `projects` comes from notion.projects_for_matching(): title, description,
    type and whether it is a standing sweep. Descriptions matter — a sweep
    like "Controlled Parking Zones" only works if the model can read that it
    exists to absorb every CPZ notice. Returns proposals for a human to
    accept or reject; nothing is written here.
    """
    listing = []
    for it in items:
        listing.append(
            f"[{it['number']}] {it['title']}\n"
            f"     type: {it.get('project_type') or '?'} | "
            f"received: {it.get('received') or '?'} | "
            f"locations: {', '.join(it.get('locations') or []) or '-'}\n"
            f"     {(it.get('summary') or '(no summary)')[:400]}"
        )

    standing, normal = [], []
    for pr in projects:
        line = f"- {pr['title']}"
        if pr.get("description"):
            line += f"\n    {pr['description'][:300]}"
        (standing if pr.get("standing") else normal).append(line)

    existing_block = ""
    if standing:
        existing_block += (
            "### Standing projects\n"
            "These exist precisely to absorb recurring routine items. If an item "
            "touches one of these subjects at all, sweep it in here — it does not "
            "get a project of its own.\n" + "\n".join(standing) + "\n\n"
        )
    existing_block += "### Other current projects\n" + ("\n".join(normal) or "(none yet)")

    response = _parse_resuming(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        timeout=600.0,
        system=VOICE,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}.\n\n"
                    "Below are items filed from our inbox — consultations, traffic orders, "
                    "infrastructure notices and general correspondence. Sort them.\n\n"
                    f"## Projects we already track\n{existing_block}\n\n"
                    f"## Filed items\n\n" + "\n\n".join(listing) + "\n\n"
                    "### How to decide\n"
                    "Work down this list and stop at the first that fits.\n\n"
                    "1. Does it belong to a project we already have? Set matches_existing "
                    "to that project's exact title. This is by far the most common right "
                    "answer, and it is your default.\n"
                    "2. Does it need no follow-up at all? Put it in not_relevant: one-off "
                    "notices, events that have passed, routine correspondence.\n"
                    "3. Only then, does it deserve a new project? A new project has to "
                    "clear a high bar — a scheme with a life across several consultations, "
                    "a corridor we will keep returning to, or a campaign we would actually "
                    "run. Several items about the same road or scheme make one project, "
                    "not several.\n\n"
                    "Never create a project that overlaps one listed above; extend that one "
                    "instead. Do not create a project for a single routine notice. A borough "
                    "the size of Lambeth generates these constantly, and a project per notice "
                    "produces a list nobody reads — err towards fewer, larger, longer-lived "
                    "projects.\n\n"
                    "If several items would each be too slight on their own but share a "
                    "theme that will clearly keep recurring, say so in reasoning: we may "
                    "want a new standing project for it."
                ),
            }
        ],
        output_format=TriageResult,
    )
    return response.parsed_output


# ---------------------------------------------------------------------------
# One item that looks like the start of something
# ---------------------------------------------------------------------------
# The counterpart to propose_projects, for the moment you are looking at a
# single item and can already tell it will run and run. propose_projects reads
# the whole backlog to spot that five emails are one scheme; this reads one
# item and asks the narrower question — does this belong somewhere we already
# track, and if not, what would the project be called?
#
# It still gets the existing projects, because "start a project for this" is
# most often answered by "we already have one".


class ItemProjectProposal(BaseModel):
    matches_existing: str | None = Field(
        default=None,
        description=(
            "Exact title of an existing project this item belongs to, or null if "
            "it genuinely needs one of its own"
        ),
    )
    reasoning: str = Field(
        description="One sentence: why this belongs where you have put it"
    )
    title: str = Field(description="What the committee would call this, e.g. 'A23 Streatham corridor'")
    description: str = Field(
        description="3-4 sentences: what it is, where it stands, why we are tracking it"
    )
    project_type: Literal[PROJECT_KINDS]
    geographic_scope: Literal[SCOPES]
    priority: Literal[PROJECT_PRIORITIES]
    primary_locations: list[str]
    next_action: str = Field(description="The single most useful next thing a volunteer could do")


def suggest_project_for_item(item: dict, projects: list[dict]) -> ItemProjectProposal:
    """Draft the project this one item would start, or name the one it joins.

    `item` is a notion.item_detail() record. Always returns a full draft even
    when it also names an existing match, so the person can disagree and start
    the new one anyway without a second round trip.
    """
    existing = []
    for pr in projects:
        line = f"- {pr['title']}"
        if pr.get("standing"):
            line += "  [standing — exists to absorb every item on its subject]"
        if pr.get("description"):
            line += f"\n    {pr['description'][:300]}"
        existing.append(line)

    facts = "\n".join(
        f"{label}: {value}"
        for label, value in (
            ("Title", item.get("title")),
            ("Type", item.get("project_type")),
            ("Locations", ", ".join(item.get("locations") or []) or "-"),
            ("Tags", ", ".join(item.get("tags") or []) or "-"),
            ("Arrived", item.get("received")),
            ("Deadline", item.get("deadline")),
        )
        if value
    )

    response = _parse_resuming(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "medium"},
        timeout=180.0,
        system=VOICE,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Today is {date.today().isoformat()}.\n\n"
                    "Somebody is looking at one filed item and wants to start tracking "
                    "the thing behind it as a project.\n\n"
                    f"## The item\n{facts}\n\n"
                    f"Summary: {(item.get('summary') or '(none)')[:1200]}\n\n"
                    f"Key points: {(item.get('key_points') or '(none)')[:1200]}\n\n"
                    f"## Projects we already track\n" + ("\n".join(existing) or "(none yet)") + "\n\n"
                    "### What to do\n"
                    "First, check whether it belongs to a project above. If it does, set "
                    "matches_existing to that exact title. A standing project is a strong "
                    "match for anything on its subject — that is what it is for.\n\n"
                    "Either way, also draft the project this item would start on its own, "
                    "so the person can overrule you. Name it after the scheme or corridor "
                    "rather than after this one item: a project outlives the email that "
                    "prompted it, and more post about the same scheme should sit under it "
                    "comfortably. Prefer a name a committee member would recognise in a "
                    "year's time.\n\n"
                    "If the item is a notice about something the council will keep "
                    "returning to, that is a project worth having. If it is a one-off with "
                    "no future, say so in reasoning — but still give your best draft."
                ),
            }
        ],
        output_format=ItemProjectProposal,
    )
    return response.parsed_output
