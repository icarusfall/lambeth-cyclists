"""
Email Service
Sends email notifications and reminders using Resend API.
"""

import resend
from datetime import datetime
from typing import Optional

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for sending email notifications via Resend API."""

    def __init__(self):
        """Initialize email service with Resend settings."""
        self.settings = get_settings()

        # Resend configuration
        self.api_key = getattr(self.settings, 'resend_api_key', None)
        self.from_email = getattr(self.settings, 'from_email', 'Lambeth Cyclists <onboarding@resend.dev>')

        # Configure Resend
        if self.api_key:
            resend.api_key = self.api_key

        # Alert email(s) - can be single email or comma-separated list
        alert_email_raw = getattr(self.settings, 'alert_email', self.settings.admin_email)
        if alert_email_raw and ',' in alert_email_raw:
            # Multiple emails separated by commas
            self.alert_email = [email.strip() for email in alert_email_raw.split(',')]
        else:
            # Single email
            self.alert_email = alert_email_raw

    def send_email(
        self,
        to_email: str | list[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send an email using Resend API.

        Args:
            to_email: Recipient email address (string) or list of addresses
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.api_key:
            logger.warning("Resend API key not configured - skipping email")
            return False

        try:
            # Handle both single email and list of emails
            recipients = [to_email] if isinstance(to_email, str) else to_email

            # Build email params
            params = {
                "from": self.from_email,
                "to": recipients,
                "subject": subject,
                "text": body_text,
            }

            # Add HTML if provided
            if body_html:
                params["html"] = body_html

            # Send via Resend
            response = resend.Emails.send(params)

            recipients_str = ', '.join(recipients)
            logger.info(f"Email sent successfully to {recipients_str}: {subject} (id: {response.get('id', 'unknown')})")
            return True

        except Exception as e:
            recipients_str = ', '.join(recipients) if isinstance(to_email, list) else to_email
            logger.error(f"Failed to send email to {recipients_str}: {e}", exc_info=True)
            return False

    def send_meeting_created_alert(
        self,
        meeting_title: str,
        meeting_date: datetime,
        meeting_url: str
    ) -> bool:
        """Send alert when a new meeting is created."""
        subject = f"New Meeting Scheduled: {meeting_title}"

        body_text = f"""
A new meeting has been scheduled:

Meeting: {meeting_title}
Date: {meeting_date.strftime('%A, %d %B %Y at %H:%M')}

The agenda will be auto-generated 2 days before the meeting.

View meeting in Notion:
{meeting_url}

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>New Meeting Scheduled</h2>

    <p>A new meeting has been scheduled:</p>

    <ul>
        <li><strong>Meeting:</strong> {meeting_title}</li>
        <li><strong>Date:</strong> {meeting_date.strftime('%A, %d %B %Y at %H:%M')}</li>
    </ul>

    <p>The agenda will be auto-generated 2 days before the meeting.</p>

    <p><a href="{meeting_url}">View meeting in Notion</a></p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_agenda_generated_alert(
        self,
        meeting_title: str,
        meeting_date: datetime,
        meeting_url: str,
        agenda_preview: str
    ) -> bool:
        """Send alert when agenda is auto-generated."""
        subject = f"Agenda Generated: {meeting_title}"

        days_until = (meeting_date - datetime.now(meeting_date.tzinfo)).days

        body_text = f"""
The agenda has been generated for your upcoming meeting:

Meeting: {meeting_title}
Date: {meeting_date.strftime('%A, %d %B %Y at %H:%M')}
Time until meeting: {days_until} days

Please review and approve the agenda in Notion:
{meeting_url}

AGENDA PREVIEW:
{agenda_preview[:500]}...

Mark the agenda as "approved" when ready to send it out to attendees.

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Agenda Generated</h2>

    <p>The agenda has been generated for your upcoming meeting:</p>

    <ul>
        <li><strong>Meeting:</strong> {meeting_title}</li>
        <li><strong>Date:</strong> {meeting_date.strftime('%A, %d %B %Y at %H:%M')}</li>
        <li><strong>Time until meeting:</strong> {days_until} days</li>
    </ul>

    <p><strong>Please review and approve the agenda in Notion.</strong></p>

    <p><a href="{meeting_url}" style="background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Review Agenda</a></p>

    <h3>Agenda Preview:</h3>
    <pre style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow: auto; font-size: 0.9em;">{agenda_preview[:500]}...</pre>

    <p style="color: #cc6600;"><strong>Mark the agenda as "approved" when ready to send it out to attendees.</strong></p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_agenda_approval_reminder(
        self,
        meeting_title: str,
        meeting_date: datetime,
        meeting_url: str,
        days_until_meeting: int
    ) -> bool:
        """Send daily reminder to approve agenda."""
        urgency = "URGENT: " if days_until_meeting <= 2 else ""
        subject = f"{urgency}Agenda Needs Approval: {meeting_title}"

        body_text = f"""
REMINDER: Agenda needs approval

Meeting: {meeting_title}
Date: {meeting_date.strftime('%A, %d %B %Y at %H:%M')}
Days until meeting: {days_until_meeting}

The agenda has been generated but still needs your approval.

Please review and mark as "approved" in Notion:
{meeting_url}

You will continue to receive daily reminders until the agenda is approved.

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 20px;">
        <h2 style="margin-top: 0;">REMINDER: Agenda Needs Approval</h2>
    </div>

    <ul>
        <li><strong>Meeting:</strong> {meeting_title}</li>
        <li><strong>Date:</strong> {meeting_date.strftime('%A, %d %B %Y at %H:%M')}</li>
        <li><strong>Days until meeting:</strong> {days_until_meeting}</li>
    </ul>

    <p>The agenda has been generated but still needs your approval.</p>

    <p><a href="{meeting_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Review & Approve Agenda</a></p>

    <p style="color: #666; font-size: 0.9em;">You will continue to receive daily reminders until the agenda is approved.</p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_meeting_tomorrow_reminder(
        self,
        meeting_title: str,
        meeting_date: datetime,
        meeting_format: Optional[str],
        location: Optional[str],
        zoom_link: Optional[str],
        meeting_url: str
    ) -> bool:
        """Send final reminder the day before meeting."""
        subject = f"Meeting Tomorrow: {meeting_title}"

        # Build meeting details
        details = []
        details.append(f"Meeting: {meeting_title}")
        details.append(f"Date: {meeting_date.strftime('%A, %d %B %Y at %H:%M')}")
        if meeting_format:
            details.append(f"Format: {meeting_format}")
        if location:
            details.append(f"Location: {location}")
        if zoom_link:
            details.append(f"Zoom Link: {zoom_link}")

        details_text = "\n".join(details)
        details_html = "\n".join([f"<li>{d}</li>" for d in details])

        body_text = f"""
REMINDER: Meeting Tomorrow

{details_text}

View meeting details in Notion:
{meeting_url}

See you tomorrow!

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px; margin-bottom: 20px;">
        <h2 style="margin-top: 0;">REMINDER: Meeting Tomorrow</h2>
    </div>

    <ul>
        {details_html}
    </ul>

    <p><a href="{meeting_url}">View meeting details in Notion</a></p>

    <p><strong>See you tomorrow!</strong></p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_meeting_minutes_reminder(
        self,
        meeting_title: str,
        meeting_date: datetime,
        meeting_url: str
    ) -> bool:
        """Send reminder to add meeting minutes after the meeting."""
        subject = f"Please Add Minutes: {meeting_title}"

        body_text = f"""
Meeting yesterday: {meeting_title}
Date: {meeting_date.strftime('%A, %d %B %Y')}

Please add the meeting minutes and notes to Notion:
{meeting_url}

Don't forget to:
- Add meeting notes
- Record decisions made
- List action items
- Set the next meeting date

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Please Add Meeting Minutes</h2>

    <p><strong>Meeting yesterday:</strong> {meeting_title}<br>
    <strong>Date:</strong> {meeting_date.strftime('%A, %d %B %Y')}</p>

    <p>Please add the meeting minutes and notes to Notion:</p>

    <p><a href="{meeting_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Add Minutes</a></p>

    <h3>Don't forget to:</h3>
    <ul>
        <li>Add meeting notes</li>
        <li>Record decisions made</li>
        <li>List action items</li>
        <li>Set the next meeting date</li>
    </ul>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_error_alert(
        self,
        error_type: str,
        error_message: str,
        context: Optional[str] = None
    ) -> bool:
        """Send alert when an error occurs."""
        subject = f"Error in Email Processor: {error_type}"

        body_text = f"""
An error occurred in the Lambeth Cyclists Email Processor:

Error Type: {error_type}
Error Message: {error_message}

{f'Context: {context}' if context else ''}

Please check the Railway logs for more details.

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin-bottom: 20px;">
        <h2 style="margin-top: 0; color: #721c24;">Error in Email Processor</h2>
    </div>

    <ul>
        <li><strong>Error Type:</strong> {error_type}</li>
        <li><strong>Error Message:</strong> {error_message}</li>
        {f'<li><strong>Context:</strong> {context}</li>' if context else ''}
    </ul>

    <p>Please check the Railway logs for more details.</p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_system_health_alert(
        self,
        message: str
    ) -> bool:
        """Send system health alert (e.g., no emails processed in X days)."""
        subject = "System Health Alert: Email Processor"

        body_text = f"""
System Health Alert:

{message}

Please check:
- Railway deployment is running
- Gmail API credentials are valid
- Notion API is accessible
- No rate limits hit

Check Railway logs for more details.

---
Lambeth Cyclists Email Processor
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 20px;">
        <h2 style="margin-top: 0;">System Health Alert</h2>
    </div>

    <p>{message}</p>

    <h3>Please check:</h3>
    <ul>
        <li>Railway deployment is running</li>
        <li>Gmail API credentials are valid</li>
        <li>Notion API is accessible</li>
        <li>No rate limits hit</li>
    </ul>

    <p>Check Railway logs for more details.</p>

    <hr>
    <p style="color: #666; font-size: 0.9em;">Lambeth Cyclists Email Processor</p>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=self.alert_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
