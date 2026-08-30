"""
Test script to verify all API connections are working.
Run this before processing emails to ensure everything is configured correctly.
"""

import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from config.logging_config import setup_logging, get_logger
from services.gmail_service import GmailService
from services.notion_service import NotionService
from services.claude_service import ClaudeService
from services.storage_service import StorageService

setup_logging(level="INFO", use_json=False)
logger = get_logger(__name__)

print("="*60)
print("Testing API Connections")
print("="*60)

# Test Gmail
try:
    gmail = GmailService()
    gmail.authenticate()
    print("✓ Gmail API: Connected")
except Exception as e:
    print(f"✗ Gmail API: Failed - {e}")

# Test Notion
try:
    notion = NotionService()
    # Try to query items (should work even if empty)
    items = notion.query_items(limit=1)
    print(f"✓ Notion API: Connected ({len(items)} items in database)")
except Exception as e:
    print(f"✗ Notion API: Failed - {e}")

# Test Claude (just verify client creation)
try:
    claude = ClaudeService()
    print("✓ Claude API: Client created")
except Exception as e:
    print(f"✗ Claude API: Failed - {e}")

# Test Google Drive
try:
    storage = StorageService()
    storage.authenticate()
    if storage.verify_folder_access():
        folder_info = storage.get_folder_info()
        print(f"✓ Google Drive: Connected")
        print(f"  Folder: {folder_info['name']}")
    else:
        print("✗ Google Drive: Cannot access folder")
except Exception as e:
    print(f"✗ Google Drive: Failed - {e}")

print("="*60)
print("Connection tests complete!")
print("="*60)
