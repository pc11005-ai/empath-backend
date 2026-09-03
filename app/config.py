from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import chats, trash
from .services.cleanup_service import purge_expired_trash

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run once on startup, then daily, so Trash empties itself over time
    # even if nobody opens the Trash view.
    scheduler.add_job(purge_expired_trash, "interval", days=1, id="purge_trash")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="EmPath API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chats.router)
app.include_router(trash.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "EmPath API"}
