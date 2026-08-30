# Lambeth Cyclists

Tooling for [Lambeth Cyclists](https://lambethcyclists.org.uk), the Lambeth branch
of the London Cycling Campaign — a volunteer cycling advocacy group in South
London.

The group's work is **projects**: schemes and campaigns followed over months,
through several consultations. Everything else here exists to feed those, or to
get them out to members.

```
        leads                            the work              outputs
  ┌───────────────────┐
  │ email (processor) │──┐
  │ added by hand     │──┼──►  triage  ──►  projects  ──►  newsletter
  │ (crawler, later)  │──┘                                  and others
  └───────────────────┘
```

## Services

Two deployments, both on Railway, both from this repo. `mcp/` is a third
service that no longer has callers - see below.

| Directory | What it is | Runs as |
|---|---|---|
| `processor/` | Watches Gmail for labelled mail, reads it with Claude (text and vision), files structured items into Notion, generates meeting agendas, sends reminders. | worker, 24/7 |
| `portal/` | The members' site at members.lambethcyclists.com. The board, triage, adding items by hand, the newsletter builder, chat. | web |
| `mcp/` | CycleBot over MCP, for MCP clients. A thin facade over `core/cyclebot.py`. | not deployed |
| `core/` | Shared by all three: how we call Claude, read Notion, send mail, and answer questions. | library |

Notion is the only datastore. There is no database of our own.

### Domains

| Host | Serves |
|---|---|
| `lambethcyclists.org.uk` | the public site (WordPress, maintained separately) |
| `members.lambethcyclists.com` | this portal |
| `lambethcyclists.com` | redirects to the public site |

The bare domain and the members' subdomain both point at the same Railway
service; `redirect_front_door` in `portal/app/main.py` tells them apart on the
Host header, so the redirect needs no deployment of its own. A login wall on
the bare domain would be the wrong front door for anyone who has just heard of
the group.

DNS is on Vercel (left over from an earlier project) while the registration is
with Name.com — so records are edited in Vercel, and renewal is at Name.com.

## Running it

Python 3.10+. One dependency set for everything:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Each service runs from its own directory, which is also how Railway starts them:

```bash
cd processor && python main.py                                   # the daemon
cd portal    && uvicorn app.main:app --reload                    # the website
cd mcp       && python server.py                                 # only for MCP clients
```

Each has its own `.env` — copy the `.env.example` beside it. Tests:

```bash
pytest
```

## Conventions that are correctness, not style

- **No sampling parameters.** `temperature` / `top_p` / `top_k` are gone from
  the Anthropic SDK 1.x signatures and rejected by Sonnet 5. Set depth with
  `output_config={"effort": ...}`.
- **Never index `response.content[0]`.** Adaptive thinking is on by default, so
  the first block is a thinking block. Select text blocks by type.
- **Server tools can pause a turn.** `web_search` and `web_fetch` may return
  `stop_reason: "pause_turn"`, and parsing a paused turn yields a schema-valid
  object filled with stubs — which looks like an answer. Resume until the turn
  ends, and reject stub output.
- **Notion is v3 throughout**: queries go to `data_sources.query()`, and pages
  are parented to a data source, not a database.
- **The agent is a library, not a service.** CycleBot's tools, prompt and loop
  live in `core/cyclebot.py`. The portal's chat calls it in-process; `mcp/`
  exposes the same tools to MCP clients; a WhatsApp bot would call the same
  function. Add a tool there and every way in gets it — a test enforces that.

## Where things came from

This started as three repos, merged in August 2026. The full history lives in
the archived originals:

- `icarusfall/lambeth-cyclists-email-processor`
- `icarusfall/lambeth-cyclists-portal`
- `icarusfall/lambeth-cyclists-mcp`

Anything here that looks arbitrary probably has a commit message explaining it
in one of those. [CLAUDE.md](CLAUDE.md) carries the current state and the known
weak points; [docs/](docs) has the setup guides.
