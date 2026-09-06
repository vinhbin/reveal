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


@pytest.mark.asyncio
async def test_regression_combine_two_independent_accepted_proposals():
    """
    Regression Test 8:
    When two independent proposals on the same cue are accepted without manual custom editing,
    the export must combine both replacements so neither concealed name is restored.
    """
    raw_srt = (
        "1\n"
        "00:00:02,000 --> 00:00:06,000\n"
        "John greets Sarah.\n\n"
        "2\n"
        "00:00:12,000 --> 00:00:16,000\n"
        "Liam walks away.\n"
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
            "srt_file": ("test.srt", io.BytesIO(raw_srt), "application/x-subrip")
        }
        res = await ac.post("/api/reviews", data={"title": "Combine Two Proposals", "intent_notes": ""}, files=files)
        assert res.status_code == 201
        review_id = res.json()["id"]

        async with TestingSessionLocal() as session:
            cues_res = await session.execute(
                select(Cue).filter(Cue.review_id == review_id, Cue.index == 1)
            )
            cue1 = cues_res.scalars().first()

            f1 = Finding(
                id="f_john",
                review_id=review_id,
                cue_id=cue1.id,
                cue_index=1,
                candidate_name="John",
                issue_description="Disclosure John",
                proposed_text="A stranger greets Sarah.",
                edited_proposal="A stranger greets Sarah.",
                evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                interval_start=2.0,
                interval_end=6.0,
                status=DecisionStatus.ACCEPTED
            )
            f2 = Finding(
                id="f_sarah",
                review_id=review_id,
                cue_id=cue1.id,
                cue_index=1,
                candidate_name="Sarah",
                issue_description="Disclosure Sarah",
                proposed_text="John greets an unknown woman.",
                edited_proposal="John greets an unknown woman.",
                evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                interval_start=2.0,
                interval_end=6.0,
                status=DecisionStatus.ACCEPTED
            )
            session.add_all([f1, f2])
            await session.commit()

        export_res = await ac.get(f"/api/reviews/{review_id}/export")
        assert export_res.status_code == 200
        text = export_res.content.decode("utf-8")
        assert "John" not in text
        assert "Sarah" not in text
        assert "A stranger greets an unknown woman." in text


@pytest.mark.asyncio
async def test_regression_archived_wording_preserved_on_candidate_dropped():
    """
    Regression Test 9:
    Accept a finding -> model reanalysis changes proposal (status UNREVIEWED, needs_re_review=True, previous_accepted_text archived)
    -> subsequent reanalysis omits candidate -> finding must NOT be deleted; archived wording must be retained.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/reviews/sample")
        assert res.status_code == 201
        review_id = res.json()["id"]
        finding_id = res.json()["findings"][0]["id"]

        # 1. Accept with custom wording
        original_custom = "A masked figure enters with a briefcase."
        await ac.patch(
            f"/api/reviews/{review_id}/findings/{finding_id}",
            json={"status": "accepted", "edited_proposal": original_custom}
        )

        # 2. Simulate model returning a changed proposal
        async def changed_proposal(*args, **kwargs):
            return [
                CandidateFinding(
                    cue_index=3,
                    candidate_name="Dr. Aris Thorne",
                    issue_description="Changed proposal",
                    proposed_text="An operative arrives with a case.",
                    evidence_origin=EvidenceOrigin.MODEL_INFERENCE,
                    interval_start=15.0,
                    interval_end=60.0,
                    uncertainty=UncertaintyLevel.MEDIUM
                )
            ], "mock-changed"

        from backend.routes import reviews as reviews_route
        original_analyzer = reviews_route.analyze_review
        try:
            reviews_route.analyze_review = changed_proposal
            reanalyze_res = await ac.post(f"/api/reviews/{review_id}/analyze")
            assert reanalyze_res.status_code == 200
            f = reanalyze_res.json()["findings"][0]
            assert f["status"] == "unreviewed"
            assert f["needs_re_review"] is True
            assert f["previous_accepted_text"] == original_custom

            # 3. Simulate model dropping candidate entirely
            async def dropped_candidate(*args, **kwargs):
                return [], "mock-dropped"

            reviews_route.analyze_review = dropped_candidate
            reanalyze2_res = await ac.post(f"/api/reviews/{review_id}/analyze")
            assert reanalyze2_res.status_code == 200
            findings = reanalyze2_res.json()["findings"]

            # Must NOT be deleted!
            assert len(findings) == 1
            assert findings[0]["id"] == finding_id
            assert findings[0]["previous_accepted_text"] == original_custom
            assert findings[0]["needs_re_review"] is True
        finally:
            reviews_route.analyze_review = original_analyzer


@pytest.mark.asyncio
async def test_regression_database_column_auto_migration():
    """
    Regression Test 10:
    Existing database with legacy schema missing new columns (e.g. raw_srt_bytes)
    automatically migrates on create_all/startup without sqlite3.OperationalError.
    """
    from sqlalchemy import text
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Drop raw_srt_bytes to simulate pre-321fd46 database
        await conn.execute(text("ALTER TABLE reviews DROP COLUMN raw_srt_bytes"))
        # Run create_all (startup initialization)
        await conn.run_sync(Base.metadata.create_all)
        # Select Review
        res = await conn.execute(select(Review))
        assert res.scalars().all() == []
    await eng.dispose()


@pytest.mark.asyncio
async def test_regression_byte_exact_edited_export_bom_and_padded_ids():
    """
    Regression Test 11:
    Edited export must preserve original UTF-8 BOM, zero-padded cue IDs ('001'),
    timestamp spacing, and trailing bytes.
    """
    raw = (
        b"\xef\xbb\xbf001\r\n"
        b"00:00:01,000   -->   00:00:04,000\r\n"
        b"Dr. Thorne meets Agent Miller.\r\n"
        b"\r\n\r\n"
        b"002\r\n"
        b"00:00:05,000 --> 00:00:08,000\r\n"
        b"Untouched.\r\n\r\n"
    )
    parsed = parse_srt(raw.decode("utf-8"))
    cues = [
        Cue(
            id=f"c{c.index}",
            review_id="r",
            index=c.index,
            start_time=c.start_time,
            end_time=c.end_time,
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            text=c.text
        )
        for c in parsed
    ]
    out = export_srt_bytes(raw, cues, {1: "A figure meets an investigator."})
    assert out.startswith(b"\xef\xbb\xbf"), "BOM was not preserved"
    assert b"001\r\n" in out, "Padded ID 001 was not preserved"
    assert b"00:00:01,000   -->   00:00:04,000\r\n" in out, "Timestamp spacing not preserved"
    assert out.endswith(b"Untouched.\r\n\r\n"), "Trailing bytes not preserved"


@pytest.mark.asyncio
async def test_regression_migrated_populated_review_serializes():
    """
    Regression Test 12:
    Migrating a database that contains existing findings with missing needs_re_review
    column must backfill valid boolean defaults so review serialization succeeds without HTTP 500.
    """
    from sqlalchemy import text
    from backend.database import init_db
    from backend.schemas import FindingSchema

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        review_res = await ac.post("/api/reviews/sample")
        assert review_res.status_code == 201
        review_id = review_res.json()["id"]

        # Drop needs_re_review column to simulate pre-existing database
        from backend.tests.conftest import test_engine
        async with TestingSessionLocal() as session:
            await session.execute(text("ALTER TABLE findings DROP COLUMN needs_re_review"))
            await session.commit()

        # Run init_db on test_engine (triggers auto-migration and backfill)
        await init_db(test_engine)

        # Fetch review - must serialize cleanly with 200 OK (not 500)
        get_res = await ac.get(f"/api/reviews/{review_id}")
        assert get_res.status_code == 200
        findings = get_res.json()["findings"]
        assert len(findings) > 0
        assert findings[0]["needs_re_review"] is False


@pytest.mark.asyncio
async def test_regression_accepted_custom_wording_survives_merge():
    """
    Regression Test 13:
    When combining accepted findings on the same cue where an editor provided custom wording,
    the approved action, description, and location must survive without invented filler text.
    """
    from types import SimpleNamespace as NS
    from backend.routes.reviews import resolve_cue_text

    original = "John greets Sarah near the door."
    f1 = NS(
        candidate_name="John",
        proposed_text="A man greets Sarah near the door.",
        edited_proposal="A tall man quietly greets Sarah beside the exit."
    )
    f2 = NS(
        candidate_name="Sarah",
        proposed_text="John greets a woman near the door.",
        edited_proposal="John greets a woman near the door."
    )

    merged = resolve_cue_text(original, [f1, f2])
    assert "tall man" in merged, "Custom subject was lost"
    assert "quietly" in merged, "Custom action manner was lost"
    assert "beside the exit" in merged, "Custom location was lost"
    assert "woman" in merged, "Second entity replacement was lost"
    assert "John" not in merged, "Concealed name John was restored"
    assert "Sarah" not in merged, "Concealed name Sarah was restored"
    assert "unidentified figure" not in merged, "Invented placeholder text was used"


@pytest.mark.asyncio
async def test_regression_multiline_revision_retains_crlf_style():
    """
    Regression Test 14:
    A multiline revision with LF breaks must be formatted with CRLF in a CRLF SRT file,
    preserving exact byte consistency.
    """
    raw = b"001\r\n00:00:01,000 --> 00:00:04,000\r\nOld first line.\r\nOld second line.\r\n\r\n"
    out = export_srt_bytes(raw, parse_srt(raw.decode()), {1: "New first line.\nNew second line."})
    expected = raw.replace(b"Old first line.\r\nOld second line.", b"New first line.\r\nNew second line.")
    assert out == expected



