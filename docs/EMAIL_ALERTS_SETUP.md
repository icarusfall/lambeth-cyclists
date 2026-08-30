# Email alerts setup

> Rewritten 30 August 2026. This guide previously described Gmail SMTP with an
> app password. **Sending is Resend.** There is no SMTP anywhere in the code —
> `SMTP_HOST`, `SMTP_USERNAME` and friends do nothing if you set them.

The processor emails you about meeting admin and about its own failures. Both
go through Resend, as does everything the portal sends; the shared code is
[`core/mail.py`](../core/mail.py).

## What you'll get

### Meeting reminders

| When | Subject | Contains |
|---|---|---|
| Agenda generated (2 days before) | `Agenda Generated: …` | meeting details, days to go, agenda preview, Notion link |
| Every day until approved | `⚠️ URGENT: Agenda Needs Approval: …` | days to go, Notion link — **daily until you mark it approved** |
| Day before | `Meeting Tomorrow: …` | date, time, format, location, Zoom link |
| Day after | `Please Add Minutes: …` | checklist: notes, decisions, action items, next date |

### Error alerts

Subject `⚠️ Error in Email Processor: …`, with what went wrong and a nudge to
check the Railway logs. Sent when processing fails, when nothing has been
processed for 7+ days (the pipeline may be down), and on critical config errors.

This matters more than it looks. When an analysis fails the processor logs the
error and files the email anyway with placeholder text — losing the email would
be worse — so **a broken pipeline looks like a quiet one**. These alerts and the
portal dashboard are the only things that say otherwise.

## Setup

### Step 1: Get a Resend API key

1. Sign in at <https://resend.com>
2. Go to <https://resend.com/api-keys> and create a key (starts `re_`)
3. Copy it — you only see it once

**Sending domain.** To send as `@lambethcyclists.com` the domain must be
verified in Resend (<https://resend.com/domains>, then add the DNS records —
ours are on Vercel, see the README). Until then use Resend's test address
`onboarding@resend.dev`, which sends only to the account owner's address.

### Step 2: Add to `processor/.env`

```bash
RESEND_API_KEY=re_your_key_here
FROM_EMAIL=Lambeth Cyclists <onboarding@resend.dev>
# Single address, or comma-separated for several
ALERT_EMAIL=your-email@gmail.com
```

`FROM_EMAIL` takes a full `Name <address>` string. `ALERT_EMAIL` falls back to
`ADMIN_EMAIL` if unset.

If `RESEND_API_KEY` is missing the processor still runs — it just cannot send.
That is deliberate: alerts failing should not stop email being filed.

On Railway, set the same three as service variables rather than committing them.

### Step 3: Send a test

```bash
cd processor && python scripts/check_email_alerts.py
```

It sends one message to `ALERT_EMAIL` and prints whether Resend accepted it.
This hits the live API — see [`scripts/README.md`](../processor/scripts/README.md).

## Troubleshooting

**`MailNotConfigured`** — `RESEND_API_KEY` is empty or absent. Distinct on
purpose from a send that was attempted and failed, so "not set up" never looks
like "broken".

**401 / "API key is invalid"** — the key is wrong or was revoked. Check
<https://resend.com/api-keys>.

**403 / "domain is not verified"** — `FROM_EMAIL` uses a domain Resend hasn't
verified. Either verify it, or fall back to `onboarding@resend.dev`.

**Accepted but nothing arrives** — with `onboarding@resend.dev` you can only
send to the Resend account owner's address. Check spam, then the Resend
dashboard, which logs every send and its delivery state.

**Too many reminders** — the daily nag is doing its job. Mark the agenda
approved in Notion and it stops.

**Nothing at all, no errors** — check the processor is actually running
(`main.py`, meeting loop every 3600s) and that `ALERT_EMAIL` is set.

## Testing the whole flow

1. Create a meeting in Notion 2 days out — title, date, format `Hybrid`,
   "Meeting Created Manually" ticked
2. Run `python main.py` in `processor/`
3. Wait for the meeting loop (hourly): you should get the agenda email
4. Don't approve it — the daily nag starts
5. Approve it in Notion — the nags stop

## Security

- Keys live in `.env`, which is gitignored (all three services' `.env` files are)
- Railway encrypts environment variables
- Revoke a key at <https://resend.com/api-keys>; it takes effect immediately
- Don't paste keys into docs — they survive in git history after editing

Every service currently authenticates as Charlie, including this one. That is
the system's biggest weak point, recorded in [CLAUDE.md](../CLAUDE.md).
