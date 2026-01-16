import motor.motor_asyncio
import beanie
from app.core.config import settings
import certifi

async def init_db():
    """
    Initializes the MongoDB database and Beanie ODM.
    Includes SSL certificate handling for cloud deployment.
    """
    client = motor.motor_asyncio.AsyncIOMotorClient(
        settings.MONGODB_URL,
        tls=True,
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True # To bypass handshake errors on some platforms
    )
    db = client[settings.MONGODB_DB_NAME]

    # Import all the models here so Beanie can find them
    from app.models.farmer import Farmer
    from app.models.interaction import Interaction

    await beanie.init_beanie(
        database=db,
        document_models=[
            Farmer,
            Interaction,
        ],
    )