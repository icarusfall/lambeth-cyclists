"""One-off: add the fields that let a project ask for help.

Adds two properties to the Projects database, both additive — no existing
data is touched:

    Lead         select     — the portal user steering this piece of work
    Help Needed  rich_text  — what somebody new could actually do here

Projects already have "Lead Volunteer" and "Committee Members", but both are
Notion `people` properties, so writing to them needs the person to hold a seat
in the Notion workspace. Portal users do not, and requiring one to lead on a
consultation would defeat the point. `Lead` is a select holding the portal
name, exactly as `Owner` works on Items.

`Help Needed` is prose rather than a checkbox because "we need help" is not
useful to read. "Someone to look over the concept designs when they land in
the autumn" is.

Usage:
    python scripts/add_project_help_fields.py            # show what would change
    python scripts/add_project_help_fields.py --apply    # make the change
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import notion  # noqa: E402
from app.auth import parse_users  # noqa: E402
from app.config import get_settings  # noqa: E402

LEAD = "Lead"
HELP_NEEDED = "Help Needed"

FALLBACK_OWNERS = ["charlie", "colin", "simon"]


def known_owners() -> list[str]:
    """Portal user names, from the Notion Portal Users DB where available."""
    names = set(FALLBACK_OWNERS)
    names.update(parse_users().keys())
    try:
        ds = notion.ds_id_for(get_settings().notion_users_db)
        rows = notion.client().data_sources.query(data_source_id=ds).get("results", [])
        names.update(
            t.strip().lower()
            for t in (notion.get_page_title(p) for p in rows)
            if t and t.strip()
        )
    except Exception as e:
        print(f"  (could not read Portal Users DB, using defaults: {e})")
    return sorted(names)


def main():
    apply = "--apply" in sys.argv
    settings = get_settings()

    if not settings.notion_api_token:
        sys.exit("NOTION_API_TOKEN is not set.")

    ds_id = notion.ds_id_for(settings.notion_projects_db)
    ds = notion.client().data_sources.retrieve(data_source_id=ds_id)
    existing = ds.get("properties", {})

    print(f"Projects data source: {ds_id}")
    print(f"{len(existing)} existing properties\n")

    to_add = {}

    if LEAD in existing:
        print(f"  '{LEAD}' already exists ({existing[LEAD]['type']}) — leaving alone")
    else:
        owners = known_owners()
        to_add[LEAD] = {"select": {"options": [{"name": n} for n in owners]}}
        print(f"  will add '{LEAD}' (select) with options: {', '.join(owners)}")

    if HELP_NEEDED in existing:
        print(f"  '{HELP_NEEDED}' already exists — leaving alone")
    else:
        to_add[HELP_NEEDED] = {"rich_text": {}}
        print(f"  will add '{HELP_NEEDED}' (rich text)")

    if not to_add:
        print("\nNothing to do — both fields are already present.")
        return

    if not apply:
        print("\nDry run. Re-run with --apply to make these changes.")
        return

    notion.client().data_sources.update(data_source_id=ds_id, properties=to_add)
    print(f"\nAdded {len(to_add)} property/properties to the Projects database.")
    print("Every project now has an empty Lead and no Help Needed text, which")
    print("is what puts it on the 'Help out' page as unled and unspoken-for.")


if __name__ == "__main__":
    main()
