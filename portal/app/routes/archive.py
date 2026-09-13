import logging

from fastapi import APIRouter, Depends, Request

from app import mailer, notion
from app.auth import require_user
from app.web import render_markdown, templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/archive")
async def archive_list(request: Request, user: str = Depends(require_user)):
    error = None
    drafts, sent = [], []
    try:
        for nl in notion.list_newsletters():
            if nl["props"].get("Status") == notion.NEWSLETTER_STATUS_SENT:
                sent.append(nl)
            else:
                drafts.append(nl)
    except Exception as e:
        logger.exception("Archive list failed")
        error = str(e)
    return templates.TemplateResponse(
        request,
        "archive.html",
        {"user": user, "drafts": drafts, "sent": sent, "error": error},
    )


@router.get("/archive/{page_id}")
async def archive_view(
    request: Request, page_id: str, user: str = Depends(require_user)
):
    nl = notion.load_newsletter(page_id)
    # Sent newsletters get the copy-paste versions: sending to the Google
    # Group and posting through LCC's messaging system often happen on
    # different days, done by different people, and the second person needs
    # exactly what went out. A draft gets none, so nobody pastes something
    # that was never sent.
    copy = None
    if nl["status"] == notion.NEWSLETTER_STATUS_SENT:
        copy = mailer.copy_paste_versions(nl["markdown"])
    return templates.TemplateResponse(
        request,
        "archive_view.html",
        {
            "user": user,
            "nl": nl,
            "html_body": render_markdown(nl["markdown"]),
            "copy": copy,
        },
    )
