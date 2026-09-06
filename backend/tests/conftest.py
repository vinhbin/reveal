import os
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.database import Base, get_db
from backend.main import app
from backend.models import EvidenceOrigin, UncertaintyLevel
from backend.analyzer import CandidateFinding

TEST_DB_FILE = "test_shared.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

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
    async def _mock_impl(video_path, cues, intent_notes="", media_duration=None):
        await asyncio.sleep(0.15)
        return DEFAULT_MOCK_FINDINGS, "mock-test-model"
    monkeypatch.setattr("backend.routes.reviews.analyze_review", _mock_impl)

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass
