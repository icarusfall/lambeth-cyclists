"""
Pydantic models for Notion database schemas.
Represents Items, Projects, and Meetings databases.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class NotionItemCreate(BaseModel):
    """Data required to create an Item in Notion."""

    # Required fields
    title: str
    summary: str
    date_received: datetime

    # Email metadata
    gmail_message_id: Optional[str] = None
    sender_email: Optional[str] = None
    has_attachments: bool = False

    # Deadlines
    consultation_deadline: Optional[datetime] = None
    action_due_date: Optional[datetime] = None
    original_estimated_completion: Optional[datetime] = None

    # Categorization
    project_type: Optional[str] = None  # traffic_order, consultation, infrastructure_project, event, other
    action_required: Optional[str] = None  # response_needed, information_only, monitoring, urgent_action
    tags: List[str] = Field(default_factory=list)

    # Locations
    locations: List[str] = Field(default_factory=list)
    geocoded_coordinates: Optional[str] = None  # JSON string

    # Content
    ai_key_points: Optional[str] = None
    lambeth_cyclist_thoughts: Optional[str] = None

    # Links
    link_to_consultation: Optional[str] = None
    attachment_urls: Optional[str] = None  # JSON string
    attachment_analysis: Optional[str] = None

    # Relations (Notion page IDs)
    related_past_items: List[str] = Field(default_factory=list)
    related_project: Optional[str] = None
    discussed_in_meetings: List[str] = Field(default_factory=list)

    # Workflow
    status: str = "new"  # new, reviewed, response_drafted, submitted, monitoring, closed
    priority: str = "medium"  # critical, high, medium, low
    processing_status: str = "ai_complete"  # pending_ai_analysis, ai_complete, needs_review, approved, migrated


class NotionProjectCreate(BaseModel):
    """Data required to create a Project in Notion."""

    # Required fields
    project_name: str
    description: str

    # Project metadata
    project_type: str = "infrastructure_campaign"  # infrastructure_campaign, ongoing_monitoring, partnership, research
    status: str = "active"  # planning, active, paused, completed, archived
    priority: str = "medium"  # strategic, high, medium, low

    # Dates
    start_date: Optional[datetime] = None
    target_completion: Optional[datetime] = None

    # Team
    lead_volunteer: Optional[str] = None  # Person property (email or ID)
    committee_members: List[str] = Field(default_factory=list)

    # Planning
    next_action: Optional[str] = None
    key_milestones: Optional[str] = None

    # Locations
    primary_locations: List[str] = Field(default_factory=list)
    geographic_scope: Optional[str] = None  # single_street, neighbourhood, borough_wide, cross_borough

    # Links
    project_folder: Optional[str] = None
    campaign_website: Optional[str] = None
    related_documents: Optional[str] = None  # JSON string

    # Outcomes
    success_metrics: Optional[str] = None
    final_outcome: Optional[str] = None
    lessons_learned: Optional[str] = None


class NotionMeetingCreate(BaseModel):
    """Data required to create a Meeting in Notion."""

    # Required fields
    meeting_title: str
    meeting_date: datetime

    # Meeting metadata
    meeting_type: str = "regular_committee"  # regular_committee, emergency, planning, special
    meeting_format: Optional[str] = None  # Hybrid, Online Only, In-person
    location: Optional[str] = None
    zoom_link: Optional[str] = None

    # Attendees (Person properties - emails or IDs)
    attendees: List[str] = Field(default_factory=list)

    # Agenda
    auto_generated_agenda: Optional[str] = None
    manual_agenda_items: Optional[str] = None
    agenda_generation_status: str = "pending"  # pending, generated, approved, published
    agenda_generated_at: Optional[datetime] = None

    # Meeting outputs
    meeting_notes: Optional[str] = None
    decisions_made: Optional[str] = None
    action_items: Optional[str] = None
    next_meeting_date: Optional[datetime] = None

    # Triggers
    agenda_trigger_date: Optional[datetime] = None
    meeting_created_manually: bool = True


class NotionItem(NotionItemCreate):
    """Complete Item from Notion, including Notion ID."""

    notion_id: str
    created_time: datetime
    last_edited_time: datetime
    url: str


class NotionProject(NotionProjectCreate):
    """Complete Project from Notion, including Notion ID."""

    notion_id: str
    created_time: datetime
    last_edited_time: datetime
    url: str
    related_items: List[str] = Field(default_factory=list)  # Item IDs


class NotionMeeting(NotionMeetingCreate):
    """Complete Meeting from Notion, including Notion ID."""

    notion_id: str
    created_time: datetime
    last_edited_time: datetime
    url: str
    items_to_discuss: List[str] = Field(default_factory=list)  # Item IDs
    projects_to_review: List[str] = Field(default_factory=list)  # Project IDs
    follow_ups_from_previous: Optional[str] = None  # Meeting ID


class NotionQueryFilter(BaseModel):
    """Filter for querying Notion databases."""

    property_name: str
    property_type: str  # "select", "multi_select", "date", "checkbox", "relation", etc.
    condition: str  # "equals", "contains", "is_empty", "before", "after", etc.
    value: Any = None


class NotionQuerySort(BaseModel):
    """Sort order for Notion queries."""

    property_name: str
    direction: str = "descending"  # "ascending" or "descending"
