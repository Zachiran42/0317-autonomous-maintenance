# Implementation Plan

Last updated: 2026-08-24

## Pivot: afterAlerte → 03:17

The existing hackathon codebase was audited at commit `1adecd1` before migration. Git history and all reusable work were preserved.

### Preserved components

- Google ADK / Vertex AI runtime integration and configurable Gemini model.
- Cloud Run, Firestore, Pub/Sub, Docker, and PowerShell deployment foundation.
- Repository abstractions, structured events, simulator patterns, dashboard visual system, and test harness.

### Replaced components

- Alert/incident workflow → approved maintenance request and run.
- Incident states → validated maintenance state machine.
- Restart/corruption fixtures → rolling maintenance with verification failure and rollback.
- Prompt-only policy → deterministic Evidence Gates and action categories.
- Incident queue UX → live plan, topology, evidence, rollback, and final report.

### Required migration status

- [x] Add maintenance requests/runs, structured plans, action executions, reports, and state machine.
- [x] Upgrade simulator to Load Balancer, WEB01, WEB02, WORKER, and DATABASE.
- [x] Add deterministic Evidence Gates for safe changes, rollback, and database maintenance.
- [x] Implement WEB01 success, WEB02 verification failure, verified rollback, and DB deferral.
- [x] Add Gemini/ADK planning and replanning with deterministic execution authority.
- [x] Migrate API, Firestore collections, Pub/Sub names, observability, and idempotency keys.
- [x] Build live topology, maintenance plan, Evidence Gate, timeline, and report UX.
- [x] Expand to 20 passing backend tests and validate the frontend build.
- [x] Make invalid planner read targets recoverable and keep reset state separate from Firestore history.
- [x] Rewrite README and submission documents; add safety and migration notes.
- [x] Build and smoke-test the final renamed Docker image.
- [x] Verify real Vertex AI, Firestore, Pub/Sub, and Cloud Run execution.
- [x] Rename GitHub repository to `0317-autonomous-maintenance` and complete final release checks.
- [x] Capture Google Cloud proof and record a sub-four-minute silent demo cut.
- [x] Produce a synchronized English-captioned submission cut.
- [x] Add an MIT license and verify the official Devpost submission requirements.
- [x] Publish the final demonstration publicly on YouTube.
- [ ] Add multimodal request ingestion only if all core proof is stable.

## Remaining work ordered by judging impact

1. Add the public YouTube URL to the Devpost submission form.
2. Review the final cut and optionally add voice-over before upload.
3. Add credible public problem evidence or anonymized operator interviews.
4. Optional PDF/image change-request extraction.

## External blockers

- Further billable Google Cloud operations require explicit cost approval.
- Devpost media upload and final submission require the submitter's account.
