import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from services.gmail_service import GmailService

gmail = GmailService()
gmail.authenticate()
print("✓ Gmail API authentication successful!")

# Try polling (should not error even if no emails)
message_ids = gmail.poll_emails()
print(f"✓ Gmail polling successful! Found {len(message_ids)} emails")

