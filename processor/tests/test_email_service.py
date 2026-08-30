"""
Unit tests for the processor's email service.

This had no tests, which is how it shipped broken: when sending moved to
core.mail, `import resend` went with it but a leftover
`resend.api_key = self.api_key` did not, so constructing EmailService raised
NameError — but only when RESEND_API_KEY was set, i.e. never in a test and
always in production. The first test here is that case.

The processor turns send failures into False (the daemon must not die because
an alert bounced), where the portal lets them raise. That difference is
deliberate; see core/tests/test_mail.py.
"""

import pytest
from unittest.mock import Mock, patch

from services.email_service import EmailService


def _settings(**overrides):
    s = Mock()
    s.resend_api_key = "re_test_key"
    s.from_email = "Lambeth Cyclists <alerts@lambethcyclists.com>"
    s.alert_email = "charlie@example.com"
    s.admin_email = "charlie@example.com"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


@pytest.fixture
def service():
    with patch("services.email_service.get_settings", return_value=_settings()):
        yield EmailService()


def test_it_constructs_when_a_key_is_configured():
    """The production case: a key is set. Regression test for the NameError."""
    with patch("services.email_service.get_settings", return_value=_settings()):
        assert EmailService().api_key == "re_test_key"


def test_it_constructs_without_a_key():
    with patch(
        "services.email_service.get_settings",
        return_value=_settings(resend_api_key=None),
    ):
        assert EmailService().api_key is None


def test_a_comma_separated_alert_list_becomes_a_list():
    with patch(
        "services.email_service.get_settings",
        return_value=_settings(alert_email="a@x.com, b@y.com"),
    ):
        assert EmailService().alert_email == ["a@x.com", "b@y.com"]


def test_a_single_alert_address_stays_a_string():
    with patch(
        "services.email_service.get_settings",
        return_value=_settings(alert_email="a@x.com"),
    ):
        assert EmailService().alert_email == "a@x.com"


def test_sending_passes_the_key_through_to_core_mail(service):
    with patch("services.email_service.core_send", return_value="msg_1") as send:
        assert service.send_email("to@x.com", "subject", "body") is True
    assert send.call_args.kwargs["api_key"] == "re_test_key"


def test_a_failed_send_becomes_false_rather_than_raising(service):
    """The daemon must survive a bounced alert."""
    with patch("services.email_service.core_send", side_effect=RuntimeError("down")):
        assert service.send_email("to@x.com", "subject", "body") is False
