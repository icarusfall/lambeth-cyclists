"""Tests for the shared mailer.

Mostly here to pin the contract: this function raises. The processor relies on
that to convert failures into False, and the portal relies on it to surface
them. A future change that made it return None on failure would silently break
the portal's error reporting.
"""

from unittest.mock import patch

import pytest

from core.mail import MailNotConfigured, send


def test_missing_key_is_its_own_error():
    """Distinct from a send that was attempted and failed."""
    with pytest.raises(MailNotConfigured):
        send(api_key="", from_email="a@b.com", to="c@d.com", subject="s", text="t")


def test_send_returns_the_resend_id():
    with patch("core.mail.resend.Emails.send", return_value={"id": "abc123"}) as m:
        got = send(api_key="re_x", from_email="a@b.com", to="c@d.com",
                   subject="s", text="t")
    assert got == "abc123"
    assert m.call_args[0][0]["to"] == ["c@d.com"], "a single address becomes a list"


def test_a_list_of_recipients_is_passed_through():
    with patch("core.mail.resend.Emails.send", return_value={"id": "x"}) as m:
        send(api_key="re_x", from_email="a@b.com", to=["c@d.com", "e@f.com"],
             subject="s", text="t")
    assert m.call_args[0][0]["to"] == ["c@d.com", "e@f.com"]


def test_optional_parts_are_omitted_rather_than_sent_empty():
    with patch("core.mail.resend.Emails.send", return_value={"id": "x"}) as m:
        send(api_key="re_x", from_email="a@b.com", to="c@d.com", subject="s", text="t")
    params = m.call_args[0][0]
    assert "html" not in params and "reply_to" not in params

    with patch("core.mail.resend.Emails.send", return_value={"id": "x"}) as m:
        send(api_key="re_x", from_email="a@b.com", to="c@d.com", subject="s",
             text="t", html="<p>t</p>", reply_to="reply@x.com")
    params = m.call_args[0][0]
    assert params["html"] == "<p>t</p>"
    assert params["reply_to"] == ["reply@x.com"], "reply_to is a list for Resend"


def test_failures_propagate():
    """Callers decide what to do; this does not decide for them."""
    with patch("core.mail.resend.Emails.send", side_effect=RuntimeError("down")):
        with pytest.raises(RuntimeError):
            send(api_key="re_x", from_email="a@b.com", to="c@d.com", subject="s", text="t")
