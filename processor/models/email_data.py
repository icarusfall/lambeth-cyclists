"""
Pydantic models for email data structures.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class EmailAttachment(BaseModel):
    """Represents an email attachment."""

    filename: str = Field(..., description="Name of the attachment file")
    mime_type: str = Field(..., description="MIME type of the attachment")
    size_bytes: int = Field(..., description="Size of attachment in bytes")
    attachment_id: str = Field(..., description="Gmail attachment ID")
    data: Optional[bytes] = Field(default=None, description="Binary data of attachment")
    local_path: Optional[str] = Field(default=None, description="Path where attachment is saved locally")
    drive_url: Optional[str] = Field(default=None, description="Google Drive URL after upload")

    class Config:
        arbitrary_types_allowed = True


class EmailData(BaseModel):
    """
    Structured representation of an email from Gmail.
    Contains metadata, body, and attachments.
    """

    # Gmail metadata
    message_id: str = Field(..., description="Gmail message ID (unique identifier)")
    thread_id: str = Field(..., description="Gmail thread ID")
    subject: str = Field(..., description="Email subject line")
    sender_email: EmailStr = Field(..., description="Sender email address")
    sender_name: Optional[str] = Field(default=None, description="Sender display name")
    recipient_emails: List[str] = Field(default_factory=list, description="Recipient email addresses (pre-validated)")
    date_received: datetime = Field(..., description="When email was received")

    # Email content
    body_plain: Optional[str] = Field(default=None, description="Plain text email body")
    body_html: Optional[str] = Field(default=None, description="HTML email body")
    snippet: Optional[str] = Field(default=None, description="Email snippet/preview")

    # Attachments
    attachments: List[EmailAttachment] = Field(default_factory=list, description="List of email attachments")
    has_attachments: bool = Field(default=False, description="Whether email has attachments")

    # Labels
    labels: List[str] = Field(default_factory=list, description="Gmail labels applied to email")

    # Processing metadata
    processed: bool = Field(default=False, description="Whether email has been processed")
    processing_error: Optional[str] = Field(default=None, description="Error message if processing failed")

    @property
    def body_text(self) -> str:
        """Get the best available email body text."""
        return self.body_plain or self.body_html or self.snippet or ""

    @property
    def attachment_count(self) -> int:
        """Get number of attachments."""
        return len(self.attachments)

    def get_attachments_by_type(self, mime_type_prefix: str) -> List[EmailAttachment]:
        """
        Get attachments matching a MIME type prefix.

        Args:
            mime_type_prefix: MIME type prefix to filter by (e.g., "image/", "application/pdf")

        Returns:
            List of matching attachments
        """
        return [att for att in self.attachments if att.mime_type.startswith(mime_type_prefix)]

    def get_image_attachments(self) -> List[EmailAttachment]:
        """Get all image attachments."""
        return self.get_attachments_by_type("image/")

    def get_pdf_attachments(self) -> List[EmailAttachment]:
        """Get all PDF attachments."""
        return self.get_attachments_by_type("application/pdf")

    def get_word_attachments(self) -> List[EmailAttachment]:
        """Get all Word document attachments."""
        word_types = [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
            "application/msword",  # .doc
        ]
        return [att for att in self.attachments if att.mime_type in word_types]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            bytes: lambda v: None,  # Don't serialize binary data to JSON
        }
