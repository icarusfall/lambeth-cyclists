# Email Alerts Setup Guide

This guide will help you set up email alerts and reminders for the Lambeth Cyclists Email Processor.

## Why Email Alerts?

The system will send you email notifications for:

### Meeting Reminders
- **When agenda is generated** (2 days before meeting) - with agenda preview
- **Daily reminders** if agenda not approved (during week before meeting)
- **Meeting tomorrow** reminder (day before) - with Zoom link and location
- **Add minutes** reminder (day after meeting)

### Error Alerts
- When email processing fails
- When the system hasn't processed emails in 7+ days (might be down)
- Critical configuration errors

This is especially useful since you mentioned needing to be "relentlessly nagged" about meeting admin!

---

## Setup Steps

### Step 1: Create Gmail App Password

Gmail no longer accepts regular passwords for third-party apps. You need to create an **App Password**.

**Prerequisites:**
- You must have 2-Step Verification enabled on your Google account
- If you don't have 2FA enabled, set it up first at: https://myaccount.google.com/security

**Create App Password:**

1. Go to your Google Account: https://myaccount.google.com/

2. Click "Security" in the left sidebar

3. Under "How you sign in to Google", click "2-Step Verification"
   - If you don't see this, you need to enable 2FA first

4. Scroll down to the bottom and click "App passwords"

5. You may need to sign in again

6. In the "Select app" dropdown, choose **"Mail"**

7. In the "Select device" dropdown, choose **"Other (Custom name)"**

8. Type: **"Lambeth Cyclists Email Processor"**

9. Click "Generate"

10. Google will show you a 16-character password like: `abcd efgh ijkl mnop`

11. **Copy this password immediately!** You won't be able to see it again.

---

### Step 2: Add to .env File

Add these lines to your `.env` file:

```bash
# Email Alerts Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop  # The 16-character app password (no spaces!)
ALERT_EMAIL=your-email@gmail.com  # Can be the same email
```

**Important:**
- For `SMTP_PASSWORD`, remove all spaces from the app password
- `SMTP_USERNAME` is your full Gmail address
- `ALERT_EMAIL` is where you want to receive the alerts (can be the same or different)

---

### Step 3: Test Email Alerts

Let's verify it's working:

1. Use the bundled `scripts/check_email_alerts.py`:

```python
from services.email_service import EmailService

email_service = EmailService()

# Send test email
success = email_service.send_email(
    to_email="your-email@gmail.com",  # Your email
    subject="Test: Email Alerts Working!",
    body_text="This is a test email from Lambeth Cyclists Email Processor. If you received this, email alerts are configured correctly!"
)

if success:
    print("✓ Test email sent successfully! Check your inbox.")
else:
    print("✗ Failed to send email. Check the logs for errors.")
```

2. Run it:
```bash
python scripts/check_email_alerts.py
```

3. Check your inbox - you should receive the test email within a few seconds

---

## What You'll Receive

### When Agenda is Generated

**Subject:** `Agenda Generated: Committee Meeting - February 2026`

**Content:**
- Meeting details (date, time, format, location)
- Days until meeting
- Preview of the generated agenda
- Link to review in Notion
- Reminder to approve the agenda

### Daily Nag (if Agenda Not Approved)

**Subject:** `⚠️ URGENT: Agenda Needs Approval: Committee Meeting`

**Content:**
- Days until meeting (getting more urgent!)
- Reminder that agenda needs approval
- Link to Notion
- You'll get this **every day** until you mark it as "approved" in Notion

### Meeting Tomorrow Reminder

**Subject:** `Meeting Tomorrow: Committee Meeting - February 2026`

**Content:**
- Meeting date and time
- Format (Hybrid/In-person/Online)
- Location
- Zoom link (if hybrid/online)
- Link to Notion for agenda

### After Meeting Reminder

**Subject:** `Please Add Minutes: Committee Meeting - February 2026`

**Content:**
- Reminder to add meeting notes
- Link to Notion
- Checklist: notes, decisions, action items, next meeting date

### Error Alerts

**Subject:** `⚠️ Error in Email Processor: [Error Type]`

**Content:**
- What went wrong
- Error message
- Reminder to check Railway logs

---

## Troubleshooting

### Error: "SMTP authentication failed"

**Check:**
- App password is correct (no spaces, 16 characters)
- 2-Step Verification is enabled on your Google account
- You're using the app password, not your regular Gmail password

**Fix:**
- Delete the app password and create a new one
- Make sure you copied it correctly (no spaces)

### Error: "Connection refused" or "Timed out"

**Check:**
- `SMTP_HOST` is `smtp.gmail.com` (not `smtp.google.com`)
- `SMTP_PORT` is `587` (not 465 or 25)
- Your network allows outbound connections on port 587

### Not Receiving Emails

**Check:**
- Check your spam/junk folder
- Verify `ALERT_EMAIL` is correct in `.env`
- Run the test script to see if there are errors

### Receiving Too Many Reminders

**To stop daily nags:**
- Go to the Meeting in Notion
- Change "Agenda Generation Status" from "generated" to "approved"
- The daily reminders will stop

**To disable all email alerts:**
- Remove `SMTP_USERNAME` and `SMTP_PASSWORD` from `.env`
- The system will continue working but won't send emails

---

## Using a Different Email Service

While Gmail is recommended, you can use other SMTP services:

### Outlook/Hotmail

```bash
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Custom SMTP Server

```bash
SMTP_HOST=mail.yourdomain.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=your-smtp-password
```

---

## Privacy & Security

**Your credentials are safe:**
- App passwords are stored only in your `.env` file
- `.env` is in `.gitignore` and never committed to GitHub
- Railway encrypts environment variables
- App passwords can be revoked anytime at: https://myaccount.google.com/apppasswords

**Best practices:**
- Use a dedicated Gmail account if you prefer (not your personal one)
- Revoke app passwords you're not using
- Don't share your `.env` file with anyone

---

## Optional: Daily Digest

If you want a daily summary instead of individual emails, you can modify the reminder settings in `config/settings.py` (future feature).

---

## Testing the Full Flow

Once set up, you can test the meeting reminder system:

1. Create a test meeting in Notion:
   - Title: "Test Committee Meeting"
   - Date: 2 days from now
   - Format: "Hybrid"
   - Meeting Created Manually: ✓

2. Run `python main.py`

3. Wait for the meeting agenda loop to run (every hour by default)

4. You should receive an email when the agenda is generated

5. Don't approve the agenda in Notion

6. Wait 24 hours - you should receive a daily nag reminder!

7. Approve the agenda in Notion - the daily nags will stop

---

## Summary

Once configured, you'll never miss meeting admin tasks:

- ✅ Agenda generated automatically (2 days before)
- ✅ Email notification with agenda preview
- ✅ Daily nags if you forget to approve it
- ✅ Final reminder the day before
- ✅ Reminder to add minutes afterwards
- ✅ Error alerts if something breaks

**You mentioned needing to be "relentlessly nagged" - this system delivers!** 😄

---

## Next Steps

After email alerts are working:
1. Test with a real meeting in Notion
2. Deploy to Railway (so it runs 24/7)
3. Enjoy automated meeting management!
