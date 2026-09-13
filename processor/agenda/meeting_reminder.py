"""
Meeting Reminder System
Sends email reminders for meetings at various stages.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from config.logging_config import get_logger
from config.settings import get_settings
from services.notion_service import NotionService
from services.email_service import EmailService
from models.notion_schemas import NotionMeeting, NotionQueryFilter, NotionQuerySort

logger = get_logger(__name__)


class MeetingReminder:
    """Manages meeting email reminders and nags."""

    def __init__(self):
        """Initialize the meeting reminder system."""
        self.notion = NotionService()
        self.email = EmailService()

    # When the day's reminders go out. The loop runs every
    # MEETING_CHECK_INTERVAL seconds, and a daily reminder is sent only by the
    # one pass that lands in the window opening at this hour — so it goes out
    # once a day, not once an hour. Stateless on purpose: nothing to record in
    # Notion, and nothing forgotten on a redeploy. 8am UTC is 9am in a British
    # summer, 8am in winter.
    DAILY_SEND_HOUR_UTC = 8

    def _in_daily_window(self, now: datetime) -> bool:
        """Whether this pass is the one that sends today's reminders.

        The window is exactly as wide as the loop's interval. Each pass takes a
        moment before the loop sleeps again, so passes are fractionally further
        apart than the window is wide: two can never both land in it. The price
        is that very occasionally a gap straddles the window and that day's
        reminder is skipped — the right way round for a nag.
        """
        start = now.replace(
            hour=self.DAILY_SEND_HOUR_UTC, minute=0, second=0, microsecond=0
        )
        interval = timedelta(seconds=get_settings().meeting_check_interval)
        return start <= now < start + interval

    async def check_and_send_reminders(self):
        """
        Check for meetings needing reminders and send them.

        Types of reminders:
        - Agenda approval reminders (daily if not approved in week before meeting)
        - Meeting tomorrow reminder (day before)
        - Minutes reminder (day after meeting)
        """
        logger.debug("Checking for meeting reminders...")

        try:
            # Check for meetings needing agenda approval reminders
            await self._send_agenda_approval_reminders()

            # Check for meetings tomorrow
            await self._send_tomorrow_reminders()

            # Check for meetings needing minutes
            await self._send_minutes_reminders()

        except Exception as e:
            logger.error(f"Error checking meeting reminders: {e}", exc_info=True)

    async def _send_agenda_approval_reminders(self):
        """
        Remind, once a day, that a meeting in the next week has an agenda
        generated but not yet approved.

        This used to promise "haven't sent a reminder today" and check nothing,
        so on an hourly loop it sent every hour. That could not show until 30
        August 2026, when the email service stopped crashing on construction;
        the first meeting after that would have had about two days of hourly
        nags.
        """
        try:
            now = datetime.now(timezone.utc)
            if not self._in_daily_window(now):
                return
            week_from_now = now + timedelta(days=7)
            tomorrow = now + timedelta(days=1)

            # Find meetings in next 7 days with generated (but not approved) agendas
            filters = [
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="on_or_after",
                    value=tomorrow.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="before",
                    value=week_from_now.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Agenda Generation Status",
                    property_type="select",
                    condition="equals",
                    value="generated"
                )
            ]

            meetings = self.notion.query_meetings(filters=filters, limit=10)

            for meeting in meetings:
                # Handle timezone-aware/naive datetime comparison
                meeting_date = meeting.meeting_date
                if meeting_date.tzinfo is None:
                    meeting_date = meeting_date.replace(tzinfo=timezone.utc)

                days_until = (meeting_date - now).days

                # Send reminder
                success = self.email.send_agenda_approval_reminder(
                    meeting_title=meeting.meeting_title,
                    meeting_date=meeting.meeting_date,
                    meeting_url=meeting.url,
                    days_until_meeting=days_until
                )

                if success:
                    logger.info(
                        f"Sent agenda approval reminder for {meeting.meeting_title} "
                        f"({days_until} days away)"
                    )

        except Exception as e:
            logger.error(f"Error sending agenda approval reminders: {e}", exc_info=True)

    async def _send_tomorrow_reminders(self):
        """
        Send reminder for meetings happening tomorrow.

        Sends once when meeting is ~24 hours away.
        """
        try:
            now = datetime.now(timezone.utc)
            tomorrow_start = now + timedelta(days=1)
            tomorrow_end = now + timedelta(days=1, hours=1)  # 1-hour window

            # Find meetings tomorrow
            filters = [
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="on_or_after",
                    value=tomorrow_start.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="before",
                    value=tomorrow_end.isoformat()
                )
            ]

            meetings = self.notion.query_meetings(filters=filters, limit=10)

            for meeting in meetings:
                # Send tomorrow reminder
                success = self.email.send_meeting_tomorrow_reminder(
                    meeting_title=meeting.meeting_title,
                    meeting_date=meeting.meeting_date,
                    meeting_format=meeting.meeting_format,
                    location=meeting.location,
                    zoom_link=meeting.zoom_link,
                    meeting_url=meeting.url
                )

                if success:
                    logger.info(f"Sent tomorrow reminder for {meeting.meeting_title}")

        except Exception as e:
            logger.error(f"Error sending tomorrow reminders: {e}", exc_info=True)

    async def _send_minutes_reminders(self):
        """
        Remind, the morning after a meeting, to add its minutes.

        Once, in the daily window, for meetings dated yesterday that have no
        notes. It used to look back over a 24-hour window on every hourly pass
        — up to twenty-four reminders — and because a meeting's date usually
        carries no time, and so reads as midnight, the first one arrived at
        noon on the day of the meeting, asking for minutes of a meeting that
        had not happened yet.
        """
        try:
            now = datetime.now(timezone.utc)
            if not self._in_daily_window(now):
                return

            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)

            filters = [
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="on_or_after",
                    value=yesterday.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="before",
                    value=today.isoformat()
                )
            ]

            meetings = self.notion.query_meetings(filters=filters, limit=10)

            for meeting in meetings:
                # Only send if no notes added yet
                if not meeting.meeting_notes:
                    success = self.email.send_meeting_minutes_reminder(
                        meeting_title=meeting.meeting_title,
                        meeting_date=meeting.meeting_date,
                        meeting_url=meeting.url
                    )

                    if success:
                        logger.info(f"Sent minutes reminder for {meeting.meeting_title}")

        except Exception as e:
            logger.error(f"Error sending minutes reminders: {e}", exc_info=True)

    async def send_agenda_generated_notification(self, meeting: NotionMeeting, agenda: str):
        """
        Send notification when agenda is first generated.

        Called by the meeting detector after generating agenda.
        """
        try:
            success = self.email.send_agenda_generated_alert(
                meeting_title=meeting.meeting_title,
                meeting_date=meeting.meeting_date,
                meeting_url=meeting.url,
                agenda_preview=agenda
            )

            if success:
                logger.info(f"Sent agenda generated notification for {meeting.meeting_title}")

            return success

        except Exception as e:
            logger.error(f"Error sending agenda generated notification: {e}", exc_info=True)
            return False
