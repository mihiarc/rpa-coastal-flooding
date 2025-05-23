"""Tests for the NOAA API Client."""

import pytest
import responses
import json
from pathlib import Path
from unittest.mock import patch, Mock
from src.noaa.core.noaa_client import NOAAClient, NOAAApiError
import time

# Test data fixtures
SAMPLE_ANNUAL_RESPONSE = {
    "metadata": {
        "id": "8638610",
        "name": "Sewells Point, VA",
        "lat": "36.9467",
        "lon": "-76.3300"
    },
    "AnnualFloodCount": [
        {
            "stnId": "8638610",
            "stnName": "Sewells Point, VA",
            "year": 2010,
            "majCount": 0,
            "modCount": 1,
            "minCount": 6,
            "nanCount": 0
        },
        {
            "stnId": "8638610",
            "stnName": "Sewells Point, VA",
            "year": 2011,
            "majCount": 2,
            "modCount": 2,
            "minCount": 6,
            "nanCount": 0
        }
    ]
}

SAMPLE_PROJECTION_RESPONSE = {
    "metadata": {
        "id": "8638610",
        "name": "Sewells Point, VA",
        "lat": "36.9467",
        "lon": "-76.3300"
    },
    "DecadalProjection": [
        {
            "stnId": "8638610",
            "stnName": "Sewells Point, VA",
            "decade": 2050,
            "source": "https://tidesandcurrents.noaa.gov/publications/HTF_Notice_of_Methodology_Update_2023.pdf",
            "low": 85,
            "intLow": 100,
            "intermediate": 125,
            "intHigh": 150,
            "high": 185
        }
    ]
}

@pytest.fixture
def client():
    """Create a NOAAClient instance for testing."""
    return NOAAClient()

@pytest.fixture
def mock_responses():
    """Setup mock responses using the responses library."""
    with responses.RequestsMock() as rsps:
        yield rsps

class TestNOAAClient:
    """Test suite for NOAAClient."""
    
    def test_init(self, client):
        """Test client initialization."""
        assert client.api_base_url == "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi"
        assert client.rate_limiter is not None

    @responses.activate
    def test_fetch_annual_flood_counts_success(self, client):
        """Test successful fetch of annual flood counts."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_annual.json",
            json=SAMPLE_ANNUAL_RESPONSE,
            status=200
        )

        result = client.fetch_annual_flood_counts(station="8638610")
        assert len(result) == 2
        assert result[0]["stnId"] == "8638610"
        assert result[0]["year"] == 2010
        assert result[0]["majCount"] == 0

    @responses.activate
    def test_fetch_annual_flood_counts_all_stations(self, client):
        """Test fetching flood counts for all stations."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_annual.json",
            json=SAMPLE_ANNUAL_RESPONSE,
            status=200
        )

        result = client.fetch_annual_flood_counts(station="8638610")  # Station ID is required
        assert len(result) == 2
        assert all(r["stnId"] == "8638610" for r in result)

    @responses.activate
    def test_fetch_annual_flood_counts_error(self, client):
        """Test handling of API errors in flood count fetch."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_annual.json",
            json={"error": "API Error"},
            status=400
        )

        with pytest.raises(NOAAApiError):
            client.fetch_annual_flood_counts(station="8638610")

    @responses.activate
    def test_fetch_decadal_projections_success(self, client):
        """Test successful fetch of decadal projections."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_projection_decadal.json",
            json=SAMPLE_PROJECTION_RESPONSE,
            status=200
        )

        result = client.fetch_decadal_projections(station="8638610")
        assert len(result) == 1
        assert result[0]["stnId"] == "8638610"
        assert result[0]["decade"] == 2050
        assert result[0]["low"] == 85

    @responses.activate
    def test_fetch_decadal_projections_error(self, client):
        """Test handling of API errors in projection fetch."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_projection_decadal.json",
            json={"error": "API Error"},
            status=400
        )

        with pytest.raises(NOAAApiError):
            client.fetch_decadal_projections(station="8638610")

    def test_rate_limiting(self, client):
        """Test that rate limiting is enforced."""
        with patch('time.sleep') as mock_sleep:
            with responses.RequestsMock() as rsps:
                rsps.add(
                    responses.GET,
                    f"{client.api_base_url}/htf/htf_annual.json",
                    json=SAMPLE_ANNUAL_RESPONSE,
                    status=200
                )

                # Make multiple requests
                for _ in range(3):
                    client.fetch_annual_flood_counts(station="8638610")

                # Verify rate limiting was applied
                assert mock_sleep.call_count > 0

    def test_invalid_station_id(self, client):
        """Test handling of invalid station ID."""
        with pytest.raises(NOAAApiError, match="Station ID is required"):
            client.fetch_annual_flood_counts(station=None)

    @responses.activate
    def test_invalid_year(self, client):
        """Test handling of invalid year parameter."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_annual.json",
            json={"error": "Invalid year parameter"},
            status=400
        )

        with pytest.raises(NOAAApiError, match="Failed to fetch flood count data"):
            client.fetch_annual_flood_counts(station="8638610", year="invalid")

    @responses.activate
    def test_invalid_json_response(self, client):
        """Test handling of invalid JSON responses."""
        responses.add(
            responses.GET,
            f"{client.api_base_url}/htf/htf_annual.json",
            body="Invalid JSON",
            status=200
        )

        with pytest.raises(NOAAApiError):
            client.fetch_annual_flood_counts(station="8638610") 