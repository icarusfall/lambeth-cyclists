"""
Main email processor that orchestrates the entire pipeline.
Coordinates: Gmail → Download → Extract → Claude → Geocode → Notion
"""

import json
from typing import List, Optional
from datetime import datetime, timezone

from config.settings import get_settings
from config.logging_config import get_logger
from services.gmail_service import GmailService
from services.claude_service import ClaudeService
from services.notion_service import NotionService
from services.geocoding_service import GeocodingService
from services.storage_service import StorageService
from processors.attachment_processor import AttachmentProcessor
from processors.content_extractor import ContentExtractor
from processors.deduplication import Deduplicator
from models.notion_schemas import NotionItemCreate

logger = get_logger(__name__)


class EmailProcessor:
    """
    Main orchestrator for email processing pipeline.
    Processes emails from Gmail and creates structured entries in Notion.
    """

    def __init__(self):
        """Initialize email processor with all required services."""
        self.settings = get_settings()

        # Initialize services
        self.gmail = GmailService()
        self.claude = ClaudeService()
        self.notion = NotionService()
        self.geocoding = GeocodingService()
        self.storage = StorageService()

        # Initialize processors
        self.attachment_processor = AttachmentProcessor()
        self.content_extractor = ContentExtractor()
        self.deduplicator = Deduplicator(self.notion)

        # Statistics
        self.stats = {
            'processed': 0,
            'duplicates': 0,
            'errors': 0,
        }

    async def process_new_emails(self) -> None:
        """
        Main entry point: Poll Gmail and process all new emails.
        """
        logger.info("Starting email processing cycle")

        try:
            # Poll Gmail for new emails
            message_ids = self.gmail.poll_emails()

            if not message_ids:
                logger.info("No new emails to process")
                return

            logger.info(f"Found {len(message_ids)} emails to process")

            # Process each email
            for message_id in message_ids:
                try:
                    await self.process_single_email(message_id)
                    self.stats['processed'] += 1

                except Exception as e:
                    logger.error(
                        f"Error processing email {message_id}: {e}",
                        exc_info=True,
                        extra={'email_id': message_id}
                    )
                    self.stats['errors'] += 1

            # Log summary
            logger.info(
                f"Email processing cycle complete: "
                f"{self.stats['processed']} processed, "
                f"{self.stats['duplicates']} duplicates, "
                f"{self.stats['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Error in email processing cycle: {e}", exc_info=True)
            raise

    async def process_single_email(self, message_id: str) -> None:
        """
        Process a single email through the complete pipeline.

        Args:
            message_id: Gmail message ID
        """
        logger.info(f"Processing email: {message_id}", extra={'email_id': message_id})

        # Step 1: Retrieve email details
        email_data = self.gmail.get_email_details(message_id)

        logger.info(
            f"Retrieved email: '{email_data.subject}' from {email_data.sender_email}",
            extra={'email_id': message_id}
        )

        # Step 2: Check for duplicates
        duplicate = self.deduplicator.check_duplicate(email_data)
        if duplicate:
            logger.info(
                f"Skipping duplicate email: {email_data.subject}",
                extra={'email_id': message_id, 'notion_item_id': duplicate.notion_id}
            )
            self.stats['duplicates'] += 1
            # Still mark as processed to prevent reprocessing
            self.gmail.mark_as_processed(message_id)
            return

        # Step 3: Download all attachments
        if email_data.has_attachments:
            logger.info(
                f"Downloading {len(email_data.attachments)} attachments",
                extra={'email_id': message_id}
            )
            self.gmail.download_all_attachments(email_data)

        # Step 4: Process attachments
        attachment_result = self.attachment_processor.process_all_attachments(
            email_data.attachments
        )

        combined_text = attachment_result['combined_text']
        images = attachment_result['images']
        unsupported = attachment_result['unsupported']

        logger.info(
            f"Processed attachments: {len(combined_text)} chars text, "
            f"{len(images)} images, {len(unsupported)} unsupported",
            extra={'email_id': message_id}
        )

        # Step 5: Analyze with Claude
        logger.info("Analyzing email with Claude AI", extra={'email_id': message_id})

        # Text analysis
        extracted_data = self.claude.analyze_email_text(
            subject=email_data.subject,
            email_body=email_data.body_text,
            attachment_text=combined_text
        )

        # Vision analysis (if images)
        image_analysis = ""
        if images:
            logger.info(f"Analyzing {len(images)} images with Claude vision", extra={'email_id': message_id})
            image_analysis = self.claude.analyze_images(images)

        # Structure the data
        structured_data = self.content_extractor.extract_structured_data(
            extracted_data,
            email_data
        )

        # Step 6: Detect related items and projects
        logger.info("Detecting related items and projects", extra={'email_id': message_id})

        # Get recent items and active projects for relationship detection
        from models.notion_schemas import NotionQueryFilter, NotionQuerySort

        recent_items = self.notion.query_items(
            sorts=[NotionQuerySort(property_name="Date Received", direction="descending")],
            limit=20
        )

        active_project_filter = NotionQueryFilter(
            property_name="Status",
            property_type="select",
            condition="equals",
            value="active"
        )
        active_projects = self.notion.query_projects(filters=[active_project_filter])

        related_item_ids, suggested_project_id = self.claude.detect_related_items(
            new_title=structured_data['title'],
            new_summary=structured_data['summary'],
            new_locations=structured_data['locations'],
            new_tags=structured_data['tags'],
            new_project_type=structured_data['project_type'],
            existing_items=recent_items,
            existing_projects=active_projects
        )

        # Step 7: Geocode locations
        geocoded_json = ""
        if structured_data['locations'] and self.geocoding.is_enabled():
            logger.info(
                f"Geocoding {len(structured_data['locations'])} locations",
                extra={'email_id': message_id}
            )
            geocoded_json = self.geocoding.geocode_locations_as_json(
                structured_data['locations']
            )

        # Step 8: Upload attachments to Google Drive
        drive_urls = {}
        if email_data.has_attachments:
            logger.info(
                f"Uploading {len(email_data.attachments)} attachments to Drive",
                extra={'email_id': message_id}
            )
            drive_urls = self.storage.upload_attachments(email_data.attachments)

        attachment_urls_json = self.content_extractor.format_attachment_urls(drive_urls)

        # Step 9: Create Notion Item
        logger.info("Creating Notion item", extra={'email_id': message_id})

        notion_item_data = NotionItemCreate(
            title=structured_data['title'][:100],  # Limit title length
            summary=structured_data['summary'],
            date_received=email_data.date_received,
            gmail_message_id=email_data.message_id,
            sender_email=email_data.sender_email,
            has_attachments=email_data.has_attachments,
            consultation_deadline=structured_data.get('consultation_deadline'),
            action_due_date=structured_data.get('action_due_date'),
            original_estimated_completion=structured_data.get('original_estimated_completion'),
            project_type=structured_data['project_type'],
            action_required=structured_data['action_required'],
            tags=structured_data['tags'],
            locations=structured_data['locations'],
            geocoded_coordinates=geocoded_json,
            ai_key_points=structured_data['ai_key_points'],
            related_past_items=related_item_ids,
            link_to_consultation=None,  # Could be extracted from email links
            attachment_urls=attachment_urls_json,
            attachment_analysis=image_analysis,
            related_project=suggested_project_id,
            status="new",
            priority=structured_data['priority'],
            processing_status="ai_complete"
        )

        notion_item = self.notion.create_item(notion_item_data)

        logger.info(
            f"Created Notion item: {notion_item.title}",
            extra={'email_id': message_id, 'notion_item_id': notion_item.notion_id}
        )

        # Step 10: Mark email as processed in Gmail
        self.gmail.mark_as_processed(message_id)

        logger.info(
            f"Successfully processed email: {email_data.subject}",
            extra={'email_id': message_id, 'notion_item_id': notion_item.notion_id}
        )

    def get_statistics(self) -> dict:
        """Get processing statistics."""
        return self.stats.copy()

    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.stats = {
            'processed': 0,
            'duplicates': 0,
            'errors': 0,
        }
