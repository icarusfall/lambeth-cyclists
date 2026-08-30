# Getting Started - Testing the Email Processor

This guide will help you set up and test the Lambeth Cyclists Email Processor locally on your Windows machine.

## 🎯 What's Working Now

The **core email processing pipeline** is complete and ready to test:

- ✅ Gmail monitoring and email retrieval
- ✅ Attachment download (PDFs, Word docs, images, Excel)
- ✅ Text extraction from documents
- ✅ Claude AI analysis (text + vision for images)
- ✅ Location geocoding with Google Maps
- ✅ Google Drive upload for attachments
- ✅ Notion item creation with all fields
- ✅ Duplicate detection (won't process the same email twice)
- ✅ Relationship detection (links related items and projects)

**What's not yet implemented:**
- Meeting agenda generation (Phase 8)
- Health monitoring and notifications (Phase 9)
- Data migration from your existing table (Phase 10)

But the main email processing functionality is fully working!

---

## 📋 Setup Checklist

Work through these steps in order:

### Step 1: Install Python Dependencies

1. Open PowerShell or Command Prompt
2. Navigate to the project directory:
   ```bash
   cd C:\Users\charl\ClaudeProjects\lambeth-cyclists-claude
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

4. Activate the virtual environment:
   ```bash
   .\venv\Scripts\activate
   ```
   You should see `(venv)` in your prompt.

5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This will take 2-3 minutes.

### Step 2: Set Up Notion Databases

Follow the **NOTION_SETUP_GUIDE.md** to:

1. Create 3 new Notion databases (Items, Projects, Meetings)
2. Add all required properties to each database
3. Create a Notion integration
4. Share all databases with the integration
5. Copy the integration token and database IDs

**Time estimate:** 30-45 minutes

**Important:** Don't delete or modify your existing Notion table yet! We'll migrate that data in Phase 10.

### Step 3: Set Up Google OAuth Credentials

Follow the **OAUTH_SETUP_GUIDE.md** to:

1. Create a Google Cloud project
2. Enable Gmail API and Google Drive API
3. Create OAuth 2.0 credentials
4. Run `python scripts/get_refresh_token.py` to get your refresh token
5. Create a Google Drive folder for attachments
6. Copy the folder ID from the URL

**Time estimate:** 20-30 minutes

**Optional:** Enable Geocoding API for location coordinates (adds 10 minutes)

### Step 4: Get Claude API Key

1. Go to https://console.anthropic.com/
2. Sign in (or create an account if needed)
3. Go to "API Keys"
4. Click "Create Key"
5. Name it "Lambeth Cyclists Email Processor"
6. Copy the API key (starts with `sk-ant-`)

**Time estimate:** 5 minutes

**Cost:** ~$2-5/month for typical usage (100 emails with attachments)

### Step 5: Create .env File

1. In the project root, create a file named `.env` (note the dot at the start)

2. Copy this template and fill in your values:

```bash
# Gmail API Configuration
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token-from-get-refresh-token-script
GMAIL_LABEL=Lambeth Cycling Projects

# Claude API
CLAUDE_API_KEY=sk-ant-your-claude-api-key

# Notion API
NOTION_API_KEY=secret_your-notion-integration-key
NOTION_ITEMS_DB_ID=your-items-database-id
NOTION_PROJECTS_DB_ID=your-projects-database-id
NOTION_MEETINGS_DB_ID=your-meetings-database-id

# Google Maps API (optional, for geocoding)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id

# Application Configuration
EMAIL_POLL_INTERVAL=300  # 5 minutes in seconds
MEETING_CHECK_INTERVAL=3600  # 1 hour in seconds
LOG_LEVEL=INFO
ADMIN_EMAIL=your-email@example.com

# Rate Limits
CLAUDE_RPM=50
GMAIL_QPM=250
NOTION_RPM=3
```

3. **Replace all the placeholder values** with your actual credentials from Steps 2-4

4. **Important:** Make sure `.env` is listed in `.gitignore` (it already is) so you don't accidentally commit it!

### Step 6: Verify Configuration

Run this test to make sure everything is configured correctly:

```bash
python -c "from config.settings import validate_settings; validate_settings()"
```

You should see:
```
✓ Configuration validated successfully
```

If you see errors, check that:
- All required fields in `.env` are filled in
- No typos in API keys or database IDs
- Values don't have quotes around them (unless they're part of the value)

---

## 🧪 Testing the Email Processor

### Test 1: Quick Smoke Test (No Real Emails)

Let's verify all services can connect:

```python
# Use the bundled scripts/check_connections.py

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
```

Run it:
```bash
python scripts/check_connections.py
```

**Expected result:** All services show ✓ (connected)

### Test 2: Process a Real Test Email

Now let's test the full pipeline with a real email:

1. **Send yourself a test email**:
   - From any email account, send an email to your Gmail
   - Subject: "TEST - Consultation on Test Street"
   - Body: "This is a test consultation about proposed cycle lane on Test Street. Deadline: 2026-02-28. Please respond with comments."
   - Add the "Lambeth Cycling Projects" label in Gmail

2. **Optional: Add a test attachment**:
   - Create a simple PDF or Word document
   - Write: "Proposed cycle lane on Test Street from Main Road to Park Avenue"
   - Attach to the email

3. **Run the email processor**:
   ```bash
   python main.py
   ```

4. **Watch the logs**:
   - You should see colorful logs showing the processing steps
   - Look for:
     - "Found 1 new emails to process"
     - "Retrieved email: 'TEST - Consultation on Test Street'"
     - "Downloading attachments" (if you added one)
     - "Analyzing email with Claude AI"
     - "Creating Notion item"
     - "Successfully processed email"

5. **Check Notion**:
   - Open your Items database in Notion
   - You should see a new entry with:
     - Title extracted by Claude
     - Summary
     - Tags (probably "consultation", "cycle_lane")
     - Locations (should include "Test Street")
     - AI Key Points
     - Priority set appropriately
     - If you had an attachment: link in "Attachment URLs"

6. **Check Google Drive**:
   - Open your attachments folder in Drive
   - You should see your attachment uploaded there

7. **Check Gmail**:
   - Your test email should now have a "processed" label

8. **Test Deduplication**:
   - Run `python main.py` again
   - The same email should **not** be processed again
   - Logs should say: "No new emails to process"

### Test 3: Test with Multiple Emails

1. Send 3-4 more test emails with different scenarios:
   - **Traffic order**: "Traffic Order - Parking removal on Sample Road"
   - **Infrastructure project**: "New cycle lane installation on Park Avenue"
   - **Consultation with image**: Attach a screenshot or diagram
   - **Event**: "Car free day on High Street - March 15th"

2. Run the processor:
   ```bash
   python main.py
   ```

3. Verify all emails are processed correctly

4. Check that:
   - Each email creates a separate Notion item
   - Images are analyzed by Claude vision
   - Different project types are correctly identified
   - Related items might be linked (if locations overlap)

---

## 🐛 Troubleshooting

### Error: "Configuration validation failed"

**Check:**
- All required fields in `.env` are filled in
- No typos in API keys
- Database IDs are correct (no extra spaces)

### Error: "Gmail API: Failed to authenticate"

**Check:**
- Client ID and Client Secret are correct
- Refresh token is valid (re-run `scripts/get_refresh_token.py` if needed)
- Gmail API is enabled in Google Cloud Console

### Error: "Notion API: Could not find database"

**Check:**
- Database IDs are correct (copy from Notion page URL)
- Notion integration has access to all 3 databases
- Database property names match exactly (case-sensitive)

### Error: "Claude API: Authentication failed"

**Check:**
- API key starts with `sk-ant-`
- No extra spaces in the key
- API key is valid in Anthropic Console

### No emails found to process

**Check:**
- Email has the correct label: "Lambeth Cycling Projects"
- Email doesn't already have the "processed" label
- Gmail label name in `.env` matches exactly (case-sensitive)

### Emails processed but no Notion items

**Check:**
- Look at the logs for errors during Notion creation
- Verify database property names match the code
- Check that all required properties exist in Notion

### Attachments not uploading to Drive

**Check:**
- Google Drive API is enabled
- Folder ID is correct (from Drive folder URL)
- Drive folder is not shared (or integration has access)

---

## 📊 Monitoring & Logs

### Understanding the Logs

The application uses colored, structured logging:

- **Green (INFO)**: Normal operations (email processed, item created)
- **Yellow (WARNING)**: Non-critical issues (geocoding disabled, attachment skipped)
- **Red (ERROR)**: Errors that need attention (API failures, missing config)
- **Cyan (DEBUG)**: Detailed debugging info (can enable with `LOG_LEVEL=DEBUG` in `.env`)

### Key Log Messages

**Success:**
```
✓ Configuration validated successfully
Found 1 new emails to process
Retrieved email: 'Consultation on Test Street' from test@example.com
Analyzing email with Claude AI
Created Notion item: Test Consultation
Successfully processed email: Consultation on Test Street
```

**Duplicate:**
```
Duplicate detected (Layer 1 - Message ID): Test Email
Skipping duplicate email: Test Email
```

**Error:**
```
Error processing email msg_123: Connection timeout
```

### Statistics

The processor tracks:
- `processed`: Number of emails successfully processed
- `duplicates`: Number of duplicate emails skipped
- `errors`: Number of emails that failed processing

These are logged at the end of each polling cycle.

---

## ⏭️ Next Steps After Testing

Once you've successfully processed a few test emails:

1. **Let it run for real**:
   - Keep `python main.py` running
   - It will poll Gmail every 5 minutes automatically
   - New emails with "Lambeth Cycling Projects" label will be processed

2. **Monitor for a day or two**:
   - Check that real emails are processed correctly
   - Verify Claude's extraction is accurate
   - Make sure attachments upload to Drive
   - Confirm no duplicates are created

3. **When ready, continue development**:
   - **Phase 8**: Meeting agenda generation
   - **Phase 9**: Health monitoring and error notifications
   - **Phase 10**: Migrate your existing Notion table data
   - **Phase 11**: Comprehensive testing
   - **Phase 12**: Deploy to Railway for 24/7 operation

---

## 💡 Tips

### Running in Background (Windows)

To keep the processor running even when you close the terminal:

1. **Option A: Use `pythonw`** (no console window):
   ```bash
   pythonw main.py
   ```

2. **Option B: Use Windows Task Scheduler**:
   - Open Task Scheduler
   - Create a new task that runs at startup
   - Action: Start `python.exe` with argument `main.py`
   - Set working directory to your project folder

### Stopping the Processor

Press `Ctrl+C` in the terminal to gracefully shut down.

### Adjusting Poll Interval

In `.env`, change `EMAIL_POLL_INTERVAL`:
- `300` = 5 minutes (default, recommended)
- `60` = 1 minute (more responsive, higher API usage)
- `600` = 10 minutes (less frequent checks)

### Viewing Processed Emails

All emails with the "processed" label have been handled by the system.

To reprocess an email (for testing):
1. Remove the "processed" label in Gmail
2. Run the processor again

### API Costs

Track your usage:
- **Gmail/Drive**: Free (very high limits)
- **Claude**: Check usage at https://console.anthropic.com/
- **Google Maps**: Check quota at https://console.cloud.google.com/

---

## 📞 Getting Help

If you run into issues:

1. **Check the logs** - Most errors are self-explanatory
2. **Review the guides**:
   - `NOTION_SETUP_GUIDE.md` - Notion database setup
   - `OAUTH_SETUP_GUIDE.md` - Google OAuth setup
   - `README.md` - Project overview
3. **Check configuration**:
   - Run `python -c "from config.settings import validate_settings; validate_settings()"`
4. **Test connections**:
   - Run the `scripts/check_connections.py` script from Test 1

---

## ✅ Success Criteria

You'll know the system is working when:

- ✅ Email with "Lambeth Cycling Projects" label is detected
- ✅ Claude extracts meaningful title, summary, and key points
- ✅ Attachments are uploaded to Google Drive
- ✅ Notion Item is created with all fields populated
- ✅ Locations are identified (and geocoded if enabled)
- ✅ Email is marked as "processed" in Gmail
- ✅ Running processor again doesn't duplicate the item

**Once you see this flow working, the core system is validated!** 🎉

---

## 🚀 Ready?

Your checklist:

1. [ ] Python dependencies installed (`pip install -r requirements.txt`)
2. [ ] Notion databases created (see NOTION_SETUP_GUIDE.md)
3. [ ] Google OAuth credentials obtained (see OAUTH_SETUP_GUIDE.md)
4. [ ] Claude API key obtained
5. [ ] `.env` file created with all credentials
6. [ ] Configuration validated (`validate_settings()`)
7. [ ] Test connections passed (`scripts/check_connections.py`)
8. [ ] Test email sent with "Lambeth Cycling Projects" label
9. [ ] Processor run successfully (`python main.py`)
10. [ ] Notion Item created and verified

Good luck! Take your time with the setup - it's worth getting right. When you're ready to continue with the remaining phases (meeting agendas, migration, deployment), just let me know!
