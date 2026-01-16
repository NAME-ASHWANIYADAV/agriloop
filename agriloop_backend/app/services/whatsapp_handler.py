from twilio.rest import Client
from typing import Optional, Dict, Any
from fastapi import BackgroundTasks
import asyncio

from app.core.config import settings
from app.models.farmer import Farmer
from app.models.interaction import Interaction
from app.models.farmer_state import FarmerState
from app.services.ai_service import AIService
from app.services.weather_service import WeatherService
from app.services.translation_service import TranslationService
from app.services.web_search_service import WebSearchService, get_web_search_service

INDIAN_LANGUAGES = {
    "english": "en", "hindi": "hi", "bengali": "bn", "telugu": "te",
    "marathi": "mr", "tamil": "ta", "gujarati": "gu", "kannada": "kn",
    "malayalam": "ml", "oriya": "or", "punjabi": "pa", "assamese": "as",
    "kashmiri": "ks", "sanskrit": "sa", "sindhi": "sd", "urdu": "ur",
}

MAIN_MENU_TEXT = """🌿 *AgriLoop AI Menu*
1️⃣ Weather Info
2️⃣ Ask Expert (Chat)
3️⃣ Pest Check (Image)
4️⃣ Waste to Wealth
5️⃣ Profile
6️⃣ Change Language
_Reply 0 to reset._"""

class WhatsAppHandler:
    def __init__(
        self,
        ai_service: AIService,
        weather_service: WeatherService,
        translation_service: TranslationService,
        web_search_service: WebSearchService
    ):
        self.ai_service = ai_service
        self.weather_service = weather_service
        self.translation_service = translation_service
        self.web_search_service = web_search_service
        self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN) if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN else None

    async def handle_message(self, payload: dict, background_tasks: BackgroundTasks):
        from_number = payload.get("From")
        message_body = payload.get("Body", "").strip()
        media_url = payload.get("MediaUrl0")
        latitude = payload.get("Latitude")
        longitude = payload.get("Longitude")

        farmer = await self.get_or_create_farmer(from_number)

        # Onboarding flow takes precedence
        if farmer.onboarding_state != "completed":
            response_text = await self.handle_onboarding(farmer, message_body)
            await self.send_whatsapp_message(to_number=from_number, message=response_text)
        else:
            # Main state machine logic
            await self.handle_stateful_message(farmer, message_body, media_url, latitude, longitude, background_tasks)

        # Log every interaction
        await self.log_interaction(farmer, message_body, media_url)

    async def get_or_create_farmer(self, phone_number: str) -> Farmer:
        farmer = await Farmer.find_one(Farmer.phone_number == phone_number)
        if not farmer:
            farmer = Farmer(phone_number=phone_number)
            await farmer.insert()
        return farmer

    async def handle_onboarding(self, farmer: Farmer, message_body: Optional[str]) -> str:
        # This function remains largely the same, guiding the user through setup.
        # Once completed, the farmer's state will be 'completed'.
        if farmer.onboarding_state == "initial":
            farmer.onboarding_state = "awaiting_language"
            await farmer.save()
            lang_options = ", ".join([f"{lang.capitalize()}" for lang in INDIAN_LANGUAGES.keys()])
            return f"Welcome to AgriLoop AI! Please choose your preferred language (e.g., English, Hindi).\n\nSupported: {lang_options}"

        elif farmer.onboarding_state == "awaiting_language":
            chosen_language_name = message_body.lower()
            if chosen_language_name in INDIAN_LANGUAGES:
                farmer.language_preference = INDIAN_LANGUAGES[chosen_language_name]
                farmer.onboarding_state = "awaiting_name"
                await farmer.save()
                return await self.translate("What is your name?", farmer)
            else:
                return await self.translate("Invalid language. Please choose a supported one.", farmer)

        elif farmer.onboarding_state == "awaiting_name":
            if message_body:
                farmer.name = message_body.strip()
                farmer.onboarding_state = "completed"
                await farmer.save() # State is now 'completed' and 'current_state' is MAIN_MENU by default
                
                welcome_message = f"Hello {farmer.name}! You are all set."
                translated_welcome = await self.translate(welcome_message, farmer)
                translated_menu = await self.translate(MAIN_MENU_TEXT, farmer)
                return f"{translated_welcome}\n\n{translated_menu}"
            else:
                return await self.translate("Please tell me your name.", farmer)
        
        return "An unexpected error occurred during onboarding."

    async def handle_stateful_message(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Main router for handling messages based on the farmer's current state."""
        
        # Always allow reset
        if message_body.lower() in ["0", "hi", "hello", "menu"]:
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            menu_text = await self.translate(MAIN_MENU_TEXT, farmer)
            await self.send_whatsapp_message(farmer.phone_number, menu_text)
            return

        state_handlers = {
            FarmerState.MAIN_MENU: self.handle_main_menu,
            FarmerState.AWAITING_QUERY: self.handle_awaiting_query,
            FarmerState.AWAITING_IMAGE: self.handle_awaiting_image,
            FarmerState.AWAITING_LANGUAGE_CHANGE: self.handle_awaiting_language_change,
            FarmerState.AWAITING_LOCATION: self.handle_awaiting_location,
            FarmerState.CONFIRM_LOCATION: self.handle_confirm_location,
            FarmerState.AWAITING_WASTE_CROP: self.handle_awaiting_waste_crop,
            FarmerState.AWAITING_WASTE_QUANTITY: self.handle_awaiting_waste_quantity,
            FarmerState.WASTE_CONFIRM_DEAL: self.handle_waste_confirm_deal,
        }

        handler = state_handlers.get(farmer.current_state)
        if handler:
            await handler(farmer, message_body, media_url, latitude, longitude, background_tasks)
        else: # Default/fallback
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            menu_text = await self.translate(MAIN_MENU_TEXT, farmer)
            await self.send_whatsapp_message(farmer.phone_number, menu_text)

    async def handle_main_menu(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for the MAIN_MENU state."""
        if message_body == "1":
            if farmer.location and "city" in farmer.location:
                farmer.current_state = FarmerState.CONFIRM_LOCATION
                await farmer.save()
                
                location_str = farmer.location['city']
                prompt = f"Your saved location is {location_str}. Is this correct? (Yes/No)"
                translated_prompt = await self.translate(prompt, farmer)
                await self.send_whatsapp_message(farmer.phone_number, translated_prompt)
            else:
                farmer.current_state = FarmerState.AWAITING_LOCATION
                await farmer.save()
                await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please share your location to get weather information.", farmer))
        
        elif message_body == "2":
            farmer.current_state = FarmerState.AWAITING_QUERY
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please ask your question.", farmer))
        
        elif message_body == "3":
            farmer.current_state = FarmerState.AWAITING_IMAGE
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please upload a photo of the affected plant.", farmer))

        elif message_body == "4": # Waste to Wealth
            farmer.current_state = FarmerState.AWAITING_WASTE_CROP
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Which crop residue do you have? (e.g., Rice Stubble, Wheat Straw)", farmer))

        elif message_body == "5":
            profile_info = f"""*Your AgriLoop AI Profile*
👤 *Name:* {farmer.name or 'Not Set'}
📞 *Phone:* {farmer.phone_number}
🌐 *Language:* {farmer.language_preference.upper()}
📍 *Location:* {farmer.location.get('city', 'Not Set') if farmer.location else 'Not Set'}
🌾 *Crops:* {', '.join(farmer.crops) if farmer.crops else 'Not Set'}
🏞️ *Farm Size:* {f'{farmer.farm_size_acres} acres' if farmer.farm_size_acres else 'Not Set'}
"""
            await self.send_whatsapp_message(farmer.phone_number, await self.translate(profile_info, farmer))

        elif message_body == "6":
            farmer.current_state = FarmerState.AWAITING_LANGUAGE_CHANGE
            await farmer.save()
            lang_options = ", ".join([f"{lang.capitalize()}" for lang in INDIAN_LANGUAGES.keys()])
            await self.send_whatsapp_message(farmer.phone_number, await self.translate(f"Please choose your new language.\n\nSupported: {lang_options}", farmer))

        else: # Invalid option
            menu_text = await self.translate(MAIN_MENU_TEXT, farmer)
            await self.send_whatsapp_message(farmer.phone_number, menu_text)

    async def handle_awaiting_query(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_QUERY state. Expects text."""
        if message_body:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Thanks! Analyzing your query...", farmer))
            
            # Translate query to English for the AI
            translated_query = await self.translation_service.translate_text(message_body, "en", farmer.language_preference)
            
            background_tasks.add_task(self.run_ai_farming_advice, farmer, translated_query)
            
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
        else: # No text provided
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please type your question.", farmer))

    async def handle_awaiting_image(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_IMAGE state. Expects an image."""
        if media_url:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Thanks! Analyzing your image...", farmer))
            background_tasks.add_task(self.run_ai_pest_analysis, farmer, media_url)
            
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
        else: # No image provided
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please upload an image for analysis.", farmer))

    async def handle_awaiting_language_change(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_LANGUAGE_CHANGE state."""
        chosen_language_name = message_body.lower()
        if chosen_language_name in INDIAN_LANGUAGES:
            farmer.language_preference = INDIAN_LANGUAGES[chosen_language_name]
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            
            response_text = f"Language changed to {chosen_language_name.capitalize()}."
            translated_response = await self.translate(response_text, farmer)
            translated_menu = await self.translate(MAIN_MENU_TEXT, farmer)
            
            await self.send_whatsapp_message(farmer.phone_number, f"{translated_response}\n\n{translated_menu}")
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Invalid language. Please choose a supported one.", farmer))

    async def handle_awaiting_location(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_LOCATION state. Expects a location."""
        if latitude and longitude:
            city_name = await self.weather_service.get_city_name_from_coords(float(latitude), float(longitude))
            farmer.location = {"lat": float(latitude), "lon": float(longitude), "city": city_name}
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            
            await self.send_whatsapp_message(farmer.phone_number, await self.translate(f"Location updated to {city_name}. Fetching weather...", farmer))
            background_tasks.add_task(self.run_weather_report, farmer)
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please share your location using the attach button.", farmer))

    async def handle_confirm_location(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for CONFIRM_LOCATION state. Expects Yes/No."""
        response_lower = message_body.lower()
        if response_lower in ["yes", "y", "haan", "ha"]:
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Fetching weather...", farmer))
            background_tasks.add_task(self.run_weather_report, farmer)
        elif response_lower in ["no", "n", "nahi"]:
            farmer.current_state = FarmerState.AWAITING_LOCATION
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please share your new location.", farmer))
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Invalid response. Please reply with Yes or No.", farmer))

    async def handle_awaiting_waste_crop(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_WASTE_CROP state. Expects crop type."""
        if message_body:
            farmer.temp_data = {"waste_crop": message_body.strip()}
            farmer.current_state = FarmerState.AWAITING_WASTE_QUANTITY
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate(f"How many tons of {message_body.strip()} do you have?", farmer))
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please tell me the type of crop residue you have.", farmer))

    async def handle_awaiting_waste_quantity(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for AWAITING_WASTE_QUANTITY state. Expects quantity."""
        if message_body and farmer.temp_data and "waste_crop" in farmer.temp_data:
            crop = farmer.temp_data["waste_crop"]
            qty_str = message_body.strip().lower().replace("ton", "").replace("tons", "").replace("quintal", "").replace("quintals", "").strip()
            try:
                # Attempt to parse as float, supporting comma as decimal separator
                qty = float(qty_str.replace(',', '.'))
            except ValueError:
                qty = 1.0 # Default to 1 ton if parsing fails

            base_rate = 0
            if "paddy" in crop.lower():
                base_rate = 1800 # per ton
            elif "wheat" in crop.lower():
                base_rate = 1500 # per ton
            # Add more crop-specific rates as needed
            
            potential_income = qty * base_rate
            carbon_saved = qty * 1.46 # Standard factor

            # Store calculations in temp_data
            farmer.temp_data["waste_qty"] = qty
            farmer.temp_data["potential_income"] = potential_income
            farmer.temp_data["carbon_saved"] = carbon_saved
            farmer.current_state = FarmerState.WASTE_CONFIRM_DEAL
            await farmer.save()

            report = f"""📊 *Anumanit Report (Estimate):*
💰 *Potential Income:* ₹{potential_income:,.0f}
🌍 *Carbon Saved:* {carbon_saved:.2f} tons (You are a Climate Hero! 🦸‍♂️)

*Kya aap isse bechna chahte hain? (Reply 'Yes' or 'Haan')*"""
            await self.send_whatsapp_message(farmer.phone_number, await self.translate(report, farmer))
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Please provide the quantity in tons/quintals.", farmer))

    async def handle_waste_confirm_deal(self, farmer: Farmer, message_body: str, media_url: Optional[str], latitude: Optional[str], longitude: Optional[str], background_tasks: BackgroundTasks):
        """Handler for WASTE_CONFIRM_DEAL state. Expects 'Yes' or 'Haan' to trigger search."""
        response_lower = message_body.lower()
        if response_lower in ["yes", "y", "haan", "ha"]:
            if farmer.temp_data and "waste_crop" in farmer.temp_data and "waste_qty" in farmer.temp_data:
                crop = farmer.temp_data["waste_crop"]
                qty = farmer.temp_data["waste_qty"]
                user_location = farmer.location

                # Clear temp data and reset state immediately
                farmer.temp_data = None
                farmer.current_state = FarmerState.MAIN_MENU
                await farmer.save()

                if user_location and "city" in user_location:
                    await self.send_whatsapp_message(farmer.phone_number, await self.translate("🔎 Searching for nearest buyers & arranging pickup... Please wait.", farmer))
                    background_tasks.add_task(self.perform_live_market_research, farmer, crop, qty, user_location)
                else:
                    await self.send_whatsapp_message(farmer.phone_number, await self.translate("To find market rates and buyers, please update your location first (Option 1 in Main Menu).", farmer))
            else:
                await self.send_whatsapp_message(farmer.phone_number, await self.translate("Something went wrong with the details. Please try again from the main menu (Reply 0).", farmer))
                farmer.current_state = FarmerState.MAIN_MENU
                await farmer.save()
        elif response_lower in ["no", "n", "nahi"]:
            farmer.temp_data = None # Clear temp data
            farmer.current_state = FarmerState.MAIN_MENU
            await farmer.save()
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Okay, returning to main menu.", farmer))
        else:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Invalid response. Please reply 'Yes' or 'Haan' to confirm, or 'No'/'Nahi' to cancel.", farmer))

    # --- Background Task Functions ---

    async def run_weather_report(self, farmer: Farmer):
        """Fetches and sends weather report."""
        weather_response = await self.ai_service.get_weather_summary(farmer)
        translated_response = await self.translate(weather_response, farmer)
        await self.send_whatsapp_message(farmer.phone_number, translated_response)
        weather_response = await self.ai_service.get_weather_summary(farmer)
        translated_response = await self.translate(weather_response, farmer)
        await self.send_whatsapp_message(farmer.phone_number, translated_response)


    async def run_ai_farming_advice(self, farmer: Farmer, query: str):
        """Runs AI advice generation and sends the result."""
        ai_response = await self.ai_service.get_farming_advice(farmer, query)
        translated_response = await self.translate(ai_response, farmer)
        await self.send_whatsapp_message(farmer.phone_number, translated_response)

    async def run_ai_pest_analysis(self, farmer: Farmer, media_url: str):
        """Runs AI pest analysis and sends the result."""
        ai_response = await self.ai_service.analyze_pest_image(media_url)
        translated_response = await self.translate(ai_response, farmer)
        await self.send_whatsapp_message(farmer.phone_number, translated_response)

    async def perform_live_market_research(self, farmer: Farmer, crop: str, qty: str, user_location: Dict[str, Any]):
        """Performs live web search for market rates and buyers, then synthesizes with AI."""
        if not user_location or "city" not in user_location:
            await self.send_whatsapp_message(farmer.phone_number, await self.translate("Could not perform market research due to missing location information.", farmer))
            return

        location_city = user_location["city"]
        
        # Define initial aggressive search queries for buyers (city-specific)
        buyer_queries_city = [
            f"Biomass briquette manufacturers in {location_city} mobile number",
            f"Paddy straw buyers in {location_city} contact",
            f"{crop} residue buyers in {location_city} phone number",
            f"Biofuel plant manager in {location_city} mobile number",
        ]
        
        buyers_results = await self.web_search_service.search_market_data(buyer_queries_city)

        # Fallback to broader search if city-specific search yields no relevant results
        if "No relevant information found online" in buyers_results:
            fallback_locations = [
                user_location.get("state"), # try state name
                "nearest industrial hub India",
                "major agricultural markets India"
            ]
            for fallback_loc in fallback_locations:
                if fallback_loc and fallback_loc != "None": # Ensure fallback_loc is not empty or "None"
                    buyer_queries_fallback = [
                        f"Biomass briquette manufacturers in {fallback_loc} mobile number",
                        f"Paddy straw buyers in {fallback_loc} contact",
                        f"{crop} residue buyers in {fallback_loc} phone number",
                        f"Biofuel plant manager in {fallback_loc} mobile number",
                    ]
                    buyers_results_fallback = await self.web_search_service.search_market_data(buyer_queries_fallback)
                    if "No relevant information found online" not in buyers_results_fallback:
                        buyers_results = buyers_results_fallback
                        break

        # Search for rates (can also use fallback logic if needed)
        from datetime import datetime
        current_month = datetime.now().strftime("%B")
        current_year = datetime.now().year
        rate_query = f"Current price of {crop} stubble biomass in India {current_month} {current_year}"
        rate_results = await self.web_search_service.search_market_data([rate_query])

        # AI Synthesis with the new, more aggressive prompt
        ai_report = await self.ai_service.synthesize_waste_to_wealth_report(
            crop=crop,
            qty=str(qty), # Ensure qty is string for the prompt
            location=location_city,
            buyers_search_results=buyers_results,
            rate_search_results=rate_results,
            language_preference=farmer.language_preference # Pass language preference
        )
        
        await self.send_whatsapp_message(farmer.phone_number, ai_report)

    # --- Utility Functions ---

    async def log_interaction(self, farmer: Farmer, query: str, media_url: Optional[str]):
        """Saves interaction to the database."""
        interaction = Interaction(
            farmer=farmer,
            query_text=query or "",
            media_url=media_url
        )
        await interaction.insert()
        
    async def translate(self, text: str, farmer: Farmer) -> str:
        """Translates text to the farmer's preferred language if not English."""
        if farmer.language_preference != "en":
            return await self.translation_service.translate_text(text, farmer.language_preference, "en")
        return text

    async def send_whatsapp_message(self, to_number: str, message: str):
        """Sends a message via Twilio, splitting it if it's too long."""
        if not self.twilio_client:
            print(f"WHATSAPP_DEBUG (to: {to_number}):\n{message}")
            return
        
        try:
            full_to_number = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
            
            # Split message into chunks of 1590 characters to be safe
            max_length = 1590
            if len(message) > max_length:
                message_chunks = [message[i:i + max_length] for i in range(0, len(message), max_length)]
                for chunk in message_chunks:
                    self.twilio_client.messages.create(
                        from_=f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
                        body=chunk,
                        to=full_to_number
                    )
            else:
                self.twilio_client.messages.create(
                    from_=f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
                    body=message,
                    to=full_to_number
                )
        except Exception as e:
            print(f"Error sending WhatsApp message to {to_number}: {e}")