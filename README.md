# Reveal — AI-Assisted Audio Description Editorial Reviewer

An editorial review assistant that helps Audio Description (AD) editors, accessibility producers, and filmmakers investigate possible **premature identity disclosures** in short films.

## Overview

In cinema with concealed character identities or mysteries, an Audio Description (AD) script might accidentally name a character (e.g. *"John enters the room"*) before the film deliberately establishes that identity visually or in dialogue. 

**Reveal** ingests a film video file (MP4/WebM), a timecoded SRT script, and optional filmmaker intent notes. It analyzes cues using Google Gen AI (`google-genai` / Gemini 2.5 Flash) and heuristic timestamp verification to flag candidate premature name disclosures, present timestamped evidence, generate proposed anonymized wording, and allow human editors to accept, edit, dismiss, or mark findings as intentional.

## Key Features

- **Multimodal & Timestamped Analysis**: Integrates Google Gen AI SDK (`google-genai`) with Gemini models (and fallback offline heuristic analysis for offline development/testing).
- **Synchronized Review Workspace**: HTML5 Video Player synchronized frame-by-frame with SRT cues and finding markers.
- **Interactive Finding Inspector**: Inspect candidate name drops, compare original vs proposed wording, edit proposals with live draft indicators, and apply decisions (*Accept*, *Dismiss*, *Mark Intentional*, *Reopen*).
- **SRT Export Engine**: Exports revised `.srt` files containing accepted text edits while strictly preserving original timing, numbering, line endings, and unaffected text.
- **Screen-Reader & Low-Vision Accessible View**: High-contrast, keyboard-navigable table interface optimized for screen readers and accessibility professionals.

## Quick Start

### 1. Backend Setup (Python 3.12 + FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --port 8001 --reload
```

### 2. Frontend Setup (React 18 + TypeScript + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Automated Testing

Run the backend test suite (unit and integration tests):

```bash
python -m pytest -v backend/tests
```

Build the frontend bundle:

```bash
cd frontend
npm run build
```

## Architecture

- **`backend/`**:
  - `main.py`: FastAPI server setup and routing.
  - `models.py` & `schemas.py`: Database models and Pydantic validation for Reviews, Cues, and Findings.
  - `srt_parser.py`: Robust SRT parser, timestamp conversion, and export serializer.
  - `analyzer.py`: Multimodal Gemini API integration (`google-genai`) and fallback heuristic rule engine.
  - `routes/reviews.py`: REST endpoints for upload, sample demo loading, decision updates, export, and streaming.
- **`frontend/`**:
  - `src/components/ReviewWorkspace.tsx`: Main split layout (video, cue list, finding inspector).
  - `src/components/VideoPlayer.tsx`: Custom video player with timeline finding markers and keyboard shortcuts.
  - `src/components/CueList.tsx`: SRT cue list with filtering by decision status.
  - `src/components/FindingInspector.tsx`: Candidate evidence inspector and proposal editor.
  - `src/components/AccessibleTextView.tsx`: High-contrast table view for screen reader accessibility.

## License

MIT License.
