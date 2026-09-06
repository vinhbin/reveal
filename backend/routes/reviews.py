import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.config import UPLOAD_DIR, SAMPLES_DIR
from backend.models import Review, Cue, Finding, ReviewStatus, DecisionStatus, EvidenceOrigin, UncertaintyLevel
from backend.schemas import (
    ReviewSchema,
    ReviewSummarySchema,
    FindingSchema,
    FindingUpdateSchema
)
from backend.srt_parser import parse_srt, export_srt
from backend.analyzer import analyze_review

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200MB
MAX_SRT_SIZE = 5 * 1024 * 1024      # 5MB
ALLOWED_VIDEO_EXTS = {".mp4", ".webm"}


@router.post("", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
    title: str = Form(...),
    intent_notes: Optional[str] = Form(""),
    video_file: UploadFile = File(...),
    srt_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload video and SRT file to create a new AD review session."""
    review_id = str(uuid.uuid4())
    
    # Validate video extension
    video_ext = os.path.splitext(video_file.filename)[1].lower() or ".mp4"
    if video_ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video file type '{video_ext}'. Only MP4 and WebM are supported."
        )

    # Save video file with size check
    saved_video_filename = f"{review_id}{video_ext}"
    saved_video_path = str(UPLOAD_DIR / saved_video_filename)
    
    file_size = 0
    with open(saved_video_path, "wb") as f:
        while chunk := await video_file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > MAX_VIDEO_SIZE:
                f.close()
                if os.path.exists(saved_video_path):
                    os.remove(saved_video_path)
                raise HTTPException(status_code=400, detail="Video file exceeds 200MB size limit.")
            f.write(chunk)

    # Read SRT content with size check
    srt_bytes = await srt_file.read()
    if len(srt_bytes) > MAX_SRT_SIZE:
        if os.path.exists(saved_video_path):
            os.remove(saved_video_path)
        raise HTTPException(status_code=400, detail="SRT script file exceeds 5MB size limit.")

    srt_content = srt_bytes.decode("utf-8-sig", errors="replace")

    # Parse SRT cues
    try:
        parsed_cues = parse_srt(srt_content)
    except Exception as e:
        if os.path.exists(saved_video_path):
            os.remove(saved_video_path)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse SRT file: {str(e)}"
        )

    # Create Review object
    review = Review(
        id=review_id,
        title=title,
        video_filename=video_file.filename,
        video_path=saved_video_path,
        srt_filename=srt_file.filename,
        srt_content=srt_content,
        intent_notes=intent_notes or "",
        status=ReviewStatus.PENDING
    )
    db.add(review)

    # Create Cue objects
    for c in parsed_cues:
        db.add(Cue(
            id=str(uuid.uuid4()),
            review_id=review_id,
            index=c.index,
            start_time=c.start_time,
            end_time=c.end_time,
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            text=c.text
        ))

    await db.commit()
    await db.refresh(review, ["cues", "findings"])
    return review


@router.post("/sample", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_sample_review(db: AsyncSession = Depends(get_db)):
    """Create a sample review session using pre-packaged demonstration assets."""
    review_id = str(uuid.uuid4())
    sample_video_path = SAMPLES_DIR / "sample_short.mp4"
    sample_srt_path = SAMPLES_DIR / "sample_ad.srt"

    # Minimal valid 1-second silent MP4 header bytes if sample video doesn't exist
    VALID_MINIMAL_MP4 = (
        b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2avc1mp41"
        b"\x00\x00\x00\x08free"
        b"\x00\x00\x00\x40mdat" + b"\x00" * 56
    )

    if not sample_srt_path.exists():
        sample_srt_content = """1
00:00:02,000 --> 00:00:06,000
In a shadowed alleyway, Detective Vance watches a flickering streetlight.

2
00:00:08,500 --> 00:00:13,000
Detective Vance adjusts his collar as rainfall slicks the cobblestones.

3
00:00:15,000 --> 00:00:19,500
Dr. Aris Thorne approaches from the mist carrying a steel briefcase.

4
00:00:22,000 --> 00:00:27,000
The stranger extends a gloved hand and hands over a keycard.

5
00:00:30,000 --> 00:00:35,000
A badge pinned to his coat shines: Detective Vance, Precinct 4.
"""
        with open(sample_srt_path, "w", encoding="utf-8") as f:
            f.write(sample_srt_content)

    if not sample_video_path.exists() or sample_video_path.stat().st_size < 100:
        with open(sample_video_path, "wb") as f:
            f.write(VALID_MINIMAL_MP4)

    saved_video_path = str(UPLOAD_DIR / f"{review_id}.mp4")
    shutil.copyfile(sample_video_path, saved_video_path)

    with open(sample_srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    parsed_cues = parse_srt(srt_content)
    intent_notes = "The identity of Dr. Aris Thorne is intended to remain concealed until the unmasking climax. Cue #3 prematurely names Dr. Aris Thorne."

    review = Review(
        id=review_id,
        title="Sample Short — The Alleyway Encounter",
        video_filename="sample_short.mp4",
        video_path=saved_video_path,
        srt_filename="sample_ad.srt",
        srt_content=srt_content,
        intent_notes=intent_notes,
        status=ReviewStatus.PENDING
    )
    db.add(review)

    for c in parsed_cues:
        db.add(Cue(
            id=str(uuid.uuid4()),
            review_id=review_id,
            index=c.index,
            start_time=c.start_time,
            end_time=c.end_time,
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            text=c.text
        ))

    await db.commit()
    return await trigger_analysis(review_id, db)


@router.get("", response_model=List[ReviewSummarySchema])
async def list_reviews(db: AsyncSession = Depends(get_db)):
    """List all review sessions with summary statistics."""
    result = await db.execute(
        select(Review).options(selectinload(Review.cues), selectinload(Review.findings)).order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    
    summaries = []
    for r in reviews:
        unreviewed = sum(1 for f in r.findings if f.status == DecisionStatus.UNREVIEWED)
        summaries.append(ReviewSummarySchema(
            id=r.id,
            title=r.title,
            video_filename=r.video_filename,
            srt_filename=r.srt_filename,
            status=r.status,
            cue_count=len(r.cues),
            finding_count=len(r.findings),
            unreviewed_count=unreviewed,
            created_at=r.created_at,
            updated_at=r.updated_at
        ))
    return summaries


@router.get("/{review_id}", response_model=ReviewSchema)
async def get_review(review_id: str, db: AsyncSession = Depends(get_db)):
    """Get full review details including cues and findings."""
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/{review_id}/analyze", response_model=ReviewSchema)
async def trigger_analysis(review_id: str, db: AsyncSession = Depends(get_db)):
    """Run multimodal / heuristic analysis to detect premature identity disclosures."""
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.status = ReviewStatus.ANALYZING
    await db.commit()

    cues_dict = [
        {
            "id": c.id,
            "index": c.index,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "start_seconds": c.start_seconds,
            "end_seconds": c.end_seconds,
            "text": c.text
        }
        for c in review.cues
    ]

    try:
        candidate_findings, model_name = await analyze_review(
            video_path=review.video_path,
            cues=cues_dict,
            intent_notes=review.intent_notes
        )

        # Only delete old findings AFTER new analysis succeeds
        for existing_f in list(review.findings):
            await db.delete(existing_f)
        await db.commit()

        cue_map = {c.index: c for c in review.cues}

        for cand in candidate_findings:
            target_cue = cue_map.get(cand.cue_index)
            if not target_cue:
                continue

            finding_obj = Finding(
                id=str(uuid.uuid4()),
                review_id=review.id,
                cue_id=target_cue.id,
                cue_index=cand.cue_index,
                candidate_name=cand.candidate_name,
                issue_description=cand.issue_description,
                proposed_text=cand.proposed_text,
                edited_proposal=cand.proposed_text,
                evidence_origin=cand.evidence_origin,
                interval_start=cand.interval_start,
                interval_end=cand.interval_end,
                uncertainty=cand.uncertainty,
                status=DecisionStatus.UNREVIEWED
            )
            db.add(finding_obj)

        review.status = ReviewStatus.COMPLETED
        review.model_used = model_name
        review.error_message = ""
    except Exception as e:
        review.status = ReviewStatus.FAILED
        review.error_message = f"Analysis failed: {str(e)}"
    
    await db.commit()
    await db.refresh(review, ["cues", "findings"])
    return review


@router.patch("/{review_id}/findings/{finding_id}", response_model=FindingSchema)
async def update_finding(
    review_id: str,
    finding_id: str,
    payload: FindingUpdateSchema,
    db: AsyncSession = Depends(get_db)
):
    """Update finding status (accept, dismiss, mark intentional, reopen) or edit proposed text."""
    result = await db.execute(
        select(Finding).filter(Finding.id == finding_id, Finding.review_id == review_id)
    )
    finding = result.scalars().first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.status is not None:
        finding.status = payload.status
    if payload.edited_proposal is not None:
        finding.edited_proposal = payload.edited_proposal

    await db.commit()
    await db.refresh(finding)
    return finding


@router.get("/{review_id}/export")
async def export_review_srt(review_id: str, db: AsyncSession = Depends(get_db)):
    """
    Export the updated SRT script.
    Resolves multiple accepted findings per cue sequentially.
    Preserves exact original timing, numbering, and untouched text.
    """
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Group accepted findings by cue_id
    cue_findings_map = {}
    for f in review.findings:
        if f.cue_id not in cue_findings_map:
            cue_findings_map[f.cue_id] = []
        cue_findings_map[f.cue_id].append(f)

    cues_to_export = []
    for cue in review.cues:
        findings_for_cue = cue_findings_map.get(cue.id, [])
        accepted_findings = [f for f in findings_for_cue if f.status == DecisionStatus.ACCEPTED]

        if accepted_findings:
            # Apply accepted text edit (or sequentially apply if multiple)
            final_text = accepted_findings[-1].edited_proposal or accepted_findings[-1].proposed_text
            is_modified = True
        else:
            final_text = cue.text
            is_modified = False

        cues_to_export.append({
            "index": cue.index,
            "start_time": cue.start_time,
            "end_time": cue.end_time,
            "text": final_text,
            "is_modified": is_modified,
            "raw_block": f"{cue.index}\n{cue.start_time} --> {cue.end_time}\n{cue.text}"
        })

    exported_srt = export_srt(cues_to_export)
    filename = f"edited_{review.srt_filename}"

    return Response(
        content=exported_srt,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(review_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a review session and its associated files."""
    result = await db.execute(select(Review).filter(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if os.path.exists(review.video_path):
        try:
            os.remove(review.video_path)
        except Exception:
            pass

    await db.delete(review)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{review_id}/video")
async def get_review_video(review_id: str, db: AsyncSession = Depends(get_db)):
    """Stream uploaded video file."""
    result = await db.execute(select(Review).filter(Review.id == review_id))
    review = result.scalars().first()
    if not review or not os.path.exists(review.video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(review.video_path, media_type="video/mp4")
