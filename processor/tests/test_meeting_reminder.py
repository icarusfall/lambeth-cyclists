"""
Unit tests for meeting reminders.

These had none, and two of the three reminders repeated on every pass of the
hourly loop: the agenda-approval nag promised "haven't sent a reminder today"
and checked nothing, and the minutes reminder watched a 24-hour window — which,
because a meeting's date carries no time and reads as midnight, opened at noon
on the day of the meeting. Neither could show until 30 August 2026, when the
email service stopped crashing on construction.

So the tests below do not check a window in isolation. They run a day of the
real loop — one pass an hour, each a few seconds later than the last, the way
`await asyncio.sleep(interval)` after some work actually behaves — against a
fake Notion that applies the date filters it is given, and count the emails.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

import agenda.meeting_reminder as reminder_module
from agenda.meeting_reminder import MeetingReminder

INTERVAL = 3600
DRIFT = timedelta(seconds=5)  # how much later each pass lands than the last


class FakeNotion:
    """Holds meetings and honours the Meeting Date filters, ignoring the rest."""

    def __init__(self, meetings):
        self.meetings = meetings

    def query_meetings(self, filters, limit=10):
        def keep(meeting):
            for f in filters:
                if f.property_name != "Meeting Date":
                    continue
                bound = datetime.fromisoformat(f.value)
                if f.condition == "on_or_after" and not meeting.meeting_date >= bound:
                    return False
                if f.condition == "before" and not meeting.meeting_date < bound:
                    return False
            return True

        return [m for m in self.meetings if keep(m)][:limit]


def _meeting(date, notes=None):
    m = Mock()
    m.meeting_title = "Committee meeting"
    m.meeting_date = date
    m.meeting_notes = notes
    m.url = "https://notion.so/meeting"
    return m


@pytest.fixture
def make_reminder():
    settings = Mock(meeting_check_interval=INTERVAL)
    with patch.object(reminder_module, "NotionService"), \
         patch.object(reminder_module, "EmailService"), \
         patch.object(reminder_module, "get_settings", return_value=settings):

        def build(meetings):
            r = MeetingReminder()
            r.notion = FakeNotion(meetings)
            r.email = Mock()
            return r

        yield build


def _run_passes(method, first_pass, hours):
    """Call an async reminder method once per simulated hourly pass."""
    now = first_pass
    passes = []
    for _ in range(hours):
        frozen = now

        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen

        with patch.object(reminder_module, "datetime", Frozen):
            asyncio.run(method())
        passes.append(now)
        now = now + timedelta(seconds=INTERVAL) + DRIFT
    return passes


MEETING = datetime(2026, 9, 23, tzinfo=timezone.utc)  # a date with no time


def test_the_daily_window_is_one_interval_wide(make_reminder):
    r = make_reminder([])
    at = lambda h, m=0, s=0: datetime(2026, 9, 20, h, m, s, tzinfo=timezone.utc)
    assert r._in_daily_window(at(8, 0, 0))
    assert r._in_daily_window(at(8, 59, 59))
    assert not r._in_daily_window(at(9, 0, 0))
    assert not r._in_daily_window(at(7, 59, 59))


def test_approval_reminders_go_once_a_day_not_once_an_hour(make_reminder):
    r = make_reminder([_meeting(MEETING)])
    # Two days of passes, starting at an awkward minute past the hour.
    start = datetime(2026, 9, 17, 0, 17, tzinfo=timezone.utc)
    _run_passes(r._send_agenda_approval_reminders, start, hours=48)
    assert r.email.send_agenda_approval_reminder.call_count == 2


def test_minutes_reminder_goes_once_the_morning_after(make_reminder):
    r = make_reminder([_meeting(MEETING)])
    sent_at = []
    r.email.send_meeting_minutes_reminder.side_effect = (
        lambda **kw: sent_at.append(reminder_module.datetime.now(timezone.utc)) or True
    )
    # From the start of the meeting day to two days later.
    start = datetime(2026, 9, 23, 0, 17, tzinfo=timezone.utc)
    _run_passes(r._send_minutes_reminders, start, hours=48)

    assert len(sent_at) == 1
    assert sent_at[0].date() == datetime(2026, 9, 24).date()
    assert sent_at[0].hour == MeetingReminder.DAILY_SEND_HOUR_UTC


def test_no_minutes_reminder_on_the_day_of_the_meeting(make_reminder):
    """The old window opened at noon on the day, before a 7.15pm meeting."""
    r = make_reminder([_meeting(MEETING)])
    start = datetime(2026, 9, 23, 0, 17, tzinfo=timezone.utc)
    _run_passes(r._send_minutes_reminders, start, hours=23)
    r.email.send_meeting_minutes_reminder.assert_not_called()


def test_no_minutes_reminder_once_notes_are_in(make_reminder):
    r = make_reminder([_meeting(MEETING, notes="Agreed to respond to the A23 consultation.")])
    start = datetime(2026, 9, 23, 0, 17, tzinfo=timezone.utc)
    _run_passes(r._send_minutes_reminders, start, hours=48)
    r.email.send_meeting_minutes_reminder.assert_not_called()
