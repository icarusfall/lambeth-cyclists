"""Newsletter sending via Resend (same service the email processor uses)."""

import logging
import re
from html.parser import HTMLParser

from app.config import get_settings
from app.web import render_markdown
from core.mail import send as core_send

logger = logging.getLogger(__name__)


def markdown_to_email_html(markdown_body: str) -> str:
    """Render newsletter markdown into a simple, phone-friendly HTML email."""
    body_html = render_markdown(markdown_body)
    return f"""\
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f4f6f4;">
  <div style="max-width:600px;margin:0 auto;padding:16px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#222;font-size:16px;line-height:1.55;">
    <div style="background:#1a7a3c;color:#fff;padding:14px 18px;border-radius:8px 8px 0 0;">
      <strong style="font-size:18px;">Lambeth Cyclists</strong>
    </div>
    <div style="background:#ffffff;padding:18px;border-radius:0 0 8px 8px;">
      {body_html}
    </div>
    <p style="color:#777;font-size:13px;padding:12px 4px;">
      Lambeth Cyclists is the Lambeth branch of the London Cycling Campaign.
    </p>
  </div>
</body>
</html>
"""


class _PlainText(HTMLParser):
    """Rendered newsletter HTML -> text that reads properly wherever it lands.

    Markdown is not plain text. Pasted into a box that doesn't render it,
    `## Get involved`, `**Wednesday**` and `[the map](https://...)` arrive
    exactly like that. So this works from the HTML the newsletter really
    renders to, and keeps what the marks meant: headings and paragraphs as
    blank-line breaks, line breaks as line breaks, list items as dashes or
    numbers, links as the words followed by the address.
    """

    _BLOCKS = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "pre", "blockquote", "table", "tr", "ul", "ol", "hr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.lists: list[list] = []  # ["ul"] or ["ol", next number]
        self.links: list[tuple[str | None, int]] = []
        self.in_pre = 0
        # Inside a list item, blocks add no blank lines. Markdown wraps an
        # item's text in <p> whenever the list has a nested list or a blank
        # line in it, and giving that <p> the usual gaps split every such
        # item into a lone dash with its words two lines below.
        self.in_item = 0

    def _gap(self):
        if not self.in_item:
            self.parts.append("\n\n")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self._BLOCKS:
            self._gap()
        if tag == "hr":
            self.parts.append("----")
            self._gap()
        elif tag == "pre":
            self.in_pre += 1
        elif tag in ("ul", "ol"):
            self.lists.append([tag, 1])
        elif tag == "li":
            kind = self.lists[-1] if self.lists else ["ul", 1]
            indent = "  " * max(len(self.lists) - 1, 0)
            if kind[0] == "ol":
                self.parts.append(f"\n{indent}{kind[1]}. ")
                kind[1] += 1
            else:
                self.parts.append(f"\n{indent}- ")
            self.in_item += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "a":
            self.links.append((attrs.get("href"), len(self.parts)))
        elif tag == "img" and attrs.get("alt"):
            self.parts.append(attrs["alt"])

    def handle_endtag(self, tag):
        if tag == "a" and self.links:
            href, start = self.links.pop()
            words = "".join(self.parts[start:]).strip()
            # A bare address is already its own text; don't print it twice.
            if href and not href.startswith("#") and href not in words:
                self.parts.append(f" ({href})")
        elif tag == "pre":
            self.in_pre -= 1
        elif tag == "li" and self.in_item:
            self.in_item -= 1
        elif tag in ("ul", "ol") and self.lists:
            self.lists.pop()
        if tag in self._BLOCKS:
            self._gap()

    def handle_data(self, data):
        if not self.in_pre:
            data = re.sub(r"\s+", " ", data)
        self.parts.append(data)

    def text(self) -> str:
        out = "".join(self.parts)
        out = re.sub(r"[ \t]+\n", "\n", out)
        # Stray spaces at the start of a line, but not a nested list's indent.
        out = re.sub(r"\n[ \t]+(?=[^ \t])(?!(?:-|\d+\.) )", "\n", out)
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip() + "\n"


def markdown_to_plain_text(markdown_body: str) -> str:
    """The newsletter as plain text, with none of the markdown marks."""
    parser = _PlainText()
    parser.feed(render_markdown(markdown_body))
    parser.close()
    return parser.text()


def copy_paste_versions(markdown_body: str) -> dict:
    """The newsletter in both forms, for pasting into the LCC messaging system.

    One place, used by the send page and the archive, so what somebody copies
    from the archive a week later is exactly what the send page would have
    given them on the day.
    """
    return {
        "text": markdown_to_plain_text(markdown_body),
        "html": markdown_to_email_html(markdown_body),
    }


def send_plain(to_email: str, subject: str, body_text: str) -> str:
    """Small utility email (password resets etc.). Returns the Resend id."""
    settings = get_settings()
    return core_send(
        api_key=settings.resend_api_key,
        from_email=settings.newsletter_from,
        to=to_email,
        subject=subject,
        text=body_text,
    )


def send_newsletter(subject: str, markdown_body: str, to_email: str) -> str:
    """Send the newsletter. Returns the Resend email id. Raises on failure."""
    settings = get_settings()
    return core_send(
        api_key=settings.resend_api_key,
        from_email=settings.newsletter_from,
        to=to_email,
        subject=subject,
        text=markdown_body,
        html=markdown_to_email_html(markdown_body),
        # newsletter@lambethcyclists.com has no mailbox behind it
        reply_to=settings.newsletter_reply_to or None,
    )
