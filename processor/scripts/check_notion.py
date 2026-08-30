
import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from services.notion_service import NotionService
from models.notion_schemas import NotionItemCreate
from datetime import datetime, timezone

# Initialize service
notion = NotionService()

# Try to create a test item
test_item = NotionItemCreate(
    title="Test Item - Please Delete",
    summary="This is a test item created by the setup script.",
    date_received=datetime.now(timezone.utc),
    status="new",
    priority="low",
    processing_status="needs_review"
)

try:
    created_item = notion.create_item(test_item)
    print(f"✓ Success! Created test item: {created_item.url}")
    print(f"✓ Item ID: {created_item.notion_id}")
    print("\nYou can now delete this test item from your Notion database.")
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nCheck that:")
    print("1. All database IDs are correct in .env")
    print("2. Notion integration has access to all databases")
    print("3. Property names match exactly (case-sensitive)")


