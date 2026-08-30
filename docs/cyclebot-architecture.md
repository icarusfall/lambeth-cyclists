# CycleBot: Lambeth Cyclists AI Assistant

## Architecture Overview

A conversational AI interface that lets Lambeth Cyclists members query Notion databases (meeting agendas, action items, ward election data, and more) via natural language. Phase 1 is a Vercel-hosted web frontend; Phase 2 will add a WhatsApp bot as a second interface to the same backend.

```
┌─────────────────────┐
│   Vercel Frontend    │
│   (Next.js 14)       │
│                      │
│  ?key=abc123 in URL  │
│  Chat UI             │
├──────────┬──────────┤
           │ POST /api/chat
           ▼
┌─────────────────────┐
│   Vercel API Route   │
│   (Serverless Fn)    │
│                      │
│  - Validates API key │
│  - Calls Anthropic   │
│    Messages API      │
│  - Streams response  │
├──────────┬──────────┤
           │ Anthropic Messages API
           │ (with mcp_servers param)
           │ (beta: mcp-client-2025-04-04)
           ▼
┌─────────────────────┐      ┌─────────────────────┐
│   Anthropic API      │─────▶│   MCP Server         │
│   (Claude Sonnet)    │◀─────│   (Railway)          │
│                      │      │                      │
│  Orchestrates tool   │      │  - FastMCP (Python)  │
│  calls based on      │      │  - Streamable HTTP   │
│  user's question     │      │  - notion-client v3  │
└─────────────────────┘      │  - data_sources API  │
                              │  - Read-only tools   │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   Notion Databases   │
                              │   (data sources API) │
                              │                      │
                              │  - Meetings          │
                              │  - Items             │
                              │  - Wards             │
                              │  - Councillors       │
                              │  - Projects          │
                              └─────────────────────┘
```

## Live Deployment (Phase 1 — Complete)

| Component | URL | Platform | Repo |
|---|---|---|---|
| **Frontend** | `cyclebot.vercel.app` | Vercel | `icarusfall/cyclebot` |
| **MCP Server** | `lambeth-cyclists-mcp-production.up.railway.app/mcp` | Railway | `icarusfall/lambeth-cyclists-mcp` |

**Access links**: `https://cyclebot.vercel.app/?key=<key>`, one key per person.

The live keys are **not recorded here** — a doc in a git repo is the wrong place
for working credentials, since they survive in history even after editing. Read
or rotate them in the Vercel dashboard: `VALID_API_KEYS` (comma-separated). Two
keys that were previously listed in this file should be treated as compromised
and rotated.

Note that a URL-embedded key is weak: it lands in browser history, in the
`Referer` header of any outbound link, and in anything that logs URLs. The
portal at members.lambethcyclists.com covers the same chat use case behind real named
logins — see "Overlap with the portal" below.

## Component Details

### 1. MCP Server (Railway)

**Tech**: Python 3.11+, `mcp[cli]` (FastMCP), `notion-client` v3, Streamable HTTP transport

**Notion API**: Uses the **data sources API** (`notion-client` v3). Each database has a `db_id` (the database itself) and a `ds_id` (the data source, which holds the schema and is used for queries). The `ds_id` is discovered automatically from the database's `data_sources` field.

**Notion integration**: "CycleBot" — a dedicated integration (separate from the Email Processor). Must be connected to each database in Notion for access.

**Tools exposed** (11 tools):

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `search_all` | Full-text search across all Notion content | `query: str` |
| `list_meetings` | List recent meetings sorted by date | `limit: int = 10` |
| `get_meeting_agenda` | Get full agenda/minutes for a meeting | `date: str`, `title_search: str` |
| `get_action_items` | Query items database | `status: str = "all"`, `assignee: str` |
| `get_ward_data` | Ward election analysis | `ward_name: str` |
| `get_councillor_data` | Councillor/candidate info | `ward_name`, `councillor_name`, `party` |
| `get_battleground_wards` | Competitive wards (non-Safe-Labour + High priority) | (none) |
| `get_projects` | Campaign projects | `status: str = "all"` |
| `get_page_detail` | Full page content by ID (drill-down) | `page_id: str` |
| `list_databases` | All databases with property schemas | (none) |

**Database IDs** (correct IDs — the `v=` param in Notion URLs is the view ID, not the database ID):

| Database | db_id | ds_id |
|---|---|---|
| Meetings | `2e42d7a24378803fb811d2f6ed029137` | `2e42d7a2-4378-80b4-bba9-000bfdd54b95` |
| Wards | `3002d7a24378814ba99cf54d0664ab1c` | `3002d7a2-4378-81f4-85f6-000b48c100c1` |
| Councillors & Candidates | `3002d7a24378814388effd4357a003d3` | `3002d7a2-4378-81d8-8f0e-000be42cf371` |
| Items | `2e32d7a2437880298c81f1af94c441a0` | `2e32d7a2-4378-80c7-ab8b-000b859cd636` |
| Projects | `2e42d7a2437880d686e8ff554556b0c1` | `2e42d7a2-4378-80f3-bafd-000baf137869` |

**Key design decisions**:
- **Read-only**: No tools that create or modify Notion data. This is a query interface.
- **Rich docstrings**: Each tool's docstring includes valid parameter values and example queries — this is what Claude reads to decide when/how to use the tool.
- **Return markdown**: Format Notion data as readable markdown in tool responses — Claude synthesises it into natural answers.
- **Error handling**: Return clear error messages rather than tracebacks.
- **Generic property extraction**: `format_properties()` handles all Notion property types, so new databases work without code changes.

**Environment variables** (Railway):
- `NOTION_API_TOKEN` — CycleBot integration token
- `MCP_API_KEY` — bearer token(s), comma-separated. The portal and the Vercel
  chat app currently hold different keys; both are listed here so either can
  be rotated without breaking the other. **Required**: since 30 August 2026 the server
  refuses to start over HTTP without it (`sys.exit` at startup), and rejects any
  request whose `Authorization: Bearer` header does not match with a 401.
  Enforced by `BearerAuthMiddleware`, an ASGI wrapper around
  `mcp.streamable_http_app()` mounted in `__main__`, using `hmac.compare_digest`.

  Until that date this variable was documented and sent by callers but **never
  read by `server.py`** — every database below was readable by anyone who knew
  the Railway URL. Any client that talks to this server must now send the
  matching value.

- Database IDs are overridable per deployment via `NOTION_<KEY>_DB` /
  `NOTION_<KEY>_DS` (e.g. `NOTION_MEETINGS_DB`), defaulting to the live Lambeth
  IDs tabulated above.
- `PORT` — set automatically by Railway

### Overlap with the portal

`cyclebot.vercel.app` and the portal's `/chat` page are two front ends onto the
same MCP server, with different auth models (URL key vs. named login) and
different beta headers. That is two things to maintain and two things to explain
to a new volunteer. The portal is the stronger candidate to keep: real accounts,
self-service passwords, and the rest of the committee workflow around it.

### 2. Vercel Frontend

**Tech**: Next.js 14 (App Router), React, Tailwind CSS, `@anthropic-ai/sdk`

**Auth**: API key passed as URL query parameter (`?key=abc123`). Validated server-side against `VALID_API_KEYS`. No cookies or sessions — stateless.

**API route** (`/api/chat`):
- Receives: `{ messages: [...], key: "abc123" }`
- Validates key against `VALID_API_KEYS`
- Creates Anthropic client with beta header `mcp-client-2025-04-04`
  (**drift**: the portal uses `mcp-client-2025-11-20`; the Vercel app should
  be brought in line when it is next touched)
- Calls `messages.stream()` with `mcp_servers` param pointing to Railway
- Streams text deltas back to the frontend as a `ReadableStream`
- `maxDuration = 60` (allows for MCP tool calls which take time)

**UI**: Mobile-first chat interface with emerald green accent. Suggested starter questions on empty state. Lightweight markdown rendering (no library — inline regex).

**Environment variables** (Vercel):
- `ANTHROPIC_API_KEY` — Anthropic API key
- `VALID_API_KEYS` — comma-separated access keys
- `MCP_SERVER_URL` — Railway MCP endpoint (`https://...railway.app/mcp`)
- `MCP_API_KEY` — bearer token sent to the MCP server

### 3. System Prompt

```
You are CycleBot, the AI assistant for Lambeth Cyclists, a cycling
advocacy group in Lambeth, South London.

You help members find information from the group's records including
meeting agendas and minutes, action items, and ward-level election
analysis for the May 2026 Lambeth council elections.

Guidelines:
- Use the available tools to look up information before answering.
  Never guess or make up data.
- If a query is ambiguous, search broadly first, then narrow down.
- Keep answers concise and practical — members are busy people.
- For ward/election queries, always clarify which election cycle
  the data relates to.
- If you can't find something, say so honestly and suggest what
  the member might search for instead.
- You have read-only access. If someone asks you to update or
  create records, explain they'll need to do that in Notion directly.
- Be friendly but not corporate. This is a community cycling group,
  not a boardroom.
```

---

## Phase 2: WhatsApp Bot

### Overview

A WhatsApp bot that lets Lambeth Cyclists members query the same Notion data by messaging in a WhatsApp group or DM. Uses the same MCP server and Anthropic API — just a different input/output channel.

```
Members message               Bot service handles          Same brain
in WhatsApp                   webhook + API calls          as web chat
     │                              │                          │
     ▼                              ▼                          ▼
┌──────────────┐  webhook   ┌───────────────────┐   ┌─────────────────┐
│   WhatsApp   │ ──────────▶│  Bot Service       │──▶│  Anthropic API   │
│   Cloud API  │ ◀──────────│  (Railway)         │   │  + MCP Server    │
└──────────────┘  send msg  │                    │   │  (already built) │
                            │  - Webhook receiver│   └─────────────────┘
                            │  - Message router  │
                            │  - Rate limiting   │
                            │  - Conversation    │
                            │    state (Redis)   │
                            └───────────────────┘
```

### How WhatsApp Cloud API Works

WhatsApp Business Platform (Cloud API) is Meta's official API for building bots. Key concepts:

1. **Meta Business Account** — you need one (free) at business.facebook.com
2. **WhatsApp Business App** — register a phone number for the bot
3. **Webhooks** — WhatsApp sends a POST to your server when a message arrives
4. **Send API** — you POST back to WhatsApp to send replies
5. **Access token** — a long-lived token for authenticating API calls

### Architecture

**Tech**: Python (FastAPI or Flask), deployed as a separate Railway service.

**Trigger options** (choose one):
- **Option A: Group mention** — bot responds when someone writes `@CycleBot <question>` in a group chat. Better for group use, avoids noise.
- **Option B: Direct message** — bot responds to any DM to the CycleBot number. Simpler, good for 1:1 queries.
- **Option C: Both** — respond to DMs always, respond in groups only when mentioned.

Recommend starting with **Option C**.

**Conversation state**: WhatsApp messages arrive one at a time (no conversation history in the webhook). The bot service needs to maintain conversation context:
- Use **Redis** (Railway has a Redis plugin) or an in-memory dict with TTL
- Key: WhatsApp user ID (phone number hash)
- Value: last N messages (capped at ~10 to control token costs)
- TTL: 30 minutes of inactivity, then reset

**Rate limiting**: Prevent abuse and control costs:
- Max 20 messages per user per hour
- Max 100 total messages per hour across all users
- Simple in-memory or Redis counter

### Detailed Flow

```
1. User sends "What's the next meeting?" in WhatsApp group

2. WhatsApp Cloud API sends webhook POST to:
   https://cyclebot-whatsapp.up.railway.app/webhook
   Body includes: sender number, message text, group ID

3. Bot service:
   a. Verifies webhook signature (security)
   b. Checks if message mentions @CycleBot (in groups) or is a DM
   c. Extracts message text
   d. Loads conversation history from Redis for this user
   e. Calls Anthropic Messages API with:
      - Same system prompt as web chat
      - Conversation history + new message
      - Same mcp_servers config (Railway MCP server)
   f. Receives Claude's response (with Notion data via MCP)
   g. Saves updated conversation to Redis
   h. Sends response back via WhatsApp Send API

4. User sees the reply in WhatsApp
```

### WhatsApp-Specific Considerations

**Message formatting**: WhatsApp supports limited formatting (bold, italic, monospace, lists). Claude's markdown output needs to be converted:
- `**bold**` → `*bold*` (WhatsApp uses single asterisks)
- `# Heading` → `*Heading*` (no heading support, use bold)
- `` `code` `` → `` `code` `` (same)
- Links: WhatsApp auto-links URLs, so just include the raw URL
- Max message length: 4096 characters. Split longer responses.

**Response time**: WhatsApp shows "typing" indicator. The bot should:
1. Send a "read receipt" immediately (so the user knows it was received)
2. Set "typing" status while waiting for Claude
3. Send the response when ready
4. If response takes >15s, send a "Let me look that up..." interim message

**Phone number**: You'll need a dedicated phone number for the bot. Options:
- Buy a cheap SIM (any carrier)
- Use a virtual number service
- Meta provides test numbers for development

### Implementation Plan

#### Prerequisites
1. Create a Meta Business Account at business.facebook.com
2. Set up a WhatsApp Business App in the Meta Developer Portal
3. Register a phone number for the bot
4. Get the WhatsApp Cloud API access token
5. Set up Redis on Railway (one-click plugin)

#### Build Sequence
1. **Scaffold the bot service** — FastAPI app with webhook endpoint
2. **Implement webhook verification** — Meta sends a verification challenge on setup
3. **Implement message handling** — parse incoming webhooks, extract text
4. **Add conversation state** — Redis-backed message history per user
5. **Connect to Anthropic API** — same pattern as the Vercel API route
6. **Add WhatsApp message sending** — format and send responses
7. **Add rate limiting** — per-user and global
8. **Deploy to Railway** — new service in the same project
9. **Configure webhook URL in Meta Developer Portal**
10. **Test in a private group first**, then add to the main group

#### Project Structure
```
cyclebot-whatsapp/
├── app.py              # FastAPI app, webhook routes
├── anthropic_client.py # Shared Anthropic API call logic
├── whatsapp.py         # WhatsApp Cloud API client (send messages, formatting)
├── conversation.py     # Redis-backed conversation state
├── rate_limit.py       # Rate limiting
├── requirements.txt
├── Procfile
└── .env.example
```

#### Environment Variables
- `WHATSAPP_TOKEN` — Cloud API access token
- `WHATSAPP_VERIFY_TOKEN` — webhook verification secret (you choose this)
- `WHATSAPP_PHONE_NUMBER_ID` — the bot's phone number ID
- `ANTHROPIC_API_KEY` — same key as Vercel frontend
- `MCP_SERVER_URL` — same Railway MCP endpoint
- `MCP_API_KEY` — same bearer token
- `REDIS_URL` — Railway Redis connection string

### Cost Estimate (Phase 2 additions)

- **WhatsApp Cloud API**: First 1,000 conversations/month are free. After that, ~$0.005–0.08 per conversation depending on type. For a community group this will be free tier.
- **Railway (bot service)**: Lightweight Python service, similar to MCP server. ~$0-2/month.
- **Railway (Redis)**: ~$5/month for the smallest instance. Could use in-memory dict instead for $0 if you accept state loss on redeploy.
- **Anthropic API**: Same as Phase 1 — pennies per query.

---

## Implementation Notes

### Things learned during Phase 1 build

- **Notion data sources API**: `notion-client` v3 uses `data_sources.query()` instead of `databases.query()`. Databases have a `data_sources` array — the `ds_id` is what you use for querying and schema retrieval.
- **Notion database IDs vs view IDs**: The `v=` parameter in Notion URLs is a **view ID**, not the database ID. The database ID is the 32-char hex before `?v=`.
- **Notion integration access**: A new Notion integration must be explicitly connected to each database (or parent page) in the Notion UI. Individual page access doesn't imply database access.
- **MCP beta header**: The Anthropic API's `mcp_servers` parameter requires the beta header `anthropic-beta: mcp-client-2025-04-04`. Set via `defaultHeaders` in the SDK.
- **FastMCP host/port**: `host` and `port` are constructor parameters on `FastMCP()`, not arguments to `mcp.run()`.
- **Streamable HTTP transport**: The Anthropic API `type: "url"` MCP server config uses Streamable HTTP (not SSE). Use `mcp.run(transport="streamable-http")`.

---

*Architecture doc for CycleBot. Charlie / Lambeth Cyclists. March 2026.*
