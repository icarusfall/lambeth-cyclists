"""
Meeting Agenda Generator
Generates formatted meeting agendas using Claude AI based on Items and Projects.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from config.logging_config import get_logger
from core.claude import response_text_of
from services.claude_service import ClaudeService
from services.notion_service import NotionService
from models.notion_schemas import NotionMeeting, NotionItem, NotionProject, NotionQueryFilter, NotionQuerySort

logger = get_logger(__name__)


# Introduction template (stored in code as requested)
MEETING_INTRODUCTION = """INTRODUCTION

Hello and welcome to the meeting for Lambeth Cyclists - we are the Lambeth branch of the charity London Cycling Campaign. Whether you are a member of LCC or not, you are more than welcome to join and give your thoughts. We are interested in basically anyone who wants to make conditions in Lambeth better for cyclists of all ages.

We try to be studiously apolitical, but part of our role is often as a consultee on TfL or Lambeth Council road or infrastructure plans. We also organise social rides when we can, and we support the central London Cycling Campaign as we can.
"""


class AgendaGenerator:
    """Generates meeting agendas with Claude AI."""

    def __init__(self):
        """Initialize the agenda generator."""
        self.notion = NotionService()
        self.claude = ClaudeService()

    def generate_agenda(self, meeting: NotionMeeting) -> Tuple[str, List[str], List[str]]:
        """
        Generate a formatted agenda for a meeting.

        Args:
            meeting: The meeting to generate an agenda for

        Returns:
            Tuple of (agenda_text, item_ids, project_ids)
        """
        logger.info(f"Generating agenda for meeting: {meeting.meeting_title}")

        try:
            # Gather relevant items and projects
            recent_items = self._get_recent_items(limit=5)
            deadline_items = self._get_items_with_approaching_deadlines(days=30)
            ongoing_projects = self._get_active_projects()

            logger.info(
                f"Found {len(recent_items)} recent items, {len(deadline_items)} deadline items, "
                f"{len(ongoing_projects)} ongoing projects"
            )

            # Generate the formatted agenda
            agenda_text = self._format_agenda(
                meeting=meeting,
                recent_items=recent_items,
                deadline_items=deadline_items,
                ongoing_projects=ongoing_projects
            )

            # Get discussion prompts from Claude
            discussion_prompts = self._generate_discussion_prompts(
                recent_items=recent_items,
                deadline_items=deadline_items,
                ongoing_projects=ongoing_projects
            )

            # Add discussion prompts to agenda
            final_agenda = agenda_text + "\n\n" + discussion_prompts

            # Collect IDs for relations
            item_ids = list(set([item.notion_id for item in recent_items + deadline_items]))
            project_ids = [project.notion_id for project in ongoing_projects]

            logger.info(f"Generated agenda: {len(final_agenda)} characters")

            return final_agenda, item_ids, project_ids

        except Exception as e:
            logger.error(f"Error generating agenda: {e}", exc_info=True)
            raise

    def _get_previous_meeting(self, current_meeting_date: datetime) -> NotionMeeting | None:
        """Get the most recent meeting before the current one."""
        try:
            filters = [
                NotionQueryFilter(
                    property_name="Meeting Date",
                    property_type="date",
                    condition="before",
                    value=current_meeting_date.isoformat()
                )
            ]
            sorts = [NotionQuerySort(property_name="Meeting Date", direction="descending")]

            meetings = self.notion.query_meetings(filters=filters, sorts=sorts, limit=1)

            if meetings:
                logger.debug(f"Found previous meeting: {meetings[0].meeting_title}")
                return meetings[0]
            else:
                logger.debug("No previous meetings found")
                return None

        except Exception as e:
            logger.warning(f"Error finding previous meeting: {e}")
            return None

    def _get_new_items(self, previous_meeting: NotionMeeting | None) -> List[NotionItem]:
        """Get items created since the last meeting."""
        if not previous_meeting:
            # No previous meeting - get items from last 60 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=60)
        else:
            cutoff_date = previous_meeting.meeting_date

        try:
            filters = [
                NotionQueryFilter(
                    property_name="Date Received",
                    property_type="date",
                    condition="on_or_after",
                    value=cutoff_date.isoformat()
                )
            ]
            sorts = [NotionQuerySort(property_name="Date Received", direction="descending")]

            items = self.notion.query_items(filters=filters, sorts=sorts, limit=50)
            logger.debug(f"Found {len(items)} items since last meeting")
            return items

        except Exception as e:
            logger.error(f"Error querying new items: {e}", exc_info=True)
            return []

    def _get_items_with_approaching_deadlines(self, days: int = 30) -> List[NotionItem]:
        """Get items with deadlines in the next N days."""
        try:
            deadline_date = datetime.now(timezone.utc) + timedelta(days=days)

            filters = [
                NotionQueryFilter(
                    property_name="Consultation Deadline",
                    property_type="date",
                    condition="on_or_before",
                    value=deadline_date.isoformat()
                ),
                NotionQueryFilter(
                    property_name="Consultation Deadline",
                    property_type="date",
                    condition="on_or_after",
                    value=datetime.now(timezone.utc).isoformat()
                )
            ]
            sorts = [NotionQuerySort(property_name="Consultation Deadline", direction="ascending")]

            items = self.notion.query_items(filters=filters, sorts=sorts, limit=20)
            logger.debug(f"Found {len(items)} items with approaching deadlines")
            return items

        except Exception as e:
            logger.error(f"Error querying deadline items: {e}", exc_info=True)
            return []

    def _get_recent_items(self, limit: int = 5) -> List[NotionItem]:
        """Get the most recent items by date received (for agenda prompting)."""
        try:
            sorts = [NotionQuerySort(property_name="Date Received", direction="descending")]

            items = self.notion.query_items(filters=None, sorts=sorts, limit=limit)
            logger.debug(f"Found {len(items)} recent items")
            return items

        except Exception as e:
            logger.error(f"Error querying recent items: {e}", exc_info=True)
            return []

    def _get_active_projects(self) -> List[NotionProject]:
        """Get all ongoing projects (not completed)."""
        try:
            filters = [
                NotionQueryFilter(
                    property_name="Status",
                    property_type="select",
                    condition="does_not_equal",
                    value="completed"
                )
            ]
            sorts = [NotionQuerySort(property_name="Priority", direction="descending")]

            projects = self.notion.query_projects(filters=filters, sorts=sorts, limit=20)
            logger.debug(f"Found {len(projects)} ongoing projects")
            return projects

        except Exception as e:
            logger.error(f"Error querying ongoing projects: {e}", exc_info=True)
            return []

    def _format_agenda(
        self,
        meeting: NotionMeeting,
        recent_items: List[NotionItem],
        deadline_items: List[NotionItem],
        ongoing_projects: List[NotionProject]
    ) -> str:
        """Format the agenda as markdown."""
        lines = []

        # Header
        lines.append(f"# {meeting.meeting_title}")
        lines.append(f"**Date:** {meeting.meeting_date.strftime('%A, %d %B %Y at %H:%M')}")

        if meeting.meeting_format:
            lines.append(f"**Format:** {meeting.meeting_format}")
        if meeting.location:
            lines.append(f"**Location:** {meeting.location}")
        if meeting.zoom_link:
            lines.append(f"**Zoom Link:** {meeting.zoom_link}")

        lines.append("\n---\n")

        # Introduction
        lines.append(MEETING_INTRODUCTION)
        lines.append("\n---\n")

        # Current Campaigns & Projects (MAIN FOCUS)
        lines.append("## CURRENT CAMPAIGNS & PROJECTS\n")
        lines.append("_This is our main focus - what we're actively working on:_\n")

        if ongoing_projects:
            for project in ongoing_projects:
                lines.append(f"### {project.project_name}\n")
                if project.description:
                    lines.append(f"{project.description}\n")
                if project.status:
                    lines.append(f"**Status:** {project.status}\n")
                if project.next_action:
                    lines.append(f"**Next Action:** {project.next_action}\n")
                lines.append("")
        else:
            lines.append("_No ongoing projects - consider what we should be focusing on!_\n")

        lines.append("\n---\n")

        # Recent Items (for prompting discussion)
        lines.append("## RECENT ITEMS FOR DISCUSSION\n")
        lines.append("_Latest items received - review and delete items not needing discussion:_\n")

        if recent_items:
            for item in recent_items:
                deadline_str = ""
                if item.consultation_deadline:
                    deadline_str = f" • Deadline: {item.consultation_deadline.strftime('%d %b %Y')}"

                location_str = ""
                if item.locations:
                    location_str = f" • {', '.join(item.locations[:2])}"

                received_str = ""
                if item.date_received:
                    received_str = f" • Received: {item.date_received.strftime('%d %b')}"

                lines.append(f"- **{item.title}**{location_str}{deadline_str}{received_str}")
                if item.summary:
                    lines.append(f"  {item.summary[:200]}")
                lines.append("")
        else:
            lines.append("_No recent items_\n")

        # Approaching Deadlines (if any)
        if deadline_items:
            lines.append("\n### ⚠️ Approaching Deadlines (Next 30 Days):\n")
            for item in deadline_items:
                deadline_str = item.consultation_deadline.strftime('%d %b %Y') if item.consultation_deadline else "TBD"
                lines.append(f"- **{item.title}** - Deadline: {deadline_str}")
                lines.append("")

        lines.append("\n---\n")

        # Any Other Business
        lines.append("## ANY OTHER BUSINESS\n")
        lines.append("_To be added during the meeting_\n")

        return "\n".join(lines)

    def _generate_discussion_prompts(
        self,
        recent_items: List[NotionItem],
        deadline_items: List[NotionItem],
        ongoing_projects: List[NotionProject]
    ) -> str:
        """Use Claude to generate discussion prompts and questions."""
        try:
            # Build context for Claude (emphasize projects as main focus)
            context_parts = []

            if ongoing_projects:
                context_parts.append("CURRENT CAMPAIGNS & PROJECTS (MAIN FOCUS):")
                for project in ongoing_projects:
                    context_parts.append(f"- {project.project_name}")
                    if project.description:
                        context_parts.append(f"  {project.description[:200]}")
                    if project.next_action:
                        context_parts.append(f"  Next action: {project.next_action[:150]}")

            if deadline_items:
                context_parts.append("\nUPCOMING DEADLINES:")
                for item in deadline_items[:3]:
                    deadline_str = item.consultation_deadline.strftime('%d %b %Y') if item.consultation_deadline else "TBD"
                    context_parts.append(f"- {item.title} (Deadline: {deadline_str})")

            if recent_items:
                context_parts.append("\nRECENT ITEMS:")
                for item in recent_items[:3]:
                    context_parts.append(f"- {item.title}")
                    if item.summary:
                        context_parts.append(f"  {item.summary[:150]}")

            context = "\n".join(context_parts)

            prompt = f"""You are helping generate discussion prompts for a Lambeth Cyclists committee meeting.

The committee's MAIN FOCUS is the ongoing projects/campaigns. These are the strategic initiatives they're working on.

Based on the projects and items below, generate:
1. Discussion questions for each ongoing project (what's next? what decisions needed?)
2. Actions the committee could take on recent items (respond to consultations, etc.)
3. How recent items might relate to or inform ongoing projects

Keep it concise and action-oriented. Focus on what the committee can do to advocate for better cycling conditions in Lambeth.

{context}

Generate 3-5 discussion prompts in markdown format."""

            # Call Claude
            message = self.claude.client.messages.create(
                model=self.claude.model,
                max_tokens=4096,
                output_config={"effort": "medium"},
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response_text_of(message)

            return f"## DISCUSSION PROMPTS (AI-Generated)\n\n{response_text}"

        except Exception as e:
            logger.warning(f"Could not generate discussion prompts: {e}")
            return "## DISCUSSION PROMPTS\n\n_Discussion prompts will be added during the meeting_"
