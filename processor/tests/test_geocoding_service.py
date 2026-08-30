"""
Unit tests for geocoding service.
Tests Google Maps API integration with mocked responses.
"""

import pytest
from unittest.mock import Mock, patch
import json

from services.geocoding_service import GeocodingService


@pytest.fixture
def geocoding_service():
    """Create a geocoding service instance with mocked settings."""
    with patch('services.geocoding_service.get_settings') as mock_settings:
        # Mock settings
        settings_obj = Mock()
        settings_obj.google_maps_api_key = "test-api-key"
        mock_settings.return_value = settings_obj

        service = GeocodingService()
        yield service


@pytest.fixture
def sample_geocoding_response():
    """Sample Google Maps Geocoding API response."""
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": "Brixton Hill, London SW2, UK",
                "geometry": {
                    "location": {
                        "lat": 51.4531,
                        "lng": -0.1178
                    }
                },
                "place_id": "ChIJ_place_id_123"
            }
        ]
    }


def test_is_enabled_with_api_key(geocoding_service):
    """Test that service is enabled when API key is configured."""
    assert geocoding_service.is_enabled() is True


def test_is_enabled_without_api_key():
    """Test that service is disabled without API key."""
    with patch('services.geocoding_service.get_settings') as mock_settings:
        settings_obj = Mock()
        settings_obj.google_maps_api_key = None
        mock_settings.return_value = settings_obj

        service = GeocodingService()
        assert service.is_enabled() is False


@patch('services.geocoding_service.requests.get')
def test_geocode_location_success(mock_get, geocoding_service, sample_geocoding_response):
    """Test successful geocoding of a location."""
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = sample_geocoding_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Geocode location
    result = geocoding_service.geocode_location("Brixton Hill")

    # Assert
    assert result is not None
    assert result["name"] == "Brixton Hill"
    assert result["lat"] == 51.4531
    assert result["lng"] == -0.1178
    assert "Brixton Hill" in result["formatted_address"]


@patch('services.geocoding_service.requests.get')
def test_geocode_location_not_found(mock_get, geocoding_service):
    """Test geocoding when location is not found."""
    # Mock API response with ZERO_RESULTS
    mock_response = Mock()
    mock_response.json.return_value = {
        "status": "ZERO_RESULTS",
        "results": []
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Geocode location
    result = geocoding_service.geocode_location("Nonexistent Street")

    # Assert
    assert result is None


@patch('services.geocoding_service.requests.get')
def test_geocode_location_network_error(mock_get, geocoding_service):
    """Test handling network errors."""
    # Mock network error
    mock_get.side_effect = Exception("Network error")

    # Geocode location
    result = geocoding_service.geocode_location("Test Street")

    # Assert
    assert result is None


@patch('services.geocoding_service.requests.get')
def test_geocode_locations_multiple(mock_get, geocoding_service, sample_geocoding_response):
    """Test geocoding multiple locations."""
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = sample_geocoding_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Geocode locations
    results = geocoding_service.geocode_locations(["Brixton Hill", "Clapham High Street"])

    # Assert
    assert len(results) == 2
    assert all(r["lat"] and r["lng"] for r in results)


def test_geocode_locations_empty_list(geocoding_service):
    """Test geocoding empty list."""
    results = geocoding_service.geocode_locations([])
    assert results == []


def test_geocode_locations_disabled():
    """Test geocoding when service is disabled."""
    with patch('services.geocoding_service.get_settings') as mock_settings:
        settings_obj = Mock()
        settings_obj.google_maps_api_key = None
        mock_settings.return_value = settings_obj

        service = GeocodingService()
        results = service.geocode_locations(["Test Street"])

        assert results == []


@patch('services.geocoding_service.requests.get')
def test_geocode_locations_rate_limit(mock_get, geocoding_service, sample_geocoding_response):
    """Test that large lists are limited to avoid rate limits."""
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = sample_geocoding_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Try to geocode 30 locations (should limit to 20)
    locations = [f"Street {i}" for i in range(30)]
    results = geocoding_service.geocode_locations(locations)

    # Should have called API max 20 times
    assert mock_get.call_count <= 20


@patch('services.geocoding_service.requests.get')
def test_geocode_locations_as_json(mock_get, geocoding_service, sample_geocoding_response):
    """Test geocoding and returning as JSON string."""
    # Mock API response
    mock_response = Mock()
    mock_response.json.return_value = sample_geocoding_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Geocode as JSON
    json_str = geocoding_service.geocode_locations_as_json(["Brixton Hill"])

    # Assert
    assert json_str != ""
    parsed = json.loads(json_str)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Brixton Hill"


def test_geocode_locations_as_json_disabled():
    """Test that empty string is returned when disabled."""
    with patch('services.geocoding_service.get_settings') as mock_settings:
        settings_obj = Mock()
        settings_obj.google_maps_api_key = None
        mock_settings.return_value = settings_obj

        service = GeocodingService()
        json_str = service.geocode_locations_as_json(["Test"])

        assert json_str == ""


def test_parse_geocoded_json(geocoding_service):
    """Test parsing geocoded JSON string."""
    json_str = '[{"name":"Test","lat":51.5,"lng":-0.1}]'
    result = geocoding_service.parse_geocoded_json(json_str)

    assert len(result) == 1
    assert result[0]["name"] == "Test"
    assert result[0]["lat"] == 51.5


def test_parse_geocoded_json_empty(geocoding_service):
    """Test parsing empty JSON string."""
    result = geocoding_service.parse_geocoded_json("")
    assert result == []


def test_parse_geocoded_json_invalid(geocoding_service):
    """Test parsing invalid JSON."""
    result = geocoding_service.parse_geocoded_json("not json")
    assert result == []


def test_format_for_display(geocoding_service):
    """Test formatting geocoded locations for display."""
    geocoded = [
        {
            "name": "Brixton Hill",
            "formatted_address": "Brixton Hill, London SW2, UK",
            "lat": 51.4531,
            "lng": -0.1178
        }
    ]

    display = geocoding_service.format_for_display(geocoded)

    assert "Brixton Hill" in display
    assert "51.4531" in display
    assert "-0.1178" in display


def test_format_for_display_empty(geocoding_service):
    """Test formatting empty list."""
    display = geocoding_service.format_for_display([])
    assert "No locations" in display


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
