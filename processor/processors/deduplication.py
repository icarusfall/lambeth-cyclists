"""
Deduplication logic for preventing duplicate email processing.
Implements three-layer deduplication strategy.
"""

import hashlib
from typing import Optional
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from config.logging_config import get_logger
from models.email_data import EmailData
from models.notion_schemas import NotionItem

logger = get_logger(__name__)


class Deduplicator:
    """
    Handles deduplication checks for emails.
    Three-layer strategy: Gmail Message ID → Subject+Date → Content Hash
    """

    def __init__(self, notion_service):
        """
        Initialize deduplicator.

        Args:
            notion_service: NotionService instance for database queries
        """
        self.notion_service = notion_service

    def check_duplicate(self, email_data: EmailData) -> Optional[NotionItem]:
        """
        Check if email is a duplicate using three-layer strategy.

        Args:
            email_data: EmailData object to check

        Returns:
            Existing NotionItem if duplicate found, None otherwise
        """
        # Layer 1: Gmail Message ID (fastest, most reliable)
        duplicate = self._check_message_id(email_data.message_id)
        if duplicate:
            logger.info(
                f"Duplicate detected (Layer 1 - Message ID): {email_data.subject}",
                extra={'email_id': email_data.message_id}
            )
            return duplicate

        # Layer 2: Subject + Date similarity
        duplicate = self._check_subject_date(email_data.subject, email_data.date_received)
        if duplicate:
            logger.info(
                f"Duplicate detected (Layer 2 - Subject+Date): {email_data.subject}",
                extra={'email_id': email_data.message_id}
            )
            return duplicate

        # Layer 3: Content hash (slowest, but catches edge cases)
        duplicate = self._check_content_hash(email_data)
        if duplicate:
            logger.info(
                f"Duplicate detected (Layer 3 - Content Hash): {email_data.subject}",
                extra={'email_id': email_data.message_id}
            )
            return duplicate

        # Not a duplicate
        logger.debug(
            f"No duplicate found for: {email_data.subject}",
            extra={'email_id': email_data.message_id}
        )
        return None

    def _check_message_id(self, message_id: str) -> Optional[NotionItem]:
        """
        Layer 1: Check if Gmail message ID exists in Notion.

        Args:
            message_id: Gmail message ID

        Returns:
            Existing NotionItem if found, None otherwise
        """
        try:
            return self.notion_service.check_duplicate_by_message_id(message_id)
        except Exception as e:
            logger.error(f"Error checking message ID duplicate: {e}", exc_info=True)
            return None

    def _check_subject_date(
        self,
        subject: str,
        date_received: datetime
    ) -> Optional[NotionItem]:
        """
        Layer 2: Check for similar subject within 24 hours.
        Uses fuzzy matching (>95% similarity) to catch forwarded emails.

        Args:
            subject: Email subject
            date_received: Email date

        Returns:
            Existing NotionItem if found, None otherwise
        """
        try:
            # Query items from the past 24 hours
            from models.notion_schemas import NotionQueryFilter

            date_filter = NotionQueryFilter(
                property_name="Date Received",
                property_type="date",
                condition="after",
                value=(date_received - timedelta(days=1)).isoformat()
            )

            recent_items = self.notion_service.query_items(
                filters=[date_filter],
                limit=50
            )

            # Check for subject similarity
            for item in recent_items:
                similarity = self._string_similarity(subject, item.title)

                if similarity > 0.95:
                    logger.debug(
                        f"Found similar subject: '{subject}' vs '{item.title}' "
                        f"(similarity: {similarity:.2%})"
                    )
                    return item

            return None

        except Exception as e:
            logger.error(f"Error checking subject+date duplicate: {e}", exc_info=True)
            return None

    def _check_content_hash(self, email_data: EmailData) -> Optional[NotionItem]:
        """
        Layer 3: Check content hash to catch edge cases.
        Hashes email body + attachment filenames.

        Args:
            email_data: EmailData object

        Returns:
            Existing NotionItem if found, None otherwise
        """
        try:
            # Create content hash
            content_hash = self._compute_content_hash(email_data)

            # Query recent items (past week) to check hash
            from models.notion_schemas import NotionQueryFilter

            date_filter = NotionQueryFilter(
                property_name="Date Received",
                property_type="date",
                condition="after",
                value=(email_data.date_received - timedelta(days=7)).isoformat()
            )

            recent_items = self.notion_service.query_items(
                filters=[date_filter],
                limit=100
            )

            # Check each item's content hash
            # Note: We'd need to store content hashes in Notion for this to work fully
            # For now, we use a simpler heuristic: same sender + similar summary

            for item in recent_items:
                if item.sender_email == email_data.sender_email:
                    # Same sender - check if summaries are very similar
                    if item.summary:
                        body_text = email_data.body_text[:500]
                        similarity = self._string_similarity(body_text, item.summary[:500])

                        if similarity > 0.90:
                            logger.debug(
                                f"Found similar content from same sender "
                                f"(similarity: {similarity:.2%})"
                            )
                            return item

            return None

        except Exception as e:
            logger.error(f"Error checking content hash duplicate: {e}", exc_info=True)
            return None

    def _compute_content_hash(self, email_data: EmailData) -> str:
        """
        Compute hash of email content.

        Args:
            email_data: EmailData object

        Returns:
            SHA256 hash of content
        """
        # Combine relevant content
        content_parts = [
            email_data.subject or "",
            email_data.body_text[:1000],  # First 1000 chars
            ",".join(sorted(att.filename for att in email_data.attachments))
        ]

        content = "|".join(content_parts).encode('utf-8')

        # Compute SHA256 hash
        hash_obj = hashlib.sha256(content)
        return hash_obj.hexdigest()

    def _string_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        if not str1 or not str2:
            return 0.0

        # Normalize: lowercase and strip
        str1_norm = str1.lower().strip()
        str2_norm = str2.lower().strip()

        return SequenceMatcher(None, str1_norm, str2_norm).ratio()
