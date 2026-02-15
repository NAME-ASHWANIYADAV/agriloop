from fastapi import Depends
from anthropic import AsyncAnthropic
import httpx
from PIL import Image
import io
import base64
from typing import Dict, Any, Optional
import json
from app.services.weather_service import WeatherService, get_weather_service
from app.models.farmer import Farmer

from app.core.config import settings

class AIService:
    def __init__(self, async_client: AsyncAnthropic, weather_service: WeatherService):
        self.async_client = async_client
        self.weather_service = weather_service
        self.text_model_name = 'claude-3-haiku-20240307'
        self.vision_model_name = 'claude-3-haiku-20240307'

    async def get_weather_summary(self, farmer: Farmer) -> str:
        if not farmer.location or "lat" not in farmer.location or "lon" not in farmer.location:
            return "I need your location to provide weather information. Please share your location or tell me your city."

        lat = farmer.location["lat"]
        lon = farmer.location["lon"]
        
        weather_data = await self.weather_service.get_weather(lat, lon)
        city_name = await self.weather_service.get_city_name(farmer)

        # Build farmer context for crop-specific advice
        farmer_context = ""
        if farmer.crops:
            farmer_context = f"\n        Farmer's crops: {', '.join(farmer.crops)}"
        if farmer.farm_size_acres:
            farmer_context += f"\n        Farm size: {farmer.farm_size_acres} acres"

        prompt = f"""
        You are an agricultural assistant. Based on the following weather data for {city_name}, 
        provide a simple, actionable summary for a farmer. Include today's weather and a brief 3-day forecast.
        Focus on what's important for farming (e.g., rain, temperature, wind).
        Give specific advice tied to the farmer's crops if known (e.g., irrigation, spraying, harvesting timing).
        {farmer_context}

        Current Weather: {weather_data['current']}
        Forecast: {weather_data['forecast']}
        """
        response = await self.async_client.messages.create(
            model=self.text_model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    async def get_farming_advice(self, farmer: Farmer, query: str, enriched_context: dict = None) -> str:
        context = f"""
        Farmer Profile:
        - Name: {farmer.name or 'N/A'}
        - Location: {self.weather_service.get_location_string(farmer) or 'N/A'}
        - Farm Size: {farmer.farm_size_acres or 'N/A'} acres
        - Crops: {', '.join(farmer.crops) if farmer.crops else 'N/A'}
        - Language: {farmer.language_preference}
        """

        # Add enriched context from AgriTech Pro
        if enriched_context:
            if "fields" in enriched_context and enriched_context["fields"]:
                context += "\n        AgriTech Pro Fields:\n"
                for f in enriched_context["fields"]:
                    health = f.get("healthScore")
                    ndvi = f.get("ndvi")
                    context += f"        - {f['name']}: Crop={f.get('cropType', 'Unknown')}"
                    if f.get("areaHectares"):
                        context += f", Area={f['areaHectares']}ha"
                    if health is not None:
                        context += f", Health={health}/100"
                    if ndvi is not None:
                        context += f", NDVI={ndvi:.3f}"
                    context += "\n"

            if "weather" in enriched_context:
                weather = enriched_context["weather"]
                context += "\n        Current Weather:\n"
                if isinstance(weather, dict):
                    if "current" in weather:
                        context += f"        - Current: {weather['current']}\n"
                    if "forecast" in weather:
                        context += f"        - Forecast: {weather['forecast']}\n"
                else:
                    context += f"        - {weather}\n"

            if "agricultural_weather" in enriched_context:
                ag = enriched_context["agricultural_weather"]
                if isinstance(ag, dict):
                    context += "\n        Agricultural Metrics:\n"
                    for key, val in ag.items():
                        if key not in ("success",) and val is not None:
                            context += f"        - {key}: {val}\n"

        prompt = f"""
        You are an expert agricultural assistant for Indian farmers. Your advice should be:
        1.  **Specific to this farmer's actual fields and conditions** — reference their field names, health scores, and NDVI values when relevant.
        2.  **Weather-aware** — factor in current and forecasted weather when advising on irrigation, spraying, harvesting, etc.
        3.  **Low-cost and accessible** — prioritize affordable, practical solutions.
        4.  **Actionable** — give clear steps the farmer can take right now.

        If the farmer's fields show low health scores (below 60) or low NDVI (below 0.4), proactively mention this and suggest corrective actions even if not directly asked.

        **Farmer & Environmental Context:**
        {context}

        **Farmer's Query:**
        "{query}"
        """
        response = await self.async_client.messages.create(
            model=self.text_model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()


    async def analyze_pest_image(self, image_url: str) -> str:
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        async with httpx.AsyncClient(auth=auth, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content

        # Convert image to base64 for Claude
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Detect image type
        image = Image.open(io.BytesIO(image_data))
        image_format = image.format.lower() if image.format else 'jpeg'
        media_type = f"image/{image_format}"
        
        prompt = """
        Analyze this image of a plant. Identify any visible pests or diseases. 
        Provide a concise summary of the issue and suggest a low-cost, organic treatment plan.
        If no issue is visible, state that the plant appears healthy.
        Focus on practical advice for Indian farmers.
        """
        
        response = await self.async_client.messages.create(
            model=self.vision_model_name,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        return response.content[0].text.strip()

    async def extract_farmer_details(self, text: str) -> Dict[str, Any]:
        """
        Extracts farmer details like name, crop type, location, and farm size from a given text.
        Returns a dictionary with extracted information.
        """
        prompt = f"""
        Extract the following information from the text provided by a farmer. 
        If a piece of information is not available, return null for that field.
        Return the information as a JSON object with keys: "name", "crop_type", "location", "farm_size_acres", "crops".
        For "location", extract "city", "state", "country", "lat" (latitude), and "lon" (longitude) if available.
        For "farm_size_acres", extract the numerical value in acres or convert to acres if another unit is mentioned.
        For "crops", extract a list of crops.

        Text: "{text}"

        Example Output:
        {{
            "name": "Ramesh",
            "crop_type": "Wheat",
            "location": {{ "city": "Delhi", "state": "Delhi", "country": "India", "lat": 28.7041, "lon": 77.1025 }},
            "farm_size_acres": 5.2,
            "crops": ["Wheat", "Rice"]
        }}
        
        Return ONLY the JSON object, no additional text.
        """
        response = await self.async_client.messages.create(
            model=self.text_model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            # The AI might include extra text, try to find the JSON part
            json_str = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(json_str)
        except json.JSONDecodeError:
            print(f"AI did not return valid JSON for detail extraction: {response.content[0].text}")
            return {}

    async def synthesize_waste_to_wealth_report(self, crop: str, qty: str, location: str, buyers_search_results: str, rate_search_results: str, language_preference: str) -> str:
        """
        Synthesizes a report for waste to wealth based on search results using AI.
        """
        prompt = f"""
        You are a Data Extraction Assistant. Your primary directive is to format extracted data as requested.
        The user's required output language is '{language_preference}'.
        **Your final response MUST be written exclusively in the '{language_preference}' language.**
        Do not use any other language, even if the user's query or the source text is in a different language.

        CONTEXT:
        Search Results for potential buyers: {buyers_search_results}
        Search Results for market rates: {rate_search_results}
        User Location: {location}
        Crop: {crop}

        INSTRUCTIONS:
        1.  **Extract Contacts:** From the "buyers" search results, find any phone numbers (landline or mobile).
        2.  **NO MASKING:** You MUST print the FULL number (e.g., 9876543210). Do NOT use 'X' (e.g., 98XX...).
        3.  **Real Entities:** Only list companies found in the search text. Do not invent names.
        4.  **Fallback to Maps:** If a company is mentioned but no phone number is found, create a Google Maps search link: `https://www.google.com/maps/search/{{Company Name}}+{{City}}`.
        5.  **Location Relevance:** Prioritize results that mention a location close to the user's location. If an exact match is not found, list the closest one and mention its location.
        6.  **Output Format (Strictly in '{language_preference}'):**
            * Company Name
            * 📞: [Full Number] OR Maps Link: [Google Maps Link]
            * 📍: [Location/Nearest City mentioned in snippet]
        """
        response = await self.async_client.messages.create(
            model=self.text_model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()


async def get_ai_service(weather_service: WeatherService = Depends(get_weather_service)):
    client = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
    return AIService(client, weather_service)