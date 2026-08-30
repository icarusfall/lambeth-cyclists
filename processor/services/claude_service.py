"""
Claude AI service for email analysis and content extraction.
Handles text analysis, vision analysis for images, and relationship detection.
"""

import json
import base64
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from anthropic import Anthropic
from anthropic.types import Message

from core.claude import MODEL, response_text_of

from config.settings import get_settings
from config.logging_config import get_logger
from models.prompts import (
    format_text_extraction_prompt,
    format_relationship_detection_prompt,
    format_discussion_prompts_prompt,
    format_agenda_summary_prompt,
    VISION_ANALYSIS_PROMPT
)
from models.email_data import EmailAttachment

logger = get_logger(__name__)

class ClaudeService:
    """
    Service for interacting with Claude AI API.
    Handles email analysis, vision analysis, and relationship detection.
    """

    def __init__(self):
        """Initialize Claude service with API credentials."""
        self.settings = get_settings()
        self.client = Anthropic(api_key=self.settings.claude_api_key)
        self.model = MODEL

    def analyze_email_text(
        self,
        subject: str,
        email_body: str,
        attachment_text: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze email text and extract structured data.

        Args:
            subject: Email subject line
            email_body: Email body content
            attachment_text: Combined text from PDF/Word attachments

        Returns:
            Dictionary with extracted structured data
        """
        try:
            # Format prompt
            prompt = format_text_extraction_prompt(subject, email_body, attachment_text)

            # Call Claude API
            logger.debug("Calling Claude API for text extraction")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract response
            response_text = response_text_of(message)

            # Parse JSON response
            extracted_data = self._parse_json_response(response_text)

            logger.info(
                f"Extracted data from email: {extracted_data.get('title', 'Unknown')}"
            )

            return extracted_data

        except Exception as e:
            logger.error(f"Error analyzing email text with Claude: {e}", exc_info=True)
            # Return minimal data on error
            return {
                "title": subject[:100],
                "summary": "Error analyzing email content. Manual review required.",
                "consultation_deadline": None,
                "action_due_date": None,
                "original_estimated_completion": None,
                "project_type": "other",
                "action_required": "needs_review",
                "priority": "medium",
                "tags": [],
                "locations": [],
                "ai_key_points": f"- Error during AI analysis: {str(e)}\n- Manual review required"
            }

    def analyze_images(self, images: List[EmailAttachment]) -> str:
        """
        Analyze images using Claude's vision capabilities.

        Args:
            images: List of image attachments with local_path set

        Returns:
            Combined analysis text from all images
        """
        if not images:
            return ""

        analyses = []

        for i, image in enumerate(images):
            try:
                analysis = self._analyze_single_image(image)
                analyses.append(f"**Image {i+1}: {image.filename}**\n\n{analysis}")
                logger.info(f"Analyzed image: {image.filename}")

            except Exception as e:
                logger.error(f"Error analyzing image {image.filename}: {e}", exc_info=True)
                analyses.append(f"**Image {i+1}: {image.filename}**\n\nError analyzing image: {str(e)}")

        return "\n\n---\n\n".join(analyses)

    def _analyze_single_image(self, image: EmailAttachment) -> str:
        """Analyze a single image with Claude vision."""
        if not image.local_path or not Path(image.local_path).exists():
            raise ValueError(f"Image file not found: {image.local_path}")

        # Read and encode image
        with open(image.local_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        # Determine media type
        media_type = self._get_media_type(image.mime_type)

        # Call Claude API with vision
        logger.debug(f"Calling Claude vision API for {image.filename}")
        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            output_config={"effort": "medium"},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": VISION_ANALYSIS_PROMPT
                    }
                ],
            }]
        )

        return response_text_of(message)

    def detect_related_items(
        self,
        new_title: str,
        new_summary: str,
        new_locations: List[str],
        new_tags: List[str],
        new_project_type: str,
        existing_items: List[Any],
        existing_projects: List[Any]
    ) -> Tuple[List[str], Optional[str]]:
        """
        Detect related past items and suggest project match.

        Args:
            new_title: Title of new item
            new_summary: Summary of new item
            new_locations: Locations mentioned in new item
            new_tags: Tags for new item
            new_project_type: Project type of new item
            existing_items: List of existing NotionItem objects
            existing_projects: List of existing NotionProject objects

        Returns:
            Tuple of (related_item_ids, suggested_project_id)
        """
        if not existing_items and not existing_projects:
            return ([], None)

        try:
            # Format prompt
            prompt = format_relationship_detection_prompt(
                new_title=new_title,
                new_summary=new_summary,
                new_locations=new_locations,
                new_tags=new_tags,
                new_project_type=new_project_type,
                existing_items=existing_items,
                existing_projects=existing_projects
            )

            # Call Claude API
            logger.debug("Calling Claude API for relationship detection")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response_text_of(message)
            result = self._parse_json_response(response_text)

            related_items = result.get("related_item_ids", [])
            suggested_project = result.get("suggested_project_id")
            confidence = result.get("project_match_confidence")

            # Only use project suggestion if confidence is high
            if confidence != "high":
                suggested_project = None

            logger.info(
                f"Found {len(related_items)} related items, "
                f"project match: {suggested_project or 'none'}"
            )

            return (related_items, suggested_project)

        except Exception as e:
            logger.error(f"Error detecting relationships with Claude: {e}", exc_info=True)
            return ([], None)

    def generate_discussion_prompts(self, critical_items: List[Any]) -> Dict[str, List[str]]:
        """
        Generate discussion prompts for critical meeting items.

        Args:
            critical_items: List of NotionItem objects (most critical/urgent)

        Returns:
            Dictionary mapping item IDs to list of discussion prompts
        """
        if not critical_items:
            return {}

        try:
            prompt = format_discussion_prompts_prompt(critical_items)

            logger.debug("Calling Claude API for discussion prompts")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                output_config={"effort": "medium"},
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response_text_of(message)
            prompts = self._parse_json_response(response_text)

            logger.info(f"Generated discussion prompts for {len(prompts)} items")

            return prompts

        except Exception as e:
            logger.error(f"Error generating discussion prompts: {e}", exc_info=True)
            return {}

    def generate_agenda_summary(
        self,
        meeting_date: str,
        item_count: int,
        deadline_count: int,
        project_count: int,
        top_items: List[Any]
    ) -> str:
        """
        Generate opening summary for meeting agenda.

        Args:
            meeting_date: Date of meeting
            item_count: Number of items since last meeting
            deadline_count: Number of upcoming deadlines
            project_count: Number of active projects
            top_items: List of top priority NotionItem objects

        Returns:
            Summary text for agenda opening
        """
        try:
            prompt = format_agenda_summary_prompt(
                meeting_date=meeting_date,
                item_count=item_count,
                deadline_count=deadline_count,
                project_count=project_count,
                top_items=top_items
            )

            logger.debug("Calling Claude API for agenda summary")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                output_config={"effort": "low"},
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            summary = response_text_of(message)

            logger.info("Generated meeting agenda summary")

            return summary

        except Exception as e:
            logger.error(f"Error generating agenda summary: {e}", exc_info=True)
            return f"Committee meeting on {meeting_date}. {item_count} items received since last meeting."

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from Claude's response, handling markdown code blocks.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed JSON dictionary
        """
        # Remove markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        # Parse JSON
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON in Claude response: {e}")

    def _get_media_type(self, mime_type: str) -> str:
        """Convert MIME type to Claude-compatible media type."""
        # Claude supports: image/jpeg, image/png, image/gif, image/webp
        mime_mapping = {
            "image/jpeg": "image/jpeg",
            "image/jpg": "image/jpeg",
            "image/png": "image/png",
            "image/gif": "image/gif",
            "image/webp": "image/webp",
        }

        return mime_mapping.get(mime_type.lower(), "image/jpeg")
