# Phase 8 & 9 Complete! 🎉

Great news - the meeting agenda generation and email reminder system are now fully implemented!

---

## What's New

### Phase 8: Meeting Agenda Generation

The system now automatically generates meeting agendas:

**How it works:**
1. You create a meeting in Notion manually (1-4 weeks before the date)
2. 1-2 days before the meeting, the system automatically:
   - Gathers all new items since the last meeting
   - Finds items with approaching deadlines (next 30 days)
   - Pulls in active projects
   - Uses Claude AI to generate discussion prompts
   - Formats a complete agenda with your introduction template
   - Updates the meeting in Notion with the agenda
   - Links relevant items and projects

**Agenda includes:**
- Meeting header (date, format, location, Zoom link)
- Your standard introduction ("Hello and welcome to Lambeth Cyclists...")
- Infrastructure & Consultations section (new items + deadlines)
- Current Campaigns & Projects
- Recruitment & Volunteers
- Any Other Business
- AI-generated discussion prompts

### Phase 9: Email Reminders & Alerts

The system now sends you email notifications:

**Meeting Reminders:**
- ✉️ When agenda is generated (2 days before) - includes agenda preview
- ✉️ **Daily nags** if agenda not approved (every day in the week before meeting!)
- ✉️ Meeting tomorrow reminder (day before) - with Zoom link and details
- ✉️ Add minutes reminder (day after meeting)

**Error Alerts:**
- ✉️ When email processing fails
- ✉️ If no emails processed in 7+ days (system might be down)
- ✉️ Critical errors

**This is the "relentless nagging" you requested!** 😄

---

## What You Need to Do Now

### Step 1: Add New Fields to Notion Meetings Database

You need to add 2 new properties to your Meetings database in Notion:

1. Open your **Meetings** database in Notion

2. Add these properties:

   **Meeting Format** - Select
   - Options: `Hybrid`, `Online Only`, `In-person`

   **Zoom Link** - URL

3. That's it! The other fields you already have.

---

### Step 2: Set Up Email Alerts (Highly Recommended!)

Follow the **EMAIL_ALERTS_SETUP.md** guide to:

1. Create a Gmail App Password (takes 5 minutes)
2. Add SMTP settings to your `.env` file
3. Test that emails are working

**Without this, you won't get the daily nags and meeting reminders!**

Quick setup:

```bash
# Add to .env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password  # From Gmail App Passwords
ALERT_EMAIL=your-email@gmail.com
```

See **EMAIL_ALERTS_SETUP.md** for detailed instructions on getting the app password.

---

### Step 3: Test Meeting Agenda Generation

Let's test the full meeting flow:

#### 3.1 Create a Test Meeting

1. Open your Meetings database in Notion

2. Create a new meeting:
   - **Meeting Title**: "Test Committee Meeting - Feb 2026"
   - **Meeting Date**: Set to 2 days from now (e.g., if today is Jan 10th, set to Jan 12th at 19:00)
   - **Meeting Type**: regular_committee
   - **Meeting Format**: Hybrid
   - **Location**: "Stockwell Centre, Morley College"
   - **Zoom Link**: Your Zoom link (or just use a dummy one for testing)
   - **Meeting Created Manually**: ✓ (check this box!)
   - **Agenda Generation Status**: pending

3. Save the meeting

#### 3.2 Run the Application

```bash
# Make sure you're in venv
.\venv\Scripts\activate

# Run the app
python main.py
```

#### 3.3 Watch for Agenda Generation

The meeting agenda loop runs every hour by default. For testing, you can either:

**Option A:** Wait up to 1 hour for it to run automatically

**Option B:** Temporarily change the interval for faster testing:
- In `.env`, add: `MEETING_CHECK_INTERVAL=60` (checks every minute)
- Restart `python main.py`
- Change it back to `3600` (1 hour) when done testing

#### 3.4 What to Expect

When the agenda is generated, you should see in the logs:
```
Found 1 meeting(s) needing agendas
Processing meeting: Test Committee Meeting - Feb 2026
Generating agenda for meeting: Test Committee Meeting - Feb 2026
Found X new items, Y deadline items, Z active projects
Successfully generated agenda
```

**In Notion:**
- The "Auto-Generated Agenda" field should be filled with the complete agenda
- "Agenda Generation Status" should change to "generated"
- "Items to Discuss" and "Projects to Review" should be linked

**In Your Email** (if SMTP is configured):
- You should receive an email with subject: "Agenda Generated: Test Committee Meeting - Feb 2026"
- Includes a preview of the agenda
- Link to review in Notion

#### 3.5 Test the Daily Nag

1. Don't approve the agenda in Notion (leave it as "generated")

2. Wait 24 hours (or change `MEETING_CHECK_INTERVAL` to test sooner)

3. You should receive a daily reminder email:
   - Subject: "⚠️ Agenda Needs Approval..."
   - You'll get this **every day** until you approve it!

4. To stop the nags:
   - Go to the meeting in Notion
   - Change "Agenda Generation Status" to "approved"
   - The daily reminders will stop

#### 3.6 Test Meeting Tomorrow Reminder

If your test meeting is now 1 day away (tomorrow):
- You should receive a "Meeting Tomorrow" email
- Includes Zoom link, location, and format

---

### Step 4: Test with Real Data

Once the test works:

1. Delete or archive the test meeting in Notion

2. Create your real February meeting:
   - **Meeting Title**: "Committee Meeting - February 2026"
   - **Meeting Date**: 10th February 2026, 19:00 (or your chosen time)
   - **Meeting Format**: Hybrid
   - **Location**: "Stockwell Centre, Morley College" (if confirmed)
   - **Zoom Link**: Your actual Zoom meeting link
   - **Meeting Created Manually**: ✓
   - **Agenda Generation Status**: pending

3. The system will automatically generate the agenda 2 days before (Feb 8th)

4. You'll get your first email notification when the agenda is generated

5. If you don't approve it, you'll get daily nags starting the next day!

---

## Troubleshooting

### Agenda Not Generated

**Check:**
- Meeting date is 1-2 days in the future
- "Meeting Created Manually" is checked
- "Agenda Generation Status" is "pending" or empty
- The meeting agenda loop is running (check logs every hour)

**Fix:**
- Check the logs for errors
- Verify all Notion database properties exist
- Ensure Notion integration has access to all 3 databases

### No Email Received

**Check:**
- SMTP settings are in `.env`
- SMTP_USERNAME and SMTP_PASSWORD are correct
- Check spam folder
- Run the email test from EMAIL_ALERTS_SETUP.md

**Fix:**
- Verify Gmail App Password is correct (16 characters, no spaces)
- Check logs for SMTP errors

### Agenda is Empty or Incomplete

**Check:**
- Do you have any items in the Items database?
- Do you have any projects in the Projects database?
- Was there a previous meeting? (for "since last meeting" section)

**Note:**
- If you have no previous meetings, it will pull items from the last 60 days
- Empty sections are normal if you have no active projects or deadlines

### Daily Nags Not Stopping

**Fix:**
- Change "Agenda Generation Status" in Notion from "generated" to "approved"
- Wait for next meeting check cycle (up to 1 hour)

---

## File Changes

Here's what was added/modified:

**New Files:**
- `agenda/agenda_generator.py` - Generates meeting agendas with Claude
- `agenda/meeting_detector.py` - Detects meetings needing agendas
- `agenda/meeting_reminder.py` - Sends email reminders
- `services/email_service.py` - SMTP email service
- `EMAIL_ALERTS_SETUP.md` - Guide for setting up email alerts

**Modified Files:**
- `main.py` - Added meeting detection and reminder calls
- `models/notion_schemas.py` - Added meeting_format and zoom_link fields
- `services/notion_service.py` - Added support for new meeting fields
- `config/settings.py` - Added SMTP configuration
- `.env.example` - Added SMTP settings template

---

## What's Next?

You now have two options:

### Option A: Deploy to Railway Now

Everything essential is complete! You can:
1. Test locally to make sure it works
2. Follow **RAILWAY_DEPLOYMENT.md** to deploy
3. System runs 24/7 in the cloud
4. You get automated meeting management and email processing

### Option B: Add Optional Features First

You could also:
- **Phase 10**: Migrate your existing Notion data (if you have historical items to preserve)
- **Phase 11**: Add comprehensive testing (for future development)
- **Phase 13**: Plan Zapier decommissioning

**Recommendation:** Deploy to Railway now! Get it running in production, use it for your February meeting, then decide if you need Phase 10/11.

---

## Quick Reference

**Key Commands:**
```bash
# Run locally
python main.py

# Test email alerts
python scripts/check_email_alerts.py

# Test connections
python scripts/check_connections.py
```

**Key Configuration:**
```bash
# In .env
EMAIL_POLL_INTERVAL=300       # Email check: every 5 minutes
MEETING_CHECK_INTERVAL=3600   # Meeting check: every 1 hour
```

**Notion Agenda Statuses:**
- `pending` → Agenda not yet generated
- `generated` → Agenda created, needs your approval (daily nags!)
- `approved` → You've reviewed and approved it (nags stop)
- `published` → You've sent it to attendees

---

## Success Criteria

You'll know everything is working when:

✅ Meeting created in Notion
✅ Agenda auto-generated 2 days before
✅ Email notification received with agenda preview
✅ Meeting shows linked items and projects in Notion
✅ Daily nag received if you don't approve
✅ Nags stop when you mark as "approved"
✅ "Meeting tomorrow" email received day before
✅ "Add minutes" email received day after

---

## Summary

**Phase 8 ✅**: Meeting agendas generate automatically with AI
**Phase 9 ✅**: Email reminders keep you on track
**Core System ✅**: Email processing working with geocoding

**You now have a fully automated system for:**
- Processing cycling advocacy emails
- Generating meeting agendas
- Nagging you about meeting admin (as requested!)
- Alerting you when things break

**Next step:** Add the 2 Notion fields, set up email alerts, test it, then deploy to Railway!

---

Questions or issues? Check the relevant guide:
- Email alerts: **EMAIL_ALERTS_SETUP.md**
- Railway deployment: **RAILWAY_DEPLOYMENT.md**
- Initial setup: **GETTING_STARTED.md**
- OAuth setup: **OAUTH_SETUP_GUIDE.md**
