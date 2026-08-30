"""Sending mail through Resend, in one place.

Both services had their own wrapper around the same three lines. What they did
around those lines differs on purpose, and that difference is kept at the call
sites rather than resolved here:

- the processor sends alerts from a daemon nobody is watching, so a failed
  send is logged and swallowed — an unreachable mail server must not stop the
  email pipeline;
- the portal sends when someone has just pressed a button, so a failure has to
  reach them rather than disappear into a log.

This function therefore raises. Best-effort callers wrap it.
"""

import logging

import resend

logger = logging.getLogger(__name__)


class MailNotConfigured(RuntimeError):
    """No Resend API key. Distinct from a send that was tried and failed."""


def send(
    *,
    api_key: str,
    from_email: str,
    to: str | list[str],
    subject: str,
    text: str,
    html: str | None = None,
    reply_to: str | None = None,
) -> str:
    """Send one email. Returns the Resend id.

    Raises MailNotConfigured if there is no API key, and whatever Resend
    raises if the send itself fails.
    """
    if not api_key:
        raise MailNotConfigured("No Resend API key configured")

    recipients = [to] if isinstance(to, str) else list(to)
    params: dict = {
        "from": from_email,
        "to": recipients,
        "subject": subject,
        "text": text,
    }
    if html:
        params["html"] = html
    if reply_to:
        # Some from-addresses have no mailbox behind them; replies need a home.
        params["reply_to"] = [reply_to]

    resend.api_key = api_key
    response = resend.Emails.send(params)
    email_id = response.get("id", "unknown")
    logger.info("Sent %r to %s (resend id %s)", subject, ", ".join(recipients), email_id)
    return email_id
