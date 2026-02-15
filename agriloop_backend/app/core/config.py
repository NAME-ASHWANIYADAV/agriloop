from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    CLAUDE_API_KEY: str
    OPENWEATHER_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str
    MONGODB_URL: str
    MONGODB_DB_NAME: str = "agriloop"
    AGRITECH_API_URL: str = "http://localhost:3000"
    AGRITECH_INTERNAL_API_KEY: str = "dev-internal-api-key"

    class Config:
        env_file = ".env"

settings = Settings()
