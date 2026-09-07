import os
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Importing the application must never initialize a user's configured database
# or require the driver for their production DATABASE_URL.
_configured_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
try:
    from backend.database import Base, get_db
    from backend.main import app
finally:
    if _configured_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _configured_database_url

from backend.models import EvidenceOrigin, UncertaintyLevel
from backend.analyzer import CandidateFinding

test_engine = None
# Keep the factory object stable for existing regression-test imports.
TestingSessionLocal = async_sessionmaker(class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

DEFAULT_MOCK_FINDINGS = [
    CandidateFinding(
        cue_index=3,
        candidate_name="Dr. Aris Thorne",
        issue_description="Cue #3 prematurely names Dr. Aris Thorne.",
        proposed_text="A masked figure approaches from the mist carrying a steel briefcase.",
        evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
        interval_start=15.0,
        interval_end=60.0,
        uncertainty=UncertaintyLevel.MEDIUM
    )
]

@pytest.fixture(autouse=True)
def mock_analyzer_for_tests(monkeypatch):
    from google import genai

    def prevent_live_provider(*args, **kwargs):
        raise AssertionError("Tests must mock Gemini; live provider calls are disabled")

    monkeypatch.setattr(genai, "Client", prevent_live_provider)

    async def _mock_impl(video_path, cues, intent_notes="", media_duration=None):
        await asyncio.sleep(0.15)
        return DEFAULT_MOCK_FINDINGS, "mock-test-model"
    monkeypatch.setattr("backend.routes.reviews.analyze_review", _mock_impl)

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    global test_engine
    with TemporaryDirectory(prefix="storage-", dir=tmp_path) as directory:
        storage = Path(directory)
        uploads = storage / "uploads"
        uploads.mkdir()
        test_engine = create_async_engine(
            f"sqlite+aiosqlite:///{(storage / 'reviews.db').as_posix()}", echo=False
        )
        TestingSessionLocal.configure(bind=test_engine)
        monkeypatch.setattr("backend.database.engine", test_engine)
        monkeypatch.setattr("backend.database.AsyncSessionLocal", TestingSessionLocal)
        monkeypatch.setattr("backend.config.UPLOAD_DIR", uploads)
        monkeypatch.setattr("backend.routes.reviews.UPLOAD_DIR", uploads)
        monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            yield storage
        finally:
            # Close all pooled SQLite handles before removing their files, on
            # both Windows (locked files) and Linux (stale, unlinked database).
            await test_engine.dispose()
