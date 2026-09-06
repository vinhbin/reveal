# Proposed architecture

This is a design, not an implemented system. Validate deployment compatibility in Replit before expanding scope.

## Components

| Component | Proposed choice | Responsibility |
| --- | --- | --- |
| Web interface | React + TypeScript | Accessible review form, video player, ordered findings, decisions, export |
| App/API host | Replit deployment | Serve the editor application and backend routes |
| Backend | Python + FastAPI | SRT handling, upload checks, review state, agent invocation |
| Agent | Google ADK + Gemini through Google Cloud | Investigate potential identity disclosures using bounded tools |
| Media storage | Private Google Cloud Storage | Film and evidence assets, with time-limited access |
| Review storage | Replit managed PostgreSQL, subject to provisioning | Review jobs, cue versions, findings, decisions |

Keep an explicit adapter around persistence. A local file or in-memory store may support development but must not be described as persistent production storage.

## Review flow

1. Parse and validate SRT and media metadata server-side.
2. Give Gemini the short film, AD cues, and brief intent notes. Gather candidate identities, disclosures, and relevant intervals; this is fallible model output.
3. The ADK agent may retrieve cues and inspect focused film intervals to investigate a candidate. Consider what is available up to the cue time separately from later identity evidence.
4. Check that findings reference existing cues and valid intervals. Surface unresolved ambiguity instead of silently guessing.
5. Persist findings; the editor decides changes in the UI.
6. Apply only accepted text changes to export. Preserve original cue timing.

Prefix-only inspection can reduce access to future events but does not prove spoiler safety. Do not supply later-event answers to a tool purportedly checking what was known earlier.

## Initial tools

- `get_ad_cues(start_ms, end_ms)`: return exact cue text and IDs.
- `inspect_video_interval(start_ms, end_ms, question)`: request focused Gemini analysis and return its evidence/inference with interval provenance.
- `get_intent_notes()`: return editor-supplied notes, clearly labeled as intent.
- `record_candidate_finding(...)`: validate and save a review candidate; never accept a revision automatically.

Set bounds on tool calls, interval lengths, retries, and total review duration. A failed tool call is an explicit error or inconclusive result.

## Data model

- Review: ID, media reference, duration, original script reference, notes, status, model/config version.
- AD cue: ID, index, start/end milliseconds, original text, current text.
- Finding: ID, cue ID, category, rationale, evidence intervals, evidence type, uncertainty, suggested text, status.
- Decision: finding ID, action, edited text when applicable, timestamp.

Finding category initially has one value: `possible_premature_identity`. Status: `pending`, `accepted`, `dismissed`, or `intentional`.

## Accessibility and evidence

Every timeline finding also appears in a semantic ordered list. Do not require dragging, color interpretation, or visual frame inspection to operate the app. Provide keyboard-accessible playback, clear headings, named controls, focus management, and announced review status.

Text evidence identifies whether a claim comes from dialogue, filmmaker notes, or generated visual analysis. A generated frame explanation may help a blind reviewer navigate, but cannot serve as independent proof of its own accuracy. Preserve the option for collaborative visual verification.

## Track fit

Replit Agent must contribute to development and the app must be deployed directly on Replit. Google libraries must be imported and actually used. Use Google AI and the chosen partner's permitted AI features; do not introduce other model providers or agent frameworks into the implementation.

References: [official rules](https://agentic-cinema.devpost.com/rules), [hackathon resources](https://agentic-cinema.devpost.com/resources), [Google ADK tools](https://adk.dev/tools-custom/), [Google video understanding](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/video-understanding).
