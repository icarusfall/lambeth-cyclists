"""
Content extractor for combining and structuring email content.
Prepares content for Claude AI analysis.
"""

from typing import Dict, Any
from datetime import datetime

from config.logging_config import get_logger
from models.email_data import EmailData

logger = get_logger(__name__)


class ContentExtractor:
    """
    Extracts and structures content from emails for AI analysis.
    Combines email body, attachment text, and metadata.
    """

    def extract_structured_data(
        self,
        claude_response: Dict[str, Any],
        email_data: EmailData
    ) -> Dict[str, Any]:
        """
        Extract structured data from Claude's response and combine with email metadata.

        Args:
            claude_response: Parsed JSON response from Claude
            email_data: Original EmailData object

        Returns:
            Dictionary with complete structured data for Notion
        """
        # Start with Claude's extracted data
        structured = claude_response.copy()

        # Add email metadata
        structured['email_metadata'] = {
            'message_id': email_data.message_id,
            'sender_email': email_data.sender_email,
            'sender_name': email_data.sender_name,
            'date_received': email_data.date_received,
            'has_attachments': email_data.has_attachments,
            'attachment_count': email_data.attachment_count,
        }

        # Parse dates to datetime objects
        structured = self._parse_dates(structured)

        # Validate and normalize data
        structured = self._validate_data(structured)

        logger.debug(f"Extracted structured data: {structured.get('title', 'Unknown')}")

        return structured

    def _parse_dates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse date strings to datetime objects.

        Args:
            data: Dictionary with date fields

        Returns:
            Dictionary with parsed datetime objects
        """
        date_fields = [
            'consultation_deadline',
            'action_due_date',
            'original_estimated_completion'
        ]

        for field in date_fields:
            if field in data and data[field]:
                try:
                    if isinstance(data[field], str):
                        # Parse ISO 8601 format
                        data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Error parsing date field '{field}': {e}")
                    data[field] = None

        return data

    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize extracted data.

        Args:
            data: Dictionary with extracted data

        Returns:
            Validated and normalized dictionary
        """
        # Ensure required fields have defaults
        defaults = {
            'title': 'Untitled Item',
            'summary': 'No summary available.',
            'project_type': 'other',
            'action_required': 'information_only',
            'priority': 'medium',
            'tags': [],
            'locations': [],
            'ai_key_points': '',
            'consultation_deadline': None,
            'action_due_date': None,
            'original_estimated_completion': None,
        }

        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value

        # Validate select field values
        valid_project_types = [
            'traffic_order', 'consultation', 'infrastructure_project', 'event', 'other'
        ]
        if data['project_type'] not in valid_project_types:
            logger.warning(f"Invalid project_type: {data['project_type']}, using 'other'")
            data['project_type'] = 'other'

        valid_action_required = [
            'response_needed', 'information_only', 'monitoring', 'urgent_action'
        ]
        if data['action_required'] not in valid_action_required:
            logger.warning(f"Invalid action_required: {data['action_required']}, using 'information_only'")
            data['action_required'] = 'information_only'

        valid_priorities = ['critical', 'high', 'medium', 'low']
        if data['priority'] not in valid_priorities:
            logger.warning(f"Invalid priority: {data['priority']}, using 'medium'")
            data['priority'] = 'medium'

        # Ensure tags and locations are lists
        if not isinstance(data['tags'], list):
            data['tags'] = []
        if not isinstance(data['locations'], list):
            data['locations'] = []

        return data

    def format_attachment_urls(self, drive_urls: Dict[str, str]) -> str:
        """
        Format attachment URLs as JSON for storage in Notion.

        Args:
            drive_urls: Dictionary mapping filename to Drive URL

        Returns:
            JSON string of attachment URLs
        """
        import json

        if not drive_urls:
            return ""

        try:
            # Format as array of objects
            attachments = [
                {"filename": filename, "url": url}
                for filename, url in drive_urls.items()
            ]

            return json.dumps(attachments, separators=(',', ':'))

        except Exception as e:
            logger.error(f"Error formatting attachment URLs: {e}")
            return ""

    def parse_attachment_urls(self, json_str: str) -> Dict[str, str]:
        """
        Parse attachment URLs from JSON string.

        Args:
            json_str: JSON string from Notion

        Returns:
            Dictionary mapping filename to URL
        """
        import json

        if not json_str:
            return {}

        try:
            attachments = json.loads(json_str)
            return {att['filename']: att['url'] for att in attachments}

        except Exception as e:
            logger.error(f"Error parsing attachment URLs: {e}")
            return {}
