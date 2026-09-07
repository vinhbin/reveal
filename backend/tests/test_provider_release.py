import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models import Review, ReviewStatus
from backend.tests.conftest import DEFAULT_MOCK_FINDINGS, TestingSessionLocal
import backend.analyzer as analyzer
import backend.routes.reviews as routes


@pytest.mark.asyncio
async def test_editor_and_delete_cannot_race_analysis(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/sample")).json()
        finding = review["findings"][0]
        url = f"/api/reviews/{review['id']}"
        async def slow_analysis(**kwargs):
            started.set()
            await release.wait()
            return DEFAULT_MOCK_FINDINGS, "mock"
        monkeypatch.setattr(routes, "analyze_review", slow_analysis)
        task = asyncio.create_task(client.post(f"{url}/analyze"))
        await started.wait()
        try:
            edit = await client.patch(f"{url}/findings/{finding['id']}", json={"status": "accepted", "edited_proposal": "My approved wording."})
            deletion = await client.delete(url)
            assert edit.status_code == 409
            assert deletion.status_code == 409
        finally:
            release.set()
            await task
        accepted = await client.patch(f"{url}/findings/{finding['id']}", json={"status": "accepted", "edited_proposal": "My approved wording."})
        assert accepted.status_code == 200
        assert accepted.json()["edited_proposal"] == "My approved wording."


@pytest.mark.asyncio
async def test_duplicate_provider_candidates_do_not_duplicate_findings(monkeypatch):
    async def duplicates(**kwargs):
        return DEFAULT_MOCK_FINDINGS * 2, "mock"
    monkeypatch.setattr(routes, "analyze_review", duplicates)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/sample")).json()
        assert len(review["findings"]) == 1
        repeated = (await client.post(f"/api/reviews/{review['id']}/analyze")).json()
        assert len(repeated["findings"]) == 1


@pytest.mark.asyncio
async def test_reconciliation_error_rolls_back_human_decision_changes(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/sample")).json()
        finding = review["findings"][0]
        url = f"/api/reviews/{review['id']}"
        await client.patch(f"{url}/findings/{finding['id']}", json={"status": "accepted", "edited_proposal": "My approved wording."})
        changed = SimpleNamespace(**vars(DEFAULT_MOCK_FINDINGS[0]))
        changed.proposed_text = "A different proposed sentence."
        async def malformed(**kwargs):
            # Simulate a merge error after a previous finding was mutated.
            return [changed, object()], "mock"
        monkeypatch.setattr(routes, "analyze_review", malformed)
        response = (await client.post(f"{url}/analyze")).json()
        assert response["status"] == "failed"
        assert response["findings"][0]["status"] == "accepted"
        assert response["findings"][0]["edited_proposal"] == "My approved wording."
        assert response["findings"][0]["needs_re_review"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
async def test_interrupted_analysis_is_retryable(monkeypatch, interruption):
    started = asyncio.Event()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/sample")).json()
        async def blocked(**kwargs):
            started.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(routes, "analyze_review", blocked)
        if interruption == "timeout":
            monkeypatch.setattr(routes, "ANALYSIS_TIMEOUT_SECONDS", 0.02)
        async with TestingSessionLocal() as session:
            task = asyncio.create_task(routes.trigger_analysis(review["id"], session))
            await started.wait()
            if interruption == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                await task
        async with TestingSessionLocal() as session:
            saved = await session.get(Review, review["id"])
            assert saved.status == ReviewStatus.FAILED
            assert saved.error_message
        async def success(**kwargs):
            return DEFAULT_MOCK_FINDINGS, "mock"
        monkeypatch.setattr(routes, "analyze_review", success)
        response = await client.post(f"/api/reviews/{review['id']}/analyze")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert len(response.json()["findings"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_fails", [False, True])
async def test_provider_requests_bounded_and_file_cleaned(monkeypatch, tmp_path, provider_fails):
    from google import genai
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"test video")
    upload = SimpleNamespace(name="files/mock", state=SimpleNamespace(name="ACTIVE"))
    fake = Mock()
    fake.files.upload.return_value = upload
    fake.files.get.return_value = upload
    fake.models.generate_content.return_value = SimpleNamespace(text=json.dumps([]))
    if provider_fails:
        fake.models.generate_content.side_effect = RuntimeError("429 quota exhausted")
    # A cleanup error must not hide a successful result or the provider error.
    fake.files.delete.side_effect = RuntimeError("cleanup unavailable")
    constructor = Mock(return_value=fake)
    monkeypatch.setattr(genai, "Client", constructor)
    if provider_fails:
        with pytest.raises(RuntimeError, match="429 quota exhausted"):
            await analyzer._run_gemini_analysis_threaded(str(video), [])
    else:
        findings, _ = await analyzer._run_gemini_analysis_threaded(str(video), [])
        assert findings == []
    options = constructor.call_args.kwargs["http_options"]
    assert 0 < options.timeout <= 60000
    assert options.retry_options.attempts == 1
    fake.files.delete.assert_called_once_with(name="files/mock")
    fake.close.assert_called_once()
