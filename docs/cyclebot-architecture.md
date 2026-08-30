# CycleBot: the Lambeth Cyclists assistant

> Rewritten 30 August 2026. The previous version described CycleBot as an MCP
> server with front ends hanging off it. That is no longer the shape: the agent
> is a library, and MCP is one of the ways to reach it.

CycleBot answers questions about the group's Notion data — meetings, filed
items, projects, ward and councillor research — in natural language. It is
read-only by construction: there are no tools that write.

## The shape

The agent — the ten tools, the system prompt, the conversation loop — lives in
[`core/cyclebot.py`](../core/cyclebot.py). Everything else is a way in.

```
                        ┌──────────────────────────┐
  portal /chat ────────▶│                          │
                        │      core.cyclebot       │
  WhatsApp (later) ────▶│                          │──▶ Notion (data sources)
                        │  10 read-only tools      │
  MCP clients ─────────▶│  system prompt + loop    │
  (via mcp/server.py)   └──────────────────────────┘
```

**Why a library and not a service.** MCP is a transport for clients you don't
control. Until 30 August 2026 the portal's own chat page reached the tools like
this:

```
portal ─▶ Anthropic API ─▶ (public internet) ─▶ Railway MCP server ─▶ Notion
```

The Anthropic MCP connector means *Anthropic's* servers call the tools, not
ours. So the MCP server had to be publicly reachable, which is why it needs a
bearer key — and why, for six months, it was readable by anyone with the URL
(see below). For a service that can already reach Notion directly, that is a
long way round to call a function.

The portal now calls `cyclebot.answer()` in-process. Same tools, no round trip,
no key, nothing publicly exposed.

### The three ways in

| Way in | How | Auth |
|---|---|---|
| Portal `/chat` | `cyclebot.answer(history, surface=...)` in-process | the portal's login |
| `mcp/server.py` | registers the same `TOOLS` with FastMCP | `MCP_API_KEY` bearer |
| WhatsApp (later) | `cyclebot.answer(history, surface=...)` | Meta webhook signature |

`core/tests/test_cyclebot.py` asserts the MCP server exposes exactly the
registered tools, described identically. Add a tool to `core.cyclebot` and every
way in gets it; add one to `mcp/server.py` instead and the test fails.

### `surface`

`answer()` takes a `surface` string appended to the shared system prompt. The
shared part — who CycleBot is, look things up before answering, read-only, be
honest about gaps — lives in `cyclebot.SYSTEM` and is the same everywhere. Only
genuine differences go in `surface`.

The difference that will matter is **who can read the conversation**. The portal
is behind a login, so its surface says the committee can discuss anything. A
WhatsApp group can contain anyone who has been added, so it should not inherit
"you may discuss everything in the databases". That is a decision for when the
channel is built, not a default to drift into.

## The tools

Ten, all read-only. Docstrings are the interface: Claude reads them to decide
when and how to call each one, so they carry valid parameter values and example
queries. Registration refuses a tool with no docstring or an unhinted parameter.

| Tool | Description | Key parameters |
|---|---|---|
| `search_all` | Full-text search across all Notion content | `query: str` |
| `list_meetings` | Recent meetings, most recent first | `limit: int = 10` |
| `get_meeting_agenda` | Full agenda/minutes for one meeting | `date`, `title_search` |
| `get_action_items` | Query the Items database | `status = "all"`, `assignee` |
| `get_ward_data` | Ward election analysis | `ward_name` |
| `get_councillor_data` | Councillor/candidate info | `ward_name`, `councillor_name`, `party` |
| `get_battleground_wards` | Competitive wards (non-Safe-Labour + High priority) | (none) |
| `get_projects` | Campaign projects | `status = "all"` |
| `get_page_detail` | Full page content by ID (drill-down) | `page_id: str` |
| `list_databases` | All databases with property schemas | (none) |

Design decisions worth keeping:

- **Return markdown**, not JSON. Claude synthesises prose from it.
- **Errors come back as text**, not tracebacks — the model can say "Notion is
  down" instead of the process dying.
- **Unknown property types surface as `[type]`** rather than being dropped, so
  Claude can see a field exists. The portal's own page rendering wants the
  opposite; `core.notion.extract_property_value` keeps both via `on_unknown`.
- **Generic property extraction**, so a new database works without code changes.

### The databases

The `v=` parameter in a Notion URL is the *view* ID, not the database ID. The
database ID is the 32-char hex before `?v=`.

| Database | db_id | ds_id |
|---|---|---|
| Meetings | `2e42d7a24378803fb811d2f6ed029137` | `2e42d7a2-4378-80b4-bba9-000bfdd54b95` |
| Wards | `3002d7a24378814ba99cf54d0664ab1c` | `3002d7a2-4378-81f4-85f6-000b48c100c1` |
| Councillors & Candidates | `3002d7a24378814388effd4357a003d3` | `3002d7a2-4378-81d8-8f0e-000be42cf371` |
| Items | `2e32d7a2437880298c81f1af94c441a0` | `2e32d7a2-4378-80c7-ab8b-000b859cd636` |
| Projects | `2e42d7a2437880d686e8ff554556b0c1` | `2e42d7a2-4378-80f3-bafd-000baf137869` |

Overridable per deployment via `NOTION_<KEY>_DB` / `NOTION_<KEY>_DS`.

Notion v3 addresses **data sources**, not databases: queries go to
`data_sources.query()`. Every database has a `data_sources` array; `ds_id` is
what you query and what holds the schema. A Notion integration must be
explicitly connected to each database in the Notion UI — access to a page does
not imply access to a database inside it.

## `mcp/server.py`

A facade, ~130 lines. It registers `core.cyclebot.TOOLS` with FastMCP and wraps
the app in bearer auth. Nothing internal depends on it any more.

It is kept because MCP is the only way a third-party client (Claude Desktop and
the like) could reach CycleBot, and at this size that option is close to free.
If you stop deploying it, the tools keep working everywhere else.

**`MCP_API_KEY` is required.** The server `sys.exit`s rather than start over
HTTP without one, and `BearerAuthMiddleware` answers 401 to anything whose
`Authorization: Bearer` header does not match (`hmac.compare_digest`, so the
check does not leak how much of a key matched). Comma-separated, so each client
can hold its own and any one can be rotated without breaking the others.

Until 30 August 2026 this variable was documented and sent by callers but
**never read by `server.py`** — every database above was readable by anyone who
knew the Railway URL. Treat any key that predates that as compromised.

`python server.py stdio` needs no key: a local process pipe is its own trust
boundary.

## The Vercel front end — retired

`cyclebot.vercel.app` (repo `icarusfall/cyclebot`, Next.js) was a second chat UI
onto the same MCP server, with URL-key auth (`?key=…`, validated against
`VALID_API_KEYS`). Confirmed 30 August 2026 as a proof of concept that was never
adopted, and being retired: the portal's `/chat` page replaces it, with real
accounts instead of a key in the URL.

It duplicated the portal with a weaker auth model and had drifted — beta header
`mcp-client-2025-04-04` against the portal's `mcp-client-2025-11-20`. A
URL-embedded key lands in browser history, in the `Referer` of any outbound
link, and in anything that logs URLs.

**It was the only consumer of the `mcp/` Railway service.** With it gone, that
service has no callers and can stop being deployed. `mcp/server.py` stays in the
repo regardless — see above.

To finish, all outside this repo:

1. Delete the Vercel deployment and archive `icarusfall/cyclebot`
2. Stop the `mcp` service on Railway (or leave it — it costs nothing idle)
3. **Revoke the `MCP_API_KEY` value the Vercel app held.** Any key predating
   30 August 2026 should be treated as compromised anyway, since the server
   spent months not checking it.

## WhatsApp: what it now takes

> Blocked on Meta business verification, which needs headed paper. That gates
> the *channel*, not the agent — everything below can be built and tested
> against the portal first.

The old plan here was a fourth service (`cyclebot-whatsapp`, its own repo, its
own Redis, its own copy of the Anthropic call logic) talking to the MCP server.
That is the shape the August 2026 consolidation existed to undo. It is no longer
what this needs.

**WhatsApp is a route, not a service.** Meta's Cloud API posts webhooks to an
HTTPS endpoint you own — so it can be a route in the portal, calling the same
`cyclebot.answer()` the chat page calls. No new deployment, no second copy of
the brain, no MCP hop, and "functionally identical to the website chat" holds by
construction rather than by discipline.

What genuinely remains to build:

1. **Webhook verification** — Meta sends a challenge on setup (`WHATSAPP_VERIFY_TOKEN`),
   and signs each delivery. Verify the signature; the endpoint is public.
2. **Conversation state.** This is the one real new piece. The portal's browser
   sends the whole history each turn; WhatsApp delivers one message with no
   context. Keyed by sender, last ~10 messages, ~30 min TTL. An in-process dict
   is enough to start (state lost on redeploy, which for a chat bot is a
   shrug); Redis is ~$5/month and only worth it if that becomes annoying —
   which would more than double the running cost of the whole system.
3. **A `surface` for WhatsApp** — see above. A group can contain non-committee
   members; decide what CycleBot may discuss there.
4. **Rate limiting** — per-sender and global. The cost risk is the Anthropic
   bill, not WhatsApp.
5. **Trigger rule** — respond to DMs always, and in groups only when mentioned
   (`@CycleBot …`). Anything else is noise in a group chat.
6. **Markdown → WhatsApp formatting** — see below.

Environment: `WHATSAPP_TOKEN`, `WHATSAPP_VERIFY_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`. `ANTHROPIC_API_KEY` and the Notion token are
already in the portal.

### WhatsApp formatting

Claude's markdown needs converting:

- `**bold**` → `*bold*` (WhatsApp uses single asterisks)
- `# Heading` → `*Heading*` (no headings)
- `` `code` `` unchanged
- Links: WhatsApp auto-links, so emit the raw URL
- **4096 character limit** — split longer replies

### Response time

Send a read receipt immediately, set "typing" while waiting, and if the answer
takes more than ~15s send an interim "Let me look that up…". Tool loops are not
fast.

### Prerequisites

1. Meta Business Account (free) at business.facebook.com — **needs business
   verification, which is what headed paper is for**
2. A WhatsApp Business App in the Meta Developer Portal
3. A dedicated phone number for the bot (cheap SIM, virtual number, or a Meta
   test number for development)
4. Cloud API access token

### Cost

First 1,000 conversations/month are free, then roughly $0.005–0.08 each — a
community group stays in the free tier. As a portal route it adds no hosting
cost. Anthropic API stays pennies per query.

## Notes from building this

- `notion-client` v3 uses `data_sources.query()`, not `databases.query()`.
- Notion database IDs vs view IDs — see above.
- A Notion integration must be connected to each database explicitly.
- `FastMCP()` takes `host`/`port` as constructor parameters, not `mcp.run()` args.
- The Anthropic `type: "url"` MCP config uses Streamable HTTP, not SSE.
- The MCP connector's beta header changes; two clients on different versions is
  a smell that they should not both exist.
- FastMCP describes a tool with its raw `__doc__`, which is indented. Both
  facades go through `cyclebot.describe()` so MCP clients and direct calls get
  identical text.

---

*Architecture doc for CycleBot. Charlie / Lambeth Cyclists. Rewritten August 2026.*
