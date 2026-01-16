from typing import Optional, Dict, List, Any
from beanie import Document
from pydantic import Field
from beanie.odm.fields import PydanticObjectId
from app.models.farmer_state import FarmerState

class Farmer(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")
    phone_number: str = Field(..., unique=True, index=True)
    name: Optional[str] = None
    onboarding_state: str = "initial" # Can be 'initial', 'awaiting_language', 'awaiting_name', 'completed'
    current_state: str = Field(default=FarmerState.MAIN_MENU)
    location: Optional[Dict[str, Any]] = None # Stores lat, lon, city, state, country
    temp_data: Optional[Dict[str, Any]] = None # Temporary storage for multi-step interactions
    farm_size_acres: Optional[float] = None
    crops: List[str] = Field(default_factory=list)
    language_preference: str = "en" # Default to English

    class Settings:
        name = "farmers"