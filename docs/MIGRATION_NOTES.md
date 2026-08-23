# Migration Notes

This file records development history and is not part of the product pitch.

The hackathon repository originally contained **AfterAlert**, a small autonomous incident-response demonstration. Before the pivot, the repository was clean and synchronized at commit `1adecd1`. History was preserved.

## Reused

- Google ADK/Vertex AI setup.
- Firestore and Pub/Sub abstractions.
- FastAPI runtime composition and Cloud Run container.
- Stateful simulator patterns and structured tool events.
- React dashboard visual system and polling.
- Docker, deployment scripts, test infrastructure, and English submission templates.

## Replaced

- Incident/alert models and API routes.
- Deadlock restart and corruption escalation fixtures.
- Restart-focused action policy.
- Incident queue and response-detail interface.
- Incident-response README, architecture, Devpost, and demo story.

## New domain

The repository now implements **03:17 — Autonomous Maintenance Window**: approved change requests, explicit plans, validated state transitions, Evidence Gates, rolling web maintenance, verification-driven rollback, database deferral, maintenance reporting, and Gemini replanning.

No Git history was deleted or squashed during the migration.

