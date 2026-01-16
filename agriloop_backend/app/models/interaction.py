from datetime import datetime
from typing import Optional
from beanie import Document, Link
from pydantic import Field
from app.models.farmer import Farmer

class Interaction(Document):
    farmer: Link[Farmer]
    query_text: str
    response_text: Optional[str] = None
    media_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "interactions"