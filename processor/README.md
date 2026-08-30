# Lambeth Cyclists Email Processor

An automated email processing and project management system for Lambeth Cyclists, a local cycling advocacy organization.

## Overview

This Python application monitors Gmail for emails tagged "Lambeth Cyclists", processes them with Claude AI (including vision for images), and creates structured entries in Notion across three databases:

- **Items** (reactive, email-triggered) - consultations, traffic orders, infrastructure projects
- **Projects** (strategic, ongoing) - multi-email campaigns like A23 Brixton Hill crossing
- **Meetings** (bi-monthly committee) - with auto-generated agendas

## Features

### Email Processing
- Monitors Gmail every 5 minutes for new emails
- Handles **all** attachments (not just one like Zapier)
- Processes images with Claude's vision capabilities
- Extracts structured data: title, summary, deadlines, locations, tags, project type, action required
- Geocodes locations with Google Maps API
- Identifies related past items in Notion
- Uploads attachments to Google Drive

### Meeting Agenda Generation
- Detects manually-created meetings in Notion 1-2 days before meeting date
- Auto-generates agendas pulling:
  - New items since last meeting
  - Items with approaching deadlines
  - Active projects needing discussion
  - Follow-ups from previous meeting
  - AI-generated discussion prompts

### Improvements Over Zapier
- Processes multiple attachments (Zapier only handled 1)
- Claude vision for infrastructure photos and diagrams
- Intelligent deduplication and relationship detection
- Three-database structure for better organization
- Geocoding for location awareness

## Prerequisites

- Python 3.10 or higher
- Gmail account with API access
- Notion workspace with integration
- Claude API key (Anthropic)
- Google Maps API key (optional, for geocoding)
- Railway account (for deployment)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/lambeth-cyclists-email-processor.git
cd lambeth-cyclists-email-processor
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

- **Gmail API:** Create OAuth credentials in Google Cloud Console
- **Claude API:** Get API key from Anthropic Console
- **Notion API:** Create integration in Notion settings
- **Google Maps API:** Enable Geocoding API in Google Cloud Console
- **Google Drive:** Set folder ID where attachments will be stored

### 5. Set Up Notion Databases

Manually create 3 databases in Notion with the schemas defined in the plan:

1. **Items Database** - Reactive, email-triggered entries
2. **Projects Database** - Strategic, long-term initiatives
3. **Meetings Database** - Bi-monthly committee meetings

Record the database IDs in your `.env` file.

### 6. Set Up Gmail OAuth

Follow these steps to authenticate with Gmail:

1. Go to Google Cloud Console
2. Create a new project or select existing
3. Enable Gmail API and Google Drive API
4. Create OAuth 2.0 credentials
5. Download credentials and follow OAuth flow to get refresh token
6. Add credentials to `.env`

## Usage

### Local Development

Run the application locally:

```bash
python main.py
```

The application will:
- Start two concurrent loops: email polling (every 5 min) and meeting agenda generation (every 1 hour)
- Process emails from Gmail with "Lambeth Cyclists" label
- Create Notion items with structured data
- Generate meeting agendas for upcoming meetings

### Testing

Run the test suite:

```bash
pytest tests/ -v
```

### Deployment to Railway

1. Push code to GitHub:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. Connect Railway to your GitHub repository

3. Set environment variables in Railway dashboard (all variables from `.env`)

4. Railway will automatically deploy using `railway.json` configuration

5. Monitor logs in Railway dashboard

## Project Structure

```
lambeth-cyclists-email-processor/
├── config/              # Configuration and logging
├── services/            # External API integrations (Gmail, Claude, Notion, Google Maps)
├── processors/          # Email and attachment processing
├── agenda/              # Meeting detection and agenda generation
├── models/              # Data structures and prompts
├── utils/               # Rate limiting, error handling, validation
├── migrations/          # Data migration scripts
├── tests/               # Unit and integration tests
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── railway.json         # Railway deployment config
└── README.md            # This file
```

## Configuration

Key configuration options in `.env`:

- `EMAIL_POLL_INTERVAL`: Seconds between Gmail polls (default: 300 = 5 minutes)
- `MEETING_CHECK_INTERVAL`: Seconds between meeting checks (default: 3600 = 1 hour)
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `ADMIN_EMAIL`: Email address for error notifications

## API Rate Limits & Costs

- **Claude API:** ~$2-5/month for 100 emails (Sonnet 3.5)
- **Gmail API:** Free (1B queries/day)
- **Notion API:** Free (standard usage)
- **Google Maps:** Free up to $200/month credit (~40,000 geocoding requests)

**Total estimated cost:** ~$2-5/month

## Data Migration

To migrate existing Notion table data:

1. Identify project clusters (items that belong together)
2. Manually create Projects in new database
3. Run migration script:
   ```bash
   python migrations/migrate_notion_data.py
   ```
4. Validate migration (check row counts, spot check data)
5. Archive old Notion table

## Troubleshooting

### Configuration Errors

If you see "Configuration validation failed":
- Check that all required environment variables are set in `.env`
- Ensure API keys are valid (not placeholder values)
- Verify Notion database IDs are correct

### Gmail Authentication Issues

If Gmail API fails:
- Ensure OAuth credentials are correctly configured
- Check that refresh token is valid
- Verify Gmail API is enabled in Google Cloud Console

### Rate Limiting

If you hit API rate limits:
- Adjust polling intervals in `.env`
- Check rate limit settings: `CLAUDE_RPM`, `GMAIL_QPM`, `NOTION_RPM`
- Review logs for excessive API calls

### Notion API Errors

If Notion operations fail:
- Verify Notion integration has access to all 3 databases
- Check database schemas match the plan
- Ensure property names are correct (case-sensitive)

## Contributing

This is a custom application for Lambeth Cyclists. For bugs or feature requests, contact the maintainer.

## License

Internal use only for Lambeth Cyclists organization.

## Support

For questions or issues:
- Check Railway logs for detailed error messages
- Review local logs in development mode
- Error notifications sent to `ADMIN_EMAIL`
- Critical errors reported to Sentry (if configured)

## Roadmap

- [x] Phase 1: Foundation & Configuration
- [ ] Phase 2: Gmail Integration
- [ ] Phase 3: Notion Integration
- [ ] Phase 4: Claude AI Integration
- [ ] Phase 5: Attachment Processing
- [ ] Phase 6: Geocoding
- [ ] Phase 7: Email Processing Pipeline
- [ ] Phase 8: Meeting Agenda Generation
- [ ] Phase 9: Main Application Loop Enhancement
- [ ] Phase 10: Data Migration
- [ ] Phase 11: Local Testing & Validation
- [ ] Phase 12: Railway Deployment
