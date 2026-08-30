"""
Test script to verify Google Maps Geocoding API is working.
This will help diagnose any issues with the API key, billing, or permissions.
"""

import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

print("=" * 70)
print("Google Maps Geocoding API Test")
print("=" * 70)
print()

# Check if API key is configured
if not GOOGLE_MAPS_API_KEY:
    print("❌ ERROR: GOOGLE_MAPS_API_KEY not found in .env file")
    print()
    print("Please add your Google Maps API key to .env:")
    print("GOOGLE_MAPS_API_KEY=your-api-key-here")
    exit(1)

print(f"✓ API key found: {GOOGLE_MAPS_API_KEY[:20]}...{GOOGLE_MAPS_API_KEY[-4:]}")
print()

# Test addresses (Lambeth-specific locations)
test_addresses = [
    "Kennington Park Road, Lambeth, London",
    "Brixton Hill, London",
    "Clapham Common, London",
    "Westminster Bridge Road, London SE1"
]

print("Testing geocoding with sample Lambeth addresses:")
print("-" * 70)
print()

all_passed = True

for i, address in enumerate(test_addresses, 1):
    print(f"Test {i}: {address}")

    # Make request to Geocoding API
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        # Check response status
        status = data.get("status")

        if status == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            formatted_address = result["formatted_address"]

            print(f"  ✓ SUCCESS")
            print(f"    Address: {formatted_address}")
            print(f"    Latitude: {location['lat']}")
            print(f"    Longitude: {location['lng']}")

        elif status == "REQUEST_DENIED":
            print(f"  ❌ FAILED: Request Denied")
            print(f"    Error: {data.get('error_message', 'No error message')}")
            print()
            print("    Common causes:")
            print("    1. Geocoding API is not enabled in Google Cloud Console")
            print("    2. API key restrictions don't allow Geocoding API")
            print("    3. Billing is not set up for your Google Cloud project")
            print()
            print("    To fix:")
            print("    - Go to https://console.cloud.google.com/")
            print("    - Enable 'Geocoding API' in APIs & Services > Library")
            print("    - Set up billing in Billing section")
            print("    - Check API key restrictions in Credentials")
            all_passed = False

        elif status == "ZERO_RESULTS":
            print(f"  ⚠️  WARNING: No results found")
            print(f"    (This is unusual for the test address)")

        elif status == "OVER_QUERY_LIMIT":
            print(f"  ❌ FAILED: Over Query Limit")
            print(f"    You may have exceeded your quota or need to enable billing")
            all_passed = False

        else:
            print(f"  ❌ FAILED: {status}")
            print(f"    Response: {data}")
            all_passed = False

    except requests.exceptions.RequestException as e:
        print(f"  ❌ FAILED: Network error")
        print(f"    Error: {e}")
        all_passed = False

    print()

print("-" * 70)

if all_passed:
    print("✅ All geocoding tests PASSED!")
    print()
    print("Your Geocoding API is working correctly.")
    print("The email processor should now be able to geocode locations.")
else:
    print("❌ Some geocoding tests FAILED")
    print()
    print("Please check the error messages above and:")
    print("1. Ensure Geocoding API is enabled")
    print("2. Verify billing is set up")
    print("3. Check API key restrictions")
    print()
    print("Helpful links:")
    print("- Enable API: https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com")
    print("- Billing: https://console.cloud.google.com/billing")
    print("- API Keys: https://console.cloud.google.com/apis/credentials")

print()
print("=" * 70)
