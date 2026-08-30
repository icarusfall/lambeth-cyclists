"""
Unit tests for email processor pipeline.
Tests the orchestration of all services.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from processors.email_processor import EmailProcessor
from models.email_data import EmailData, EmailAttachment


@pytest.fixture
def email_processor():
    """Create email processor with mocked services."""
    with patch('processors.email_processor.get_settings'):
        processor = EmailProcessor()

        # Mock all services
        processor.gmail = Mock()
        processor.claude = Mock()
        processor.notion = Mock()
        processor.geocoding = Mock()
        processor.storage = Mock()
        processor.attachment_processor = Mock()
        processor.content_extractor = Mock()
        processor.deduplicator = Mock()

        yield processor


@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return EmailData(
        message_id="msg_test_123",
        thread_id="thread_456",
        subject="Test Consultation - Brixton Hill",
        sender_email="test@example.com",
        sender_name="Test Sender",
        recipient_emails=["lambeth@example.com"],
        date_received=datetime.now(timezone.utc),
        body_plain="This is a test consultation about cycling infrastructure.",
        body_html=None,
        snippet="Test consultation...",
        attachments=[],
        has_attachments=False,
        labels=["Lambeth Cycling Projects"],
        processed=False
    )


@pytest.mark.asyncio
async def test_process_new_emails_no_emails(email_processor):
    """Test processing when no new emails are found."""
    # Mock Gmail returning no emails
    email_processor.gmail.poll_emails.return_value = []

    # Process emails
    await email_processor.process_new_emails()

    # Assert no processing occurred
    email_processor.gmail.get_email_details.assert_not_called()
    assert email_processor.stats['processed'] == 0


@pytest.mark.asyncio
async def test_process_new_emails_with_emails(email_processor, sample_email_data):
    """Test processing multiple new emails."""
    # Mock Gmail returning emails
    email_processor.gmail.poll_emails.return_value = ["msg_1", "msg_2"]
    email_processor.gmail.get_email_details.return_value = sample_email_data

    # Mock deduplicator (no duplicates)
    email_processor.deduplicator.check_duplicate.return_value = None

    # Mock attachment processing
    email_processor.attachment_processor.process_all_attachments.return_value = {
        'combined_text': '',
        'images': [],
        'unsupported': []
    }

    # Mock Claude analysis
    email_processor.claude.analyze_email_text.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'consultation',
        'action_required': 'response_needed',
        'priority': 'high',
        'tags': ['consultation'],
        'locations': ['Brixton Hill'],
        'ai_key_points': '- Test point'
    }
    email_processor.claude.detect_related_items.return_value = ([], None)

    # Mock content extractor
    email_processor.content_extractor.extract_structured_data.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'consultation',
        'action_required': 'response_needed',
        'priority': 'high',
        'tags': ['consultation'],
        'locations': ['Brixton Hill'],
        'ai_key_points': '- Test point',
        'consultation_deadline': None,
        'action_due_date': None,
        'original_estimated_completion': None
    }
    email_processor.content_extractor.format_attachment_urls.return_value = ""

    # Mock Notion queries and creation
    email_processor.notion.query_items.return_value = []
    email_processor.notion.query_projects.return_value = []

    mock_notion_item = Mock()
    mock_notion_item.notion_id = "notion_123"
    mock_notion_item.title = "Test Item"
    email_processor.notion.create_item.return_value = mock_notion_item

    # Mock geocoding
    email_processor.geocoding.is_enabled.return_value = False

    # Mock storage
    email_processor.storage.upload_attachments.return_value = {}

    # Process emails
    await email_processor.process_new_emails()

    # Assert both emails were processed
    assert email_processor.stats['processed'] == 2
    assert email_processor.gmail.mark_as_processed.call_count == 2


@pytest.mark.asyncio
async def test_process_single_email_duplicate(email_processor, sample_email_data):
    """Test that duplicate emails are skipped."""
    # Mock Gmail
    email_processor.gmail.get_email_details.return_value = sample_email_data

    # Mock deduplicator returning existing item
    existing_item = Mock()
    existing_item.notion_id = "existing_123"
    email_processor.deduplicator.check_duplicate.return_value = existing_item

    # Process email
    await email_processor.process_single_email("msg_test_123")

    # Assert duplicate was detected and email was marked processed
    assert email_processor.stats['duplicates'] == 1
    email_processor.gmail.mark_as_processed.assert_called_once_with("msg_test_123")

    # Assert no Notion item was created
    email_processor.notion.create_item.assert_not_called()


@pytest.mark.asyncio
async def test_process_single_email_with_attachments(email_processor, sample_email_data):
    """Test processing email with attachments."""
    # Add attachments to email data
    attachment = EmailAttachment(
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=1000,
        attachment_id="att_123"
    )
    sample_email_data.attachments = [attachment]
    sample_email_data.has_attachments = True

    # Mock Gmail
    email_processor.gmail.get_email_details.return_value = sample_email_data
    email_processor.gmail.download_all_attachments.return_value = ["/tmp/test.pdf"]

    # Mock deduplicator (not duplicate)
    email_processor.deduplicator.check_duplicate.return_value = None

    # Mock attachment processing
    email_processor.attachment_processor.process_all_attachments.return_value = {
        'combined_text': 'Extracted text from PDF',
        'images': [],
        'unsupported': []
    }

    # Mock Claude analysis
    email_processor.claude.analyze_email_text.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'traffic_order',
        'action_required': 'response_needed',
        'priority': 'high',
        'tags': [],
        'locations': [],
        'ai_key_points': ''
    }
    email_processor.claude.detect_related_items.return_value = ([], None)

    # Mock content extractor
    email_processor.content_extractor.extract_structured_data.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'traffic_order',
        'action_required': 'response_needed',
        'priority': 'high',
        'tags': [],
        'locations': [],
        'ai_key_points': '',
        'consultation_deadline': None,
        'action_due_date': None,
        'original_estimated_completion': None
    }
    email_processor.content_extractor.format_attachment_urls.return_value = '{"test.pdf":"https://drive.google.com/..."}'

    # Mock Notion
    email_processor.notion.query_items.return_value = []
    email_processor.notion.query_projects.return_value = []

    mock_notion_item = Mock()
    mock_notion_item.notion_id = "notion_123"
    mock_notion_item.title = "Test Item"
    email_processor.notion.create_item.return_value = mock_notion_item

    # Mock storage
    email_processor.storage.upload_attachments.return_value = {
        "test.pdf": "https://drive.google.com/file/123"
    }

    # Mock geocoding
    email_processor.geocoding.is_enabled.return_value = False

    # Process email
    await email_processor.process_single_email("msg_test_123")

    # Assert attachments were processed
    email_processor.gmail.download_all_attachments.assert_called_once()
    email_processor.attachment_processor.process_all_attachments.assert_called_once()
    email_processor.storage.upload_attachments.assert_called_once()


@pytest.mark.asyncio
async def test_process_single_email_with_images(email_processor, sample_email_data):
    """Test processing email with images."""
    # Add image attachment
    image = EmailAttachment(
        filename="diagram.jpg",
        mime_type="image/jpeg",
        size_bytes=2000,
        attachment_id="att_img",
        local_path="/tmp/diagram.jpg"
    )
    sample_email_data.attachments = [image]
    sample_email_data.has_attachments = True

    # Mock Gmail
    email_processor.gmail.get_email_details.return_value = sample_email_data

    # Mock deduplicator
    email_processor.deduplicator.check_duplicate.return_value = None

    # Mock attachment processing (image separated)
    email_processor.attachment_processor.process_all_attachments.return_value = {
        'combined_text': '',
        'images': [image],
        'unsupported': []
    }

    # Mock Claude text analysis
    email_processor.claude.analyze_email_text.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'infrastructure_project',
        'action_required': 'information_only',
        'priority': 'medium',
        'tags': [],
        'locations': [],
        'ai_key_points': ''
    }

    # Mock Claude vision analysis
    email_processor.claude.analyze_images.return_value = "Image shows proposed cycle lane design"
    email_processor.claude.detect_related_items.return_value = ([], None)

    # Mock content extractor
    email_processor.content_extractor.extract_structured_data.return_value = {
        'title': 'Test Item',
        'summary': 'Test summary',
        'project_type': 'infrastructure_project',
        'action_required': 'information_only',
        'priority': 'medium',
        'tags': [],
        'locations': [],
        'ai_key_points': '',
        'consultation_deadline': None,
        'action_due_date': None,
        'original_estimated_completion': None
    }
    email_processor.content_extractor.format_attachment_urls.return_value = ""

    # Mock Notion
    email_processor.notion.query_items.return_value = []
    email_processor.notion.query_projects.return_value = []

    mock_notion_item = Mock()
    mock_notion_item.notion_id = "notion_123"
    mock_notion_item.title = "Test Item"
    email_processor.notion.create_item.return_value = mock_notion_item

    # Mock storage
    email_processor.storage.upload_attachments.return_value = {}

    # Mock geocoding
    email_processor.geocoding.is_enabled.return_value = False

    # Process email
    await email_processor.process_single_email("msg_test_123")

    # Assert vision analysis was called
    email_processor.claude.analyze_images.assert_called_once_with([image])


def test_get_statistics(email_processor):
    """Test getting processing statistics."""
    email_processor.stats['processed'] = 5
    email_processor.stats['duplicates'] = 2
    email_processor.stats['errors'] = 1

    stats = email_processor.get_statistics()

    assert stats['processed'] == 5
    assert stats['duplicates'] == 2
    assert stats['errors'] == 1


def test_reset_statistics(email_processor):
    """Test resetting statistics."""
    email_processor.stats['processed'] = 5
    email_processor.stats['duplicates'] = 2

    email_processor.reset_statistics()

    assert email_processor.stats['processed'] == 0
    assert email_processor.stats['duplicates'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
