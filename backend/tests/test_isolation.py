import pytest
from google import genai
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(2))
async def test_each_test_starts_with_clean_database_and_uploads(setup_test_db, iteration):
    from backend.routes.reviews import UPLOAD_DIR

    assert UPLOAD_DIR == setup_test_db / "uploads"
    assert not list(UPLOAD_DIR.iterdir())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/reviews")).json() == []
        response = await client.post("/api/reviews/sample")
        assert response.status_code == 201
        assert response.json()["model_used"] == "mock-test-model"
        assert len((await client.get("/api/reviews")).json()) == 1
        assert list(UPLOAD_DIR.iterdir())


def test_accidental_live_gemini_client_is_blocked():
    with pytest.raises(AssertionError, match="live provider calls are disabled"):
        genai.Client(api_key="not-a-real-key")
