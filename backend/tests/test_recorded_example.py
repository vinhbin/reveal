import hashlib
import shutil

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from backend.config import SAMPLES_DIR
from backend.main import app
from backend.models import Review
from backend.tests.conftest import TestingSessionLocal
import backend.routes.reviews as routes


@pytest.mark.asyncio
async def test_recorded_example_is_immutable_editable_copy_without_model_call(monkeypatch):
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    async def forbidden(**kwargs):
        raise AssertionError("Recorded examples must not call a model")
    monkeypatch.setattr(routes, "analyze_review", forbidden)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        snapshot = (await client.get("/api/examples/mara")).json()
        first = await client.post("/api/reviews/example")
        assert first.status_code == 201
        review = first.json()
        assert review["status"] == "completed"
        assert review["analysis_source"] == "recorded"
        assert review["recorded_at"].startswith("2026-09-07T05:34:34")
        assert review["model_used"] == "google-adk/agent-platform/gemini-3.6-flash"
        summary = (await client.get("/api/reviews")).json()[0]
        assert summary["id"] == review["id"]
        assert summary["model_used"] == review["model_used"]
        assert summary["analysis_source"] == "recorded"
        assert summary["recorded_at"] == review["recorded_at"]
        assert summary["recorded_at"].endswith("Z")
        assert snapshot["video_sha256"] == hashlib.sha256((SAMPLES_DIR / "sample_short.mp4").read_bytes()).hexdigest()
        assert snapshot["srt_sha256"] == hashlib.sha256((SAMPLES_DIR / "sample_ad.srt").read_bytes()).hexdigest()
        assert not {"id", "review_id", "cue_id", "video_path"} & snapshot["findings"][0].keys()
        finding = review["findings"][0]
        for key, value in snapshot["findings"][0].items():
            assert finding[key] == value
        assert (await client.get(f"/api/reviews/{review['id']}/export")).content == (SAMPLES_DIR / "sample_ad.srt").read_bytes()
        edited = await client.patch(f"/api/reviews/{review['id']}/findings/{finding['id']}", json={"status": "accepted"})
        assert edited.status_code == 200
        assert b"A hooded figure" in (await client.get(f"/api/reviews/{review['id']}/export")).content
        second = (await client.post("/api/reviews/example")).json()
        assert second["id"] != review["id"]
        assert second["findings"][0]["status"] == "unreviewed"
        assert (await client.get("/api/examples/mara")).json() == snapshot


@pytest.mark.asyncio
async def test_sample_reference_survives_deployment_root_change_and_delete(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/example")).json()
        async with TestingSessionLocal() as db:
            stored = await db.get(Review, review["id"])
            assert stored.video_path == "sample:mara-v1"
        assert not list(routes.UPLOAD_DIR.iterdir())
        new_root = tmp_path / "new-deployment" / "samples"
        new_root.mkdir(parents=True)
        shutil.copyfile(SAMPLES_DIR / "sample_short.mp4", new_root / "sample_short.mp4")
        monkeypatch.setattr(routes, "SAMPLES_DIR", new_root)
        response = await client.get(f"/api/reviews/{review['id']}/video")
        assert response.status_code == 200
        assert response.content == (new_root / "sample_short.mp4").read_bytes()
        assert (await client.delete(f"/api/reviews/{review['id']}")).status_code == 204
        assert (new_root / "sample_short.mp4").is_file()


@pytest.mark.asyncio
async def test_legacy_missing_media_never_falls_back_and_webm_has_correct_type(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    async def forbidden(**kwargs):
        raise AssertionError("Missing video must stop before provider execution")
    monkeypatch.setattr(routes, "analyze_review", forbidden)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/example")).json()
        async with TestingSessionLocal() as db:
            stored = await db.get(Review, review["id"])
            stored.video_path = str(tmp_path / "old-vance.mp4")
            await db.commit()
        response = await client.get(f"/api/reviews/{review['id']}/video")
        assert response.status_code == 404
        assert "unavailable" in response.json()["detail"].lower()
        failed = (await client.post(f"/api/reviews/{review['id']}/analyze")).json()
        assert failed["status"] == "failed"
        assert "unavailable" in failed["error_message"]
        assert failed["analysis_source"] == "recorded"
        webm = tmp_path / "clip.webm"
        webm.write_bytes(b"\x1a\x45\xdf\xa3test-webm")
        async with TestingSessionLocal() as db:
            stored = await db.get(Review, review["id"])
            stored.video_path = str(webm)
            await db.commit()
        response = await client.get(f"/api/reviews/{review['id']}/video")
        assert response.headers["content-type"] == "video/webm"


@pytest.mark.asyncio
async def test_recorded_provenance_survives_failure_then_clears_on_success(monkeypatch):
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    async def failed(**kwargs):
        raise RuntimeError("quota unavailable")
    async def succeeded(**kwargs):
        assert kwargs["video_path"] == str(SAMPLES_DIR / "sample_short.mp4")
        return [], "google-adk/agent-platform/test-model"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/example")).json()
        monkeypatch.setattr(routes, "analyze_review", failed)
        failure = (await client.post(f"/api/reviews/{review['id']}/analyze")).json()
        assert failure["status"] == "failed"
        assert failure["analysis_source"] == "recorded"
        assert failure["recorded_at"] == review["recorded_at"]
        assert failure["findings"] == review["findings"]
        monkeypatch.setattr(routes, "analyze_review", succeeded)
        success = (await client.post(f"/api/reviews/{review['id']}/analyze")).json()
        assert success["status"] == "completed"
        assert success["analysis_source"] == "live"
        assert success["recorded_at"] is None


@pytest.mark.asyncio
async def test_existing_populated_database_adds_nullable_provenance_without_relabeling(monkeypatch):
    from backend.database import init_db
    from backend.tests import conftest
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        review = (await client.post("/api/reviews/example")).json()
        async with conftest.test_engine.begin() as connection:
            await connection.execute(text("ALTER TABLE reviews DROP COLUMN analysis_source"))
            await connection.execute(text("ALTER TABLE reviews DROP COLUMN recorded_at"))
        await init_db(conftest.test_engine)
        await init_db(conftest.test_engine)
        response = await client.get(f"/api/reviews/{review['id']}")
        assert response.status_code == 200
        migrated = response.json()
        assert migrated["analysis_source"] is None
        assert migrated["recorded_at"] is None
        assert migrated["model_used"] == review["model_used"]
        assert migrated["findings"] == review["findings"]


@pytest.mark.asyncio
async def test_mismatched_recording_assets_refuse_copy(monkeypatch, tmp_path):
    shutil.copyfile(SAMPLES_DIR / "sample_short.mp4", tmp_path / "sample_short.mp4")
    (tmp_path / "sample_ad.srt").write_text("A different film's script.", encoding="utf-8")
    monkeypatch.setattr(routes, "SAMPLES_DIR", tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/reviews/example")).status_code == 503
        assert (await client.get("/api/reviews")).json() == []
