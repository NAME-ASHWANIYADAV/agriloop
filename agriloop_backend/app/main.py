from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import httpx
from app.core.database import init_db
from app.core.config import settings
from app.routers import whatsapp
from dotenv import load_dotenv
import os

load_dotenv()

PING_INTERVAL = 600  # 10 minutes in seconds


async def keep_alive_loop():
    """Pings self, AgriTech Pro, and HuggingFace to prevent free-tier sleep."""
    await asyncio.sleep(30)  # Wait for server to fully start

    targets = []

    # Self-ping (Render sets RENDER_EXTERNAL_URL automatically)
    self_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_URL")
    if self_url:
        targets.append(("Self (AgriLoop)", self_url))

    # AgriTech Pro backend
    agritech_url = settings.AGRITECH_API_URL
    if agritech_url and agritech_url != "http://localhost:3000":
        targets.append(("AgriTech Pro", f"{agritech_url}/health"))

    # Hugging Face Flask ML
    hf_url = os.getenv("HUGGINGFACE_SPACE_URL")
    if hf_url:
        targets.append(("Flask ML (HuggingFace)", f"{hf_url}/internal/health"))

    if not targets:
        print("Keep-alive: No targets configured, skipping.")
        return

    print(f"Keep-alive: Pinging {len(targets)} target(s) every {PING_INTERVAL // 60} min")
    for name, url in targets:
        print(f"  → {name}: {url}")

    while True:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for name, url in targets:
                try:
                    resp = await client.get(url)
                    print(f"Keep-alive OK: {name} ({resp.status_code})")
                except Exception as e:
                    print(f"Keep-alive FAIL: {name} — {e}")
        await asyncio.sleep(PING_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    await init_db()
    keep_alive_task = asyncio.create_task(keep_alive_loop())
    yield
    # Shutdown
    keep_alive_task.cancel()


app = FastAPI(title="AgriLoop AI", lifespan=lifespan)

app.include_router(whatsapp.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to AgriLoop AI"}
