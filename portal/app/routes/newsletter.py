import logging
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from app import ai, mailer, notion
from app.auth import require_user
from app.config import get_settings
from app.web import render_markdown, templates

logger = logging.getLogger(__name__)
router = APIRouter()


def month_label() -> str:
    return date.today().strftime("%B %Y")


def pages_to_md(pages: list[dict]) -> str:
    """Simplified Notion pages -> compact markdown for AI prompts."""
    parts = []
    for p in pages:
        lines = [f"### {p['title']}"]
        for name, value in p["props"].items():
            lines.append(f"- {name}: {value}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts) or "(nothing)"


async def parse_story_form(request: Request) -> list[dict]:
    """Read story cards from the builder form. Cards use suffixed field names
    (headline_0, summary_0, include_0, ...); only cards with their include
    checkbox ticked come back."""
    form = await request.form()
    indices = sorted(
        {
            key.split("_")[-1]
            for key in form.keys()
            if key.startswith("headline_")
        },
        key=lambda s: int(s) if s.isdigit() else 0,
    )
    stories = []
    for i in indices:
        if not form.get(f"include_{i}"):
            continue
        headline = (form.get(f"headline_{i}") or "").strip()
        summary = (form.get(f"summary_{i}") or "").strip()
        if not headline and not summary:
            continue
        stories.append(
            {
                "headline": headline,
                "summary": summary,
                "source": (form.get(f"source_{i}") or "").strip(),
                "url": (form.get(f"url_{i}") or "").strip(),
            }
        )
    return stories


def stories_to_md(stories: list[dict]) -> str:
    parts = []
    for s in stories:
        lines = [f"### {s['headline']}", s["summary"]]
        if s.get("url"):
            lines.append(f"Link: {s['url']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts) or "(no stories selected)"


# ---------------------------------------------------------------------------
# Builder page
# ---------------------------------------------------------------------------


def _ago(iso: str | None) -> str:
    """'4 minutes ago', from a Notion timestamp.

    Relative on purpose: Notion's times are UTC and Lambeth is not, and an
    interval has no timezone to get wrong.
    """
    if not iso:
        return ""
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    mins = int((datetime.now(timezone.utc) - then).total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)


def _mentions_date(text: str, when: date) -> bool:
    """Whether text names this date the ways people write one: 23 September,
    23rd Sept, September 23, Wednesday 23rd, 23/9."""
    mon = _MONTHS[when.month - 1][:3] + "[a-z]*"
    day = f"{when.day}(?:st|nd|rd|th)?"
    patterns = (
        rf"\b{day}\s+(?:of\s+)?{mon}\b",
        rf"\b{mon}\s+{day}\b",
        rf"\b{when.day}/0?{when.month}\b",
        rf"\b{when.strftime('%A')}\s+{day}\b",
    )
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _meetings_not_mentioned(markdown_body: str) -> list[dict]:
    """Upcoming meetings this draft says nothing about.

    The draft step is handed the diary, but only at the moment somebody
    presses it: a draft pasted in, or written before the meeting went into
    Notion, never hears about it. So the builder checks the text itself. A
    meeting counts as mentioned if its date or its venue appears anywhere —
    loose on purpose, because nagging about a meeting the draft already
    covers is worse than missing one worded oddly. Only the next two months:
    next year's AGM is not this newsletter's business.
    """
    horizon = date.today() + timedelta(days=60)
    text = markdown_body or ""
    out = []
    for m in notion.upcoming_meetings():
        props = m.get("props", {})
        try:
            when = date.fromisoformat(str(props.get("Meeting Date", ""))[:10])
        except ValueError:
            continue
        if when > horizon:
            continue
        where = props.get("Location", "")
        venue = where.split(",")[0].strip()
        if _mentions_date(text, when) or (venue and venue.lower() in text.lower()):
            continue
        kind = (props.get("Meeting Type") or "meeting").replace("_", " ")
        out.append(
            {
                "when": f"{when.strftime('%A')} {when.day} {when.strftime('%B')}",
                "where": where,
                "what": kind if "meeting" in kind else f"{kind} meeting",
                "url": m.get("url"),
            }
        )
    return out


@router.get("/newsletter")
async def builder(
    request: Request,
    id: str | None = None,
    new: bool = False,
    user: str = Depends(require_user),
):
    """The builder, opened on the draft in progress if there is one.

    A saved draft belongs to the group, not to whichever browser saved it.
    This page used to open blank unless the address carried ?id=, so a draft
    saved and closed looked lost — and the natural next move, starting again,
    makes a second one. `?new=1` is the deliberate way to do that.
    """
    existing = None
    other_drafts = 0
    opened_automatically = False

    if not id and not new:
        try:
            drafts = notion.current_drafts()
            if drafts:
                id = drafts[0]["id"]
                other_drafts = len(drafts) - 1
                opened_automatically = True
        except Exception:
            # Never fatal: the worst case is the blank builder it used to be.
            logger.exception("Looking for a draft in progress failed")

    if id:
        try:
            existing = notion.load_newsletter(id)
        except Exception as e:
            logger.exception("Failed to load newsletter %s", id)
            existing = {"error": str(e)}

    # Never fatal: a diary that will not load costs the nudge, not the page.
    missing_meetings = []
    if existing and not existing.get("error"):
        try:
            missing_meetings = _meetings_not_mentioned(existing["markdown"])
        except Exception:
            logger.exception("Checking the draft against the diary failed")

    return templates.TemplateResponse(
        request,
        "newsletter.html",
        {
            "user": user,
            "month": month_label(),
            "existing": existing,
            "opened_automatically": opened_automatically,
            "other_drafts": other_drafts,
            "saved_ago": _ago(existing.get("saved_at")) if existing else "",
            "missing_meetings": missing_meetings,
            "group_email": get_settings().group_email,
        },
    )


# ---------------------------------------------------------------------------
# Gather (htmx partials)
# ---------------------------------------------------------------------------


async def headlines_to_skip(request: Request) -> list[str]:
    """Headlines of story cards already on the page, so the AI doesn't repeat
    them — unless the 'include stories we've already seen' box is ticked, in
    which case nothing is skipped."""
    form = await request.form()
    if form.get("include_seen"):
        return []
    return [
        str(v).strip()
        for k, v in form.multi_items()
        if k.startswith("headline_") and str(v).strip()
    ]


@router.post("/newsletter/suggest")
async def suggest(request: Request, user: str = Depends(require_user)):
    skip = await headlines_to_skip(request)
    try:
        items_md = pages_to_md(notion.recent_items(days=45))
        projects_md = pages_to_md(notion.active_projects())
        stories = ai.suggest_stories(items_md, projects_md, skip)
    except Exception as e:
        logger.exception("Suggest stories failed")
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Suggesting stories failed: {e}"}
        )
    if not stories:
        return templates.TemplateResponse(
            request,
            "partials/_error.html",
            {
                "error": (
                    "Nothing new to suggest beyond the stories already listed. "
                    "Tick “include stories we've already seen” to get the full "
                    "set of suggestions again."
                )
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/_stories.html",
        {"stories": [s.model_dump() for s in stories], "label": "From Notion"},
    )


@router.post("/newsletter/news-scan")
async def scan_news(request: Request, user: str = Depends(require_user)):
    skip = await headlines_to_skip(request)
    try:
        stories = ai.news_scan(skip)
    except Exception as e:
        logger.exception("News scan failed")
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"News scan failed: {e}"}
        )
    if not stories:
        return templates.TemplateResponse(
            request,
            "partials/_error.html",
            {
                "error": (
                    "News scan found nothing new beyond the stories already "
                    "listed. Tick “include stories we've already seen” to see "
                    "everything the scan can find."
                )
            },
        )
    return templates.TemplateResponse(
        request,
        "partials/_stories.html",
        {"stories": [s.model_dump() for s in stories], "label": "From the news"},
    )


# ---------------------------------------------------------------------------
# Draft
# ---------------------------------------------------------------------------


@router.post("/newsletter/draft")
async def draft(request: Request, user: str = Depends(require_user)):
    form = await request.form()
    stories = await parse_story_form(request)
    if not stories:
        return templates.TemplateResponse(
            request,
            "partials/_error.html",
            {"error": "Tick at least one story before drafting."},
        )
    try:
        meetings_md = pages_to_md(notion.upcoming_meetings())
        markdown_body = ai.draft_newsletter(
            stories_to_md(stories), meetings_md, month_label()
        )
    except Exception as e:
        logger.exception("Draft newsletter failed")
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Drafting failed: {e}"}
        )
    return templates.TemplateResponse(
        request,
        "partials/_draft.html",
        {
            "markdown_body": markdown_body,
            "subject": form.get("subject") or f"Lambeth Cyclists — {month_label()}",
            "page_id": form.get("page_id") or "",
            "base_version": form.get("base_version") or "",
            "saved": False,
        },
    )


@router.post("/newsletter/preview")
async def preview(
    request: Request,
    markdown_body: str = Form(""),
    user: str = Depends(require_user),
):
    return Response(
        f'<div class="preview card">{render_markdown(markdown_body)}</div>',
        media_type="text/html",
    )


@router.post("/newsletter/save")
async def save(
    request: Request,
    markdown_body: str = Form(...),
    subject: str = Form(...),
    page_id: str = Form(""),
    base_version: str = Form(""),
    force: str = Form(""),
    user: str = Depends(require_user),
):
    """Save the draft for everyone.

    Refuses if somebody else has saved since this copy was opened, unless the
    person has seen that warning and chosen to save over it. Whatever happens,
    the text goes back into the box: a failed save used to replace the whole
    draft area with an error, and the only copy left was in the clipboard.
    """
    page_id = page_id.strip()

    def draft(**extra):
        return templates.TemplateResponse(
            request,
            "partials/_draft.html",
            {
                "markdown_body": markdown_body,
                "subject": subject,
                "page_id": page_id,
                "base_version": base_version,
                "saved": False,
                **extra,
            },
        )

    try:
        if page_id and base_version and not force:
            current = notion.load_newsletter(page_id)
            if current["version"] != base_version:
                logger.info("%s's save of %s refused: changed since opened", user, page_id)
                return draft(conflict=True, saved_ago=_ago(current["saved_at"]))

        saved_id = notion.save_newsletter_draft(
            title=f"Newsletter — {month_label()}",
            subject=subject,
            markdown_body=markdown_body,
            page_id=page_id or None,
        )
        saved = notion.load_newsletter(saved_id)
    except Exception as e:
        logger.exception("Save draft failed")
        return draft(error=f"Saving to Notion failed: {e}")

    # Checked again on every save, so a meeting put in Notion while the draft
    # is open still gets noticed.
    missing_meetings = []
    try:
        missing_meetings = _meetings_not_mentioned(markdown_body)
    except Exception:
        logger.exception("Checking the draft against the diary failed")

    logger.info("%s saved newsletter draft %s", user, saved_id)
    response = templates.TemplateResponse(
        request,
        "partials/_draft.html",
        {
            "markdown_body": markdown_body,
            "subject": subject,
            "page_id": saved_id,
            "base_version": saved["version"],
            "missing_meetings": missing_meetings,
            "saved": True,
        },
    )
    # So a reload, a bookmark or a link pasted to Colin opens this draft.
    response.headers["HX-Push-Url"] = f"/newsletter?id={saved_id}"
    return response


@router.post("/newsletter/{page_id}/discard")
async def discard(request: Request, page_id: str, user: str = Depends(require_user)):
    """Move a draft to Notion's trash. Buttons calling this use hx-confirm."""
    try:
        nl = notion.load_newsletter(page_id)
        if nl["status"] == notion.NEWSLETTER_STATUS_SENT:
            return templates.TemplateResponse(
                request,
                "partials/_error.html",
                {"error": "That newsletter has been sent — it stays in the archive."},
            )
        notion.discard_newsletter(page_id)
    except Exception as e:
        logger.exception("Discard draft failed")
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Discarding failed: {e}"}
        )
    if request.headers.get("HX-Request"):
        return Response(status_code=200, headers={"HX-Redirect": "/archive"})
    return RedirectResponse("/archive", status_code=303)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


@router.get("/newsletter/{page_id}/send")
async def send_page(
    request: Request, page_id: str, user: str = Depends(require_user)
):
    nl = notion.load_newsletter(page_id)
    return templates.TemplateResponse(
        request,
        "send.html",
        {
            "user": user,
            "nl": nl,
            "html_preview": render_markdown(nl["markdown"]),
            "group_email": get_settings().group_email,
        },
    )


@router.post("/newsletter/{page_id}/send-test")
async def send_test(
    request: Request,
    page_id: str,
    test_email: str = Form(...),
    user: str = Depends(require_user),
):
    nl = notion.load_newsletter(page_id)
    try:
        mailer.send_newsletter(
            f"[TEST] {nl['subject']}", nl["markdown"], test_email.strip()
        )
    except Exception as e:
        logger.exception("Test send failed")
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Test send failed: {e}"}
        )
    return Response(
        f'<p class="flash ok">Test sent to {test_email} — check how it looks on your phone.</p>',
        media_type="text/html",
    )


@router.post("/newsletter/{page_id}/send")
async def send(
    request: Request,
    page_id: str,
    user: str = Depends(require_user),
):
    form = await request.form()
    to_group = bool(form.get("channel_group"))
    for_lcc = bool(form.get("channel_lcc"))
    if not (to_group or for_lcc):
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": "Pick at least one channel."}
        )

    nl = notion.load_newsletter(page_id)
    channels = []
    group_result = None

    if to_group:
        group_email = get_settings().group_email
        if not group_email:
            return templates.TemplateResponse(
                request,
                "partials/_error.html",
                {"error": "GROUP_EMAIL isn't configured — can't send to the group."},
            )
        try:
            group_result = mailer.send_newsletter(
                nl["subject"], nl["markdown"], group_email
            )
            channels.append("Google Group")
        except Exception as e:
            logger.exception("Group send failed")
            return templates.TemplateResponse(
                request,
                "partials/_error.html",
                {"error": f"Sending to the group failed (nothing marked as sent): {e}"},
            )

    if for_lcc:
        channels.append("LCC")

    try:
        notion.mark_newsletter_sent(page_id, sent_by=user, channels=channels)
    except Exception as e:
        logger.exception("Marking sent failed")
        # The email (if any) already went — surface but don't pretend it failed
        return templates.TemplateResponse(
            request,
            "partials/_error.html",
            {
                "error": (
                    f"Email was sent, but updating Notion failed: {e}. "
                    "Set the status manually in Notion."
                )
            },
        )

    return templates.TemplateResponse(
        request,
        "partials/_sent.html",
        {
            "nl": nl,
            "channels": channels,
            "group_result": group_result,
            "for_lcc": for_lcc,
            "html_body": mailer.markdown_to_email_html(nl["markdown"]),
            "text_body": nl["markdown"],
        },
    )
