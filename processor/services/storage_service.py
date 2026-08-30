"""
Google Drive storage service for uploading email attachments.
Handles file uploads to a specified Drive folder and returns shareable URLs.
"""

from typing import List, Dict
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config.settings import get_settings, GMAIL_SCOPES
from config.logging_config import get_logger
from models.email_data import EmailAttachment

logger = get_logger(__name__)


class StorageService:
    """
    Service for uploading attachments to Google Drive.
    Uses same OAuth credentials as Gmail API.
    """

    def __init__(self):
        """Initialize Google Drive service."""
        self.settings = get_settings()
        self.credentials: Credentials = None
        self.service = None
        self.folder_id = self.settings.google_drive_folder_id

    def authenticate(self) -> None:
        """
        Authenticate with Google Drive API using OAuth 2.0.
        Reuses Gmail OAuth credentials.
        """
        try:
            # Build credentials from environment variables
            self.credentials = Credentials(
                token=None,
                refresh_token=self.settings.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.gmail_client_id,
                client_secret=self.settings.gmail_client_secret,
                scopes=GMAIL_SCOPES  # Includes drive.file scope
            )

            # Refresh the credentials
            if self.credentials.expired or not self.credentials.valid:
                self.credentials.refresh(Request())

            # Build Drive service
            self.service = build('drive', 'v3', credentials=self.credentials)

            logger.info("Successfully authenticated with Google Drive API")

        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive API: {e}", exc_info=True)
            raise

    def ensure_authenticated(self) -> None:
        """Ensure service is authenticated, authenticate if needed."""
        if self.service is None:
            self.authenticate()

    def upload_file(
        self,
        file_path: str,
        filename: str,
        mime_type: str
    ) -> str:
        """
        Upload a file to Google Drive folder.

        Args:
            file_path: Local path to file
            filename: Name for file in Drive
            mime_type: MIME type of file

        Returns:
            Shareable URL to the uploaded file
        """
        self.ensure_authenticated()

        try:
            # File metadata
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }

            # Upload file
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )

            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()

            file_id = file.get('id')

            # Make file accessible to anyone with the link
            self._make_file_public(file_id)

            # Get shareable link
            url = file.get('webViewLink') or file.get('webContentLink')

            logger.info(f"Uploaded file to Drive: {filename} -> {url}")

            return url

        except HttpError as e:
            logger.error(f"Google Drive API error uploading {filename}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error uploading {filename} to Drive: {e}", exc_info=True)
            raise

    def upload_attachments(
        self,
        attachments: List[EmailAttachment]
    ) -> Dict[str, str]:
        """
        Upload multiple attachments to Google Drive.

        Args:
            attachments: List of EmailAttachment objects with local_path set

        Returns:
            Dictionary mapping filename to Drive URL
        """
        urls = {}

        for attachment in attachments:
            if not attachment.local_path or not Path(attachment.local_path).exists():
                logger.warning(f"Skipping {attachment.filename}: file not found")
                continue

            try:
                url = self.upload_file(
                    file_path=attachment.local_path,
                    filename=attachment.filename,
                    mime_type=attachment.mime_type
                )

                urls[attachment.filename] = url
                attachment.drive_url = url

            except Exception as e:
                logger.error(f"Failed to upload {attachment.filename}: {e}")
                # Continue with other attachments even if one fails

        logger.info(f"Uploaded {len(urls)}/{len(attachments)} attachments to Drive")

        return urls

    def _make_file_public(self, file_id: str) -> None:
        """
        Make a file accessible to anyone with the link.

        Args:
            file_id: Google Drive file ID
        """
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }

            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()

            logger.debug(f"Made file {file_id} publicly accessible")

        except HttpError as e:
            logger.error(f"Error making file {file_id} public: {e}", exc_info=True)
            raise

    def get_folder_info(self) -> Dict[str, str]:
        """
        Get information about the Drive folder.

        Returns:
            Dictionary with folder name and URL
        """
        self.ensure_authenticated()

        try:
            folder = self.service.files().get(
                fileId=self.folder_id,
                fields='id, name, webViewLink'
            ).execute()

            return {
                'id': folder.get('id'),
                'name': folder.get('name'),
                'url': folder.get('webViewLink')
            }

        except HttpError as e:
            logger.error(f"Error getting folder info: {e}", exc_info=True)
            raise

    def verify_folder_access(self) -> bool:
        """
        Verify that the configured folder exists and is accessible.

        Returns:
            True if folder is accessible, False otherwise
        """
        try:
            folder_info = self.get_folder_info()
            logger.info(f"Drive folder verified: {folder_info['name']} ({folder_info['url']})")
            return True

        except Exception as e:
            logger.error(f"Cannot access Drive folder {self.folder_id}: {e}")
            return False
