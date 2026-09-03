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
from fastapi.responses import Response

from app import ai, notion
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
            # Internal work — the AGM, the remits, LCC's paperwork — is
            # tracked like anything else but never shown here. This page is
            # the one a stranger meets, and it should read as what the group
            # does, not what it has to administer. It is on the desk instead.
            "projects": [
                p for p in projects if p["live"] and not p["standing"] and not p["internal"]
            ],
            "standing": [
                p for p in projects if p["live"] and p["standing"] and not p["internal"]
            ],
            "closed": [p for p in projects if not p["live"] and not p["internal"]],
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


# ---------------------------------------------------------------------------
# Turning one item into a project
# ---------------------------------------------------------------------------
# The batch triage flow reads the whole backlog at once, which is right for
# clearing a pile. This is the other moment: you are reading one item, you can
# already tell the council will keep coming back to it, and you want somewhere
# to file the next six emails about it. Nothing is written until a button is
# pressed.


@router.post("/items/{page_id}/project/suggest")
async def suggest_project(request: Request, page_id: str, user: str = Depends(require_user)):
    """Draft the project this item would start — or name the one it joins."""
    try:
        item = notion.item_detail(page_id)
        projects = notion.projects_for_matching()
        proposal = ai.suggest_project_for_item(item, projects)
    except Exception as e:
        logger.exception("Suggesting a project for %s failed", page_id)
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Couldn't work that out: {e}"}
        )
    return templates.TemplateResponse(
        request,
        "partials/_item_project_form.html",
        {
            "user": user,
            "item_id": page_id,
            "s": proposal,
            "projects": projects,
            "project_kinds": ai.PROJECT_KINDS,
            "scopes": ai.SCOPES,
            "priorities": ai.PROJECT_PRIORITIES,
        },
    )


@router.post("/items/{page_id}/project")
async def give_item_a_project(
    request: Request,
    page_id: str,
    existing_id: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    project_type: str = Form("ongoing_monitoring"),
    geographic_scope: str = Form("neighbourhood"),
    priority: str = Form("medium"),
    primary_locations: str = Form(""),
    next_action: str = Form(""),
    user: str = Depends(require_user),
):
    """File the item under a project — an existing one, or a new one.

    Answers with a redirect to the project rather than a fragment: the point
    of the press was to go and look at the thing you just made.
    """
    try:
        if existing_id:
            project_id = existing_id
        else:
            if not title.strip():
                return templates.TemplateResponse(
                    request, "partials/_error.html", {"error": "Give it a name first."}
                )
            created = notion.create_project(
                title=title.strip(),
                description=description.strip(),
                project_type=project_type,
                geographic_scope=geographic_scope,
                priority=priority,
                primary_locations=[l.strip() for l in primary_locations.split(",") if l.strip()],
                next_action=next_action.strip(),
            )
            project_id = created["id"]
            logger.info("%s started project %r from item %s", user, title.strip()[:60], page_id)
        notion.attach_items_to_project([page_id], project_id)
    except Exception as e:
        logger.exception("Giving item %s a project failed", page_id)
        return templates.TemplateResponse(
            request, "partials/_error.html", {"error": f"Couldn't save that: {e}"}
        )

    # htmx cannot usefully follow a 303, so tell it where to go instead.
    return Response(status_code=204, headers={"HX-Redirect": f"/work/{project_id}"})
