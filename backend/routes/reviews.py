import asyncio
import os
import re
import difflib
from datetime import datetime
from pathlib import Path
import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.bundled_example import MARA_REFERENCE, load_recorded_example, resolve_video_path
from backend.database import get_db
from backend.config import UPLOAD_DIR, SAMPLES_DIR
from backend.models import Review, Cue, Finding, ReviewStatus, DecisionStatus, EvidenceOrigin, UncertaintyLevel
from backend.schemas import (
    ReviewSchema,
    ReviewSummarySchema,
    FindingSchema,
    FindingUpdateSchema
)
from backend.srt_parser import parse_srt, export_srt_bytes
from backend.analyzer import analyze_review, get_media_duration

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
examples_router = APIRouter(prefix="/api/examples", tags=["examples"])

MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200MB
MIN_VIDEO_SIZE = 1024               # 1KB
MAX_SRT_SIZE = 5 * 1024 * 1024      # 5MB
ALLOWED_VIDEO_EXTS = {".mp4", ".webm"}
ANALYSIS_TIMEOUT_SECONDS = 300


async def lock_editorial_review(review_id: str, db: AsyncSession):
    """Serialize editorial changes with the analysis claim on SQLite and Postgres."""
    result = await db.execute(
        update(Review)
        .where(Review.id == review_id, Review.status != ReviewStatus.ANALYZING)
        .values(status=Review.status)
    )
    if result.rowcount == 0:
        exists = await db.get(Review, review_id)
        await db.rollback()
        if exists is None:
            raise HTTPException(status_code=404, detail="Review not found")
        raise HTTPException(status_code=409, detail="Wait for analysis to finish before changing this review.")


async def fail_analysis(review_id: str, message: str, db: AsyncSession):
    # Roll back partial reconciliation before recording failure. Existing human
    # decisions must survive both cancellation and errors while merging results.
    await db.rollback()
    await db.execute(
        update(Review)
        .where(Review.id == review_id, Review.status == ReviewStatus.ANALYZING)
        .values(status=ReviewStatus.FAILED, error_message=message)
    )
    await db.commit()


def validate_video_magic_bytes(header: bytes, ext: str) -> bool:
    """Validate that file header contains valid MP4 or WebM magic signatures."""
    if len(header) < 12:
        return False
    if ext == ".mp4":
        return b"ftyp" in header[:32]
    if ext == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return False


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

    # Save video file with size and magic bytes check
    saved_video_filename = f"{review_id}{video_ext}"
    saved_video_path = str(UPLOAD_DIR / saved_video_filename)
    
    file_size = 0
    header_bytes = b""
    with open(saved_video_path, "wb") as f:
        while chunk := await video_file.read(1024 * 1024):
            file_size += len(chunk)
            if len(header_bytes) < 32:
                header_bytes += chunk[:32 - len(header_bytes)]
            if file_size > MAX_VIDEO_SIZE:
                f.close()
                if os.path.exists(saved_video_path):
                    os.remove(saved_video_path)
                raise HTTPException(status_code=400, detail="Video file exceeds 200MB size limit.")
            f.write(chunk)

    if file_size < MIN_VIDEO_SIZE or not validate_video_magic_bytes(header_bytes, video_ext):
        if os.path.exists(saved_video_path):
            os.remove(saved_video_path)
        raise HTTPException(status_code=400, detail="Invalid video file: missing valid MP4/WebM container header or file too small.")

    # Read SRT content with size and encoding check
    srt_bytes = await srt_file.read()
    if len(srt_bytes) > MAX_SRT_SIZE:
        if os.path.exists(saved_video_path):
            os.remove(saved_video_path)
        raise HTTPException(status_code=400, detail="SRT script file exceeds 5MB size limit.")

    try:
        srt_content = srt_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            srt_content = srt_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            if os.path.exists(saved_video_path):
                os.remove(saved_video_path)
            raise HTTPException(status_code=400, detail="Invalid SRT file: must be valid UTF-8 encoding.")

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

    # Probe real duration
    media_duration = get_media_duration(saved_video_path)

    # Create Review object
    review = Review(
        id=review_id,
        title=title,
        video_filename=video_file.filename,
        video_path=saved_video_path,
        srt_filename=srt_file.filename,
        srt_content=srt_content,
        raw_srt_bytes=srt_bytes,
        media_duration=media_duration,
        intent_notes=intent_notes or "",
        status=ReviewStatus.PENDING
    )
    db.add(review)

    # Create Cue objects with raw block tracking
    for c in parsed_cues:
        db.add(Cue(
            id=str(uuid.uuid4()),
            review_id=review_id,
            index=c.index,
            start_time=c.start_time,
            end_time=c.end_time,
            start_seconds=c.start_seconds,
            end_seconds=c.end_seconds,
            text=c.text,
            raw_block=c.raw_block,
            start_byte=c.start_char,
            end_byte=c.end_char
        ))

    await db.commit()
    db.expire_all()
    res = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    return res.scalars().first()


@router.post("/sample", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_sample_review(db: AsyncSession = Depends(get_db)):
    """Create and analyze a sample session using the bundled demonstration assets."""
    review = await build_sample_review(db)
    return await trigger_analysis(review.id, db)


async def build_sample_review(db: AsyncSession, snapshot: dict | None = None):
    """Build independent editorial state around durable, versioned sample media."""
    review_id = str(uuid.uuid4())
    sample_video_path = SAMPLES_DIR / "sample_short.mp4"
    sample_srt_path = SAMPLES_DIR / "sample_ad.srt"

    if not sample_srt_path.is_file() or not sample_video_path.is_file():
        raise HTTPException(status_code=503, detail="The bundled sample assets are unavailable. Please upload a clip and matching script.")

    with open(sample_srt_path, "rb") as f:
        srt_bytes = f.read()
    srt_content = srt_bytes.decode("utf-8")

    saved_video_path = MARA_REFERENCE

    parsed_cues = parse_srt(srt_content)
    media_duration = get_media_duration(str(sample_video_path)) or 72.0
    intent_notes = (
        "Synthetic test scene: Mara's identity is intended to remain concealed until "
        "her staff badge is shown at 00:01:06 (66 seconds). The cue at 00:00:05 "
        "names her before that reveal. Naming her at or after 66 seconds is intentional."
    )

    review = Review(
        id=review_id,
        title="Sample Short — Synthetic Mara Reveal",
        video_filename="sample_short.mp4",
        video_path=saved_video_path,
        srt_filename="sample_ad.srt",
        srt_content=srt_content,
        raw_srt_bytes=srt_bytes,
        media_duration=media_duration,
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
            text=c.text,
            raw_block=c.raw_block,
            start_byte=c.start_char,
            end_byte=c.end_char
        ))

    if snapshot is not None:
        review.title = "Recorded Example: Synthetic Mara Reveal"
        review.status = ReviewStatus.COMPLETED
        review.analysis_source = "recorded"
        review.recorded_at = datetime.fromisoformat(snapshot["recorded_at"].replace("Z", "+00:00"))
        review.model_used = snapshot["model_used"]
        review.intent_notes = snapshot["intent_notes"]
        await db.flush()
        cue_result = await db.execute(select(Cue).where(Cue.review_id == review_id))
        cue_map = {cue.index: cue for cue in cue_result.scalars()}
        for finding in snapshot["findings"]:
            db.add(Finding(
                id=str(uuid.uuid4()), review_id=review_id,
                cue_id=cue_map[finding["cue_index"]].id,
                edited_proposal=finding["proposed_text"],
                status=DecisionStatus.UNREVIEWED, needs_re_review=False,
                **finding,
            ))
    await db.commit()
    return await get_review(review_id, db)


def verified_example():
    try:
        return load_recorded_example(SAMPLES_DIR)
    except (OSError, ValueError, KeyError):
        raise HTTPException(status_code=503, detail="The recorded example assets are unavailable or do not match the verified recording.")


@examples_router.get("/mara")
async def get_recorded_example():
    """Read the original public snapshot, unaffected by editable review copies."""
    return verified_example()


@router.post("/example", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_recorded_example(db: AsyncSession = Depends(get_db)):
    """Copy verified recorded findings without invoking an analysis provider."""
    return await build_sample_review(db, snapshot=verified_example())


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
            model_used=r.model_used,
            analysis_source=r.analysis_source,
            recorded_at=r.recorded_at,
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
    """
    Run multimodal / heuristic analysis with ATOMIC concurrency protection.
    Preserves existing human decisions and accepted text, flagging changed proposals for re-review.
    """
    # Atomic conditional claim: only transitions if status != ANALYZING
    claim_stmt = (
        update(Review)
        .where(Review.id == review_id, Review.status != ReviewStatus.ANALYZING)
        .values(status=ReviewStatus.ANALYZING)
    )
    claim_res = await db.execute(claim_stmt)
    if claim_res.rowcount == 0:
        # Check if review doesn't exist vs already analyzing
        check_res = await db.execute(select(Review).filter(Review.id == review_id))
        if not check_res.scalars().first():
            raise HTTPException(status_code=404, detail="Review not found")
        raise HTTPException(status_code=409, detail="Analysis is already in progress for this review.")
    
    try:
        await db.commit()

        result = await db.execute(
            select(Review)
            .options(selectinload(Review.cues), selectinload(Review.findings))
            .filter(Review.id == review_id)
        )
        review = result.scalars().first()
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
        video_path = resolve_video_path(review.video_path, SAMPLES_DIR)
        if not video_path.is_file():
            raise FileNotFoundError("This review's video is unavailable. Upload the original clip again.")
        candidate_findings, model_name = await asyncio.wait_for(
            analyze_review(
                video_path=str(video_path),
                cues=cues_dict,
                intent_notes=review.intent_notes,
                media_duration=review.media_duration
            ),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )

        cue_map = {c.index: c for c in review.cues}
        existing_findings_map = {
            (f.cue_index, f.candidate_name): f
            for f in review.findings
        }

        seen_candidates = set()
        for cand in candidate_findings:
            target_cue = cue_map.get(cand.cue_index)
            if not target_cue:
                continue

            key = (cand.cue_index, cand.candidate_name)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            if key in existing_findings_map:
                existing_f = existing_findings_map.pop(key)
                
                # Check if model proposal changed
                proposal_changed = (cand.proposed_text.strip() != existing_f.proposed_text.strip())
                
                if existing_f.status == DecisionStatus.ACCEPTED:
                    if proposal_changed:
                        # Proposal changed: require re-review, preserve previous accepted wording
                        existing_f.previous_accepted_text = existing_f.edited_proposal or existing_f.proposed_text
                        existing_f.status = DecisionStatus.UNREVIEWED
                        existing_f.needs_re_review = True
                        existing_f.proposed_text = cand.proposed_text
                        existing_f.edited_proposal = cand.proposed_text
                    # If unchanged, keep existing_f.status == ACCEPTED and keep edited_proposal intact!
                elif existing_f.status in (DecisionStatus.DISMISSED, DecisionStatus.INTENTIONAL):
                    # Preserve decision status
                    pass
                else:
                    # UNREVIEWED: update proposal if not custom edited
                    if existing_f.edited_proposal == existing_f.proposed_text:
                        existing_f.edited_proposal = cand.proposed_text
                    existing_f.proposed_text = cand.proposed_text

                # Update metadata
                existing_f.issue_description = cand.issue_description
                existing_f.evidence_origin = cand.evidence_origin
                existing_f.interval_start = cand.interval_start
                existing_f.interval_end = cand.interval_end
                existing_f.uncertainty = cand.uncertainty
            else:
                # Brand new finding
                new_finding = Finding(
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
                    status=DecisionStatus.UNREVIEWED,
                    needs_re_review=False
                )
                db.add(new_finding)

        # For remaining findings that were NOT reported by the new analysis:
        # If human had reviewed it (ACCEPTED, DISMISSED, INTENTIONAL, or archived accepted text), do NOT delete it!
        for remaining_f in existing_findings_map.values():
            if remaining_f.status == DecisionStatus.ACCEPTED:
                remaining_f.needs_re_review = True
                if "[Note: Dropped in latest model analysis]" not in remaining_f.issue_description:
                    remaining_f.issue_description += " [Note: Dropped in latest model analysis]"
            elif remaining_f.needs_re_review or remaining_f.previous_accepted_text:
                # Retain finding with archived accepted text whose proposal was changed and now omitted
                if "[Note: Dropped in latest model analysis]" not in remaining_f.issue_description:
                    remaining_f.issue_description += " [Note: Dropped in latest model analysis]"
            elif remaining_f.status in (DecisionStatus.DISMISSED, DecisionStatus.INTENTIONAL):
                # Retain human editorial decisions
                pass
            elif remaining_f.status == DecisionStatus.UNREVIEWED:
                await db.delete(remaining_f)

        review.status = ReviewStatus.COMPLETED
        review.model_used = model_name
        review.analysis_source = "offline" if "offline" in model_name.lower() else "live"
        review.recorded_at = None
        review.error_message = ""
        await db.commit()
    except asyncio.CancelledError:
        await asyncio.shield(fail_analysis(review_id, "Analysis was interrupted. Please retry.", db))
        raise
    except TimeoutError:
        await fail_analysis(review_id, "Analysis timed out. Please retry when Gemini is available.", db)
    except Exception as e:
        await fail_analysis(review_id, f"Analysis failed: {str(e)}", db)
    
    db.expire_all()
    res = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    return res.scalars().first()


@router.patch("/{review_id}/findings/{finding_id}", response_model=FindingSchema)
async def update_finding(
    review_id: str,
    finding_id: str,
    payload: FindingUpdateSchema,
    db: AsyncSession = Depends(get_db)
):
    """Update finding status (accept, dismiss, mark intentional, reopen) or edit proposed text."""
    await lock_editorial_review(review_id, db)
    result = await db.execute(
        select(Finding).filter(Finding.id == finding_id, Finding.review_id == review_id)
    )
    finding = result.scalars().first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.status is not None:
        finding.status = payload.status
        if payload.status == DecisionStatus.ACCEPTED:
            finding.needs_re_review = False
    if payload.edited_proposal is not None:
        finding.edited_proposal = payload.edited_proposal

    await db.commit()
    await db.refresh(finding)
    return finding


def _extract_entity_replacement(cue_text: str, name: str, proposal: str) -> str:
    """Extracts what `name` was replaced with in `proposal` relative to `cue_text`."""
    if not name or name not in cue_text or not proposal:
        return ""
    idx = cue_text.find(name)
    prefix = cue_text[:idx]
    suffix = cue_text[idx + len(name):]

    # 1. Exact prefix/suffix match
    if proposal.startswith(prefix) and (not suffix or proposal.endswith(suffix)) and len(proposal) >= len(prefix) + len(suffix):
        return proposal[len(prefix):len(proposal) - len(suffix)] if len(suffix) > 0 else proposal[len(prefix):]

    # 2. Token-level diff matching
    cue_tokens = re.findall(r"\w+|[^\w\s]", cue_text)
    prop_tokens = re.findall(r"\w+|[^\w\s]", proposal)
    name_tokens = re.findall(r"\w+|[^\w\s]", name)
    name_len = len(name_tokens)
    name_start = -1
    for i in range(len(cue_tokens) - name_len + 1):
        if cue_tokens[i:i + name_len] == name_tokens:
            name_start = i
            break

    if name_start != -1:
        s = difflib.SequenceMatcher(None, cue_tokens, prop_tokens)
        for tag, alo, ahi, blo, bhi in s.get_opcodes():
            if alo <= name_start and ahi >= name_start + name_len:
                repl_tokens = prop_tokens[blo:bhi]
                if repl_tokens:
                    res = ""
                    for t in repl_tokens:
                        if res and re.match(r"^\w", t):
                            res += " " + t
                        else:
                            res += t
                    return res

    # 3. Fallback character-level diff matching
    s = difflib.SequenceMatcher(None, cue_text, proposal)
    blocks = s.get_matching_blocks()
    for i in range(len(blocks) - 1):
        a_end = blocks[i].a + blocks[i].size
        next_a = blocks[i + 1].a
        if a_end <= idx and next_a >= idx + len(name):
            b_start = blocks[i].b + blocks[i].size
            next_b = blocks[i + 1].b
            return proposal[b_start:next_b]
    return ""


def resolve_cue_text(cue_text: str, accepted_findings: list) -> str:
    """
    Resolves accepted cue revisions at the cue level.
    If multiple findings exist on the same cue:
    1. If any finding has an authoritative custom edit where none of the accepted candidate names remain, use it.
    2. If custom edits exist differing from default proposals:
       Evaluates candidate base sentences to preserve approved actions, descriptions, and locations
       while absorbing other accepted entity replacements without re-exposing concealed names.
    3. Guarantees that no accepted finding's concealed name is restored in the exported text.
    """
    if not accepted_findings:
        return cue_text
    if len(accepted_findings) == 1:
        f = accepted_findings[0]
        return (getattr(f, "edited_proposal", None) or getattr(f, "proposed_text", None) or cue_text).strip()

    names = [getattr(f, "candidate_name", "") for f in accepted_findings if getattr(f, "candidate_name", "")]

    # 1. Authoritative custom edit that eliminates all names
    for f in reversed(accepted_findings):
        proposal = (getattr(f, "edited_proposal", None) or getattr(f, "proposed_text", None) or "").strip()
        if proposal and all(not re.search(rf"\b{re.escape(name)}\b", proposal) for name in names if name):
            return proposal

    def get_replacement_for_finding(f):
        name = getattr(f, "candidate_name", "")
        if not name:
            return ""
        edited = (getattr(f, "edited_proposal", None) or "").strip()
        if edited:
            repl = _extract_entity_replacement(cue_text, name, edited)
            if repl and not re.search(rf"\b{re.escape(name)}\b", repl):
                return repl
        prop = (getattr(f, "proposed_text", None) or "").strip()
        if prop:
            repl = _extract_entity_replacement(cue_text, name, prop)
            if repl and not re.search(rf"\b{re.escape(name)}\b", repl):
                return repl
        return ""

    # 2. Check for custom edits differing from default proposed_text
    custom_findings = [
        f for f in accepted_findings
        if (getattr(f, "edited_proposal", "") or "").strip() and
           (getattr(f, "edited_proposal", "") or "").strip() != (getattr(f, "proposed_text", "") or "").strip()
    ]

    if custom_findings:
        # Sort candidates by comprehensive editorial changes (lowest similarity ratio to cue_text first)
        def _edit_distance(f):
            txt = (getattr(f, "edited_proposal", "") or "").strip()
            return difflib.SequenceMatcher(None, cue_text, txt).ratio()

        sorted_custom = sorted(custom_findings, key=_edit_distance)

        best_result = None
        best_unresolved_count = 999

        for base_f in sorted_custom:
            cand = (getattr(base_f, "edited_proposal", "") or "").strip()
            other_findings = [f for f in accepted_findings if f != base_f]
            for f in other_findings:
                name = getattr(f, "candidate_name", "")
                if name and re.search(rf"\b{re.escape(name)}\b", cand):
                    repl = get_replacement_for_finding(f)
                    if repl:
                        cand = re.sub(rf"\b{re.escape(name)}\b", repl, cand)

            remaining = [name for name in names if re.search(rf"\b{re.escape(name)}\b", cand)]
            if len(remaining) < best_unresolved_count:
                best_unresolved_count = len(remaining)
                best_result = cand
                if best_unresolved_count == 0:
                    break

        result = best_result or (getattr(sorted_custom[0], "edited_proposal", "") or "").strip()

        # Enforce name concealment guarantee: purge any remaining concealed names
        for f in accepted_findings:
            name = getattr(f, "candidate_name", "")
            if name and re.search(rf"\b{re.escape(name)}\b", result):
                repl = get_replacement_for_finding(f)
                if repl:
                    result = re.sub(rf"\b{re.escape(name)}\b", repl, result)

        return result

    # 3. Default proposals merge onto original cue_text
    result = cue_text
    sorted_findings = sorted(accepted_findings, key=lambda f: len(getattr(f, "candidate_name", "") or ""), reverse=True)

    for f in sorted_findings:
        name = getattr(f, "candidate_name", "")
        if not name or not re.search(rf"\b{re.escape(name)}\b", result):
            continue
        repl = get_replacement_for_finding(f)
        if repl:
            result = re.sub(rf"\b{re.escape(name)}\b", repl, result)

    return result


@router.get("/{review_id}/export")
async def export_review_srt(review_id: str, db: AsyncSession = Depends(get_db)):
    """
    Export the updated SRT script.
    Byte-exact preservation for untouched cues.
    Resolves accepted cue revisions at the cue level.
    """
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.cues), selectinload(Review.findings))
        .filter(Review.id == review_id)
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Map accepted revisions by cue index
    cue_revisions: Dict[int, str] = {}
    for cue in review.cues:
        accepted_findings = [f for f in review.findings if f.cue_id == cue.id and f.status == DecisionStatus.ACCEPTED]
        if accepted_findings:
            cue_revisions[cue.index] = resolve_cue_text(cue.text, accepted_findings)

    raw_bytes = review.raw_srt_bytes or review.srt_content.encode("utf-8")
    exported_bytes = export_srt_bytes(raw_bytes, review.cues, cue_revisions)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(review.srt_filename).stem).strip(".-")[:100] or "reveal"
    variant = "original" if exported_bytes == raw_bytes else "revised"
    filename = f"{stem}-{variant}.srt"

    return Response(
        content=exported_bytes,
        media_type="application/x-subrip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(review_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a review session and its associated files."""
    await lock_editorial_review(review_id, db)
    result = await db.execute(select(Review).filter(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    video_path = Path(review.video_path)
    bundled = review.video_path.startswith("sample:") or video_path.resolve().is_relative_to(SAMPLES_DIR.resolve())
    if not bundled and video_path.is_file():
        try:
            video_path.unlink()
        except Exception:
            pass

    await db.delete(review)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{review_id}/video")
async def get_review_video(review_id: str, db: AsyncSession = Depends(get_db)):
    """Stream uploaded video file with byte-range support."""
    result = await db.execute(select(Review).filter(Review.id == review_id))
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    try:
        video_path = resolve_video_path(review.video_path, SAMPLES_DIR)
        if not video_path.is_file():
            raise FileNotFoundError
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="This review's video is unavailable. Uploaded clips may be lost after a deployment; upload the original clip again.")
    media_type = "video/webm" if video_path.suffix.lower() == ".webm" else "video/mp4"
    return FileResponse(video_path, media_type=media_type)
