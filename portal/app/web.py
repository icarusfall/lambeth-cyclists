"""Shared Jinja2 environment + small template helpers."""

from datetime import date

import markdown as md
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def render_markdown(text: str) -> str:
    """Markdown to HTML, the one way the portal does it.

    `nl2br` makes a single line break a line break. Standard markdown joins
    lines into one paragraph unless a blank line separates them — right for
    prose wrapped at 80 columns, wrong for what people actually paste here.
    The September 2026 newsletter was pasted in from an email, and its meeting
    details, each on its own line, went out to the Google Group run together
    into one. The builder's preview, the email, the archive and the plain-text
    copy all render through this, so what you preview is what goes out.
    """
    return md.markdown(text or "", extensions=["extra", "nl2br"])


_MONTHS = (
    "January February March April May June July "
    "August September October November December"
).split()


def humandate(value) -> str:
    """'9 September' — no platform-specific strftime directives.

    %-d is glibc-only and %#d is Windows-only, so neither survives the trip
    between local development and Railway. This does the job in both.
    """
    if not value:
        return ""
    try:
        return f"{value.day} {_MONTHS[value.month - 1]}"
    except (AttributeError, IndexError):
        return str(value)


templates.env.filters["markdown"] = render_markdown
templates.env.filters["humandate"] = humandate

# Available in every template, including the standalone htmx partials, so
# deadline countdowns don't depend on each route remembering to pass it.
# Bound as the function, not a value: the server is long-running, so a date
# evaluated at import would freeze at deploy time. Templates call today().
templates.env.globals["today"] = date.today
