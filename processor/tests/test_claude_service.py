"""
Unit tests for Claude service.
Tests email analysis, vision analysis, and relationship detection with mocked API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from services.claude_service import ClaudeService


def _thinking_block():
    """Sonnet 5 runs adaptive thinking, so responses lead with a thinking block.

    Fixtures include one so the tests exercise the real response shape: callers
    must select text blocks by type, never by content[0].
    """
    block = Mock()
    block.type = "thinking"
    block.thinking = ""
    return block
from models.email_data import EmailAttachment


@pytest.fixture
def claude_service():
    """Create a Claude service instance with mocked client."""
    with patch('services.claude_service.get_settings') as mock_settings:
        # Mock settings
        settings_obj = Mock()
        settings_obj.claude_api_key = "test-api-key"
        mock_settings.return_value = settings_obj

        service = ClaudeService()
        service.client = Mock()  # Mock Anthropic client

        yield service


@pytest.fixture
def sample_extracted_data():
    """Sample extracted data from Claude."""
    return {
        "title": "Test Traffic Order",
        "summary": "Traffic order for new cycle lane on Test Street.",
        "consultation_deadline": "2026-02-15T23:59:59",
        "action_due_date": None,
        "original_estimated_completion": None,
        "project_type": "traffic_order",
        "action_required": "response_needed",
        "priority": "high",
        "tags": ["cycle_lane", "traffic_order"],
        "locations": ["Test Street", "Sample Road"],
        "ai_key_points": "- New cycle lane proposed\n- Consultation deadline Feb 15\n- Response needed"
    }


@pytest.fixture
def sample_claude_response(sample_extracted_data):
    """Sample Claude API response."""
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = json.dumps(sample_extracted_data)
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    return mock_message


def test_analyze_email_text(claude_service, sample_claude_response, sample_extracted_data):
    """Test analyzing email text and extracting structured data."""
    # Mock Claude API response
    claude_service.client.messages.create.return_value = sample_claude_response

    # Analyze email
    result = claude_service.analyze_email_text(
        subject="Test Email",
        email_body="This is a test email about a traffic order.",
        attachment_text="Additional details from attachment."
    )

    # Assert
    assert result["title"] == "Test Traffic Order"
    assert result["project_type"] == "traffic_order"
    assert result["action_required"] == "response_needed"
    assert result["priority"] == "high"
    assert "cycle_lane" in result["tags"]
    assert "Test Street" in result["locations"]


def test_analyze_email_text_with_markdown_json(claude_service):
    """Test parsing JSON response wrapped in markdown code blocks."""
    # Mock Claude response with markdown
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = "```json\n{\"title\": \"Test\", \"summary\": \"Test summary\"}\n```"
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Analyze email
    result = claude_service.analyze_email_text("Subject", "Body")

    # Assert JSON was correctly parsed
    assert result["title"] == "Test"
    assert result["summary"] == "Test summary"


def test_analyze_email_text_error_handling(claude_service):
    """Test error handling when Claude API fails."""
    # Mock Claude API to raise exception
    claude_service.client.messages.create.side_effect = Exception("API Error")

    # Analyze email
    result = claude_service.analyze_email_text(
        subject="Test Subject",
        email_body="Test body"
    )

    # Assert error fallback data is returned
    assert "Test Subject" in result["title"]
    assert result["action_required"] == "needs_review"
    assert "Error during AI analysis" in result["ai_key_points"]


def test_analyze_images(claude_service, tmp_path):
    """Test analyzing images with vision API."""
    # Create a temporary fake image
    image_path = tmp_path / "test_image.jpg"
    image_path.write_bytes(b"fake image data")

    # Create attachment
    attachment = EmailAttachment(
        filename="test_image.jpg",
        mime_type="image/jpeg",
        size_bytes=100,
        attachment_id="att_123",
        local_path=str(image_path)
    )

    # Mock Claude vision response
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = "This image shows a proposed cycle lane on Test Street."
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Analyze images
    result = claude_service.analyze_images([attachment])

    # Assert
    assert "test_image.jpg" in result
    assert "proposed cycle lane" in result


def test_analyze_images_empty_list(claude_service):
    """Test analyzing empty list of images."""
    result = claude_service.analyze_images([])
    assert result == ""


def test_detect_related_items(claude_service):
    """Test detecting related items and project matches."""
    # Mock existing items
    mock_item = Mock()
    mock_item.notion_id = "item_123"
    mock_item.title = "Previous Item"
    mock_item.locations = ["Test Street"]
    mock_item.tags = ["cycle_lane"]

    # Mock existing projects
    mock_project = Mock()
    mock_project.notion_id = "project_456"
    mock_project.project_name = "Test Street Improvements"
    mock_project.primary_locations = ["Test Street"]

    # Mock Claude response
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = json.dumps({
        "related_item_ids": ["item_123"],
        "related_item_explanations": {
            "item_123": "Same location"
        },
        "suggested_project_id": "project_456",
        "project_match_confidence": "high",
        "project_match_reason": "Same street"
    })
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Detect relationships
    related_items, suggested_project = claude_service.detect_related_items(
        new_title="New Item on Test Street",
        new_summary="Another consultation on Test Street",
        new_locations=["Test Street"],
        new_tags=["cycle_lane"],
        new_project_type="consultation",
        existing_items=[mock_item],
        existing_projects=[mock_project]
    )

    # Assert
    assert "item_123" in related_items
    assert suggested_project == "project_456"


def test_detect_related_items_low_confidence(claude_service):
    """Test that low confidence project matches are rejected."""
    # Mock Claude response with low confidence
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = json.dumps({
        "related_item_ids": [],
        "related_item_explanations": {},
        "suggested_project_id": "project_456",
        "project_match_confidence": "low",
        "project_match_reason": "Different location"
    })
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Detect relationships
    related_items, suggested_project = claude_service.detect_related_items(
        new_title="New Item",
        new_summary="Summary",
        new_locations=["Different Street"],
        new_tags=[],
        new_project_type="other",
        existing_items=[],
        existing_projects=[]
    )

    # Assert project suggestion is None due to low confidence
    assert suggested_project is None


def test_generate_discussion_prompts(claude_service):
    """Test generating discussion prompts for meeting items."""
    # Mock critical items
    mock_item = Mock()
    mock_item.notion_id = "item_123"
    mock_item.title = "Urgent Traffic Order"
    mock_item.summary = "Traffic order with tight deadline"
    mock_item.consultation_deadline = "2026-02-15"
    mock_item.action_required = "response_needed"

    # Mock Claude response
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = json.dumps({
        "item_123": [
            "Who can draft the response by Feb 15?",
            "Should we coordinate with local BID?"
        ]
    })
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Generate prompts
    prompts = claude_service.generate_discussion_prompts([mock_item])

    # Assert
    assert "item_123" in prompts
    assert len(prompts["item_123"]) == 2
    assert "Feb 15" in prompts["item_123"][0]


def test_generate_agenda_summary(claude_service):
    """Test generating meeting agenda summary."""
    # Mock top items
    mock_item = Mock()
    mock_item.title = "Important Consultation"
    mock_item.project_type = "consultation"
    mock_item.action_required = "response_needed"

    # Mock Claude response
    mock_message = Mock()
    mock_content = Mock()
    mock_content.text = "Since our last meeting, we've received 10 new items including several urgent consultations. This meeting will focus on prioritizing responses."
    mock_content.type = "text"
    mock_message.content = [_thinking_block(), mock_content]
    claude_service.client.messages.create.return_value = mock_message

    # Generate summary
    summary = claude_service.generate_agenda_summary(
        meeting_date="2026-02-15",
        item_count=10,
        deadline_count=3,
        project_count=5,
        top_items=[mock_item]
    )

    # Assert
    assert "10 new items" in summary
    assert "urgent consultations" in summary


def test_parse_json_response_with_code_block(claude_service):
    """Test parsing JSON from markdown code blocks."""
    response_text = "```json\n{\"key\": \"value\"}\n```"
    result = claude_service._parse_json_response(response_text)
    assert result["key"] == "value"


def test_parse_json_response_plain(claude_service):
    """Test parsing plain JSON."""
    response_text = '{"key": "value"}'
    result = claude_service._parse_json_response(response_text)
    assert result["key"] == "value"


def test_parse_json_response_invalid(claude_service):
    """Test error handling for invalid JSON."""
    with pytest.raises(ValueError):
        claude_service._parse_json_response("not valid json")


def test_get_media_type(claude_service):
    """Test MIME type to media type conversion."""
    assert claude_service._get_media_type("image/jpeg") == "image/jpeg"
    assert claude_service._get_media_type("image/jpg") == "image/jpeg"
    assert claude_service._get_media_type("image/png") == "image/png"
    assert claude_service._get_media_type("image/unknown") == "image/jpeg"  # Default


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
