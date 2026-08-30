"""
Notion API service for managing Items, Projects, and Meetings databases.
Handles CRUD operations, queries, and relations between databases.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from notion_client import Client
from notion_client.errors import APIResponseError

from config.settings import get_settings
from config.logging_config import get_logger
from models.notion_schemas import (
    NotionItemCreate, NotionItem,
    NotionProjectCreate, NotionProject,
    NotionMeetingCreate, NotionMeeting,
    NotionQueryFilter, NotionQuerySort
)

logger = get_logger(__name__)


class NotionService:
    """
    Service for interacting with Notion API.
    Manages Items, Projects, and Meetings databases.
    """

    def __init__(self):
        """Initialize Notion service with API credentials."""
        self.settings = get_settings()
        self.client = Client(auth=self.settings.notion_api_key)

        # Database IDs
        self.items_db_id = self.settings.notion_items_db_id
        self.projects_db_id = self.settings.notion_projects_db_id
        self.meetings_db_id = self.settings.notion_meetings_db_id

        self._ds_cache: Dict[str, str] = {}

    def ds_id_for(self, db_id: str) -> str:
        """Resolve (and cache) a database's data source id.

        notion-client v3 addresses data sources rather than databases: queries
        go to data_sources.query() and new pages are parented to a data source.
        A database's id is stable, so the lookup is cached for the process.
        """
        if db_id not in self._ds_cache:
            db = self.client.databases.retrieve(database_id=db_id)
            self._ds_cache[db_id] = db["data_sources"][0]["id"]
        return self._ds_cache[db_id]

    def _data_source_parent(self, db_id: str) -> Dict[str, str]:
        """Parent block for creating a page in a database, v3 style."""
        return {"type": "data_source_id", "data_source_id": self.ds_id_for(db_id)}

    # === ITEM OPERATIONS ===

    def create_item(self, item_data: NotionItemCreate) -> NotionItem:
        """
        Create a new Item in Notion.

        Args:
            item_data: Item data to create

        Returns:
            Created NotionItem with Notion ID
        """
        try:
            properties = self._build_item_properties(item_data)

            response = self.client.pages.create(
                parent=self._data_source_parent(self.items_db_id),
                properties=properties
            )

            notion_item = self._parse_item_response(response)

            logger.info(
                f"Created Notion item: {item_data.title}",
                extra={'notion_item_id': notion_item.notion_id}
            )

            return notion_item

        except APIResponseError as e:
            logger.error(f"Notion API error creating item: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error creating Notion item: {e}", exc_info=True)
            raise

    def _build_item_properties(self, item_data: NotionItemCreate) -> Dict[str, Any]:
        """Build Notion properties object for Item."""
        properties = {
            "Title": {"title": [{"text": {"content": item_data.title}}]},
            "Summary": {"rich_text": [{"text": {"content": item_data.summary}}]},
            "Date Received": {"date": {"start": item_data.date_received.isoformat()}},
            "Has Attachments": {"checkbox": item_data.has_attachments},
            "Status": {"select": {"name": item_data.status}},
            "Priority": {"select": {"name": item_data.priority}},
            "Processing Status": {"select": {"name": item_data.processing_status}},
        }

        # Optional text fields
        if item_data.gmail_message_id:
            properties["Gmail Message ID"] = {"rich_text": [{"text": {"content": item_data.gmail_message_id}}]}
        if item_data.sender_email:
            properties["Sender Email"] = {"email": item_data.sender_email}
        if item_data.ai_key_points:
            properties["AI Key Points"] = {"rich_text": [{"text": {"content": item_data.ai_key_points[:2000]}}]}
        if item_data.lambeth_cyclist_thoughts:
            properties["Lambeth Cyclist Thoughts"] = {"rich_text": [{"text": {"content": item_data.lambeth_cyclist_thoughts[:2000]}}]}
        if item_data.attachment_urls:
            properties["Attachment URLs"] = {"rich_text": [{"text": {"content": item_data.attachment_urls[:2000]}}]}
        if item_data.attachment_analysis:
            properties["Attachment Analysis"] = {"rich_text": [{"text": {"content": item_data.attachment_analysis[:2000]}}]}
        if item_data.geocoded_coordinates:
            properties["Geocoded Coordinates"] = {"rich_text": [{"text": {"content": item_data.geocoded_coordinates[:2000]}}]}

        # Optional URL fields
        if item_data.link_to_consultation:
            properties["Link to Consultation"] = {"url": item_data.link_to_consultation}

        # Optional date fields
        if item_data.consultation_deadline:
            properties["Consultation Deadline"] = {"date": {"start": item_data.consultation_deadline.isoformat()}}
        if item_data.action_due_date:
            properties["Action Due Date"] = {"date": {"start": item_data.action_due_date.isoformat()}}
        if item_data.original_estimated_completion:
            properties["Original Estimated Completion"] = {"date": {"start": item_data.original_estimated_completion.isoformat()}}

        # Optional select fields
        if item_data.project_type:
            properties["Project Type"] = {"select": {"name": item_data.project_type}}
        if item_data.action_required:
            properties["Action Required"] = {"select": {"name": item_data.action_required}}

        # Multi-select fields
        if item_data.tags:
            properties["Tags"] = {"multi_select": [{"name": tag} for tag in item_data.tags]}
        if item_data.locations:
            properties["Locations"] = {"multi_select": [{"name": loc} for loc in item_data.locations]}

        # Relations
        if item_data.related_project:
            properties["Related Project"] = {"relation": [{"id": item_data.related_project}]}
        if item_data.related_past_items:
            properties["Related Past Items"] = {"relation": [{"id": item_id} for item_id in item_data.related_past_items]}
        if item_data.discussed_in_meetings:
            properties["Discussed in Meetings"] = {"relation": [{"id": meeting_id} for meeting_id in item_data.discussed_in_meetings]}

        return properties

    def _parse_item_response(self, response: Dict[str, Any]) -> NotionItem:
        """Parse Notion API response into NotionItem."""
        props = response["properties"]

        # Get values with defaults for required fields
        summary = self._get_rich_text(props.get("Summary")) or "No summary"
        date_received = self._get_date(props.get("Date Received")) or datetime.now(timezone.utc)

        return NotionItem(
            notion_id=response["id"],
            created_time=datetime.fromisoformat(response["created_time"].replace('Z', '+00:00')),
            last_edited_time=datetime.fromisoformat(response["last_edited_time"].replace('Z', '+00:00')),
            url=response["url"],
            title=self._get_title(props.get("Title")),
            summary=summary,
            date_received=date_received,
            gmail_message_id=self._get_rich_text(props.get("Gmail Message ID")),
            sender_email=self._get_email(props.get("Sender Email")),
            has_attachments=self._get_checkbox(props.get("Has Attachments")),
            consultation_deadline=self._get_date(props.get("Consultation Deadline")),
            action_due_date=self._get_date(props.get("Action Due Date")),
            original_estimated_completion=self._get_date(props.get("Original Estimated Completion")),
            project_type=self._get_select(props.get("Project Type")),
            action_required=self._get_select(props.get("Action Required")),
            tags=self._get_multi_select(props.get("Tags")),
            locations=self._get_multi_select(props.get("Locations")),
            geocoded_coordinates=self._get_rich_text(props.get("Geocoded Coordinates")),
            ai_key_points=self._get_rich_text(props.get("AI Key Points")),
            lambeth_cyclist_thoughts=self._get_rich_text(props.get("Lambeth Cyclist Thoughts")),
            related_past_items=self._get_relation(props.get("Related Past Items")),
            link_to_consultation=self._get_url(props.get("Link to Consultation")),
            attachment_urls=self._get_rich_text(props.get("Attachment URLs")),
            attachment_analysis=self._get_rich_text(props.get("Attachment Analysis")),
            related_project=self._get_relation_single(props.get("Related Project")),
            discussed_in_meetings=self._get_relation(props.get("Discussed in Meetings")),
            status=self._get_select(props.get("Status")) or "new",
            priority=self._get_select(props.get("Priority")) or "medium",
            processing_status=self._get_select(props.get("Processing Status")) or "ai_complete",
        )

    def query_items(
        self,
        filters: Optional[List[NotionQueryFilter]] = None,
        sorts: Optional[List[NotionQuerySort]] = None,
        limit: int = 100
    ) -> List[NotionItem]:
        """
        Query Items database with filters and sorting.

        Args:
            filters: List of filters to apply
            sorts: List of sort orders
            limit: Maximum number of results

        Returns:
            List of NotionItem objects
        """
        try:
            query_params = {"data_source_id": self.ds_id_for(self.items_db_id), "page_size": min(limit, 100)}

            if filters:
                query_params["filter"] = self._build_filter(filters)
            if sorts:
                query_params["sorts"] = [{"property": s.property_name, "direction": s.direction} for s in sorts]

            response = self.client.data_sources.query(**query_params)

            items = [self._parse_item_response(page) for page in response["results"]]

            logger.debug(f"Queried Items database: {len(items)} results")

            return items

        except APIResponseError as e:
            logger.error(f"Notion API error querying items: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error querying items: {e}", exc_info=True)
            raise

    def check_duplicate_by_message_id(self, message_id: str) -> Optional[NotionItem]:
        """
        Check if an item with the given Gmail message ID already exists.

        Args:
            message_id: Gmail message ID

        Returns:
            Existing NotionItem if found, None otherwise
        """
        filters = [NotionQueryFilter(
            property_name="Gmail Message ID",
            property_type="rich_text",
            condition="equals",
            value=message_id
        )]

        items = self.query_items(filters=filters, limit=1)

        return items[0] if items else None

    # === PROJECT OPERATIONS ===

    def create_project(self, project_data: NotionProjectCreate) -> NotionProject:
        """
        Create a new Project in Notion.

        Args:
            project_data: Project data to create

        Returns:
            Created NotionProject with Notion ID
        """
        try:
            properties = self._build_project_properties(project_data)

            response = self.client.pages.create(
                parent=self._data_source_parent(self.projects_db_id),
                properties=properties
            )

            notion_project = self._parse_project_response(response)

            logger.info(
                f"Created Notion project: {project_data.project_name}",
                extra={'notion_project_id': notion_project.notion_id}
            )

            return notion_project

        except APIResponseError as e:
            logger.error(f"Notion API error creating project: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error creating Notion project: {e}", exc_info=True)
            raise

    def _build_project_properties(self, project_data: NotionProjectCreate) -> Dict[str, Any]:
        """Build Notion properties object for Project."""
        properties = {
            "Project Name": {"title": [{"text": {"content": project_data.project_name}}]},
            "Description": {"rich_text": [{"text": {"content": project_data.description}}]},
            "Project Type": {"select": {"name": project_data.project_type}},
            "Status": {"select": {"name": project_data.status}},
            "Priority": {"select": {"name": project_data.priority}},
        }

        # Optional fields
        if project_data.start_date:
            properties["Start Date"] = {"date": {"start": project_data.start_date.isoformat()}}
        if project_data.target_completion:
            properties["Target Completion"] = {"date": {"start": project_data.target_completion.isoformat()}}
        if project_data.next_action:
            properties["Next Action"] = {"rich_text": [{"text": {"content": project_data.next_action[:2000]}}]}
        if project_data.key_milestones:
            properties["Key Milestones"] = {"rich_text": [{"text": {"content": project_data.key_milestones[:2000]}}]}
        if project_data.primary_locations:
            properties["Primary Locations"] = {"multi_select": [{"name": loc} for loc in project_data.primary_locations]}
        if project_data.geographic_scope:
            properties["Geographic Scope"] = {"select": {"name": project_data.geographic_scope}}
        if project_data.project_folder:
            properties["Project Folder"] = {"url": project_data.project_folder}
        if project_data.campaign_website:
            properties["Campaign Website"] = {"url": project_data.campaign_website}
        if project_data.related_documents:
            properties["Related Documents"] = {"rich_text": [{"text": {"content": project_data.related_documents[:2000]}}]}
        if project_data.success_metrics:
            properties["Success Metrics"] = {"rich_text": [{"text": {"content": project_data.success_metrics[:2000]}}]}
        if project_data.final_outcome:
            properties["Final Outcome"] = {"rich_text": [{"text": {"content": project_data.final_outcome[:2000]}}]}
        if project_data.lessons_learned:
            properties["Lessons Learned"] = {"rich_text": [{"text": {"content": project_data.lessons_learned[:2000]}}]}

        return properties

    def _parse_project_response(self, response: Dict[str, Any]) -> NotionProject:
        """Parse Notion API response into NotionProject."""
        props = response["properties"]

        return NotionProject(
            notion_id=response["id"],
            created_time=datetime.fromisoformat(response["created_time"].replace('Z', '+00:00')),
            last_edited_time=datetime.fromisoformat(response["last_edited_time"].replace('Z', '+00:00')),
            url=response["url"],
            project_name=self._get_title(props.get("Project Name")),
            description=self._get_rich_text(props.get("Description")) or "",
            project_type=self._get_select(props.get("Project Type")) or "infrastructure_campaign",
            status=self._get_select(props.get("Status")) or "active",
            priority=self._get_select(props.get("Priority")) or "medium",
            start_date=self._get_date(props.get("Start Date")),
            target_completion=self._get_date(props.get("Target Completion")),
            next_action=self._get_rich_text(props.get("Next Action")),
            key_milestones=self._get_rich_text(props.get("Key Milestones")),
            primary_locations=self._get_multi_select(props.get("Primary Locations")),
            geographic_scope=self._get_select(props.get("Geographic Scope")),
            project_folder=self._get_url(props.get("Project Folder")),
            campaign_website=self._get_url(props.get("Campaign Website")),
            related_documents=self._get_rich_text(props.get("Related Documents")),
            success_metrics=self._get_rich_text(props.get("Success Metrics")),
            final_outcome=self._get_rich_text(props.get("Final Outcome")),
            lessons_learned=self._get_rich_text(props.get("Lessons Learned")),
            related_items=self._get_relation(props.get("Related Items")),
        )

    def query_projects(
        self,
        filters: Optional[List[NotionQueryFilter]] = None,
        sorts: Optional[List[NotionQuerySort]] = None,
        limit: int = 100
    ) -> List[NotionProject]:
        """Query Projects database."""
        try:
            query_params = {"data_source_id": self.ds_id_for(self.projects_db_id), "page_size": min(limit, 100)}

            if filters:
                query_params["filter"] = self._build_filter(filters)
            if sorts:
                query_params["sorts"] = [{"property": s.property_name, "direction": s.direction} for s in sorts]

            response = self.client.data_sources.query(**query_params)

            projects = [self._parse_project_response(page) for page in response["results"]]

            logger.debug(f"Queried Projects database: {len(projects)} results")

            return projects

        except APIResponseError as e:
            logger.error(f"Notion API error querying projects: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error querying projects: {e}", exc_info=True)
            raise

    # === MEETING OPERATIONS ===

    def create_meeting(self, meeting_data: NotionMeetingCreate) -> NotionMeeting:
        """Create a new Meeting in Notion."""
        try:
            properties = self._build_meeting_properties(meeting_data)

            response = self.client.pages.create(
                parent=self._data_source_parent(self.meetings_db_id),
                properties=properties
            )

            notion_meeting = self._parse_meeting_response(response)

            logger.info(
                f"Created Notion meeting: {meeting_data.meeting_title}",
                extra={'notion_meeting_id': notion_meeting.notion_id}
            )

            return notion_meeting

        except APIResponseError as e:
            logger.error(f"Notion API error creating meeting: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error creating Notion meeting: {e}", exc_info=True)
            raise

    def _build_meeting_properties(self, meeting_data: NotionMeetingCreate) -> Dict[str, Any]:
        """Build Notion properties object for Meeting."""
        properties = {
            "Meeting Title": {"title": [{"text": {"content": meeting_data.meeting_title}}]},
            "Meeting Date": {"date": {"start": meeting_data.meeting_date.isoformat()}},
            "Meeting Type": {"select": {"name": meeting_data.meeting_type}},
            "Agenda Generation Status": {"select": {"name": meeting_data.agenda_generation_status}},
            "Meeting Created Manually": {"checkbox": meeting_data.meeting_created_manually},
        }

        # Optional fields
        if meeting_data.meeting_format:
            properties["Meeting Format"] = {"select": {"name": meeting_data.meeting_format}}
        if meeting_data.location:
            properties["Location"] = {"rich_text": [{"text": {"content": meeting_data.location}}]}
        if meeting_data.zoom_link:
            properties["Zoom Link"] = {"url": meeting_data.zoom_link}
        if meeting_data.auto_generated_agenda:
            properties["Auto-Generated Agenda"] = {"rich_text": [{"text": {"content": meeting_data.auto_generated_agenda[:2000]}}]}
        if meeting_data.manual_agenda_items:
            properties["Manual Agenda Items"] = {"rich_text": [{"text": {"content": meeting_data.manual_agenda_items[:2000]}}]}
        if meeting_data.agenda_generated_at:
            properties["Agenda Generated At"] = {"date": {"start": meeting_data.agenda_generated_at.isoformat()}}
        if meeting_data.meeting_notes:
            properties["Meeting Notes"] = {"rich_text": [{"text": {"content": meeting_data.meeting_notes[:2000]}}]}
        if meeting_data.decisions_made:
            properties["Decisions Made"] = {"rich_text": [{"text": {"content": meeting_data.decisions_made[:2000]}}]}
        if meeting_data.action_items:
            properties["Action Items"] = {"rich_text": [{"text": {"content": meeting_data.action_items[:2000]}}]}
        if meeting_data.next_meeting_date:
            properties["Next Meeting Date"] = {"date": {"start": meeting_data.next_meeting_date.isoformat()}}
        if meeting_data.agenda_trigger_date:
            properties["Agenda Trigger Date"] = {"date": {"start": meeting_data.agenda_trigger_date.isoformat()}}

        return properties

    def _parse_meeting_response(self, response: Dict[str, Any]) -> NotionMeeting:
        """Parse Notion API response into NotionMeeting."""
        props = response["properties"]

        return NotionMeeting(
            notion_id=response["id"],
            created_time=datetime.fromisoformat(response["created_time"].replace('Z', '+00:00')),
            last_edited_time=datetime.fromisoformat(response["last_edited_time"].replace('Z', '+00:00')),
            url=response["url"],
            meeting_title=self._get_title(props.get("Meeting Title")),
            meeting_date=self._get_date(props.get("Meeting Date")) or datetime.now(timezone.utc),
            meeting_type=self._get_select(props.get("Meeting Type")) or "regular_committee",
            meeting_format=self._get_select(props.get("Meeting Format")),
            location=self._get_rich_text(props.get("Location")),
            zoom_link=self._get_url(props.get("Zoom Link")),
            auto_generated_agenda=self._get_rich_text(props.get("Auto-Generated Agenda")),
            manual_agenda_items=self._get_rich_text(props.get("Manual Agenda Items")),
            agenda_generation_status=self._get_select(props.get("Agenda Generation Status")) or "pending",
            agenda_generated_at=self._get_date(props.get("Agenda Generated At")),
            meeting_notes=self._get_rich_text(props.get("Meeting Notes")),
            decisions_made=self._get_rich_text(props.get("Decisions Made")),
            action_items=self._get_rich_text(props.get("Action Items")),
            next_meeting_date=self._get_date(props.get("Next Meeting Date")),
            agenda_trigger_date=self._get_date(props.get("Agenda Trigger Date")),
            meeting_created_manually=self._get_checkbox(props.get("Meeting Created Manually")) or True,
            items_to_discuss=self._get_relation(props.get("Items to Discuss")),
            projects_to_review=self._get_relation(props.get("Projects to Review")),
            follow_ups_from_previous=self._get_relation_single(props.get("Follow-ups from Previous Meeting")),
        )

    def update_meeting_agenda(self, meeting_id: str, agenda: str, items: List[str], projects: List[str]) -> None:
        """
        Update a meeting with generated agenda.

        Args:
            meeting_id: Notion meeting page ID
            agenda: Generated agenda markdown
            items: List of item IDs to link
            projects: List of project IDs to link
        """
        try:
            properties = {
                "Auto-Generated Agenda": {"rich_text": [{"text": {"content": agenda[:2000]}}]},
                "Agenda Generation Status": {"select": {"name": "generated"}},
                "Agenda Generated At": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            }

            if items:
                properties["Items to Discuss"] = {"relation": [{"id": item_id} for item_id in items]}
            if projects:
                properties["Projects to Review"] = {"relation": [{"id": project_id} for project_id in projects]}

            self.client.pages.update(page_id=meeting_id, properties=properties)

            logger.info(
                f"Updated meeting agenda ({len(items)} items, {len(projects)} projects)",
                extra={'notion_meeting_id': meeting_id}
            )

        except APIResponseError as e:
            logger.error(f"Notion API error updating meeting: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error updating meeting: {e}", exc_info=True)
            raise

    def query_meetings(
        self,
        filters: Optional[List[NotionQueryFilter]] = None,
        sorts: Optional[List[NotionQuerySort]] = None,
        limit: int = 100
    ) -> List[NotionMeeting]:
        """Query Meetings database."""
        try:
            query_params = {"data_source_id": self.ds_id_for(self.meetings_db_id), "page_size": min(limit, 100)}

            if filters:
                query_params["filter"] = self._build_filter(filters)
            if sorts:
                query_params["sorts"] = [{"property": s.property_name, "direction": s.direction} for s in sorts]

            response = self.client.data_sources.query(**query_params)

            meetings = [self._parse_meeting_response(page) for page in response["results"]]

            logger.debug(f"Queried Meetings database: {len(meetings)} results")

            return meetings

        except APIResponseError as e:
            logger.error(f"Notion API error querying meetings: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error querying meetings: {e}", exc_info=True)
            raise

    # === HELPER METHODS ===

    def _build_filter(self, filters: List[NotionQueryFilter]) -> Dict[str, Any]:
        """Build Notion filter object from list of filters."""
        if len(filters) == 1:
            return self._build_single_filter(filters[0])
        else:
            return {
                "and": [self._build_single_filter(f) for f in filters]
            }

    def _build_single_filter(self, filter_obj: NotionQueryFilter) -> Dict[str, Any]:
        """Build a single Notion filter."""
        filter_dict = {
            "property": filter_obj.property_name,
            filter_obj.property_type: {filter_obj.condition: filter_obj.value}
        }
        return filter_dict

    def _get_title(self, prop: Optional[Dict]) -> str:
        """Extract title from Notion property."""
        if not prop or not prop.get("title"):
            return ""
        return prop["title"][0]["text"]["content"] if prop["title"] else ""

    def _get_rich_text(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract rich text from Notion property."""
        if not prop or not prop.get("rich_text"):
            return None
        return prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else None

    def _get_date(self, prop: Optional[Dict]) -> Optional[datetime]:
        """Extract date from Notion property."""
        if not prop or not prop.get("date") or not prop["date"].get("start"):
            return None
        return datetime.fromisoformat(prop["date"]["start"].replace('Z', '+00:00'))

    def _get_select(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract select value from Notion property."""
        if not prop or not prop.get("select"):
            return None
        return prop["select"]["name"] if prop["select"] else None

    def _get_multi_select(self, prop: Optional[Dict]) -> List[str]:
        """Extract multi-select values from Notion property."""
        if not prop or not prop.get("multi_select"):
            return []
        return [item["name"] for item in prop["multi_select"]]

    def _get_checkbox(self, prop: Optional[Dict]) -> bool:
        """Extract checkbox value from Notion property."""
        if not prop:
            return False
        return prop.get("checkbox", False)

    def _get_url(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract URL from Notion property."""
        if not prop:
            return None
        return prop.get("url")

    def _get_email(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract email from Notion property."""
        if not prop:
            return None
        return prop.get("email")

    def _get_relation(self, prop: Optional[Dict]) -> List[str]:
        """Extract relation IDs from Notion property."""
        if not prop or not prop.get("relation"):
            return []
        return [item["id"] for item in prop["relation"]]

    def _get_relation_single(self, prop: Optional[Dict]) -> Optional[str]:
        """Extract single relation ID from Notion property."""
        relations = self._get_relation(prop)
        return relations[0] if relations else None
