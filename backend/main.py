from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routes.reviews import router as reviews_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield

app = FastAPI(
    title="Reveal API",
    description="AI-assisted Audio Description (AD) Editorial Review Tool API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reviews_router)

@app.get("/")
async def root():
    return {
        "message": "Reveal AD Reviewer API is running.",
        "frontend_url": "http://localhost:5173",
        "swagger_docs": "http://localhost:8001/docs",
        "health_check": "http://localhost:8001/health"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "Reveal", "version": "1.0.0"}
