from fastapi import FastAPI
from app.core.database import init_db
from app.routers import whatsapp
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AgriLoop AI")

@app.on_event("startup")
async def startup_event():
    await init_db()

app.include_router(whatsapp.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to AgriLoop AI"}
