# Google OAuth Setup Guide

This guide will walk you through setting up OAuth credentials for Gmail and Google Drive APIs. These credentials are required for the email processor to access your Gmail account and upload attachments to Drive.

## Overview

You need to:
1. Create a Google Cloud project
2. Enable Gmail API and Google Drive API
3. Create OAuth 2.0 credentials
4. Obtain a refresh token
5. Add credentials to your `.env` file

---

## Step 1: Create Google Cloud Project

### 1.1 Go to Google Cloud Console

1. Visit https://console.cloud.google.com/
2. Sign in with your Google account (the one that has access to your Lambeth Cyclists Gmail)

### 1.2 Create New Project

1. Click on the project dropdown at the top (next to "Google Cloud")
2. Click "NEW PROJECT"
3. Project name: "Lambeth Cyclists Email Processor" (or any name you prefer)
4. Organization: Leave as-is (or select if you have one)
5. Click "CREATE"
6. Wait for the project to be created (30 seconds)
7. Select the new project from the dropdown

---

## Step 2: Enable Required APIs

### 2.1 Enable Gmail API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
   - Or visit: https://console.cloud.google.com/apis/library
2. Search for "Gmail API"
3. Click on "Gmail API"
4. Click "ENABLE"
5. Wait for it to enable (10-20 seconds)

### 2.2 Enable Google Drive API

1. Still in "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on "Google Drive API"
4. Click "ENABLE"

### 2.3 Enable Google Maps Geocoding API (Optional)

If you want location geocoding:

1. Search for "Geocoding API"
2. Click on "Geocoding API"
3. Click "ENABLE"

---

## Step 3: Create OAuth 2.0 Credentials

### 3.1 Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
   - Or visit: https://console.cloud.google.com/apis/credentials/consent
2. **User Type**: Select "External" (unless you have a Google Workspace)
3. Click "CREATE"

4. **Fill out the form**:
   - **App name**: "Lambeth Cyclists Email Processor"
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
   - Leave other fields blank
5. Click "SAVE AND CONTINUE"

6. **Scopes** (Step 2):
   - Click "ADD OR REMOVE SCOPES"
   - Search and add these scopes:
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/drive.file`
   - Click "UPDATE"
   - Click "SAVE AND CONTINUE"

7. **Test users** (Step 3):
   - Click "ADD USERS"
   - Enter your Gmail address (the one you'll use for Lambeth Cyclists emails)
   - Click "ADD"
   - Click "SAVE AND CONTINUE"

8. **Summary** (Step 4):
   - Review and click "BACK TO DASHBOARD"

### 3.2 Create OAuth Client ID

1. Go to "APIs & Services" → "Credentials"
   - Or visit: https://console.cloud.google.com/apis/credentials
2. Click "CREATE CREDENTIALS" → "OAuth client ID"
3. **Application type**: Select "Desktop app"
4. **Name**: "Lambeth Cyclists Desktop Client"
5. Click "CREATE"

6. **Save Your Credentials**:
   - A popup will show your Client ID and Client secret
   - **IMPORTANT**: Copy both of these - you'll need them!
   - Client ID: Looks like `123456-abcdef.apps.googleusercontent.com`
   - Client secret: Looks like `GOCSPX-abc123...`
   - Click "OK"

7. **Download Credentials** (optional but recommended):
   - In the credentials list, find your OAuth client
   - Click the download icon (⬇) on the right
   - Save the JSON file as `credentials.json` in your project root
   - This file contains your Client ID and Client secret

---

## Step 4: Obtain Refresh Token

Now you need to authorize the app and get a refresh token. There are two methods:

### Method A: Using Python Script (Recommended)

1. Create a file called `scripts/get_refresh_token.py` in your project root:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

# Scopes for Gmail and Drive
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/drive.file'
]

def get_refresh_token():
    """Get refresh token through OAuth flow."""

    # Option 1: Use downloaded credentials.json
    if os.path.exists('credentials.json'):
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json',
            SCOPES
        )
    # Option 2: Manual entry of credentials
    else:
        client_id = input("Enter your Client ID: ")
        client_secret = input("Enter your Client Secret: ")

        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            },
            SCOPES
        )

    # Run local server for OAuth
    creds = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print("SUCCESS! Here are your credentials:")
    print("="*60)
    print(f"\nGMAIL_CLIENT_ID={flow.client_config['client_id']}")
    print(f"GMAIL_CLIENT_SECRET={flow.client_config['client_secret']}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\n" + "="*60)
    print("Copy these values to your .env file")
    print("="*60)

if __name__ == '__main__':
    get_refresh_token()
```

2. Run the script:
   ```bash
   python scripts/get_refresh_token.py
   ```

3. **A browser window will open**:
   - You'll see a warning "Google hasn't verified this app"
   - Click "Advanced"
   - Click "Go to Lambeth Cyclists Email Processor (unsafe)"
   - Click "Continue" to grant permissions
   - You'll see a message "The authentication flow has completed"
   - Close the browser

4. **Copy the output**:
   - The script will print your Client ID, Client Secret, and Refresh Token
   - Copy these to your `.env` file

### Method B: Using Google OAuth Playground (Alternative)

1. Go to https://developers.google.com/oauthplayground/
2. Click the gear icon (⚙️) in the top right
3. Check "Use your own OAuth credentials"
4. Enter your Client ID and Client Secret
5. Close settings

6. In the left sidebar, find and select:
   - `Gmail API v1` → `https://www.googleapis.com/auth/gmail.readonly`
   - `Gmail API v1` → `https://www.googleapis.com/auth/gmail.modify`
   - `Drive API v3` → `https://www.googleapis.com/auth/drive.file`

7. Click "Authorize APIs"
8. Sign in and grant permissions
9. Click "Exchange authorization code for tokens"
10. Copy the "Refresh token" value

---

## Step 5: Update .env File

1. Open (or create) `.env` in your project root
2. Add your credentials:

```bash
# Gmail API Configuration
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token
GMAIL_LABEL=Lambeth Cycling Projects

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID=your-drive-folder-id

# Google Maps API (optional)
GOOGLE_MAPS_API_KEY=your-maps-api-key
```

3. **Get your Google Drive Folder ID**:
   - Go to Google Drive
   - Create a folder called "Lambeth Cyclists Attachments" (or any name)
   - Open the folder
   - Copy the folder ID from the URL:
     - URL looks like: `https://drive.google.com/drive/folders/1ABC123XYZ...`
     - Folder ID is: `1ABC123XYZ...` (the part after `/folders/`)
   - Paste into `GOOGLE_DRIVE_FOLDER_ID`

4. **Get Google Maps API Key** (optional):
   - In Google Cloud Console, go to "APIs & Services" → "Credentials"
   - Click "CREATE CREDENTIALS" → "API key"
   - Copy the API key
   - Click "RESTRICT KEY" (recommended):
     - Name: "Lambeth Cyclists Geocoding Key"
     - API restrictions: Select "Restrict key"
     - Select "Geocoding API"
     - Click "SAVE"
   - Paste into `GOOGLE_MAPS_API_KEY`

---

## Step 6: Test Your Setup

### 6.1 Test Configuration

Run this Python script to verify your credentials work:

```python
from config.settings import get_settings, validate_settings

try:
    validate_settings()
    print("✓ Configuration validated successfully!")
except Exception as e:
    print(f"✗ Configuration error: {e}")
```

### 6.2 Test Gmail Connection

```python
from services.gmail_service import GmailService

gmail = GmailService()
gmail.authenticate()
print("✓ Gmail API authentication successful!")

# Try polling (should not error even if no emails)
message_ids = gmail.poll_emails()
print(f"✓ Gmail polling successful! Found {len(message_ids)} emails")
```

### 6.3 Test Google Drive Connection

```python
from services.storage_service import StorageService

storage = StorageService()
storage.authenticate()
print("✓ Google Drive authentication successful!")

# Verify folder access
if storage.verify_folder_access():
    print("✓ Drive folder accessible!")
    folder_info = storage.get_folder_info()
    print(f"  Folder: {folder_info['name']}")
    print(f"  URL: {folder_info['url']}")
else:
    print("✗ Cannot access Drive folder")
```

---

## Troubleshooting

### Error: "invalid_grant"

**Problem**: Refresh token is invalid or expired.

**Solution**:
1. Delete `token.json` if it exists
2. Run `scripts/get_refresh_token.py` again to get a new refresh token
3. Update `.env` with the new refresh token

### Error: "redirect_uri_mismatch"

**Problem**: OAuth redirect URI doesn't match what's configured.

**Solution**:
1. In Google Cloud Console, go to "APIs & Services" → "Credentials"
2. Click on your OAuth client ID
3. Under "Authorized redirect URIs", add:
   - `http://localhost:8080/`
   - `http://localhost/`
4. Click "SAVE"
5. Try again

### Error: "Access blocked: This app's request is invalid"

**Problem**: App is not verified or test user not added.

**Solution**:
1. Go to "OAuth consent screen" in Google Cloud Console
2. Check that your email is added under "Test users"
3. Click "ADD USERS" and add your email if missing

### Error: "Gmail API has not been used in project"

**Problem**: Gmail API not enabled.

**Solution**:
1. Go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click "ENABLE"
4. Wait 1-2 minutes for it to propagate

### Error: "The user does not have sufficient permissions"

**Problem**: Scopes not granted or insufficient permissions.

**Solution**:
1. Check that all required scopes are added in OAuth consent screen
2. Re-run `scripts/get_refresh_token.py` to re-grant permissions
3. Make sure you click "Allow" for all permissions in the OAuth flow

---

## Security Best Practices

1. **Never commit .env file to Git** - It's already in `.gitignore`
2. **Keep credentials.json secure** - Don't share it publicly
3. **Use Railway environment variables** for production deployment
4. **Rotate credentials periodically** - Create new OAuth client every 6-12 months
5. **Monitor API usage** - Check Google Cloud Console for unusual activity

---

## Summary Checklist

- [ ] Created Google Cloud project
- [ ] Enabled Gmail API
- [ ] Enabled Google Drive API
- [ ] Enabled Geocoding API (optional)
- [ ] Configured OAuth consent screen
- [ ] Created OAuth client ID (Desktop app)
- [ ] Obtained refresh token using `scripts/get_refresh_token.py`
- [ ] Created Google Drive folder for attachments
- [ ] Updated `.env` with all credentials
- [ ] Tested Gmail authentication
- [ ] Tested Drive authentication
- [ ] Verified configuration with `validate_settings()`

Once all items are checked, you're ready to test the email processor locally!

---

## Next Steps

After completing OAuth setup:

1. ✅ **Set up Notion databases** (if not done already) - See `NOTION_SETUP_GUIDE.md`
2. ✅ **Get Claude API key** - From https://console.anthropic.com/
3. ✅ **Test email processing** - Run `python main.py` to start the application
4. ✅ **Monitor first few emails** - Check Notion to verify items are created correctly
5. ✅ **Deploy to Railway** - Once local testing is successful

**Need help?** Check the troubleshooting section above or review the logs in the console.
