"""
Helper script to obtain Google OAuth refresh token.
Run this script to authorize the application and get credentials for .env file.
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import os
import sys

# Scopes for Gmail and Drive
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/drive'  # Full Drive access (needed for existing folders)
]


def get_refresh_token():
    """Get refresh token through OAuth flow."""

    print("="*70)
    print("Google OAuth Refresh Token Generator")
    print("for Lambeth Cyclists Email Processor")
    print("="*70)
    print()

    # Check if credentials.json exists
    if os.path.exists('credentials.json'):
        print("✓ Found credentials.json file")
        print("  Using credentials from file...")
        print()

        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json',
            SCOPES
        )

    else:
        print("credentials.json not found.")
        print("You can either:")
        print("  1. Download credentials.json from Google Cloud Console")
        print("  2. Enter your Client ID and Client Secret manually")
        print()

        choice = input("Enter Client ID and Secret manually? (y/n): ")

        if choice.lower() != 'y':
            print("\nPlease download credentials.json from Google Cloud Console:")
            print("1. Go to https://console.cloud.google.com/apis/credentials")
            print("2. Find your OAuth 2.0 Client ID")
            print("3. Click the download icon")
            print("4. Save as 'credentials.json' in this directory")
            print("5. Run this script again")
            sys.exit(1)

        print()
        client_id = input("Enter your Client ID: ").strip()
        client_secret = input("Enter your Client Secret: ").strip()

        if not client_id or not client_secret:
            print("\n✗ Error: Client ID and Secret are required!")
            sys.exit(1)

        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"]
                }
            },
            SCOPES
        )

    print("\n" + "="*70)
    print("Starting OAuth flow...")
    print("="*70)
    print()
    print("A browser window will open for authentication.")
    print("Please:")
    print("  1. Sign in with your Google account")
    print("  2. Click 'Advanced' if you see a warning")
    print("  3. Click 'Go to Lambeth Cyclists Email Processor (unsafe)'")
    print("  4. Click 'Allow' to grant permissions")
    print("  5. Return to this terminal")
    print()

    input("Press ENTER to open browser...")

    try:
        # Run local server for OAuth
        creds = flow.run_local_server(
            port=0,
            authorization_prompt_message='Please visit this URL to authorize the application: {url}',
            success_message='The authentication flow has completed. You may close this window.',
            open_browser=True
        )

        print("\n" + "="*70)
        print("✓ SUCCESS! Authentication completed!")
        print("="*70)
        print()
        print("Add these values to your .env file:")
        print()
        print("# Gmail API Configuration")
        print(f"GMAIL_CLIENT_ID={flow.client_config['client_id']}")
        print(f"GMAIL_CLIENT_SECRET={flow.client_config['client_secret']}")
        print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
        print()
        print("="*70)
        print()
        print("Next steps:")
        print("  1. Copy the above values to your .env file")
        print("  2. Set up your Google Drive folder ID")
        print("  3. Get your Notion API key and database IDs")
        print("  4. Get your Claude API key")
        print("  5. Test the application with: python main.py")
        print()
        print("See OAUTH_SETUP_GUIDE.md for detailed instructions.")
        print("="*70)

    except Exception as e:
        print(f"\n✗ Error during authentication: {e}")
        print("\nTroubleshooting tips:")
        print("  - Make sure you're using the correct Google account")
        print("  - Check that all APIs are enabled in Google Cloud Console")
        print("  - Verify OAuth consent screen is configured correctly")
        print("  - Ensure your email is added as a test user")
        print("\nSee OAUTH_SETUP_GUIDE.md for more help.")
        sys.exit(1)


if __name__ == '__main__':
    get_refresh_token()
