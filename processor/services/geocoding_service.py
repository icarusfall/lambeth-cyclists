"""
Geocoding service for converting location strings to coordinates.
Uses Google Maps Geocoding API to geocode street names and landmarks.
"""

import json
from typing import List, Dict, Optional
import requests

from config.settings import get_settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class GeocodingService:
    """
    Service for geocoding locations using Google Maps API.
    Converts street names and landmarks to lat/lng coordinates.
    """

    def __init__(self):
        """Initialize geocoding service."""
        self.settings = get_settings()
        self.api_key = self.settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"

        # Add context for better UK results
        self.region = "uk"
        self.bounds = "51.4,-0.2|51.5,-0.05"  # Rough bounds for Lambeth

    def is_enabled(self) -> bool:
        """Check if geocoding is enabled (API key configured)."""
        return self.api_key is not None and self.api_key != ""

    def geocode_location(self, location: str) -> Optional[Dict[str, any]]:
        """
        Geocode a single location string.

        Args:
            location: Location string (e.g., "Brixton Hill", "A23", "Lambert Road")

        Returns:
            Dictionary with:
                - name: Original location string
                - formatted_address: Full formatted address from Google
                - lat: Latitude
                - lng: Longitude
                - place_id: Google Place ID
            Or None if geocoding fails
        """
        if not self.is_enabled():
            logger.warning("Geocoding service disabled (no API key)")
            return None

        try:
            # Build query with context for Lambeth, London
            query = f"{location}, Lambeth, London, UK"

            # API parameters
            params = {
                "address": query,
                "key": self.api_key,
                "region": self.region,
                "bounds": self.bounds,
            }

            # Make request
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check status
            if data.get("status") != "OK":
                logger.warning(f"Geocoding failed for '{location}': {data.get('status')}")
                return None

            # Extract first result
            if not data.get("results"):
                logger.warning(f"No geocoding results for '{location}'")
                return None

            result = data["results"][0]
            geometry = result.get("geometry", {})
            location_data = geometry.get("location", {})

            geocoded = {
                "name": location,
                "formatted_address": result.get("formatted_address"),
                "lat": location_data.get("lat"),
                "lng": location_data.get("lng"),
                "place_id": result.get("place_id"),
            }

            logger.debug(
                f"Geocoded '{location}' -> {geocoded['formatted_address']} "
                f"({geocoded['lat']}, {geocoded['lng']})"
            )

            return geocoded

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error geocoding '{location}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error geocoding '{location}': {e}", exc_info=True)
            return None

    def geocode_locations(self, locations: List[str]) -> List[Dict[str, any]]:
        """
        Geocode multiple locations.

        Args:
            locations: List of location strings

        Returns:
            List of successfully geocoded location dictionaries
        """
        if not self.is_enabled():
            logger.info("Geocoding service disabled, skipping geocoding")
            return []

        if not locations:
            return []

        geocoded_results = []

        # Limit to reasonable number to avoid rate limits / excessive API calls
        locations_to_process = locations[:20]

        if len(locations) > 20:
            logger.warning(
                f"Geocoding limited to first 20 of {len(locations)} locations to avoid rate limits"
            )

        for location in locations_to_process:
            # Skip empty or very short location strings
            if not location or len(location.strip()) < 3:
                continue

            result = self.geocode_location(location)
            if result:
                geocoded_results.append(result)

        logger.info(
            f"Geocoded {len(geocoded_results)}/{len(locations_to_process)} locations"
        )

        return geocoded_results

    def geocode_locations_as_json(self, locations: List[str]) -> str:
        """
        Geocode locations and return as JSON string for storage in Notion.

        Args:
            locations: List of location strings

        Returns:
            JSON string with geocoded locations (or empty string if none/disabled)
        """
        geocoded = self.geocode_locations(locations)

        if not geocoded:
            return ""

        try:
            # Compact JSON format
            json_str = json.dumps(geocoded, separators=(',', ':'))
            return json_str

        except Exception as e:
            logger.error(f"Error serializing geocoded locations to JSON: {e}")
            return ""

    def parse_geocoded_json(self, json_str: str) -> List[Dict[str, any]]:
        """
        Parse geocoded locations from JSON string.

        Args:
            json_str: JSON string from Notion

        Returns:
            List of geocoded location dictionaries
        """
        if not json_str:
            return []

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing geocoded JSON: {e}")
            return []

    def format_for_display(self, geocoded: List[Dict[str, any]]) -> str:
        """
        Format geocoded locations for human-readable display.

        Args:
            geocoded: List of geocoded location dictionaries

        Returns:
            Formatted string with locations and coordinates
        """
        if not geocoded:
            return "No locations geocoded"

        lines = []
        for loc in geocoded:
            lines.append(
                f"• {loc['name']}: {loc['formatted_address']} "
                f"({loc['lat']:.6f}, {loc['lng']:.6f})"
            )

        return "\n".join(lines)
