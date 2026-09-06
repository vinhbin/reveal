# Reveal build plan

Planning baseline: September 5, 2026. Target: Replit-track submission by September 9 at 5 p.m. Eastern, with a noon Eastern internal freeze. Dates are targets, not completed work.

## Product decision

Build an editorial tool for reviewing AD before release. The initial question is: does a line identify a deliberately concealed character before the film establishes that identity?

Early naming is not automatically an error. The system must consider dialogue, recognizable faces, prior appearances, deliberate concealment, clarity exceptions, and filmmaker notes. Suggest human review when evidence is inconclusive.

## User journey

1. Create a review and upload an original/authorized short film and an SRT AD script.
2. Optionally add plain-language intent, such as "Keep the intruder unidentified until the final shot." Do not require users to label every reveal time.
3. Run review; display progress, recoverable errors, and completed findings.
4. Open a finding to inspect the AD cue, current scene, later evidence, rationale, uncertainty, and proposed wording.
5. Edit and accept the suggestion, dismiss it, or mark it intentional. Save the decision.
6. Export the revised SRT while preserving cue timing and unaffected text.

No auto-accept. Distinguish a completed review with no findings from a failed or inconclusive review.

## Scope boundaries

Included: one project/film at a time, short English-language films, SRT input/output, identity review, editor decisions, persistent review state, accessible text and video views.

Deferred: full-length movies, batch studio ingestion, streaming-service integration, character recognition guarantees, AD generation and narration, automatic clue-omission or motive scoring, collaboration/accounts unless needed for safe hosting.

For the public judging demo, start with owned sample media. Arbitrary uploads require access controls, size/duration limits, and deletion behavior before public exposure. No uncontrolled public storage bucket.

## Milestones

### 0. Plan and repository — September 5

- Establish the product scope, source ledger, architecture, and Replit handoff.
- Initialize Git and create a private GitHub remote.
- Record pending setup: Replit project, Google Cloud project/billing, model access, owned demo media, and reviewer availability.

Exit: documents committed and remote reachable. No application claimed.

### 1. Prove the core review — September 6

- Use Replit Agent to create the project and record its contribution.
- Prepare an original short mystery with multiple shots/scenes; retain media rights and author intent separately from test labels.
- Implement SRT parsing and a simple Gemini baseline using video, dialogue context, AD, and brief notes.
- Inspect whether identity evidence is correct and whether an acceptable early name stays unflagged.

Exit: actual model output with reproducible inputs, evidence timestamps, and observed failures. If evidence is unreliable, narrow to evidence retrieval rather than displaying unsupported verdicts.

### 2. Complete the editor workflow — September 7

- Add bounded ADK tools for inspecting film intervals, retrieving AD cues, and recording candidate findings.
- Build the timeline plus an equivalent ordered text view, editable suggestions, saved decisions, and export.
- Add timestamp/cue-reference validation, uncertainty states, upload limits, and clear errors.

Exit: one complete review can be performed with only the keyboard; an accepted edit survives reload and exports correctly.

### 3. Evaluate and fix — September 8

- Run the small evaluation below and record raw counts, not just percentages.
- Seek feedback from an AD professional and a blind/low-vision reviewer; one person may have both backgrounds. Contact requires user authorization.
- Test screen-reader navigation, focus, status announcements, media controls, and the text evidence view.
- Test Replit deployment using the same flow the judges will follow.

Exit: documented misses/false alarms, known limitations, and a working hosted review. If reviewers are unavailable, state that user validation has not occurred.

### 4. Submission package — September 9, before noon Eastern

- Recheck official rules and deployment requirements.
- Prepare a demo of at most three minutes showing real runtime analysis and an editor decision.
- Complete setup instructions, reproducible sample data, architecture, evaluation results, and attribution.
- Review repository for credentials and media rights before making it public.
- Confirm working Replit URL, public repository/license, and submission text; submit before the official deadline.

## Small evaluation design

Start with two distinct original short films: one development fixture and one held-out fixture. For each, create three AD variants: acceptable description, a deliberately premature identity disclosure, and legitimate early naming of a different non-concealed character. This gives six film/script combinations, not six independent films. It is a pilot, not a validated benchmark.

Freeze the prompt before the held-out fixture. Keep expected flags and author-assigned reveal timestamps outside model inputs. Provide natural filmmaker notes only. Use unfamiliar original footage to reduce memorized-plot leakage.

Compare a simple name/timing baseline where applicable, a strong single Gemini prompt, and the tool-using workflow. Record model/version, settings, inputs, latency, and token use. Added tools must earn their complexity through useful evidence or measured workflow benefit; they need not be a multi-agent system.

Record:

- Correctly surfaced seeded issues / total seeded issues.
- Incorrect flags / total flags, plus clean cases receiving any false alarm / total clean cases.
- Evidence timestamp correctness and cases requiring abstention.
- Reviewer agreement, useful suggestions, and reasons for dismissal.
- Review time only if measured against a comparable manual task.

A supported flag must cite the correct AD cue and relevant film interval. Reject out-of-range timestamps and nonexistent cue references in code. A model's confidence wording is not a calibrated probability.

## Acceptance checks

- SRT parsing preserves order/timing and rejects malformed input with an actionable message.
- Dismissing findings leaves export unchanged; accepting a revision changes only the selected cue text.
- Missing evidence and model/API failures do not appear as successful clean reviews.
- A legitimate early-naming control is included in the demo/evaluation.
- Keyboard users can upload/select a sample, start review, navigate findings, decide, and export.
- Supporting text distinguishes direct film/dialogue evidence, filmmaker notes, and model inference. Model-generated visual descriptions are not independent verification for a blind reviewer.
- Secrets stay server-side; unpublished films and scripts stay out of Git and logs.

## Decision register

- Chosen direction: editorial review, not a viewer companion.
- Chosen track: Replit, pending actual registration/submission.
- Initial check: premature identity disclosure only.
- Agent framework: Google ADK; reasoning: Gemini through Google Cloud.
- Repository: private during development; public required for submission.
- No paid plan, cloud deployment, public publication, or external outreach completed by this planning work.
