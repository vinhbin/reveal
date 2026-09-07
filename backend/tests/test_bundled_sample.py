import subprocess

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import SAMPLES_DIR
from backend.main import app
import backend.routes.reviews as routes


@pytest.mark.asyncio
async def test_public_sample_uses_matching_mara_scene(monkeypatch):
    # Existing editorial regression tests deliberately use a separate legacy
    # script. This test exercises the assets shipped to visitors instead.
    monkeypatch.setattr(routes, "SAMPLES_DIR", SAMPLES_DIR)
    observed = {}
    async def mock_analysis(**kwargs):
        observed.update(kwargs)
        return [], "mock-test-only"
    monkeypatch.setattr(routes, "analyze_review", mock_analysis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/reviews/sample")
        assert response.status_code == 201
        review = response.json()
        assert "Synthetic Mara" in review["title"]
        assert [cue["text"] for cue in review["cues"]] == [
            "Mara waits in the theater lobby.",
            "The visitor approaches the counter.",
            "Mara lowers her hood.",
        ]
        assert review["cues"][0]["start_seconds"] == 5
        assert review["cues"][2]["start_seconds"] == 66
        assert "66 seconds" in observed["intent_notes"]
        assert 71 <= observed["media_duration"] <= 73
        video = await client.get(f"/api/reviews/{review['id']}/video")
        assert video.content == (SAMPLES_DIR / "sample_short.mp4").read_bytes()
        exported = await client.get(f"/api/reviews/{review['id']}/export")
        assert exported.content == (SAMPLES_DIR / "sample_ad.srt").read_bytes()


def test_bundled_video_depicts_a_scene_instead_of_blank_frames():
    frame = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "10", "-i", str(SAMPLES_DIR / "sample_short.mp4"),
         "-frames:v", "1", "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=15,
    ).stdout
    assert len(frame) == 64 * 36 * 3
    assert len({frame[i:i + 3] for i in range(0, len(frame), 3)}) > 20


@pytest.mark.asyncio
async def test_missing_sample_assets_report_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "SAMPLES_DIR", tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/reviews/sample")
        assert response.status_code == 503
        assert "sample" in response.json()["detail"].lower()
