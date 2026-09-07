import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv

# Load environment variables from root or backend .env
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("REVEAL_UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve()
SAMPLES_DIR = BASE_DIR / "samples"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/reveal.db")
if DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed_database_url = urlsplit(DATABASE_URL)
    database_query = [
        ("ssl" if key == "sslmode" else key, value)
        for key, value in parse_qsl(parsed_database_url.query)
        if key != "channel_binding"
    ]
    DATABASE_URL = urlunsplit(parsed_database_url._replace(query=urlencode(database_query)))

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Google Gen AI / Cloud settings
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
REVEAL_MODEL = os.getenv("REVEAL_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
