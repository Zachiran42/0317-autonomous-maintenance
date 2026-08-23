# Judging Checklist

## Innovation & Operational Utility — 40%

- [x] Solves a frequent, expensive incident-response workflow.
- [x] Runs from an event to an outcome without continuous human prompting.
- [x] Performs an observable remediation and verifies recovery.
- [x] Demonstrates disciplined non-action and escalation for unsafe conditions.
- [x] Preserves an operator-friendly audit trail without private chain-of-thought.
- [ ] Add two operator interviews or credible problem evidence before final submission.
- [ ] Replace placeholder branding with a memorable human-selected name.

## Architectural Discipline & Tech Stack — 30%

- [x] Gemini 3.5 Flash is the configured production model.
- [x] Google ADK is the primary agent framework and receives real callable tools.
- [x] Cloud Run hosts the production application.
- [x] Firestore provides durable incident/event persistence.
- [x] Pub/Sub provides asynchronous event delivery.
- [x] Action authority is enforced in code and defaults to escalation.
- [x] Local adapters enable deterministic, token-free tests.
- [x] Structured errors, correlation IDs, and idempotent completed workflows exist.
- [ ] Verify the ADK 2.7 runtime against real Vertex AI credentials.
- [ ] Add authenticated Pub/Sub push or clearly frame public push as a hackathon limitation.
- [ ] Add a transactional claim/lease if load testing uses multiple Cloud Run instances.

## Demo & Production Readiness — 30%

- [x] Operations dashboard visibly shows state changes and agent activity.
- [x] Recoverable and unsafe buttons make the demo deterministic.
- [x] Backend tests pass locally in Python 3.12 Docker.
- [x] Frontend production build passes.
- [ ] Complete and verify the full Docker image build.
- [ ] Deploy and capture the public Cloud Run URL.
- [ ] Capture visible Vertex AI, Firestore, and Pub/Sub proof.
- [ ] Record and trim a sub-four-minute demo video.
- [ ] Run the full demo twice against the deployed application.
- [ ] Add GitHub repository and demo video links to Devpost.

## Compliance and submission hygiene

- [x] English documentation and application UI.
- [x] No secrets or credentials in source.
- [x] AI development disclosure included.
- [x] Reused/pre-existing component statement included.
- [x] No unverified cloud claims presented as completed.
- [ ] Choose and add a license.
- [ ] Confirm official deadline/time zone and all current rules on submission day.
- [ ] Publish optional technical article and social post only after the core submission is verified.
- [ ] Consider an additional Google AI model only if it improves the workflow without demo risk.

