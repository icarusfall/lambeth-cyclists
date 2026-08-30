"""
Unit tests for Notion service.
Tests database operations with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from services.notion_service import NotionService
from models.notion_schemas import (
    NotionItemCreate, NotionProjectCreate, NotionMeetingCreate,
    NotionQueryFilter
)


@pytest.fixture
def notion_service():
    """Create a Notion service instance with mocked client."""
    with patch('services.notion_service.get_settings') as mock_settings:
        # Mock settings
        settings_obj = Mock()
        settings_obj.notion_api_key = "test-api-key"
        settings_obj.notion_items_db_id = "items_db_id"
        settings_obj.notion_projects_db_id = "projects_db_id"
        settings_obj.notion_meetings_db_id = "meetings_db_id"
        mock_settings.return_value = settings_obj

        service = NotionService()
        service.client = Mock()  # Mock Notion client

        # v3 resolves a database's data source before querying it or parenting
        # a page to it, so the mock has to answer databases.retrieve with the
        # real shape. Each db id maps to a distinct data source id, which lets
        # the tests assert that pages land in the right one.
        service.client.databases.retrieve.side_effect = lambda database_id: {
            "data_sources": [{"id": f"ds_of_{database_id}"}]
        }

        yield service


@pytest.fixture
def sample_item_data():
    """Sample item data for testing."""
    return NotionItemCreate(
        title="Test Traffic Order",
        summary="Testing traffic order for cycling infrastructure",
        date_received=datetime.now(timezone.utc),
        gmail_message_id="msg_test_123",
        sender_email="test@example.com",
        has_attachments=True,
        consultation_deadline=datetime.now(timezone.utc),
        project_type="traffic_order",
        action_required="response_needed",
        tags=["LTN", "cycle_infrastructure"],
        locations=["Test Street", "Sample Road"],
        ai_key_points="- Key point 1\n- Key point 2",
        status="new",
        priority="high",
        processing_status="ai_complete"
    )


@pytest.fixture
def sample_notion_item_response():
    """Sample Notion API response for an item."""
    return {
        "id": "page_123",
        "created_time": "2026-01-09T10:00:00.000Z",
        "last_edited_time": "2026-01-09T10:00:00.000Z",
        "url": "https://notion.so/page_123",
        "properties": {
            "Title": {"title": [{"text": {"content": "Test Item"}}]},
            "Summary": {"rich_text": [{"text": {"content": "Test summary"}}]},
            "Date Received": {"date": {"start": "2026-01-09T10:00:00.000Z"}},
            "Gmail Message ID": {"rich_text": [{"text": {"content": "msg_test_123"}}]},
            "Sender Email": {"email": "test@example.com"},
            "Has Attachments": {"checkbox": True},
            "Status": {"select": {"name": "new"}},
            "Priority": {"select": {"name": "high"}},
            "Processing Status": {"select": {"name": "ai_complete"}},
            "Project Type": {"select": {"name": "traffic_order"}},
            "Action Required": {"select": {"name": "response_needed"}},
            "Tags": {"multi_select": [{"name": "LTN"}, {"name": "cycle_infrastructure"}]},
            "Locations": {"multi_select": [{"name": "Test Street"}]},
        }
    }


def test_create_item(notion_service, sample_item_data, sample_notion_item_response):
    """Test creating an item in Notion."""
    # Mock Notion API response
    notion_service.client.pages.create.return_value = sample_notion_item_response

    # Create item
    notion_item = notion_service.create_item(sample_item_data)

    # Assert
    assert notion_item.notion_id == "page_123"
    assert notion_item.title == "Test Item"
    assert notion_item.gmail_message_id == "msg_test_123"
    assert notion_item.status == "new"
    assert "LTN" in notion_item.tags


def test_build_item_properties(notion_service, sample_item_data):
    """Test building Notion properties from item data."""
    properties = notion_service._build_item_properties(sample_item_data)

    # Assert required fields
    assert "Title" in properties
    assert "Summary" in properties
    assert "Date Received" in properties
    assert "Status" in properties
    assert "Priority" in properties

    # Assert optional fields
    assert "Gmail Message ID" in properties
    assert "Tags" in properties
    assert len(properties["Tags"]["multi_select"]) == 2

def test_parse_item_response(notion_service, sample_notion_item_response):
    """Test parsing Notion API response into NotionItem."""
    notion_item = notion_service._parse_item_response(sample_notion_item_response)

    assert notion_item.notion_id == "page_123"
    assert notion_item.title == "Test Item"
    assert notion_item.summary == "Test summary"
    assert notion_item.status == "new"


def test_query_items(notion_service):
    """Test querying items database."""
    # Mock Notion API response
    notion_service.client.data_sources.query.return_value = {
        "results": [
            {
                "id": "page_1",
                "created_time": "2026-01-09T10:00:00.000Z",
                "last_edited_time": "2026-01-09T10:00:00.000Z",
                "url": "https://notion.so/page_1",
                "properties": {
                    "Title": {"title": [{"text": {"content": "Item 1"}}]},
                    "Summary": {"rich_text": [{"text": {"content": "Summary 1"}}]},
                    "Date Received": {"date": {"start": "2026-01-09T10:00:00.000Z"}},
                    "Status": {"select": {"name": "new"}},
                    "Priority": {"select": {"name": "medium"}},
                    "Processing Status": {"select": {"name": "ai_complete"}},
                }
            }
        ]
    }

    # Query items
    items = notion_service.query_items()

    # Assert
    assert len(items) == 1
    assert items[0].title == "Item 1"


def test_check_duplicate_by_message_id(notion_service, sample_notion_item_response):
    """Test checking for duplicate by Gmail message ID."""
    # Mock query response
    notion_service.client.data_sources.query.return_value = {
        "results": [sample_notion_item_response]
    }

    # Check for duplicate
    duplicate = notion_service.check_duplicate_by_message_id("msg_test_123")

    # Assert
    assert duplicate is not None
    assert duplicate.gmail_message_id == "msg_test_123"


def test_check_duplicate_returns_none_when_not_found(notion_service):
    """Test that check_duplicate returns None when no duplicate found."""
    # Mock empty query response
    notion_service.client.data_sources.query.return_value = {
        "results": []
    }

    # Check for duplicate
    duplicate = notion_service.check_duplicate_by_message_id("nonexistent_id")

    # Assert
    assert duplicate is None


def test_create_project(notion_service):
    """Test creating a project in Notion."""
    project_data = NotionProjectCreate(
        project_name="Test Project",
        description="Test project description",
        project_type="infrastructure_campaign",
        status="active",
        priority="high",
        primary_locations=["Brixton Hill"]
    )

    # Mock Notion API response
    notion_service.client.pages.create.return_value = {
        "id": "project_123",
        "created_time": "2026-01-09T10:00:00.000Z",
        "last_edited_time": "2026-01-09T10:00:00.000Z",
        "url": "https://notion.so/project_123",
        "properties": {
            "Project Name": {"title": [{"text": {"content": "Test Project"}}]},
            "Description": {"rich_text": [{"text": {"content": "Test project description"}}]},
            "Project Type": {"select": {"name": "infrastructure_campaign"}},
            "Status": {"select": {"name": "active"}},
            "Priority": {"select": {"name": "high"}},
            "Primary Locations": {"multi_select": [{"name": "Brixton Hill"}]},
        }
    }

    # Create project
    notion_project = notion_service.create_project(project_data)

    # Assert
    assert notion_project.notion_id == "project_123"
    assert notion_project.project_name == "Test Project"
    assert notion_project.status == "active"


def test_create_meeting(notion_service):
    """Test creating a meeting in Notion."""
    meeting_data = NotionMeetingCreate(
        meeting_title="Test Meeting - January 2026",
        meeting_date=datetime(2026, 1, 15, 19, 0, tzinfo=timezone.utc),
        meeting_type="regular_committee",
        location="Zoom",
        agenda_generation_status="pending"
    )

    # Mock Notion API response
    notion_service.client.pages.create.return_value = {
        "id": "meeting_123",
        "created_time": "2026-01-09T10:00:00.000Z",
        "last_edited_time": "2026-01-09T10:00:00.000Z",
        "url": "https://notion.so/meeting_123",
        "properties": {
            "Meeting Title": {"title": [{"text": {"content": "Test Meeting - January 2026"}}]},
            "Meeting Date": {"date": {"start": "2026-01-15T19:00:00.000Z"}},
            "Meeting Type": {"select": {"name": "regular_committee"}},
            "Location": {"rich_text": [{"text": {"content": "Zoom"}}]},
            "Agenda Generation Status": {"select": {"name": "pending"}},
            "Meeting Created Manually": {"checkbox": True},
        }
    }

    # Create meeting
    notion_meeting = notion_service.create_meeting(meeting_data)

    # Assert
    assert notion_meeting.notion_id == "meeting_123"
    assert notion_meeting.meeting_title == "Test Meeting - January 2026"
    assert notion_meeting.agenda_generation_status == "pending"


def test_update_meeting_agenda(notion_service):
    """Test updating a meeting with generated agenda."""
    # Mock Notion API
    notion_service.client.pages.update.return_value = {}

    # Update agenda
    notion_service.update_meeting_agenda(
        meeting_id="meeting_123",
        agenda="# Test Agenda\n\n## Items\n- Item 1",
        items=["item_1", "item_2"],
        projects=["project_1"]
    )

    # Assert update was called
    notion_service.client.pages.update.assert_called_once()


def test_build_filter_single(notion_service):
    """Test building a single Notion filter."""
    filters = [NotionQueryFilter(
        property_name="Status",
        property_type="select",
        condition="equals",
        value="new"
    )]

    filter_obj = notion_service._build_filter(filters)

    assert filter_obj["property"] == "Status"
    assert filter_obj["select"]["equals"] == "new"


def test_build_filter_multiple(notion_service):
    """Test building multiple Notion filters with AND."""
    filters = [
        NotionQueryFilter(
            property_name="Status",
            property_type="select",
            condition="equals",
            value="new"
        ),
        NotionQueryFilter(
            property_name="Priority",
            property_type="select",
            condition="equals",
            value="high"
        )
    ]

    filter_obj = notion_service._build_filter(filters)

    assert "and" in filter_obj
    assert len(filter_obj["and"]) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
