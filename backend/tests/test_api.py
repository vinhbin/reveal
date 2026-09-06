import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["app"] == "Reveal"

@pytest.mark.asyncio
async def test_sample_review_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/reviews/sample")
        assert res.status_code == 201
        review = res.json()
        review_id = review["id"]
        assert "Sample Short" in review["title"]
        assert len(review["cues"]) > 0

        res_get = await ac.get(f"/api/reviews/{review_id}")
        assert res_get.status_code == 200
        detail = res_get.json()
        assert detail["id"] == review_id

        if detail["findings"]:
            finding = detail["findings"][0]
            finding_id = finding["id"]
            res_patch = await ac.patch(
                f"/api/reviews/{review_id}/findings/{finding_id}",
                json={"status": "accepted", "edited_proposal": "A masked intruder enters."}
            )
            assert res_patch.status_code == 200
            updated_f = res_patch.json()
            assert updated_f["status"] == "accepted"
            assert updated_f["edited_proposal"] == "A masked intruder enters."

            res_export = await ac.get(f"/api/reviews/{review_id}/export")
            assert res_export.status_code == 200
            assert "A masked intruder enters." in res_export.text

        res_del = await ac.delete(f"/api/reviews/{review_id}")
        assert res_del.status_code == 204
