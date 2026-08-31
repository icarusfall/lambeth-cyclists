"""What Lambeth Cyclists is working on.

The front of the site, and the part a new helper reads first. It answers one
question — what's going on and where could I fit — so it is organised around
the work rather than around the post that arrives about it. Filed items are
the paper trail underneath a piece of work; they are never a list of their
own here.
"""

import logging
import re

from fastapi import APIRouter, Depends, Form, Request

from app import notion
from app.auth import require_user
from app.config import get_settings
from app.web import templates

logger = logging.getLogger(__name__)
router = APIRouter()

_UUID = re.compile(
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)


@router.get("/")
async def work(request: Request, user: str = Depends(require_user)):
    projects, error = [], None
    try:
        projects = notion.project_overview()
    except Exception as e:
        logger.exception("Loading the work overview failed")
        error = f"Couldn't load our projects from Notion: {e}"

    # Never fatal. A map that fails to build should cost you the map, not the
    # page it sits on.
    map_data = None
    try:
        map_data = notion.map_points()
    except Exception:
        logger.exception("Building the map failed")

    return templates.TemplateResponse(
        request,
        "work.html",
        {
            "user": user,
            "projects": [p for p in projects if p["live"] and not p["standing"]],
            "standing": [p for p in projects if p["live"] and p["standing"]],
            "closed": [p for p in projects if not p["live"]],
            "error": error,
            "map": map_data,
            "mapbox_token": get_settings().mapbox_token,
        },
    )


def _comments(page_id: str) -> tuple[list[dict], str | None]:
    """Discussion on a page. A comment thread that won't load must not take
    the page down with it — the rest of it is still worth reading."""
    try:
        return notion.list_comments(page_id), None
    except Exception as e:
        logger.exception("Loading comments for %s failed", page_id)
        return [], f"Couldn't load the discussion: {e}"


@router.get("/work/{page_id}")
async def project(request: Request, page_id: str, user: str = Depends(require_user)):
    if not _UUID.match(page_id):
        return templates.TemplateResponse(
            request,
            "project.html",
            {"user": user, "p": None, "error": "That isn't one of ours."},
            status_code=404,
        )
    try:
        p = notion.project_detail(page_id)
    except Exception as e:
        logger.exception("Loading project %s failed", page_id)
        return templates.TemplateResponse(
            request,
            "project.html",
            {"user": user, "p": None, "error": f"Couldn't load that: {e}"},
            status_code=404,
        )
    comments, comment_error = _comments(page_id)
    map_data = None
    try:
        map_data = notion.map_points(project_id=page_id)
    except Exception:
        logger.exception("Building the map for %s failed", page_id)

    return templates.TemplateResponse(
        request,
        "project.html",
        {
            "user": user,
            "p": p,
            "error": None,
            "comments": comments,
            "comment_error": comment_error,
            "comment_target": f"/work/{page_id}/comment",
            "map": map_data,
            "mapbox_token": get_settings().mapbox_token,
            "statuses": notion.PROJECT_STATUSES,
        },
    )


@router.post("/work/{page_id}/status")
async def set_status(
    request: Request,
    page_id: str,
    status: str = Form(...),
    outcome: str = Form(""),
    user: str = Depends(require_user),
):
    """Move a project along — including off the front page.

    Closing is not deleting. The project keeps its items, its discussion and
    everything filed under it; it stops being listed as live work and moves to
    "What we've finished with" instead.
    """
    error = None
    try:
        p = notion.set_project_status(page_id, status, outcome)
        logger.info("%s set %s to %s", user, page_id, status)
    except ValueError as e:
        p = notion.project_detail(page_id)
        error = str(e)
    except Exception as e:
        logger.exception("Setting status on %s failed", page_id)
        p = notion.project_detail(page_id)
        error = f"Couldn't save that: {e}"

    return templates.TemplateResponse(
        request,
        "partials/_status.html",
        {
            "p": p,
            "user": user,
            "statuses": notion.PROJECT_STATUSES,
            "saved": error is None,
            "error": error,
        },
    )


@router.post("/work/{page_id}/comment")
@router.post("/items/{page_id}/comment")
async def comment(
    request: Request,
    page_id: str,
    body: str = Form(""),
    user: str = Depends(require_user),
):
    """Add to the discussion, and hand back the whole thread.

    Both projects and items comment the same way, because to Notion they are
    both just pages.
    """
    target = request.url.path
    text = body.strip()
    if not text:
        comments, error = _comments(page_id)
        return templates.TemplateResponse(
            request,
            "partials/_comments.html",
            {
                "user": user,
                "comments": comments,
                "comment_error": error or "Write something first.",
                "comment_target": target,
            },
        )

    error = None
    try:
        notion.add_comment(page_id, user, text)
        logger.info("%s commented on %s", user, page_id)
    except Exception as e:
        logger.exception("Commenting on %s failed", page_id)
        error = f"Couldn't post that: {e}"

    comments, load_error = _comments(page_id)
    return templates.TemplateResponse(
        request,
        "partials/_comments.html",
        {
            "user": user,
            "comments": comments,
            "comment_error": error or load_error,
            "comment_target": target,
            # Only clear the box if the comment actually landed; otherwise the
            # person would lose what they wrote.
            "keep": text if error else "",
        },
    )


@router.get("/help")
async def help_out(request: Request, user: str = Depends(require_user)):
    """Where a new person looks first: what could I actually do?

    Two kinds of answer. A project that has spelled out what it wants is the
    good kind. A consultation with a closing date is the urgent kind. Both are
    kept short on purpose — twenty undifferentiated asks reads as a wall and
    nobody picks any of them.
    """
    ways, jobs, error = [], [], None
    try:
        ways = notion.ways_to_help()
    except Exception as e:
        logger.exception("Loading ways to help failed")
        error = f"Couldn't load this from Notion: {e}"
    try:
        jobs = notion.unclaimed_items()
    except Exception:
        logger.exception("Loading the unclaimed queue failed")
    return templates.TemplateResponse(
        request,
        "help.html",
        {"user": user, "ways": ways, "jobs": jobs, "error": error},
    )


@router.post("/work/{page_id}/lead")
async def take_the_lead(
    request: Request,
    page_id: str,
    release: str = Form(""),
    user: str = Depends(require_user),
):
    """Put your name to a piece of work, or take it off again."""
    try:
        if release:
            p = notion.release_project(page_id, user)
        else:
            p = notion.claim_project(page_id, user)
    except Exception as e:
        logger.exception("Changing the lead on %s failed", page_id)
        return templates.TemplateResponse(
            request,
            "partials/_error.html",
            {"error": f"Couldn't save that: {e}"},
        )
    message = None
    if not release and p["lead"] != user:
        message = f"{(p['lead'] or 'Someone').capitalize()} got there first."
    return templates.TemplateResponse(
        request, "partials/_lead.html", {"p": p, "user": user, "message": message}
    )


@router.post("/work/{page_id}/help-needed")
async def help_needed(
    request: Request,
    page_id: str,
    text: str = Form(""),
    user: str = Depends(require_user),
):
    """Say what somebody new could do here."""
    try:
        notion.set_help_needed(page_id, text.strip())
        p = notion.project_detail(page_id)
    except Exception as e:
        logger.exception("Saving help-needed for %s failed", page_id)
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Couldn't save that: {e}"}
        )
    logger.info("%s set what help %s needs", user, page_id)
    return templates.TemplateResponse(
        request, "partials/_help_needed.html", {"p": p, "user": user, "saved": True}
    )
