"""
Test script for email alerts.
Tests both single recipient and multiple recipients.
"""

import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from services.email_service import EmailService

email_service = EmailService()

print("=" * 60)
print("Testing Email Alerts")
print("=" * 60)
print()

# Test 1: Single recipient
print("Test 1: Sending to single recipient...")
success = email_service.send_email(
    to_email="charlie.ullman@gmail.com",
    subject="Test: Single Recipient",
    body_text="This is a test email to a single recipient. If you received this, email alerts are working!"
)

if success:
    print("✓ Single recipient test email sent successfully!")
else:
    print("✗ Failed to send single recipient email. Check the logs for errors.")

print()

# Test 2: Multiple recipients (example - replace with actual committee member emails)
print("Test 2: Sending to multiple recipients...")
print("(Edit the email addresses in test_email_alerts.py to test with real committee members)")

# Uncomment and edit these lines to test with multiple recipients:
# success = email_service.send_email(
#     to_email=[
#         "charlie.ullman@gmail.com",
#         "colin@example.com",  # Replace with actual email
#         "member3@example.com"  # Replace with actual email
#     ],
#     subject="Test: Multiple Recipients",
#     body_text="This is a test email to multiple committee members. Everyone should receive this!"
# )
#
# if success:
#     print("✓ Multiple recipient test email sent successfully!")
# else:
#     print("✗ Failed to send multiple recipient email. Check the logs for errors.")

print()

# Test 3: Using ALERT_EMAIL from settings (checks .env configuration)
print("Test 3: Sending to ALERT_EMAIL from .env...")
success = email_service.send_email(
    to_email=email_service.alert_email,  # Uses whatever is in .env
    subject="Test: ALERT_EMAIL Configuration",
    body_text="This email was sent to the ALERT_EMAIL address(es) configured in your .env file. This is how meeting reminders will be sent."
)

if success:
    print("✓ ALERT_EMAIL test sent successfully!")
    if isinstance(email_service.alert_email, list):
        print(f"  Sent to {len(email_service.alert_email)} recipients: {', '.join(email_service.alert_email)}")
    else:
        print(f"  Sent to: {email_service.alert_email}")
else:
    print("✗ Failed to send ALERT_EMAIL test. Check the logs for errors.")

print()
print("=" * 60)
print("Email alert tests complete!")
print()
print("To use multiple recipients:")
print("1. Edit your .env file")
print("2. Set ALERT_EMAIL to: email1@gmail.com, email2@gmail.com, email3@gmail.com")
print("3. Run this test again to verify")
print("=" * 60)
