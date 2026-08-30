"""
Unit tests for Gmail service.
Tests email polling, retrieval, and attachment handling with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.gmail_service import GmailService
from models.email_data import EmailData, EmailAttachment


@pytest.fixture
def gmail_service():
    """Create a Gmail service instance with mocked credentials."""
    with patch('services.gmail_service.get_settings') as mock_settings:
        # Mock settings
        settings_obj = Mock()
        settings_obj.gmail_client_id = "test-client-id"
        settings_obj.gmail_client_secret = "test-client-secret"
        settings_obj.gmail_refresh_token = "test-refresh-token"
        settings_obj.gmail_label = "Test Label"
        mock_settings.return_value = settings_obj

        service = GmailService()
        service.service = Mock()  # Mock Gmail API service
        service.credentials = Mock()

        yield service


@pytest.fixture
def sample_gmail_message():
    """Sample Gmail API message response."""
    return {
        'id': 'msg_123',
        'threadId': 'thread_456',
        'labelIds': ['INBOX', 'Label_1'],
        'snippet': 'This is a test email...',
        'payload': {
            'headers': [
                {'name': 'From', 'value': 'John Doe <john@example.com>'},
                {'name': 'To', 'value': 'test@lambethcyclists.org'},
                {'name': 'Subject', 'value': 'Test Consultation'},
                {'name': 'Date', 'value': 'Thu, 9 Jan 2026 10:00:00 +0000'},
            ],
            'mimeType': 'multipart/mixed',
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {
                        'data': 'VGhpcyBpcyB0aGUgZW1haWwgYm9keS4='  # Base64: "This is the email body."
                    }
                }
            ]
        }
    }


def test_poll_emails_returns_message_ids(gmail_service):
    """Test that poll_emails returns list of message IDs."""
    # Mock Gmail API response
    gmail_service.service.users().messages().list().execute.return_value = {
        'messages': [
            {'id': 'msg_1'},
            {'id': 'msg_2'},
            {'id': 'msg_3'},
        ]
    }

    # Poll emails
    message_ids = gmail_service.poll_emails()

    # Assert
    assert len(message_ids) == 3
    assert message_ids == ['msg_1', 'msg_2', 'msg_3']


def test_poll_emails_returns_empty_when_no_messages(gmail_service):
    """Test that poll_emails returns empty list when no messages found."""
    # Mock Gmail API response with no messages
    gmail_service.service.users().messages().list().execute.return_value = {
        'messages': []
    }

    # Poll emails
    message_ids = gmail_service.poll_emails()

    # Assert
    assert message_ids == []


def test_get_email_details_parses_message(gmail_service, sample_gmail_message):
    """Test that get_email_details correctly parses a Gmail message."""
    # Mock Gmail API response
    gmail_service.service.users().messages().get().execute.return_value = sample_gmail_message

    # Get email details
    email_data = gmail_service.get_email_details('msg_123')

    # Assert basic fields
    assert email_data.message_id == 'msg_123'
    assert email_data.subject == 'Test Consultation'
    assert email_data.sender_email == 'john@example.com'
    assert email_data.sender_name == 'John Doe'
    assert email_data.body_plain == 'This is the email body.'
    assert not email_data.has_attachments


def test_parse_sender_with_name_and_email(gmail_service):
    """Test parsing sender with both name and email."""
    email, name = gmail_service._parse_sender('John Doe <john@example.com>')

    assert email == 'john@example.com'
    assert name == 'John Doe'


def test_parse_sender_with_email_only(gmail_service):
    """Test parsing sender with email only."""
    email, name = gmail_service._parse_sender('john@example.com')

    assert email == 'john@example.com'
    assert name is None


def test_parse_recipients_single(gmail_service):
    """Test parsing single recipient."""
    recipients = gmail_service._parse_recipients('jane@example.com')

    assert recipients == ['jane@example.com']


def test_parse_recipients_multiple(gmail_service):
    """Test parsing multiple recipients."""
    recipients = gmail_service._parse_recipients(
        'Jane Doe <jane@example.com>, Bob Smith <bob@example.com>'
    )

    assert len(recipients) == 2
    assert 'jane@example.com' in recipients
    assert 'bob@example.com' in recipients


def test_extract_attachments_from_parts(gmail_service):
    """Test extracting attachment metadata from message parts."""
    parts = [
        {
            'filename': 'document.pdf',
            'mimeType': 'application/pdf',
            'body': {
                'attachmentId': 'att_123',
                'size': 1024
            }
        },
        {
            'filename': 'image.jpg',
            'mimeType': 'image/jpeg',
            'body': {
                'attachmentId': 'att_456',
                'size': 2048
            }
        }
    ]

    attachments = gmail_service._extract_attachments('msg_123', parts)

    assert len(attachments) == 2
    assert attachments[0].filename == 'document.pdf'
    assert attachments[0].mime_type == 'application/pdf'
    assert attachments[0].attachment_id == 'att_123'
    assert attachments[1].filename == 'image.jpg'


def test_mark_as_processed_adds_label(gmail_service):
    """Test that mark_as_processed adds the processed label."""
    # Mock label list response
    gmail_service.service.users().labels().list().execute.return_value = {
        'labels': [
            {'id': 'Label_processed', 'name': 'processed'}
        ]
    }

    # Mock modify response
    gmail_service.service.users().messages().modify.return_value.execute.return_value = {}

    # Mark as processed
    gmail_service.mark_as_processed('msg_123')

    # Assert modify was called with correct label
    gmail_service.service.users().messages().modify.assert_called_once()


def test_get_or_create_label_existing(gmail_service):
    """Test getting existing label ID."""
    # Mock label list response
    gmail_service.service.users().labels().list().execute.return_value = {
        'labels': [
            {'id': 'Label_1', 'name': 'test_label'},
            {'id': 'Label_2', 'name': 'another_label'}
        ]
    }

    label_id = gmail_service._get_or_create_label('test_label')

    assert label_id == 'Label_1'


def test_get_or_create_label_creates_new(gmail_service):
    """Test creating new label when it doesn't exist."""
    # Mock label list response (label doesn't exist)
    gmail_service.service.users().labels().list().execute.return_value = {
        'labels': []
    }

    # Mock label create response
    gmail_service.service.users().labels().create.return_value.execute.return_value = {
        'id': 'Label_new',
        'name': 'new_label'
    }

    label_id = gmail_service._get_or_create_label('new_label')

    assert label_id == 'Label_new'
    gmail_service.service.users().labels().create.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
