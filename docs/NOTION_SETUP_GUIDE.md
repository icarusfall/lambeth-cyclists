# Notion Database Setup Guide

This guide will walk you through creating the three Notion databases required for the Lambeth Cyclists Email Processor.

## Prerequisites

1. Access to your "Lambeth Cyclists Workspace" in Notion
2. Admin permissions to create databases

## Overview

You'll create three databases:
1. **Items** - Reactive, email-triggered entries (consultations, traffic orders, etc.)
2. **Projects** - Strategic, long-term initiatives (campaigns, ongoing work)
3. **Meetings** - Bi-monthly committee meetings with auto-generated agendas

## Step 1: Create the Items Database

### 1.1 Create New Database

1. In Notion, create a new page called "Items" (or "Lambeth Items")
2. Add a database (Database - Full page)
3. This will be your Items database

### 1.2 Add Properties

Add the following properties (exact names matter - they're case-sensitive):

**Basic Info:**
- `Title` - Title (default, already exists)
- `Summary` - Text

**Email Metadata:**
- `Date Received` - Date
- `Gmail Message ID` - Text
- `Sender Email` - Email
- `Has Attachments` - Checkbox

**Deadlines:**
- `Consultation Deadline` - Date
- `Action Due Date` - Date
- `Original Estimated Completion` - Date

**Categorization:**
- `Project Type` - Select
  - Options: traffic_order, consultation, infrastructure_project, event, other
- `Action Required` - Select
  - Options: response_needed, information_only, monitoring, urgent_action
- `Tags` - Multi-select
  - Add common tags: LTN, cycle_infrastructure, parking, public_realm, traffic_order, etc.

**Locations:**
- `Locations` - Multi-select
  - Add common locations: Brixton Hill, Clapham High Street, Lambeth Bridge, etc.
- `Geocoded Coordinates` - Text

**Content:**
- `AI Key Points` - Text
- `Lambeth Cyclist Thoughts` - Text

**Links:**
- `Link to Consultation` - URL
- `Attachment URLs` - Text
- `Attachment Analysis` - Text

**Relations:**
- `Related Past Items` - Relation to Items (self-relation)
  - When adding: Select "Items" database, allow multiple
- `Related Project` - Relation to Projects (will add after creating Projects database)
- `Discussed in Meetings` - Relation to Meetings (will add after creating Meetings database)

**Workflow:**
- `Status` - Select
  - Options: new, reviewed, response_drafted, submitted, monitoring, closed
- `Priority` - Select
  - Options: critical, high, medium, low
- `Processing Status` - Select
  - Options: pending_ai_analysis, ai_complete, needs_review, approved, migrated

### 1.3 Get Database ID

1. Open the Items database in Notion
2. Click "Share" in the top right
3. Copy the database link (e.g., `https://notion.so/items-abc123?v=...`)
4. The database ID is the part after the last `/` and before the `?` (e.g., `abc123`)
5. Save this for your `.env` file as `NOTION_ITEMS_DB_ID`

---

## Step 2: Create the Projects Database

### 2.1 Create New Database

1. Create a new page called "Projects" (or "Lambeth Projects")
2. Add a database (Database - Full page)

### 2.2 Add Properties

**Basic Info:**
- `Project Name` - Title (default)
- `Description` - Text

**Project Metadata:**
- `Project Type` - Select
  - Options: infrastructure_campaign, ongoing_monitoring, partnership, research
- `Status` - Select
  - Options: planning, active, paused, completed, archived
- `Priority` - Select
  - Options: strategic, high, medium, low

**Dates:**
- `Start Date` - Date
- `Target Completion` - Date

**Team:**
- `Lead Volunteer` - Person
- `Committee Members` - Person (allow multiple)

**Planning:**
- `Next Action` - Text
- `Key Milestones` - Text

**Locations:**
- `Primary Locations` - Multi-select
  - Copy common locations from Items database
- `Geographic Scope` - Select
  - Options: single_street, neighbourhood, borough_wide, cross_borough

**Links:**
- `Project Folder` - URL
- `Campaign Website` - URL
- `Related Documents` - Text

**Outcomes:**
- `Success Metrics` - Text
- `Final Outcome` - Text
- `Lessons Learned` - Text

**Relations:**
- `Related Items` - Relation to Items
  - Select "Items" database, allow multiple

### 2.3 Get Database ID

Same process as Items - get the database ID from the share link and save as `NOTION_PROJECTS_DB_ID`.

---

## Step 3: Create the Meetings Database

### 3.1 Create New Database

1. Create a new page called "Meetings" (or "Committee Meetings")
2. Add a database (Database - Full page)

### 3.2 Add Properties

**Basic Info:**
- `Meeting Title` - Title (default)
- `Meeting Date` - Date (enable time)
- `Meeting Type` - Select
  - Options: regular_committee, emergency, planning, special
- `Location` - Text

**Attendees:**
- `Attendees` - Person (allow multiple)

**Agenda:**
- `Auto-Generated Agenda` - Text
- `Manual Agenda Items` - Text
- `Agenda Generation Status` - Select
  - Options: pending, generated, approved, published
- `Agenda Generated At` - Date (enable time)

**Meeting Outputs:**
- `Meeting Notes` - Text
- `Decisions Made` - Text
- `Action Items` - Text
- `Next Meeting Date` - Date

**Triggers:**
- `Agenda Trigger Date` - Date
- `Meeting Created Manually` - Checkbox

**Relations:**
- `Items to Discuss` - Relation to Items
  - Select "Items" database, allow multiple
- `Projects to Review` - Relation to Projects
  - Select "Projects" database, allow multiple
- `Follow-ups from Previous Meeting` - Relation to Meetings (self-relation)
  - Select "Meetings" database, allow single

### 3.3 Get Database ID

Same process - save as `NOTION_MEETINGS_DB_ID`.

---

## Step 4: Complete Relations in Items Database

Now that all three databases exist, go back to Items database and add the missing relations:

1. Open Items database
2. Add property `Related Project` - Relation to Projects (allow single)
3. Add property `Discussed in Meetings` - Relation to Meetings (allow multiple)

---

## Step 5: Create Notion Integration

### 5.1 Create Integration

1. Go to https://www.notion.so/my-integrations
2. Click "+ New integration"
3. Name: "Lambeth Cyclists Email Processor"
4. Associated workspace: Select "Lambeth Cyclists Workspace"
5. Capabilities: Read content, Update content, Insert content
6. Click "Submit"

### 5.2 Copy Internal Integration Token

1. After creating, you'll see "Internal Integration Token"
2. Click "Show" and copy the token (starts with `secret_`)
3. Save this as `NOTION_API_KEY` in your `.env` file

### 5.3 Share Databases with Integration

For each of the three databases (Items, Projects, Meetings):

1. Open the database page
2. Click "..." (more options) in the top right
3. Scroll down to "Connections"
4. Click "+ Add connections"
5. Search for "Lambeth Cyclists Email Processor"
6. Click to add the integration

**Important:** If you don't share the databases with the integration, the API won't be able to access them!

---

## Step 6: Update .env File

Add the following to your `.env` file:

```bash
# Notion API
NOTION_API_KEY=secret_your_integration_token_here
NOTION_ITEMS_DB_ID=your_items_database_id_here
NOTION_PROJECTS_DB_ID=your_projects_database_id_here
NOTION_MEETINGS_DB_ID=your_meetings_database_id_here
```

---

## Step 7: Test the Setup (Optional)

You can test that everything is set up correctly by creating a simple Python script:

```python
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
```

Save this as `test_notion_setup.py` and run:

```bash
python test_notion_setup.py
```

If successful, you'll see the test item created in your Items database. You can then delete it manually.

---

## Troubleshooting

### Error: "Could not find database"

- Double-check the database IDs in your `.env` file
- Make sure you're using the correct format (just the ID, not the full URL)
- Ensure the integration has been added to the database (Step 5.3)

### Error: "Unauthorized" or "Forbidden"

- Verify the integration token is correct in `.env`
- Check that all databases are shared with the integration
- Ensure the integration has "Read content", "Update content", and "Insert content" capabilities

### Error: "Property does not exist"

- Property names are case-sensitive! They must match exactly
- Check for typos in property names
- Make sure all required properties are created in each database

### Relations not working

- Ensure the target databases are created before adding relations
- When adding a relation property, make sure you select the correct database
- Check that "allow multiple" is enabled where specified

---

## Summary

Once complete, you should have:

1. ✅ Items database with 30+ properties
2. ✅ Projects database with 20+ properties
3. ✅ Meetings database with 18+ properties
4. ✅ All relations properly configured
5. ✅ Notion integration created and shared with all databases
6. ✅ Database IDs and integration token added to `.env`

You're now ready to process emails and create structured Notion entries!

---

## Sample Database Views (Optional)

Consider creating these views in your databases for better usability:

### Items Database Views

**By Status:**
- Group by: Status
- Sort by: Priority (descending), then Date Received (descending)
- Filter: Status ≠ closed

**Urgent Actions:**
- Filter: Action Required = response_needed OR urgent_action
- Filter: Consultation Deadline < 14 days from now
- Sort by: Consultation Deadline (ascending)

**Recent Items:**
- Sort by: Date Received (descending)
- Limit: 50

### Projects Database Views

**Active Projects:**
- Filter: Status = active
- Sort by: Priority (descending)

**By Location:**
- Group by: Primary Locations
- Sort by: Status, Priority

### Meetings Database Views

**Upcoming Meetings:**
- Filter: Meeting Date >= Today
- Sort by: Meeting Date (ascending)

**Needs Agenda:**
- Filter: Agenda Generation Status = pending
- Sort by: Meeting Date (ascending)
