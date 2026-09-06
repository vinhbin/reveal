# Reveal

An editorial review assistant that helps audio-description editors investigate possible premature identity disclosures in short films.

**Status:** planning only. No application or performance results yet.

**Hackathon direction:** Agentic Cinema, Replit track. Build with Replit Agent, deploy the application on Replit, and use Gemini through Google Cloud for the review agent. Track selection is a project decision, not a completed submission.

## Product

An editor supplies a short film, a timecoded audio-description (AD) script, and optional brief filmmaker notes. Reveal finds possible conflicts between what the AD discloses and what the film has established at that moment. Each finding links the script line to relevant film evidence and offers a revision for human review.

Primary users are AD editors, accessibility producers, and filmmakers, including blind and low-vision professionals. Reveal's interface must support keyboard and screen-reader use.

## First release

- One short film per review, approximately 60–120 seconds.
- UTF-8 SRT audio-description scripts.
- One primary check: possible premature identity disclosure.
- Evidence with timestamps, uncertainty, and an editable suggested revision.
- Accept, dismiss, or mark a finding intentional; export a revised SRT.

Reveal does not certify accessibility or establish the correct interpretation of a film. Clue omissions, motive interpretation, full-length films, and viewer-facing live assistance are future research areas.

## Project documents

- [Build plan](docs/PLAN.md): scope, milestones, acceptance criteria, and evaluation.
- [Architecture](docs/ARCHITECTURE.md): proposed components and review flow.
- [Evidence](docs/EVIDENCE.md): supported claims and limits.
- [Replit Agent handoff](docs/REPLIT_HANDOFF.md): implementation instructions for the selected track.

## Development and submission

Implementation is intended to begin in Replit Agent using the handoff document. Record its actual contribution. No runtime credentials, videos, or private filmmaker scripts belong in Git.

The repository starts private. The hackathon requires a public, openly licensed repository for submission; publication is a later step after checking assets and credentials. The MIT license covers project code and documentation, not third-party films or research sources.

Deadline currently listed in the [official rules](https://agentic-cinema.devpost.com/rules): September 9, 2026, 2 p.m. PDT / 5 p.m. Eastern. Recheck requirements before submission.
