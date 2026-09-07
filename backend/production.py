from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.main import health_check, lifespan
from backend.routes.reviews import router as reviews_router

app = FastAPI(title="Reveal", lifespan=lifespan)
app.include_router(reviews_router)
app.add_api_route("/health", health_check, methods=["GET"])

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
