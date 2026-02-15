"""
AgriTech Pro Service
HTTP client wrapper for calling AgriTech Pro's internal API endpoints.
Used by the WhatsApp handler to fetch field data, satellite analysis, and weather.
"""

import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings


class AgriTechService:
    """Service for communicating with AgriTech Pro's internal API."""

    def __init__(self):
        self.base_url = settings.AGRITECH_API_URL.rstrip('/')
        self.api_key = settings.AGRITECH_INTERNAL_API_KEY
        self.headers = {
            "X-Internal-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        self.timeout = 30.0  # Default timeout in seconds

    async def lookup_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Find an AgriTech Pro user by phone number.
        Returns user info dict or None if not found.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/internal/user/by-phone",
                    params={"phone": phone},
                    headers=self.headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("user")
                elif response.status_code == 404:
                    return None
                else:
                    print(f"AgriTech user lookup failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"AgriTech user lookup error: {e}")
            return None

    async def get_user_fields(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all fields for a given AgriTech Pro user.
        Returns list of field dicts.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/internal/fields/{user_id}",
                    headers=self.headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("fields", [])
                else:
                    print(f"AgriTech fields fetch failed: {response.status_code}")
                    return []
        except Exception as e:
            print(f"AgriTech fields error: {e}")
            return []

    async def analyze_field_health(self, latitude: float, longitude: float, field_name: str = "Field") -> Optional[Dict[str, Any]]:
        """
        Run satellite analysis on a field location.
        Returns analysis result dict or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:  # Longer timeout for satellite
                response = await client.post(
                    f"{self.base_url}/api/internal/satellite/analyze",
                    json={
                        "latitude": latitude,
                        "longitude": longitude,
                        "field_name": field_name,
                    },
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"AgriTech satellite analysis failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"AgriTech satellite analysis error: {e}")
            return None

    async def predict_crop(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Predict crop type for a given location using CNN-LSTM model.
        Returns prediction result dict or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/internal/satellite/predict-crop",
                    json={
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"AgriTech crop prediction failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"AgriTech crop prediction error: {e}")
            return None

    async def get_agricultural_weather(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get agricultural weather data (soil moisture, evapotranspiration, etc.).
        Returns weather data dict or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/internal/weather/agricultural",
                    params={"lat": latitude, "lon": longitude},
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"AgriTech weather failed: {response.status_code}")
                    return None
        except Exception as e:
            print(f"AgriTech weather error: {e}")
            return None


def get_agritech_service():
    """Dependency injection factory for AgriTechService."""
    return AgriTechService()
