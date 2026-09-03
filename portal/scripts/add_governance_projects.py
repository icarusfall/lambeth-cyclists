"""Create the two projects that came out of the LCC group forum, 3 Sep 2026.

    Sharing out the jobs      — outward. Front page and /help. This is
                                recruitment: eleven remits, two people.
    Running the group         — internal. LCC's governance document, the group
                                agreement, the AGM, the annual check-in, and
                                the bank account question.

The second opens its description with `notion.INTERNAL_MARKER`, which is what
keeps it off the front page and off the help page while leaving it a normal
project at /work/{id}, listed on the desk.

Dry run by default, like the other scripts here:

    python scripts/add_governance_projects.py
    python scripts/add_governance_projects.py --apply

Safe to run twice: it skips a title that already exists.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import notion  # noqa: E402

REMITS = (
    "coordinator, finance, treasurer, rides, cycle checks, political liaison, "
    "infrastructure, campaigns, comms, volunteering and inclusivity champion"
)

JOBS_HELP = (
    "Take on one of the jobs, or a piece of one. The ones that would make the "
    "most difference now are comms (the newsletter and keeping this site "
    "honest), rides, and cycle checks — all of which are a few hours a month "
    "rather than a standing commitment. You do not have to be an LCC member. "
    "Say so in the discussion below and Charlie will pick it up; LCC's own "
    "sign-up, with its code of conduct and safeguarding video, is not ready "
    "until the end of the year, so for now this is an informal conversation."
)

PROJECTS = (
    {
        "title": "Sharing out the jobs",
        "description": (
            "London Cycling Campaign asks every local group to say who covers "
            "which job — 'remit' is their word for it. There are eleven: "
            f"{REMITS}. One person can hold several, and LCC does not mind how "
            "many are filled: the only hard requirement is a coordinator plus "
            "one other person, which Lambeth already meets. So nothing here is "
            "urgent. But eleven jobs shared between two people is the reason "
            "things move slowly, and it is the most concrete way anyone new "
            "could help. You do not need to be an LCC member to take one on — "
            "membership only matters for voting on who holds them."
        ),
        "project_type": "membership",
        "priority": "high",
        "next_action": (
            "Decide which of the eleven we actually want filled, rather than "
            "asking for all of them at once."
        ),
        "help_needed": JOBS_HELP,
    },
    {
        "title": "Running the group",
        "description": (
            notion.INTERNAL_MARKER + " LCC is scrapping the per-group "
            "constitutions and replacing them with one governance document, "
            "plus a group agreement covering comms, influencing and "
            "inclusivity. The template is due out for comment. Alongside it: "
            "an annual meeting with four weeks' notice and compliance updates, "
            "a volunteer sign-up form carrying a code of conduct and a "
            "safeguarding video, and an annual check-in form asking what we "
            "have done, what we would like to do and what is not working. None "
            "of it lands before the end of 2026. Lambeth is roughly two years "
            "without an AGM, so we restart from the new document rather than "
            "revive a constitution nobody has read. Also parked here: whether "
            "to close the bank account. No treasurer is required without one, "
            "but truing up the accounts and dealing with what is left in it is "
            "months of work, and nothing is forcing it."
        ),
        "project_type": "membership",
        "priority": "medium",
        "next_action": (
            "Watch for the governance template and comment on it when it lands."
        ),
        "help_needed": "",
    },
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually write to Notion")
    args = ap.parse_args()

    existing = {p["title"].strip().lower() for p in notion.projects_for_matching()}

    for spec in PROJECTS:
        internal = spec["description"].startswith(notion.INTERNAL_MARKER)
        where = "desk only" if internal else "front page and /help"
        print(f"\n{spec['title']}  [{where}]")
        print(f"  {spec['description'][:200]}...")

        if spec["title"].strip().lower() in existing:
            print("  -> already there, skipping.")
            continue
        if not args.apply:
            print("  -> would create (dry run).")
            continue

        page = notion.create_project(
            title=spec["title"],
            description=spec["description"],
            project_type=spec["project_type"],
            geographic_scope="borough_wide",
            priority=spec["priority"],
            primary_locations=[],
            next_action=spec["next_action"],
        )
        print(f"  -> created {page['url']}")
        if spec["help_needed"]:
            notion.set_help_needed(page["id"], spec["help_needed"])
            print("  -> said what help it wants.")

    if not args.apply:
        print("\nNothing written. Re-run with --apply.")


if __name__ == "__main__":
    main()
