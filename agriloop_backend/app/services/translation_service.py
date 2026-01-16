from deep_translator import GoogleTranslator, exceptions
from typing import Optional, List
import asyncio

class TranslationService:
    async def translate_text(self, text: str, target_language: str, source_language: Optional[str] = 'auto') -> str:
        """
        Translates text using GoogleTranslator from deep_translator asynchronously.
        """
        if not text:
            return ""
        
        # deep_translator is a synchronous library, so run it in a thread pool executor
        # to prevent blocking the asyncio event loop.
        try:
            translated_text = await asyncio.to_thread(
                GoogleTranslator(source=source_language, target=target_language).translate,
                text
            )
            return translated_text if translated_text is not None else text
        except exceptions.TranslationNotFound:
            print(f"Translation failed for '{text}' from {source_language} to {target_language}. Target language might not be supported.")
            return text
        except Exception as e:
            print(f"Error during translation of '{text}': {e}")
            return text # Return original text on error

    async def detect_language(self, text: str) -> str:
        """
        Detects language using GoogleTranslator from deep_translator asynchronously.
        """
        if not text:
            return "en" # Default to English if no text

        try:
            # deep_translator's detect method returns a tuple like ('en', 'english')
            detected = await asyncio.to_thread(GoogleTranslator().detect, text)
            return detected[0] if detected else "en"
        except Exception as e:
            print(f"Error during language detection of '{text}': {e}")
            return "en" # Default to English on error
    
    async def get_supported_languages(self) -> List[str]:
        """
        Returns a list of language codes supported by GoogleTranslator.
        """
        # This will be a blocking call, but typically only called once at startup if needed
        # Or, we can hardcode a list for simplicity if frequent calls are an issue
        try:
            supported_languages_dict = await asyncio.to_thread(GoogleTranslator().get_supported_languages, as_dict=True)
            return list(supported_languages_dict.values()) # Returns language codes
        except Exception as e:
            print(f"Error fetching supported languages: {e}")
            return ["en", "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "or", "pa", "as", "ur"] # Fallback to common Indian languages + English

def get_translation_service():
    """
    Dependency injector for the TranslationService.
    """
    return TranslationService()