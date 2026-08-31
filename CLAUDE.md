# Lambeth Cyclists — Project Management System

> Last reviewed: **31 August 2026**. Earlier revisions described three separate
> repos; they were merged into this one on 30 August, and both services were
> deployed from the merged repo on 31 August. **The consolidation is complete.**
> The portal was reshaped around the work rather than the inbox later the same
> day — see [`portal/`](#portal) — because the next job is making it fit to
> show a stranger. Items marked **[UNCONFIRMED]** need Charlie to verify — do
> not treat them as fact.

## The Problem

Lambeth Cyclists is a real-world cycling advocacy group in South London, part of
the London Cycling Campaign (LCC) charity. It runs on skeleton staff and needs
tooling so that responding to consultations, traffic orders and infrastructure
projects doesn't depend on one person's inbox.

**Goal:** reduce the administrative load on the chair so more time goes to
advocacy, and so new volunteers can be onboarded without inheriting a decade of
undocumented context.

---

## One repo, several services

| Directory | What it is | Runs as | Interaction model |
|---|---|---|---|
| `processor/` | Email processor. Watches Gmail, extracts structured data with Claude, files it into Notion, generates meeting agendas, sends reminders. | Railway worker | Autonomous daemon, 24/7 |
| `portal/` | Members' portal at **members.lambethcyclists.com**. What we're working on, where you could help, a map, discussion, newsletter builder, triage, archive, chat. | Railway web | On-demand only — every AI call is a button press |
| `mcp/` | CycleBot over MCP: a ~130-line facade over `core.cyclebot`, for MCP clients. | not deployed | no callers since the Vercel app was retired |
| `core/` | Shared by all of them: how we call Claude, read Notion, send mail, and answer questions. | library | — |

Notion is the only datastore. There is no database of our own.

**What is shared, and why.** `core/` exists because the three repos drifted:
the same model name in two files, one of which went stale for six weeks; the
same Notion helpers copied and quietly diverged; the same secret under two
names. Anything used by more than one service belongs there.

| Module | Holds |
|---|---|
| `core/claude.py` | `MODEL`, `response_text_of`, `parse_resuming`, stub detection |
| `core/notion.py` | property extraction, page simplification, data-source resolution |
| `core/mail.py` | Resend sending; raises, and each caller decides what that means |
| `core/cyclebot.py` | the CycleBot agent: ten read-only Notion tools, system prompt, loop |

One `requirements.txt` at the root installs everything for every service. Both
Railway services build from it. It does **not** install `core` — see
[Deployment](#deployment) for why `-e .` cannot work on Railway.

Two things deploy: `processor/` (worker) and `portal/` (web). `mcp/` is kept in
the repo as the one way a third-party MCP client could reach CycleBot, but has
nothing calling it.

### Data flow

```
Gmail ──► processor ──► Notion ◄── portal (read/write)
                          ▲
                          └── core.cyclebot ◄── portal chat (in-process)
                                    ▲          ◄── WhatsApp (later)
                                    └── mcp/server.py (facade, not deployed)
```

---

## Models and AI conventions

**Everything uses `claude-sonnet-5`**, from `core.claude.MODEL`. Chosen over
Opus to keep running costs at charity scale; extraction quality has been
sufficient.

These are correctness requirements on current models, not style:

- **No sampling parameters.** `temperature` / `top_p` / `top_k` are removed from
  the Anthropic SDK 1.x call signatures and rejected by Sonnet 5. Control
  response depth with `output_config={"effort": ...}` instead (`low` for
  deterministic structured extraction, `medium` where some judgement helps).
- **Never index into `response.content[0]`.** Adaptive thinking is on by
  default, so the first block is a thinking block. Use
  `core.claude.response_text_of(message)`.
- **Server tools can pause a turn.** `web_search` / `web_fetch` may return
  `stop_reason: "pause_turn"`, and parsing a paused turn yields a schema-valid
  object full of stubs — which looks like an answer. Use
  `core.claude.parse_resuming`, and reject stub output
  (`core.claude.looks_like_stub`). This does **not** apply to local tools:
  `core.cyclebot.answer` loops on `tool_use` instead.
- **Structured output** in the portal uses `messages.parse(output_format=Model)`
  with a Pydantic model. The processor still hand-parses JSON from a text
  response (`_parse_json_response`) — a candidate for the same treatment.

---

## Service notes

### `processor/` (email processor)

Two async loops in `main.py`: email polling (every 300s) and meeting checks
(every 3600s). Pipeline: Gmail → attachments (PDF/Word/Excel/images) → Claude
analysis (text + vision) → geocoding → Drive upload → Notion item, with
duplicate detection and relationship detection against existing items/projects.

- `agenda/` — meeting detection, agenda generation, reminder emails
- `processors/` — email pipeline and attachment extraction
- `services/` — one module per external API
- `scripts/` — live-API helper checks and OAuth setup (see `scripts/README.md`)
- `tests/` — unit tests, all mocked

Email sending is **Resend**, not SMTP, via `core.mail`. `docs/` was rewritten on
30 August 2026 to stop describing the old SMTP setup.

### `portal/`

FastAPI + Jinja2 + htmx, phone-friendly, login-protected. No build step and no
JavaScript framework: pages are server-rendered and htmx swaps fragments in
place.

**It is organised around the work, not around the post that arrives about it.**
That is the one thing to understand before changing anything here. A
coordinator wants an inbox to sort; somebody who joined last week wants to know
what is going on and where they might fit. Until 31 August 2026 the site only
served the first, and opened on the triage queue — which that day contained a
single card, and that card was a volunteer offering to help.

So a **project** is the unit of browsing, and the items filed under it are its
paper trail, seen only in that context. "Items" and "projects" are Notion's
words for Charlie's filing; the site avoids both. Nobody joining should have to
learn them.

| Route | What it is | Who it is for |
|---|---|---|
| `/` | *What we're working on* — the project cards, plus a borough map | anyone, first visit |
| `/work/{id}` | one piece of work: where it's up to, who leads it, what help it wants, what has come in, discussion | anyone |
| `/help` | *Where you could help* — work that has said what it needs, then anything closing soon | a new helper |
| `/desk` | the old dashboard: needs-someone board, your items, next meeting, pipeline health | the coordinator |
| `/triage` | sorting the pile | the coordinator |
| `/newsletter`, `/archive`, `/chat`, `/items/*`, `/account` | as before | mixed |

Nav shows five links and hides the machinery behind **More**, for the same
reason.

**Discussion** is Notion's own page comments (`client.comments`), on both
projects and items — not a sixth database, so a conversation started in the
portal is the one Charlie sees in Notion. Everything posts as the integration,
so the author's name is written in as a **bold first run** and parsed back off
it in `_read_comment`. Notion's API cannot delete a comment; only a person, in
Notion, can, and the form says so before anyone presses the button.

**Sorting the pile** has two paths. The tick-list with a sticky action bar is
the fast one and the default — most of what arrives is routine post belonging
to nothing, and ticking thirty titles beats waiting on a model. `propose_projects`
still reads the whole pile at once for the cases where it earns its keep, which
is spotting that five separate emails are the same scheme.

**Newsletter builder:** gather (AI suggestions from Notion + a live web news
scan) → draft → send (Resend to the Google Group, plus copy-paste HTML for the
LCC messaging system). Self-service passwords via a Notion Portal Users DB.

The **chat** page calls `core.cyclebot.answer()` **in this process**. It used to
go out through the Anthropic MCP connector to the Railway MCP server — meaning
Anthropic's servers called our tools over the public internet, which is why that
server needs a bearer key. Same tools now, no round trip, no key.

#### Things that will bite you

**The two relations are not synced.** `Projects."Related Items"` and
`Items."Related Project"` are separate one-way properties pointing at each
other's database. Attaching an item writes only the item's side, so every
project reads as having no items. Counts and lists come from querying Items
filtered by `Related Project` — never from the project's own relation.

**`Lead` and `Help Needed` are ours, and optional.** Projects already had `Lead
Volunteer` and `Committee Members`, but both are Notion `people` properties and
writing to them needs a workspace seat. Portal users do not have one, and
leading on a consultation should not require it. So `Lead` is a select holding
the portal name, exactly as `Owner` works on Items. Added by
`scripts/add_project_help_fields.py` (dry-run by default, `--apply` to write).
`Help Needed` is prose, because "help needed" is not something anybody can say
yes to and "someone to read the concept designs when they land" is.

**Maps are optional.** `MAPBOX_TOKEN` unset means no map and every page
otherwise unchanged. The token is a public `pk.` one — readable in the page
source by design, protected by URL restriction at Mapbox. **Use a separate
token for local development:** a token that also permits localhost is not
restricted at all, since anyone can copy it out of the page and serve from
their own.

**Geocoding is the processor's job, and it has two gaps.** Items added by hand
through `/items/new` are never geocoded, so they carry location names and
nothing to plot; the map resolves those names against places already geocoded
on other items, which is a stopgap covering roughly a fifth of them. And five
items have `Geocoded Coordinates` clipped at exactly 2000 characters, because
the processor writes more JSON than Notion's `rich_text` cap allows and it cuts
mid-object — `_geocodes` salvages whole objects with a regex when the parse
fails. Both proper fixes belong in the processor. Every map states how many of
its items it could not place, because a map that quietly drops what it cannot
locate reads as though that work does not exist.

**Settings read two `.env` files**, `("../.env", ".env")`, root first so the
service's own wins. A key several services share can live once at the repo
root. On Railway neither file exists and everything comes from service
variables.

**There are no tests.** Every other service has some; this one has none, and it
now carries the most logic.

### `mcp/` (CycleBot over MCP)

A facade. It registers `core.cyclebot.TOOLS` with FastMCP and wraps the app in
`BearerAuthMiddleware`; the tools themselves live in `core/`. A test asserts the
two ways in expose identical tools, described identically.

Served over streamable-HTTP behind **bearer auth** (`MCP_API_KEY`). The server
**refuses to start over HTTP without a key** — deliberate. It previously ran
unauthenticated: `.env.example` documented the key and callers sent it, but
`server.py` never read it, leaving every database readable by anyone with the
URL. Fixed 30 August 2026; treat any key older than that as compromised.

**Not deployed.** Its only caller was `cyclebot.vercel.app`, deleted on
31 August 2026 along with the Railway service and the key. The file stays
because it is the one way a third-party MCP client could reach CycleBot, and
at ~130 lines over `core.cyclebot` it costs nothing to keep. To bring it
back: a new Railway service, `cd mcp && python server.py`, `PYTHONPATH=/app`,
`NOTION_API_TOKEN`, and a freshly generated `MCP_API_KEY`
(`python -c "import secrets; print(secrets.token_urlsafe(32))"`).

---

## Deployment

Two Railway services, both from this repo, both built from the **repo root**
(Root Directory unset) with a start command that `cd`s into the service:

| Service | Start command |
|---|---|
| processor | `cd processor && python main.py` |
| portal | `cd portal && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Both need **`PYTHONPATH=/app`**. `core/` is put on the path rather than
installed: Railway's builder copies only `pyproject.toml` and
`requirements.txt` into the install layer, so `pip install -e .` runs before
`core/` exists and fails with `package directory 'core' does not exist`. It
cannot work under that builder however the service is configured. Locally the
whole tree is there, so `pip install -e .` is what the README asks for.

There is no `Procfile` and no `railway.json`. Railway's Config as Code is
deprecated in favour of Infrastructure as Code (`.railway/railway.ts`), which
this repo has not adopted — see [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md).

---

## Costs

Roughly **$2–5/month**: Railway within free credit, Claude API a few dollars,
Google Maps and Mapbox within free credit (Mapbox gives 50,000 map loads a
month; a portal with a handful of users will not approach it), Gmail and Notion
free. This replaced a Zapier
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
2. **A green Railway service can be running old code.** When a deploy fails,
   Railway keeps serving the last good build, so a service shows healthy while
   running whatever last succeeded. The portal sat like that for a day: right
   repo, right start command, failing every deploy, serving the pre-merge
   build. Nothing in the dashboard says "you are looking at stale code" —
   only the Deployments list does.

   So **merging the repos and deploying the merged repo are two migrations,
   not one**, and the second can silently not happen. After any change that
   matters, check the deployment went green, not just that the push landed.
3. **Silent failures, now partly visible.** The processor still logs an error
   and carries on when an analysis fails, writing placeholder text into
   Summary and AI Key Points. That is the right call — losing the email would
   be worse — but it means a broken pipeline looks like a quiet one. The
   portal dashboard now says so, and the item detail page marks affected items
   as never read. Nothing yet pushes that to anyone who is not looking.
4. **Everyone with a login can read everything.** There is no per-item
   visibility, and filed items are member correspondence — real names, real
   email addresses, sometimes complaints about neighbours. That was fine while
   the only users were Charlie and Colin. It is the open question now that the
   point of the portal is to hand logins to people who have just volunteered.
   Charlie is checking LCC policy and asking the committee before anyone else
   is added. **Do not treat "the portal is ready" as "invite people".**
5. **Projects are thinly populated.** The triager exists, the standing sweeps
   exist, and sorting is now a five-minute tick-list rather than a wait on a
   model — but most of the backlog has not been through it, so the Projects
   database does not yet reflect what the group is working on. This is the
   one thing that makes the new front page look emptier than the group is.
6. **Two Anthropic console keys** under two names, both live. Aliased so
   either resolves, but usage is split across two lines on the bill.
7. **Local Python is 3.10, Railway builds on 3.13.** Everything works on both,
   but they are far enough apart that a dependency could behave differently.
8. **Wards/Councillors data is post-election.** Built for the May 2026 Lambeth
   council elections, which have passed. `get_battleground_wards` in particular
   answers a question nobody is asking now. Whether this becomes a "who
   represents each ward" reference or goes is open. **[UNCONFIRMED]**

---

## Fixed

On 30–31 August 2026, recorded because the shape of the code only makes
sense with them in mind:

- The processor ran a retired model for six weeks, filing every email
  unanalysed, because `MODEL` was written out in two files.
- The MCP server ran unauthenticated: the key was documented and sent, and
  never read.
- `cyclebot.vercel.app`, a second chat UI onto the same data with a key in the
  URL, was a proof of concept never adopted. Deleted 31 August, along with the
  `mcp` Railway service it was the only caller of, and the `MCP_API_KEY` it
  used. `mcp/server.py` stays in the repo as a ~130-line facade over
  `core.cyclebot` — the only way a third-party MCP client could reach CycleBot.
- Every Railway deploy of the merged repo failed on `-e .` in
  `requirements.txt`, and Railway went on serving the pre-merge build, so the
  merge was invisible in production for a day. See weak point 2.
- The three repos had two Notion layers at different major versions, and
  copies of the same helpers that had quietly diverged. `notion-client` is now
  v3 everywhere; the processor's old `<3` pin is gone.
- Sharing the mailer left `resend.api_key = self.api_key` in
  `processor/services/email_service.py` after `import resend` was removed, so
  `EmailService()` raised `NameError` whenever `RESEND_API_KEY` was set — i.e.
  in every deployment that could actually send. There were no tests for that
  service; there are now.
- The portal opened on the triage queue, which is a coordinator's page. On the
  day it was rewritten that queue showed one card, and the card was somebody
  volunteering to help. See [`portal/`](#portal).
- Five items' geocode JSON was silently truncated at exactly 2000 characters by
  Notion's `rich_text` cap, so it would not parse and those items had no
  location at all. The portal salvages what it can; **the processor still
  writes them that way** and should chunk the value the way `_body_blocks` does
  for newsletter bodies. Not fixed, only worked around.

---

## WhatsApp

Charlie wants CycleBot in a WhatsApp group, and wants the website chat to stay
functionally identical to it. Since the agent is a library, that now holds by
construction: WhatsApp is a **route in the portal** calling the same
`cyclebot.answer()`, not a fourth service with its own copy of the brain.

Blocked on Meta business verification, which needs Lambeth Cyclists headed
paper. That gates the channel, not the agent. What genuinely remains is
conversation state (WhatsApp delivers one message with no history), a `surface`
saying what CycleBot may discuss in a group that can contain non-committee
members, rate limiting, and markdown→WhatsApp formatting. See
[docs/cyclebot-architecture.md](docs/cyclebot-architecture.md).

---

## Links

- GitHub: https://github.com/icarusfall/lambeth-cyclists
- Railway: https://railway.app/
- Claude Console: https://console.anthropic.com/
- Notion integrations: https://www.notion.so/my-integrations
- Resend: https://resend.com/
- LCC: https://lcc.org.uk/
- Portal: https://members.lambethcyclists.com
- Archived original repos: `../archive` (they hold all the history)
