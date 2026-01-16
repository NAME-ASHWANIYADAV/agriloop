from fastapi import APIRouter, Depends, Request, BackgroundTasks

from app.services.ai_service import AIService, get_ai_service
from app.services.weather_service import WeatherService, get_weather_service
from app.services.translation_service import TranslationService, get_translation_service
from app.services.web_search_service import WebSearchService, get_web_search_service
from app.services.whatsapp_handler import WhatsAppHandler

router = APIRouter()

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    ai_service: AIService = Depends(get_ai_service),
    weather_service: WeatherService = Depends(get_weather_service),
    translation_service: TranslationService = Depends(get_translation_service),
    web_search_service: WebSearchService = Depends(get_web_search_service)
):
    """
    Handles incoming WhatsApp messages from Twilio.
    """
    form_data = await request.form()
    payload = dict(form_data)
    
    handler = WhatsAppHandler(ai_service, weather_service, translation_service, web_search_service)
    await handler.handle_message(payload, background_tasks)
    
    return {"status": "ok"}
