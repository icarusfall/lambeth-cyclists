"""
Gmail API service for email monitoring and retrieval.
Handles OAuth authentication, email polling, and attachment download.
"""

import os
import base64
import tempfile
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import get_settings, GMAIL_SCOPES, GMAIL_PROCESSED_LABEL
from config.logging_config import get_logger
from models.email_data import EmailData, EmailAttachment

logger = get_logger(__name__)


class GmailService:
    """
    Service for interacting with Gmail API.
    Handles authentication, email polling, retrieval, and labeling.
    """

    def __init__(self):
        """Initialize Gmail service with OAuth credentials."""
        self.settings = get_settings()
        self.credentials: Optional[Credentials] = None
        self.service = None
        self.temp_dir = tempfile.mkdtemp(prefix="lambeth_cyclists_")

    def authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth 2.0.
        Uses refresh token from environment variables.
        """
        try:
            # Build credentials from environment variables
            self.credentials = Credentials(
                token=None,
                refresh_token=self.settings.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.gmail_client_id,
                client_secret=self.settings.gmail_client_secret,
                scopes=GMAIL_SCOPES
            )

            # Refresh the credentials
            if self.credentials.expired or not self.credentials.valid:
                self.credentials.refresh(Request())

            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.credentials)

            logger.info("Successfully authenticated with Gmail API")

        except Exception as e:
            logger.error(f"Failed to authenticate with Gmail API: {e}", exc_info=True)
            raise

    def ensure_authenticated(self) -> None:
        """Ensure service is authenticated, authenticate if needed."""
        if self.service is None:
            self.authenticate()

    def poll_emails(self) -> List[str]:
        """
        Poll Gmail for new unprocessed emails with the target label.

        Returns:
            List of Gmail message IDs to process
        """
        self.ensure_authenticated()

        try:
            # Build query: has target label AND doesn't have processed label
            query = f'label:{self.settings.gmail_label} -label:{GMAIL_PROCESSED_LABEL}'

            # Query Gmail
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50  # Process up to 50 emails per poll
            ).execute()

            messages = results.get('messages', [])

            if messages:
                message_ids = [msg['id'] for msg in messages]
                logger.info(f"Found {len(message_ids)} new emails to process")
                return message_ids
            else:
                logger.debug("No new emails found")
                return []

        except HttpError as e:
            logger.error(f"Gmail API error while polling: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error while polling Gmail: {e}", exc_info=True)
            raise

    def get_email_details(self, message_id: str) -> EmailData:
        """
        Retrieve full email details including body and attachments.

        Args:
            message_id: Gmail message ID

        Returns:
            EmailData object with complete email information
        """
        self.ensure_authenticated()

        try:
            # Get message with full format
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Parse email metadata
            headers = {header['name'].lower(): header['value']
                      for header in message['payload']['headers']}

            # Extract sender info
            sender_raw = headers.get('from', '')
            sender_email, sender_name = self._parse_sender(sender_raw)

            # Extract recipients
            to_raw = headers.get('to', '')
            recipient_emails = self._parse_recipients(to_raw)

            # Parse date
            date_str = headers.get('date', '')
            date_received = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()

            # Extract body
            body_plain, body_html = self._extract_body(message['payload'])

            # Extract attachments
            attachments = []
            if 'parts' in message['payload']:
                attachments = self._extract_attachments(message_id, message['payload']['parts'])

            # Get labels
            label_ids = message.get('labelIds', [])

            # Build EmailData object
            email_data = EmailData(
                message_id=message_id,
                thread_id=message['threadId'],
                subject=headers.get('subject', '(No Subject)'),
                sender_email=sender_email,
                sender_name=sender_name,
                recipient_emails=recipient_emails,
                date_received=date_received,
                body_plain=body_plain,
                body_html=body_html,
                snippet=message.get('snippet'),
                attachments=attachments,
                has_attachments=len(attachments) > 0,
                labels=label_ids,
                processed=False
            )

            logger.info(
                f"Retrieved email: {email_data.subject} from {email_data.sender_email} "
                f"({len(attachments)} attachments)",
                extra={'email_id': message_id}
            )

            return email_data

        except HttpError as e:
            logger.error(f"Gmail API error retrieving message {message_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error retrieving email {message_id}: {e}", exc_info=True)
            raise

    def _parse_sender(self, sender_raw: str) -> tuple[str, Optional[str]]:
        """Parse sender email and name from 'From' header."""
        # Format: "Name <email@example.com>" or just "email@example.com"
        if '<' in sender_raw and '>' in sender_raw:
            name_part = sender_raw.split('<')[0].strip().strip('"')
            email_part = sender_raw.split('<')[1].split('>')[0].strip()
            return email_part, name_part if name_part else None
        else:
            return sender_raw.strip(), None

    def _parse_recipients(self, to_raw: str) -> List[str]:
        """Parse recipient emails from 'To' header."""
        if not to_raw:
            return []

        # Split by comma and extract emails
        recipients = []
        for recipient in to_raw.split(','):
            if '<' in recipient and '>' in recipient:
                email = recipient.split('<')[1].split('>')[0].strip()
            else:
                email = recipient.strip()

            # Filter out invalid emails (must have @)
            if email and '@' in email and ':' not in email and ';' not in email:
                recipients.append(email)

        return recipients

    def _extract_body(self, payload: dict) -> tuple[Optional[str], Optional[str]]:
        """Extract plain text and HTML body from message payload."""
        body_plain = None
        body_html = None

        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')

                if mime_type == 'text/plain' and 'data' in part.get('body', {}):
                    body_plain = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')

                elif mime_type == 'text/html' and 'data' in part.get('body', {}):
                    body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')

                # Recursively check nested parts
                elif 'parts' in part:
                    nested_plain, nested_html = self._extract_body(part)
                    if nested_plain and not body_plain:
                        body_plain = nested_plain
                    if nested_html and not body_html:
                        body_html = nested_html

        # Single-part message
        elif 'body' in payload and 'data' in payload['body']:
            mime_type = payload.get('mimeType', '')
            data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

            if mime_type == 'text/plain':
                body_plain = data
            elif mime_type == 'text/html':
                body_html = data

        return body_plain, body_html

    def _extract_attachments(self, message_id: str, parts: List[dict]) -> List[EmailAttachment]:
        """Extract attachment metadata from message parts."""
        attachments = []

        for part in parts:
            # Check if this part is an attachment
            if part.get('filename') and 'body' in part and 'attachmentId' in part['body']:
                attachment = EmailAttachment(
                    filename=part['filename'],
                    mime_type=part['mimeType'],
                    size_bytes=part['body'].get('size', 0),
                    attachment_id=part['body']['attachmentId']
                )
                attachments.append(attachment)

            # Recursively check nested parts
            if 'parts' in part:
                nested_attachments = self._extract_attachments(message_id, part['parts'])
                attachments.extend(nested_attachments)

        return attachments

    def download_attachment(self, message_id: str, attachment: EmailAttachment) -> str:
        """
        Download an attachment and save to temporary directory.

        Args:
            message_id: Gmail message ID
            attachment: EmailAttachment object

        Returns:
            Local file path where attachment was saved
        """
        self.ensure_authenticated()

        try:
            # Get attachment data from Gmail API
            att_data = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment.attachment_id
            ).execute()

            # Decode attachment data
            file_data = base64.urlsafe_b64decode(att_data['data'])

            # Save to temp directory
            file_path = Path(self.temp_dir) / attachment.filename
            with open(file_path, 'wb') as f:
                f.write(file_data)

            # Update attachment object
            attachment.data = file_data
            attachment.local_path = str(file_path)

            logger.debug(
                f"Downloaded attachment: {attachment.filename} ({attachment.size_bytes} bytes)",
                extra={'email_id': message_id}
            )

            return str(file_path)

        except HttpError as e:
            logger.error(
                f"Gmail API error downloading attachment {attachment.filename}: {e}",
                exc_info=True,
                extra={'email_id': message_id}
            )
            raise
        except Exception as e:
            logger.error(
                f"Error downloading attachment {attachment.filename}: {e}",
                exc_info=True,
                extra={'email_id': message_id}
            )
            raise

    def download_all_attachments(self, email_data: EmailData) -> List[str]:
        """
        Download all attachments for an email.

        Args:
            email_data: EmailData object with attachments

        Returns:
            List of local file paths where attachments were saved
        """
        if not email_data.has_attachments:
            return []

        file_paths = []
        for attachment in email_data.attachments:
            try:
                file_path = self.download_attachment(email_data.message_id, attachment)
                file_paths.append(file_path)
            except Exception as e:
                logger.warning(
                    f"Failed to download attachment {attachment.filename}: {e}",
                    extra={'email_id': email_data.message_id}
                )
                # Continue with other attachments even if one fails

        logger.info(
            f"Downloaded {len(file_paths)}/{len(email_data.attachments)} attachments",
            extra={'email_id': email_data.message_id}
        )

        return file_paths

    def mark_as_processed(self, message_id: str) -> None:
        """
        Mark email as processed by adding the 'processed' label.

        Args:
            message_id: Gmail message ID
        """
        self.ensure_authenticated()

        try:
            # Get or create 'processed' label
            label_id = self._get_or_create_label(GMAIL_PROCESSED_LABEL)

            # Add label to message
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()

            logger.info(f"Marked email as processed", extra={'email_id': message_id})

        except HttpError as e:
            logger.error(
                f"Gmail API error marking email as processed: {e}",
                exc_info=True,
                extra={'email_id': message_id}
            )
            raise
        except Exception as e:
            logger.error(
                f"Error marking email as processed: {e}",
                exc_info=True,
                extra={'email_id': message_id}
            )
            raise

    def _get_or_create_label(self, label_name: str) -> str:
        """
        Get label ID by name, create if doesn't exist.

        Args:
            label_name: Name of the label

        Returns:
            Gmail label ID
        """
        try:
            # List all labels
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            # Find label by name
            for label in labels:
                if label['name'].lower() == label_name.lower():
                    return label['id']

            # Label doesn't exist, create it
            logger.info(f"Creating Gmail label: {label_name}")

            label_body = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }

            created_label = self.service.users().labels().create(
                userId='me',
                body=label_body
            ).execute()

            return created_label['id']

        except HttpError as e:
            logger.error(f"Gmail API error with labels: {e}", exc_info=True)
            raise

    def cleanup(self) -> None:
        """Clean up temporary directory and files."""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")

    def __del__(self):
        """Cleanup on object destruction."""
        self.cleanup()
