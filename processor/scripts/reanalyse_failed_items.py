"""Re-run Claude analysis on items the pipeline filed but never read.

When a Claude call fails, process_single_email logs it and carries on, writing
placeholder text into Summary and AI Key Points so the item still lands in
Notion. That is the right call at the time — the email is not lost — but it
leaves rows that look filed and are not.

This finds those rows, re-fetches each email from Gmail by its stored message
id (the body is not kept in Notion, only the id), re-reads the attachments,
runs the analysis again, and writes the real values over the placeholders.

Usage:
    python scripts/reanalyse_failed_items.py            # show what it would do
    python scripts/reanalyse_failed_items.py --apply    # rewrite them
    python scripts/reanalyse_failed_items.py --apply --limit 1
"""

import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

import sys

from config.logging_config import setup_logging, get_logger
from config.settings import get_settings
from processors.attachment_processor import AttachmentProcessor
from services.claude_service import ClaudeService
from services.gmail_service import GmailService
from services.notion_service import NotionService

logger = get_logger(__name__)

FAILURE_MARKERS = ("Error analyzing email content", "Error during AI analysis")


def rich_text(prop):
    return "".join(s.get("plain_text", "") for s in (prop or {}).get("rich_text", []))


def find_failed(notion, limit=None):
    """Items whose stored analysis is the failure placeholder."""
    settings = get_settings()
    ds = notion.client.databases.retrieve(database_id=settings.notion_items_db_id)
    ds_id = ds["data_sources"][0]["id"] if "data_sources" in ds else None

    if ds_id:
        response = notion.client.data_sources.query(data_source_id=ds_id, page_size=100)
    else:
        response = notion.client.databases.query(database_id=settings.notion_items_db_id, page_size=100)

    out = []
    for page in response.get("results", []):
        props = page.get("properties", {})
        blob = rich_text(props.get("Summary")) + rich_text(props.get("AI Key Points"))
        if any(m in blob for m in FAILURE_MARKERS):
            out.append(
                {
                    "id": page["id"],
                    "title": "".join(
                        s.get("plain_text", "") for s in props.get("Title", {}).get("title", [])
                    ),
                    "gmail_id": rich_text(props.get("Gmail Message ID")),
                }
            )
    return out[:limit] if limit else out


def reanalyse(item, gmail, claude, attachments, notion):
    """Re-read one email and return the fresh analysis, or None."""
    if not item["gmail_id"]:
        print("      no Gmail message id stored — cannot re-fetch")
        return None

    email = gmail.get_email_details(item["gmail_id"])

    attachment_text = ""
    if email.attachments:
        for att in email.attachments:
            try:
                gmail.download_attachment(email.message_id, att)
            except Exception as e:
                print(f"      could not download {att.filename}: {e}")
        result = attachments.process_all_attachments(email.attachments)
        attachment_text = result.get("combined_text", "")

    data = claude.analyze_email_text(
        subject=email.subject,
        email_body=email.body_text,
        attachment_text=attachment_text,
    )
    if any(m in str(data.get("summary", "")) for m in FAILURE_MARKERS):
        print("      analysis failed again — leaving it alone")
        return None
    return data


def write_back(notion, page_id, data):
    """Overwrite the placeholder fields with the real analysis."""
    props = {}
    if data.get("summary"):
        props["Summary"] = {"rich_text": [{"text": {"content": str(data["summary"])[:2000]}}]}
    if data.get("ai_key_points"):
        props["AI Key Points"] = {"rich_text": [{"text": {"content": str(data["ai_key_points"])[:2000]}}]}
    for field, prop in (("project_type", "Project Type"), ("action_required", "Action Required"),
                        ("priority", "Priority")):
        if data.get(field):
            props[prop] = {"select": {"name": str(data[field])}}
    for field, prop in (("tags", "Tags"), ("locations", "Locations")):
        values = data.get(field) or []
        if values:
            props[prop] = {"multi_select": [{"name": str(v)[:100]} for v in values[:12]]}
    if data.get("consultation_deadline"):
        props["Consultation Deadline"] = {"date": {"start": str(data["consultation_deadline"])[:10]}}
    props["Processing Status"] = {"select": {"name": "needs_review"}}

    notion.client.pages.update(page_id=page_id, properties=props)
    return props


def main():
    setup_logging(level="WARNING")
    apply = "--apply" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    notion = NotionService()
    failed = find_failed(notion, limit)

    print(f"{len(failed)} item(s) with a failed analysis\n")
    if not failed:
        return
    for f in failed:
        print(f"  - {f['title'][:66]}  (gmail:{f['gmail_id'] or 'MISSING'})")

    if not apply:
        print("\nDry run. Re-run with --apply to re-read and rewrite these.")
        return

    gmail = GmailService()
    gmail.authenticate()
    claude = ClaudeService()
    attachments = AttachmentProcessor()

    print(f"\nUsing model {claude.model}\n")
    fixed = 0
    for f in failed:
        print(f"--- {f['title'][:66]}")
        try:
            data = reanalyse(f, gmail, claude, attachments, notion)
            if not data:
                continue
            write_back(notion, f["id"], data)
            fixed += 1
            print(f"      rewritten: {str(data.get('summary'))[:110]}")
            print(f"      type={data.get('project_type')} action={data.get('action_required')} "
                  f"priority={data.get('priority')}")
        except Exception as e:
            logger.exception("Re-analysis failed for %s", f["id"])
            print(f"      FAILED: {e}")

    print(f"\nRewrote {fixed} of {len(failed)} item(s).")
    print("Processing Status set to needs_review so they get a human glance.")


if __name__ == "__main__":
    main()
