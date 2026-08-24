# Judging Checklist

## Innovation & Operational Utility — 40%

- [x] Eliminates a painful multi-step after-hours maintenance task.
- [x] Runs autonomously after one approved request.
- [x] Handles deviation from the happy path, not only a successful script.
- [x] Performs observable update, verification, rollback, rollback verification, and refusal.
- [x] Preserves availability and records zero human intervention.
- [x] Differentiates clearly from alert triage, monitoring, copilot, and chatbot products.
- [ ] Add credible public data or two anonymized operator interviews supporting the problem statement.

## Architectural Discipline & Tech Stack — 30%

- [x] Google ADK is the primary planning/replanning framework.
- [x] Gemini 3.5 Flash is the configured production model through Vertex AI.
- [x] Evidence Gates enforce authority in code.
- [x] Maintenance state machine rejects invalid transitions.
- [x] Mutating tools have action IDs and idempotency keys.
- [x] Duplicate request/Pub/Sub processing cannot repeat a completed run.
- [x] Rollback requires ownership and captured state.
- [x] Firestore, Pub/Sub, and Cloud Run production adapters exist.
- [x] Structured logs/events correlate maintenance and action IDs.
- [x] Bounded plan validation retries exist.
- [x] Verify real ADK planning/replanning through Vertex AI.
- [ ] Add Firestore transactional run claiming before multi-instance load tests.
- [ ] Configure authenticated Pub/Sub push and a dead-letter topic for production hardening.

## Demo & Production Readiness — 30%

- [x] Dashboard instantly communicates autonomy, evidence, and reversibility.
- [x] Stateful topology changes live.
- [x] Plan visibly shows completed, rolled-back, and deferred steps.
- [x] Evidence panel shows individual machine facts and the blocking decision.
- [x] Final report gives a concise submission-ready outcome.
- [x] Twenty backend tests and frontend production build pass.
- [x] Final renamed Docker image and smoke test pass.
- [x] Cloud Run deployment works on the public URL.
- [x] Firestore, Pub/Sub, Vertex, and Cloud Run execution evidence is recorded.
- [ ] Complete two rehearsals and record a sub-four-minute video.

## Compliance and hygiene

- [x] English app and submission material.
- [x] No private chain-of-thought exposure.
- [x] No employer names, real hosts, private logs, credentials, or proprietary data.
- [x] AI development disclosure and reuse disclosure included.
- [x] Cloud-dependent claims are backed by a recorded production run.
- [ ] Add a license.
- [ ] Verify official deadline/rules on submission day.
- [ ] Add multimodal ingestion only after every core proof item passes.
