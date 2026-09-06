import asyncio
import json
import logging
import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from backend.config import GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, REVEAL_MODEL
from backend.models import EvidenceOrigin, UncertaintyLevel

logger = logging.getLogger("reveal.analyzer")

PROPER_NOUN_REGEX = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
COMMON_EXCLUSIONS = {
    "The", "A", "An", "In", "On", "At", "He", "She", "They", "It", "We", "You",
    "Suddenly", "Meanwhile", "Then", "As", "With", "After", "Before", "Inside",
    "Outside", "Behind", "Across", "Above", "Below", "Slowly", "Quickly", "Cue"
}

class CandidateFinding:
    def __init__(
        self,
        cue_index: int,
        candidate_name: str,
        issue_description: str,
        proposed_text: str,
        evidence_origin: EvidenceOrigin,
        interval_start: float,
        interval_end: float,
        uncertainty: UncertaintyLevel
    ):
        self.cue_index = cue_index
        self.candidate_name = candidate_name
        self.issue_description = issue_description
        self.proposed_text = proposed_text
        self.evidence_origin = evidence_origin
        self.interval_start = interval_start
        self.interval_end = interval_end
        self.uncertainty = uncertainty


async def analyze_review(
    video_path: str,
    cues: List[Dict[str, Any]],
    intent_notes: Optional[str] = ""
) -> Tuple[List[CandidateFinding], str]:
    """
    Analyzes AD cues against video and intent notes.
    If live API credentials exist, invokes Gemini API via thread isolation.
    If API call fails, raises RuntimeError so review status is FAILED.
    """
    is_live_configured = bool(GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT)

    if is_live_configured:
        try:
            return await _run_gemini_analysis_threaded(video_path, cues, intent_notes)
        except Exception as e:
            logger.error(f"Live Gemini API analysis failed: {e}")
            raise RuntimeError(f"Live model analysis failed: {str(e)}")

    # Deterministic offline heuristic mode when no API key configured
    findings = run_heuristic_analysis(cues, intent_notes)
    return findings, "reveal-heuristic-analyzer (offline demo mode)"


async def _run_gemini_analysis_threaded(
    video_path: str,
    cues: List[Dict[str, Any]],
    intent_notes: Optional[str] = ""
) -> Tuple[List[CandidateFinding], str]:
    """Runs synchronous google-genai client calls in a background thread."""
    def _sync_call():
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else genai.Client()
        model_id = REVEAL_MODEL
        model_used = f"google-genai/{model_id}"

        cues_formatted = json.dumps([
            {
                "index": c["index"],
                "start": c["start_time"],
                "end": c["end_time"],
                "text": c["text"]
            }
            for c in cues
        ], indent=2)

        prompt = f"""
You are an expert Audio Description (AD) accessibility reviewer for film.
Analyze the following SRT script cues alongside the provided video.
Filmmaker Intent Notes: "{intent_notes or 'None provided.'}"

AD Script Cues:
{cues_formatted}

Identify any PREMATURE IDENTITY DISCLOSURES — instances where an AD cue explicitly names a character (e.g. "John", "Detective Vance", "Elena") BEFORE their identity is visually established, introduced in dialogue, or revealed in the narrative timeline.

Return ONLY a JSON array matching this exact schema:
[
  {{
    "cue_index": 1,
    "candidate_name": "Detective Vance",
    "issue_description": "Cue names Detective Vance at 0:12, but character identity is established later.",
    "proposed_text": "A shadowed figure in a trench coat steps into the frame.",
    "evidence_origin": "model_inference",
    "interval_start": 0.0,
    "interval_end": 70.0,
    "uncertainty": "medium"
  }}
]
If no premature identity disclosures exist, return [].
Note: evidence_origin MUST be one of: "model_inference", "dialogue", "filmmaker_intent". Never return "human_verification".
"""

        contents = []
        if os.path.exists(video_path) and os.path.getsize(video_path) > 1024:
            logger.info(f"Uploading video file {video_path} to Gemini...")
            video_file = client.files.upload(file=video_path)
            
            # Poll until video processing state is ACTIVE
            max_polls = 30
            for _ in range(max_polls):
                file_info = client.files.get(name=video_file.name)
                state_name = getattr(file_info.state, "name", str(file_info.state))
                if state_name == "ACTIVE":
                    break
                if state_name == "FAILED":
                    raise RuntimeError("Gemini video file processing failed.")
                time.sleep(2)
            
            contents.append(video_file)

        contents.append(prompt)

        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )

        raw_text = response.text.strip()
        findings_data = json.loads(raw_text)

        max_cue_index = max((c["index"] for c in cues), default=9999)
        valid_findings = []

        for item in findings_data:
            c_idx = int(item.get("cue_index", 0))
            if c_idx < 1 or c_idx > max_cue_index:
                continue

            origin_str = str(item.get("evidence_origin", "model_inference")).lower()
            if origin_str == "dialogue":
                origin = EvidenceOrigin.DIALOGUE
            elif origin_str == "filmmaker_intent":
                origin = EvidenceOrigin.FILMMAKER_INTENT
            else:
                # Force model_inference; disallow model claiming human_verification
                origin = EvidenceOrigin.MODEL_INFERENCE

            unc_str = str(item.get("uncertainty", "medium")).lower()
            uncertainty = UncertaintyLevel.MEDIUM
            if unc_str == "low":
                uncertainty = UncertaintyLevel.LOW
            elif unc_str == "high":
                uncertainty = UncertaintyLevel.HIGH

            interval_start = max(0.0, float(item.get("interval_start", 0.0)))
            interval_end = max(interval_start, float(item.get("interval_end", 0.0)))

            valid_findings.append(CandidateFinding(
                cue_index=c_idx,
                candidate_name=str(item.get("candidate_name", "Concealed Character")),
                issue_description=str(item.get("issue_description", "Premature identity disclosure detected.")),
                proposed_text=str(item.get("proposed_text", "")),
                evidence_origin=origin,
                interval_start=interval_start,
                interval_end=interval_end,
                uncertainty=uncertainty
            ))

        return valid_findings, model_used

    return await asyncio.to_thread(_sync_call)


def run_heuristic_analysis(cues: List[Dict[str, Any]], intent_notes: Optional[str] = "") -> List[CandidateFinding]:
    """
    Deterministic rule-based analyzer that detects proper names used early in AD cues
    before an explicit reveal context, dialogue, or filmmaker intent flag.
    """
    findings = []
    
    concealed_names_from_notes = set()
    if intent_notes:
        for match in PROPER_NOUN_REGEX.finditer(intent_notes):
            name = match.group(1)
            if name not in COMMON_EXCLUSIONS and len(name) > 2:
                concealed_names_from_notes.add(name.lower())

    name_occurrences: Dict[str, List[Dict[str, Any]]] = {}

    for cue in cues:
        text = cue["text"]
        found_names = PROPER_NOUN_REGEX.findall(text)
        for name in found_names:
            if name in COMMON_EXCLUSIONS or len(name) <= 2:
                continue
            if name not in name_occurrences:
                name_occurrences[name] = []
            name_occurrences[name].append(cue)

    for name, occurrences in name_occurrences.items():
        first_cue = occurrences[0]
        first_cue_idx = first_cue["index"]
        first_cue_start = first_cue["start_seconds"]

        name_lower = name.lower()
        matched_in_notes = any(c_name in name_lower or name_lower in c_name for c_name in concealed_names_from_notes)
        
        is_concealed = matched_in_notes or (first_cue_start < 30.0)

        if is_concealed:
            later_reveal_time = first_cue_start + 45.0
            
            proposed_text = first_cue["text"]
            if name in proposed_text:
                anon = "the stranger"
                if "Doctor" in name or "Dr" in name or "Thorne" in name:
                    anon = "a masked figure"
                elif "Agent" in name or "Detective" in name or "Vance" in name:
                    anon = "an investigator"
                elif "John" in name or "Marcus" in name:
                    anon = "an unidentified man"
                elif "Sarah" in name or "Elena" in name:
                    anon = "an unknown woman"
                
                proposed_text = re.sub(rf"\b{re.escape(name)}\b", anon, proposed_text)

            origin = EvidenceOrigin.FILMMAKER_INTENT if matched_in_notes else EvidenceOrigin.MODEL_INFERENCE
            
            findings.append(CandidateFinding(
                cue_index=first_cue_idx,
                candidate_name=name,
                issue_description=f"[Demo Rule] Cue #{first_cue_idx} uses proper name '{name}' at {first_cue['start_time']} before established reveal.",
                proposed_text=proposed_text,
                evidence_origin=origin,
                interval_start=first_cue_start,
                interval_end=later_reveal_time,
                uncertainty=UncertaintyLevel.MEDIUM if origin == EvidenceOrigin.MODEL_INFERENCE else UncertaintyLevel.LOW
            ))

    return findings
