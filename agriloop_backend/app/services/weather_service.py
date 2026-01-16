import httpx
from app.core.config import settings
from app.models.farmer import Farmer

class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"

    async def get_weather(self, lat: float, lon: float) -> dict:
        async with httpx.AsyncClient() as client:
            # Fetch current weather
            current_weather_url = f"{self.base_url}/weather"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric"
            }
            current_response = await client.get(current_weather_url, params=params)
            current_response.raise_for_status()
            current_data = current_response.json()

            # Fetch forecast
            forecast_url = f"{self.base_url}/forecast"
            forecast_response = await client.get(forecast_url, params=params)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()

            return {
                "current": current_data,
                "forecast": forecast_data
            }

    def get_location_string(self, farmer: Farmer) -> str:
        location_parts = []
        if farmer.location and farmer.location.get("city"):
            location_parts.append(farmer.location["city"])
        if farmer.location and farmer.location.get("state"):
            location_parts.append(farmer.location["state"])
        if farmer.location and farmer.location.get("country"):
            location_parts.append(farmer.location["country"])
        return ", ".join(filter(None, location_parts))

    async def get_city_name(self, farmer: Farmer) -> str:
        if not farmer.location or "lat" not in farmer.location or "lon" not in farmer.location:
            return "Unknown Location"
        return await self.get_city_name_from_coords(farmer.location["lat"], farmer.location["lon"])

    async def get_city_name_from_coords(self, lat: float, lon: float) -> str:
        async with httpx.AsyncClient() as client:
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {"lat": lat, "lon": lon, "appid": self.api_key, "units": "metric"}
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get("name", "Unknown Location")
            return "Unknown Location"

def get_weather_service():
    return WeatherService(api_key=settings.OPENWEATHER_API_KEY)
