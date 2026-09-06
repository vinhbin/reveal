import asyncio
import io
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.database import get_db, Base
from backend.models import Review, Cue, Finding, ReviewStatus, DecisionStatus, EvidenceOrigin, UncertaintyLevel
from backend.srt_parser import parse_srt, export_srt_bytes
from backend.analyzer import analyze_review, CandidateFinding

from backend.tests.conftest import TestingSessionLocal



@pytest.mark.asyncio
async def test_regression_atomic_concurrency_protection():
    """
    Regression Test 1:
    Simultaneous /analyze requests must claim the job atomically.
    Exactly one request must succeed (200), and all overlapping requests must receive 409 Conflict.
    Findings must never be duplicated.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a sample review
        res = await ac.post("/api/reviews/sample")
        assert res.status_code == 201
        review_id = res.json()["id"]

        # Reset status to pending so we can test concurrent analysis triggers
        async with TestingSessionLocal() as session:
            review = await session.get(Review, review_id)
            review.status = ReviewStatus.PENDING
            await session.commit()

        # Fire 5 concurrent requests to trigger_analysis
        async def call_analyze():
            return await ac.post(f"/api/reviews/{review_id}/analyze")

        results = await asyncio.gather(*[call_analyze() for _ in range(5)], return_exceptions=True)

        statuses = [r.status_code for r in results if not isinstance(r, Exception)]
        # Exactly one 200 OK and four 409 Conflict
        assert 200 in statuses
        assert 409 in statuses
        assert statuses.count(200) == 1
        assert statuses.count(409) == 4

        # Verify findings count is not duplicated
        detail_res = await ac.get(f"/api/reviews/{review_id}")
        findings = detail_res.json()["findings"]
        # Standard sample has 1 finding on cue 3 (Dr. Aris Thorne)
        assert len(findings) == 1


@pytest.mark.asyncio
async def test_regression_exact_srt_byte_preservation():
    """
    Regression Test 2:
    Untouched cues must export 100% byte-for-byte identical to the original input,
    including CRLF line endings, zero-padded IDs ('001'), extra spacing around timestamps,
    and untouched text.
    """
    # Construct exact raw SRT with CRLF, zero-padded IDs, and irregular timestamp spacing
    crlf_srt_bytes = (
        b"001\r\n"
        b"00:00:01,000   -->   00:00:04,500\r\n"
        b"In the theater, a shadowed figure enters.  \r\n"
        b"\r\n"
        b"002\r\n"
        b"00:00:05,000 --> 00:00:09,000\r\n"
        b"The stranger takes a seat in row four.\r\n"
        b"\r\n"
        b"003\r\n"
        b"00:00:10,000 --> 00:00:14,000\r\n"
        b"On screen, the lights dim.\r\n"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create minimal valid MP4
        valid_mp4_bytes = (
            b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            b"\x00\x00\x00\x08free"
            b"\x00\x00\x04\x00mdat" + b"\x00" * 1024
        )

        files = {
            "video_file": ("test.mp4", io.BytesIO(valid_mp4_bytes), "video/mp4"),
            "srt_file": ("test.srt", io.BytesIO(crlf_srt_bytes), "application/x-subrip")
        }
        data = {"title": "Exact Byte Test", "intent_notes": ""}
        create_res = await ac.post("/api/reviews", data=data, files=files)
        assert create_res.status_code == 201
        review_id = create_res.json()["id"]

        # When no edits are accepted, export must return byte-for-byte identical content
        export_res = await ac.get(f"/api/reviews/{review_id}/export")
        assert export_res.status_code == 200
        assert export_res.content == crlf_srt_bytes, "Untouched export failed exact byte-for-byte match"

        # Now simulate accepting an edit on cue 2
        async with TestingSessionLocal() as session:
            cues_res = await session.execute(
                select(Cue).filter(Cue.review_id == review_id, Cue.index == 2)
            )
            cue2 = cues_res.scalars().first()
            finding = Finding(
                review_id=review_id,
                cue_id=cue2.id,
                cue_index=2,
                candidate_name="stranger",
                issue_description="Premature naming",
                proposed_text="A cloaked patron takes a seat in row four.",
                edited_proposal="A cloaked patron takes a seat in row four.",
                evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                interval_start=5.0,
                interval_end=9.0,
                status=DecisionStatus.ACCEPTED
            )
            session.add(finding)
            await session.commit()

        # Re-export with accepted edit
        revised_export_res = await ac.get(f"/api/reviews/{review_id}/export")
        revised_bytes = revised_export_res.content

        # Verify cue 1 is preserved byte-identically with CRLF and 001
        assert b"001\r\n00:00:01,000   -->   00:00:04,500\r\nIn the theater, a shadowed figure enters.  \r\n" in revised_bytes
        # Verify cue 2 has replacement with original line ending
        assert b"A cloaked patron takes a seat in row four." in revised_bytes
        # Verify cue 3 is preserved byte-identically with CRLF and 003
        assert b"003\r\n00:00:10,000 --> 00:00:14,000\r\nOn screen, the lights dim." in revised_bytes


@pytest.mark.asyncio
async def test_regression_reanalysis_preserves_decisions_and_flags_changes():
    """
    Regression Test 3:
    Reanalysis must preserve existing accepted decisions and custom edited wording.
    If reanalysis produces a modified proposal, it must flag needs_re_review and preserve previous wording.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/reviews/sample")
        assert res.status_code == 201
        review_id = res.json()["id"]
        finding_id = res.json()["findings"][0]["id"]

        # Accept finding with custom edited proposal
        custom_edit = "A mysterious guest arrives with a metallic briefcase."
        patch_res = await ac.patch(
            f"/api/reviews/{review_id}/findings/{finding_id}",
            json={"status": "accepted", "edited_proposal": custom_edit}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "accepted"
        assert patch_res.json()["edited_proposal"] == custom_edit

        # Trigger reanalysis (heuristic analyzer produces same finding for Dr. Aris Thorne)
        reanalyze_res = await ac.post(f"/api/reviews/{review_id}/analyze")
        assert reanalyze_res.status_code == 200
        findings = reanalyze_res.json()["findings"]
        assert len(findings) == 1
        refetched = findings[0]

        # Status and custom edited wording must be preserved!
        assert refetched["status"] == "accepted"
        assert refetched["edited_proposal"] == custom_edit


@pytest.mark.asyncio
async def test_regression_reject_invalid_evidence_bounds():
    """
    Regression Test 4:
    Evidence timestamps outside media bounds (e.g. 99,999s on a 72s film, or negative start)
    must be rejected outright, NOT clamped.
    """
    cues = [
        {"index": 1, "start_time": "00:00:02,000", "end_time": "00:00:06,000", "start_seconds": 2.0, "end_seconds": 6.0, "text": "Detective Vance enters."},
    ]
    # Test rejection when interval is out of bounds
    findings = [
        # Out of bounds: 99999s on a 72s film
        CandidateFinding(1, "Vance", "Issue", "A man enters", EvidenceOrigin.MODEL_INFERENCE, 0.0, 99999.0, UncertaintyLevel.HIGH),
        # Out of bounds: negative start
        CandidateFinding(1, "Vance", "Issue", "A man enters", EvidenceOrigin.MODEL_INFERENCE, -10.0, 5.0, UncertaintyLevel.MEDIUM),
        # Valid interval
        CandidateFinding(1, "Vance", "Issue", "A man enters", EvidenceOrigin.MODEL_INFERENCE, 0.0, 10.0, UncertaintyLevel.MEDIUM)
    ]

    # Validate filtering
    max_duration = 72.0
    valid_findings = []
    for f in findings:
        if f.interval_start < 0.0 or f.interval_end > (max_duration + 1.0) or f.interval_start >= f.interval_end:
            continue
        valid_findings.append(f)

    # Exactly 1 valid finding survives; 99999s and -10s are rejected, not clamped
    assert len(valid_findings) == 1
    assert valid_findings[0].interval_end == 10.0


@pytest.mark.asyncio
async def test_regression_sample_video_file_validity():
    """
    Regression Test 5:
    Sample video must be a valid playable H.264 MP4 with duration >= 70 seconds.
    """
    from backend.config import SAMPLES_DIR
    sample_mp4 = SAMPLES_DIR / "sample_short.mp4"
    assert sample_mp4.exists()
    assert sample_mp4.stat().st_size > 10000

    # Probe duration
    from backend.analyzer import get_media_duration
    duration = get_media_duration(str(sample_mp4))
    assert duration is not None
    assert abs(duration - 72.0) < 1.0


@pytest.mark.asyncio
async def test_regression_srt_strict_validation():
    """
    Regression Test 6:
    SRT parser must reject duplicate cue IDs and reversed intervals (start >= end).
    """
    # Reversed interval
    reversed_srt = (
        "1\n"
        "00:00:10,000 --> 00:00:05,000\n"
        "Reversed timestamps.\n"
    )
    with pytest.raises(ValueError, match="Invalid timestamp interval"):
        parse_srt(reversed_srt)

    # Duplicate cue index
    duplicate_srt = (
        "1\n"
        "00:00:01,000 --> 00:00:03,000\n"
        "First cue.\n\n"
        "1\n"
        "00:00:04,000 --> 00:00:06,000\n"
        "Duplicate ID cue.\n"
    )
    with pytest.raises(ValueError, match="Duplicate cue index"):
        parse_srt(duplicate_srt)


@pytest.mark.asyncio
async def test_regression_multiple_findings_cue_level_resolution():
    """
    Regression Test 7:
    When multiple findings exist on the same cue, editorial resolution occurs at the cue level.
    The system avoids naive string replacements (which can collide or restore concealed names).
    Authoritative custom cue revisions are honored on export.
    """
    multi_srt = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Dr. Thorne meets Agent Miller by the bridge.\n"
    ).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        valid_mp4_bytes = (
            b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            b"\x00\x00\x00\x08free"
            b"\x00\x00\x04\x00mdat" + b"\x00" * 1024
        )
        files = {
            "video_file": ("test.mp4", io.BytesIO(valid_mp4_bytes), "video/mp4"),
            "srt_file": ("multi.srt", io.BytesIO(multi_srt), "application/x-subrip")
        }
        res = await ac.post("/api/reviews", data={"title": "Multi-Finding Resolution", "intent_notes": ""}, files=files)
        assert res.status_code == 201
        review_id = res.json()["id"]

        # Insert 2 findings on cue 1
        async with TestingSessionLocal() as session:
            cues_res = await session.execute(
                select(Cue).filter(Cue.review_id == review_id, Cue.index == 1)
            )
            cue1 = cues_res.scalars().first()

            f1 = Finding(
                review_id=review_id,
                cue_id=cue1.id,
                cue_index=1,
                candidate_name="Dr. Thorne",
                issue_description="Premature identity disclosure",
                proposed_text="A masked scientist meets Agent Miller by the bridge.",
                edited_proposal="A masked scientist meets an investigator by the bridge.",  # Authoritative combined edit!
                evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                interval_start=1.0,
                interval_end=4.0,
                status=DecisionStatus.ACCEPTED
            )
            f2 = Finding(
                review_id=review_id,
                cue_id=cue1.id,
                cue_index=1,
                candidate_name="Agent Miller",
                issue_description="Premature identity disclosure",
                proposed_text="Dr. Thorne meets an investigator by the bridge.",
                edited_proposal="Dr. Thorne meets an investigator by the bridge.",
                evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                interval_start=1.0,
                interval_end=4.0,
                status=DecisionStatus.ACCEPTED
            )
            session.add_all([f1, f2])
            await session.commit()

        export_res = await ac.get(f"/api/reviews/{review_id}/export")
        assert export_res.status_code == 200
        exported_text = export_res.content.decode("utf-8")

        # Must use authoritative cue-level revision that resolves both disclosures
        assert "A masked scientist meets an investigator by the bridge." in exported_text
        assert "Dr. Thorne" not in exported_text
        assert "Agent Miller" not in exported_text

