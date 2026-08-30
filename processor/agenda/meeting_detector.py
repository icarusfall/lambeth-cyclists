"""
Meeting Detector
Detects meetings that need agendas generated and triggers the generation process.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from config.logging_config import get_logger
from services.notion_service import NotionService
from agenda.agenda_generator import AgendaGenerator
from agenda.meeting_reminder import MeetingReminder
from models.notion_schemas import NotionMeeting, NotionQueryFilter

logger = get_logger(__name__)


class MeetingDetector:
    """Detects and processes meetings needing agendas."""

    def __init__(self):
        """Initialize the meeting detector."""
        self.notion = NotionService()
        self.agenda_generator = AgendaGenerator()
        self.reminder = MeetingReminder()

    async def check_and_generate(self):
        """
        Check for meetings needing agendas and generate them.

        Looks for meetings:
        - 1-2 days in the future
        - With agenda_generation_status = "pending" or None
        - That were manually created
        """
        logger.debug("Checking for meetings needing agendas...")

        try:
            # Find meetings needing agendas
            meetings = self._find_meetings_needing_agendas()

            if not meetings:
                logger.debug("No meetings need agendas at this time")
                return

            logger.info(f"Found {len(meetings)} meeting(s) needing agendas")

            # Generate agendas for each meeting
            for meeting in meetings:
                try:
                    await self._process_meeting(meeting)
                except Exception as e:
                    logger.error(
                        f"Error processing meeting {meeting.meeting_title}: {e}",
                        exc_info=True
                    )
                    # Continue with other meetings

        except Exception as e:
            logger.error(f"Error in meeting detection: {e}", exc_info=True)

    def _find_meetings_needing_agendas(self) -> List[NotionMeeting]:
        """
        Find meetings that need agendas generated.

        Criteria:
        - Meeting date is within next 3 days
        - Agenda generation status is "pending" or empty
        - Meeting was manually created
        """
        try:
            now = datetime.now(timezone.utc)
            # Look for meetings from now until 3 days out
            # This catches meetings happening soon that need agendas
            window_start = now
            window_end = now + timedelta(days=3)

            # Query for meetings in the window
            filters = [
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="on_or_after",
                    value=window_start.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="before",
                    value=window_end.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Meeting Created Manually",
                    property_type="checkbox",
                    condition="equals",
                    value=True
                )
            ]

            meetings = self.notion.query_meetings(filters=filters, limit=10)

            # Filter to only those with pending status
            pending_meetings = [
                m for m in meetings
                if not m.agenda_generation_status or m.agenda_generation_status == "pending"
            ]

            logger.debug(
                f"Found {len(pending_meetings)} meetings in window "
                f"({window_start.strftime('%d %b')} - {window_end.strftime('%d %b')})"
            )

            return pending_meetings

        except Exception as e:
            logger.error(f"Error finding meetings: {e}", exc_info=True)
            return []

    async def _process_meeting(self, meeting: NotionMeeting):
        """Generate and save agenda for a meeting."""
        logger.info(f"Processing meeting: {meeting.meeting_title}")

        try:
            # Generate the agenda
            agenda_text, item_ids, project_ids = self.agenda_generator.generate_agenda(meeting)

            # Update the meeting in Notion
            self.notion.update_meeting_agenda(
                meeting_id=meeting.notion_id,
                agenda=agenda_text,
                items=item_ids,
                projects=project_ids
            )

            logger.info(
                f"Successfully generated agenda for: {meeting.meeting_title}",
                extra={
                    'meeting_id': meeting.notion_id,
                    'items_count': len(item_ids),
                    'projects_count': len(project_ids)
                }
            )

            # Send email notification that agenda was generated
            # Update meeting object with URL for notification
            meeting.url = f"https://notion.so/{meeting.notion_id.replace('-', '')}"
            await self.reminder.send_agenda_generated_notification(meeting, agenda_text)

        except Exception as e:
            logger.error(
                f"Failed to process meeting {meeting.meeting_title}: {e}",
                exc_info=True
            )
            raise
