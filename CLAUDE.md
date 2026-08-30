# Lambeth Cyclists — Project Management System

> Last reviewed: **30 August 2026**. Earlier revisions of this file described a
> single email-processing app; the system is now three deployed services across
> three repos. Items marked **[UNCONFIRMED]** need Charlie to verify — do not
> treat them as fact.

## The Problem

Lambeth Cyclists is a real-world cycling advocacy group in South London, part of
the London Cycling Campaign (LCC) charity. It runs on skeleton staff and needs
tooling so that responding to consultations, traffic orders and infrastructure
projects doesn't depend on one person's inbox.

**Goal:** reduce the administrative load on the chair so more time goes to
advocacy, and so new volunteers can be onboarded without inheriting a decade of
undocumented context.

---

## The three repos

| Repo | What it is | Runs on | Interaction model |
|---|---|---|---|
| `lambeth-cyclists-claude` | Email processor. Watches Gmail, extracts structured data with Claude, files it into Notion, generates meeting agendas, sends reminders. | Railway (worker) | Autonomous daemon, 24/7 |
| `lambeth-cyclists-mcp` | "CycleBot" MCP server. Read-only Notion tools exposed over MCP. | Railway (web) | Called by the portal's chat, and by Claude clients |
| `lambeth-cyclists-portal` | Members' portal at **members.lambethcyclists.com**. Dashboard, newsletter builder, archive, chat. | Railway (web) | On-demand only — every AI call is a button press |

They share one Notion workspace. Nothing else is shared: no common library, no
common config format. Keeping conventions aligned by hand is a known cost.

### Data flow

```
Gmail ──► email processor ──► Notion ◄── portal (read/write)
                                 ▲
                                 └── MCP server (read-only) ◄── portal chat
```

---

## Models and AI conventions

**All three repos use `claude-sonnet-5`.** Chosen over Opus to keep running
costs at charity scale; extraction quality has been sufficient.

Conventions that apply everywhere — these are not stylistic, they are
correctness requirements on current models:

- **No sampling parameters.** `temperature` / `top_p` / `top_k` are removed from
  the Anthropic SDK 1.x call signatures and rejected by Sonnet 5. Control
  response depth with `output_config={"effort": ...}` instead (`low` for
  deterministic structured extraction, `medium` where some judgement helps).
- **Never index into `response.content[0]`.** Adaptive thinking is on by
  default, so the first block is a thinking block. Select text blocks by type:
  - processor: `response_text_of(message)` in `services/claude_service.py`
  - portal: `next(b.text for b in response.content if b.type == "text")`
- **Structured output** in the portal uses `messages.parse(output_format=Model)`
  with a Pydantic model. The processor still hand-parses JSON from a text
  response (`_parse_json_response`) — a candidate for the same treatment.

---

## Repo notes

### `lambeth-cyclists-claude` (email processor)

Two async loops in `main.py`: email polling (every 300s) and meeting checks
(every 3600s). Pipeline: Gmail → attachments (PDF/Word/Excel/images) → Claude
analysis (text + vision) → geocoding → Drive upload → Notion item, with
duplicate detection and relationship detection against existing items/projects.

- `agenda/` — meeting detection, agenda generation, reminder emails
- `processors/` — email pipeline and attachment extraction
- `services/` — one module per external API
- `scripts/` — live-API helper checks and OAuth setup (see `scripts/README.md`)
- `tests/` — unit tests, all mocked. `pytest.ini` scopes collection to `tests/`
  so a bare `pytest` cannot fire the live-API scripts.

**`notion-client` is deliberately pinned `<3`.** `services/notion_service.py`
uses the v2 `databases.query()` surface. v3 replaces it with the data_sources
API. Upgrading is a code migration, not a version bump — the other two repos are
already on v3.

Email sending is **Resend**, not SMTP. Some older guides in this repo still
describe the SMTP setup; treat Resend as authoritative.

### `lambeth-cyclists-mcp` (CycleBot)

FastMCP server exposing read-only tools over five Notion databases: Meetings,
Items, Projects, Wards, Councillors & Candidates. Uses the v3 data_sources API.

Served over streamable-HTTP behind **bearer auth** (`MCP_API_KEY`), enforced by
`BearerAuthMiddleware`. The server **refuses to start over HTTP without a key** —
this is deliberate. It previously ran unauthenticated: `.env.example` documented
the key and the portal sent it, but `server.py` never read it, leaving every
database readable by anyone with the URL. Fixed 30 August 2026.

Database IDs default to the live Lambeth ones but are overridable via
`NOTION_<KEY>_DB` / `NOTION_<KEY>_DS` env vars.

The Wards/Councillors data was built for the **May 2026 Lambeth council
elections**, which have now passed. Whether it still earns its place, or should
become a post-election "who represents each ward" reference, is an open
question. **[UNCONFIRMED]**

### `lambeth-cyclists-portal`

FastAPI + Jinja2 + htmx, phone-friendly, login-protected. Notion is the only
datastore. Newsletter builder: gather (AI suggestions from Notion + a live web
news scan) → draft → send (Resend to the Google Group, plus copy-paste HTML for
the LCC messaging system). Self-service passwords via a Notion Portal Users DB.

The chat page reaches Notion through the MCP server using the Anthropic MCP
connector, so its answers are grounded in real database content.

---

## Costs

Roughly **$2–5/month**: Railway within free credit, Claude API a few dollars,
Google Maps within free credit, Gmail and Notion free. This replaced a Zapier
subscription (Zapier only handled one attachment per email).

Whether the Zapier account was ever actually cancelled is **[UNCONFIRMED]** — it
was listed as "Phase 13, wait a week or two" in January 2026 and never ticked
off. Worth checking for a live subscription.

---

## Key people

- **Charlie Ullman** — chair. charlie.ullman@gmail.com
- **Colin** — committee member. colin@penning.org.uk

Current committee composition beyond these two is **[UNCONFIRMED]**.

---

## Standard meeting introduction

Used in auto-generated agendas:

> "Hello and welcome to the meeting for Lambeth Cyclists - we are the Lambeth
> branch of the charity London Cycling Campaign. Whether you are a member of LCC
> or not, you are more than welcome to join and give your thoughts. We are
> interested in basically anyone who wants to make conditions in Lambeth better
> for cyclists of all ages.
>
> We try to be studiously apolitical, but part of our role is often as a
> consultee on TfL or Lambeth Council road or infrastructure plans. We also
> organise social rides when we can, and we support the central London Cycling
> Campaign as we can."

---

## Known weak points

Ordered roughly by how much pain they cause:

1. **Single-operator dependency.** Every service authenticates as Charlie —
   his Gmail OAuth token, his API keys. Nothing survives him being
   unavailable, and no volunteer can take a task without being handed
   credentials.
2. **Silent failures, now partly visible.** The processor still logs an error
   and carries on when an analysis fails, writing placeholder text into
   Summary and AI Key Points. That is the right call — losing the email would
   be worse — but it means a broken pipeline looks like a quiet one. The
   portal dashboard now says so, and the item detail page marks affected items
   as never read. Nothing yet pushes that to anyone who is not looking.
3. **Projects are thinly populated.** The triager exists and the standing
   sweeps exist, but most of the backlog has not been through them, so the
   Projects database does not yet reflect what the group is actually working
   on.
4. **Two Anthropic console keys** under two names, both live. Aliased so
   either resolves, but usage is split across two lines on the bill.
5. **Local Python is 3.10, Railway builds on 3.13.** Everything works on both,
   but they are far enough apart that a dependency could behave differently.

Fixed on 30 August 2026, recorded here because the shape of the code only
makes sense with them in mind:

- The processor ran a retired model for six weeks, filing every email
  unanalysed, because `MODEL` was written out in two files.
- The MCP server ran unauthenticated: the key was documented and sent, and
  never read.
- The three repos had two Notion layers at different major versions, and
  copies of the same helpers that had quietly diverged.

## Links

- GitHub: https://github.com/icarusfall/lambeth-cyclists-email-processor
- Railway: https://railway.app/
- Claude Console: https://console.anthropic.com/
- Notion integrations: https://www.notion.so/my-integrations
- LCC: https://lcc.org.uk/
- Portal: https://members.lambethcyclists.com
