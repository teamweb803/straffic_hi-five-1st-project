import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.pdm.scheduler import get_scheduler
from app.routers.internal_router import router as internal_router
from app.routers.pdm_router import router as pdm_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler = get_scheduler()
    if settings.scheduler_autostart:
        scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(
    title="PDM Algorithm MVP",
    description="Rule-based, Isolation Forest, LSTM-AE OCR quality analysis + scheduler.",
    version="1.1.0",
    lifespan=lifespan,
)

app.include_router(pdm_router)
app.include_router(internal_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
