"""
Configuration settings for Lambeth Cyclists Email Processor.
Loads environment variables and provides validation.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gmail API Configuration
    gmail_client_id: str = Field(..., env="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(..., env="GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = Field(..., env="GMAIL_REFRESH_TOKEN")
    gmail_label: str = Field(default="Lambeth Cycling Projects", env="GMAIL_LABEL")

    # Claude API
    claude_api_key: str = Field(..., env="CLAUDE_API_KEY")

    # Notion API
    notion_api_key: str = Field(..., env="NOTION_API_KEY")
    notion_items_db_id: str = Field(..., env="NOTION_ITEMS_DB_ID")
    notion_projects_db_id: str = Field(..., env="NOTION_PROJECTS_DB_ID")
    notion_meetings_db_id: str = Field(..., env="NOTION_MEETINGS_DB_ID")

    # Google Maps API (optional)
    google_maps_api_key: Optional[str] = Field(default=None, env="GOOGLE_MAPS_API_KEY")

    # Google Drive Configuration
    google_drive_folder_id: str = Field(..., env="GOOGLE_DRIVE_FOLDER_ID")

    # Application Configuration
    email_poll_interval: int = Field(default=300, env="EMAIL_POLL_INTERVAL")
    meeting_check_interval: int = Field(default=3600, env="MEETING_CHECK_INTERVAL")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    admin_email: str = Field(..., env="ADMIN_EMAIL")

    # Rate Limits
    claude_rpm: int = Field(default=50, env="CLAUDE_RPM")
    gmail_qpm: int = Field(default=250, env="GMAIL_QPM")
    notion_rpm: int = Field(default=3, env="NOTION_RPM")

    # Email Alerts Configuration (Resend API)
    resend_api_key: Optional[str] = Field(default=None, env="RESEND_API_KEY")
    from_email: str = Field(default="Lambeth Cyclists <onboarding@resend.dev>", env="FROM_EMAIL")
    alert_email: Optional[str] = Field(default=None, env="ALERT_EMAIL")

    # Error Monitoring (optional)
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @field_validator("email_poll_interval", "meeting_check_interval")
    @classmethod
    def validate_positive_interval(cls, v: int) -> int:
        """Validate intervals are positive."""
        if v <= 0:
            raise ValueError("Interval must be positive")
        return v

    model_config = SettingsConfigDict(
        # Resolved against this package, not the working directory, so the
        # daemon and the tests both find it wherever they are started from.
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Tolerate leftover keys in .env (e.g. the SMTP_* vars superseded by
        # Resend) instead of refusing to start. Matches the portal's config.
        extra="ignore",
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the application settings singleton.
    Loads settings from environment on first call.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def validate_settings() -> None:
    """
    Validate that all required settings are present.
    Raises ValueError if any required settings are missing.
    """
    try:
        settings = get_settings()

        # Check critical API keys
        required_keys = [
            ("Gmail Client ID", settings.gmail_client_id),
            ("Gmail Client Secret", settings.gmail_client_secret),
            ("Gmail Refresh Token", settings.gmail_refresh_token),
            ("Claude API Key", settings.claude_api_key),
            ("Notion API Key", settings.notion_api_key),
            ("Notion Items DB ID", settings.notion_items_db_id),
            ("Notion Projects DB ID", settings.notion_projects_db_id),
            ("Notion Meetings DB ID", settings.notion_meetings_db_id),
            ("Google Drive Folder ID", settings.google_drive_folder_id),
            ("Admin Email", settings.admin_email),
        ]

        missing = [name for name, value in required_keys if not value or value == "your-" or value.startswith("secret_your")]

        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        print("✓ Configuration validated successfully")

    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        raise


# Constants
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive"  # Full Drive access for folder access
]

GMAIL_PROCESSED_LABEL = "processed"

# Notion property names (for consistency)
NOTION_PROPS = {
    "title": "Title",
    "summary": "Summary",
    "date_received": "Date Received",
    "gmail_message_id": "Gmail Message ID",
    "sender_email": "Sender Email",
    "has_attachments": "Has Attachments",
    "consultation_deadline": "Consultation Deadline",
    "action_due_date": "Action Due Date",
    "original_estimated_completion": "Original Estimated Completion",
    "project_type": "Project Type",
    "action_required": "Action Required",
    "tags": "Tags",
    "locations": "Locations",
    "geocoded_coordinates": "Geocoded Coordinates",
    "ai_key_points": "AI Key Points",
    "lambeth_cyclist_thoughts": "Lambeth Cyclist Thoughts",
    "related_past_items": "Related Past Items",
    "link_to_consultation": "Link to Consultation",
    "attachment_urls": "Attachment URLs",
    "attachment_analysis": "Attachment Analysis",
    "related_project": "Related Project",
    "discussed_in_meetings": "Discussed in Meetings",
    "status": "Status",
    "priority": "Priority",
    "processing_status": "Processing Status",
}

# Notion select options
PROJECT_TYPES = ["traffic_order", "consultation", "infrastructure_project", "event", "other"]
ACTION_REQUIRED_OPTIONS = ["response_needed", "information_only", "monitoring", "urgent_action"]
STATUS_OPTIONS = ["new", "reviewed", "response_drafted", "submitted", "monitoring", "closed"]
PRIORITY_OPTIONS = ["critical", "high", "medium", "low"]
PROCESSING_STATUS_OPTIONS = ["pending_ai_analysis", "ai_complete", "needs_review", "approved", "migrated"]
