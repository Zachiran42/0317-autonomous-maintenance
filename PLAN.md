# Implementation Plan

Last updated: 2026-08-23

# Pivot: afterAlerte → 03:17

## Product direction

**03:17 — Autonomous Maintenance Window** executes approved after-hours infrastructure changes, verifies every action, rolls back failed changes, and refuses to continue when deterministic evidence no longer makes the next action safe.

Tagline: **“Sleep through the maintenance window.”**

## Existing components

- FastAPI backend with Google ADK 2.x / Vertex AI runtime path.
- Gemini model configuration through environment variables.
- In-memory and Firestore repository implementations.
- Local background tasks and Pub/Sub push worker path.
- Stateful service simulator with health, metrics, logs, and actions.
- Code-enforced action policy and correlated structured events.
- React/TypeScript/Vite dashboard, Docker image, Cloud Run scripts, and 8 passing tests.

## Reusable components

- ADK runner/session integration and callable Python tool pattern.
- Repository abstraction, Firestore serialization, and Pub/Sub publisher.
- Simulator locking/copy semantics and observable state mutation.
- Structured logging, event timeline, runtime composition, API health endpoint.
- Dashboard visual system, polling, responsive layout, Docker and deployment configuration.

## Obsolete components

- Incident, alert, incident queue, probable-cause, and incident-remediation domain model.
- Recoverable deadlock and unsafe corruption demo fixtures.
- Stateless restart-only action policy.
- AfterAlert positioning and incident-response submission narrative.

## Required migrations

- [ ] Add maintenance requests/runs, structured plans, action executions, reports, and a validated state machine.
- [ ] Upgrade simulator to load balancer, WEB01, WEB02, WORKER, and DATABASE topology.
- [ ] Add deterministic Evidence Gates for safe changes, rollback, and database maintenance.
- [ ] Implement WEB01 success, WEB02 verification failure, verified rollback, and DB deferral.
- [ ] Give Gemini/ADK genuine planning and replanning tools while code retains execution authority.
- [ ] Migrate API, Firestore collections, Pub/Sub event names, observability, and idempotency keys.
- [ ] Replace dashboard with live topology, maintenance plan, evidence panel, timeline, and final report.
- [ ] Expand test coverage to the complete golden scenario and all safety/state boundaries.
- [ ] Rewrite README and submission documents; add safety and migration notes.
- [ ] Rename GitHub repository to `0317-autonomous-maintenance` and verify `main` synchronization.

## Work ordered by judging impact

1. Golden autonomous flow with real state mutation and rollback.
2. Evidence Gate clarity and deterministic refusal of the database step.
3. Gemini planning/replanning through Google ADK.
4. Live topology, plan adaptation, evidence, and final outcome storytelling.
5. Idempotency, state transitions, persistence, failure recovery, and observability.
6. Cloud deployment proof and submission documentation.
7. Multimodal change-request ingestion only after the core is verified.

## Current hackathon blockers

- Real Google Cloud deployment and proof still require explicit approval because the selected project is billed.
- Real Vertex AI/Firestore/Pub/Sub integration must be verified after deployment.
- Multimodal input is intentionally deferred until the golden flow is stable.

## Phase 1 — Functional core

- [x] Inspect workspace, Git/GitHub, runtimes, Docker, and Google Cloud CLI.
- [x] Scaffold FastAPI backend, service simulator, incident models, persistence, policy, and tools.
- [x] Implement deterministic local agent plus genuine Google ADK / Vertex AI runtime path.
- [x] Cover recoverable and unsafe incidents with automated tests (8 passing).

## Phase 2 — Google requirements

- [x] Add Firestore production persistence with local in-memory fallback.
- [x] Add Pub/Sub event transport with local background-task fallback.
- [x] Add Cloud Run container and PowerShell/Bash deployment scripts.

## Phase 3 — Demo UI

- [x] Build compact React/TypeScript operations dashboard.
- [x] Add system overview, incident queue, activity timeline, incident details, and demo controls.

## Phase 4 — Hardening

- [x] Add idempotency, code-enforced policy, structured errors, and correlated JSON logging.
- [x] Run backend tests, frontend build, Docker build, and container smoke test; fix all failures.

## Phase 5 — Submission

- [x] Write README and architecture documentation.
- [x] Draft Devpost submission, four-minute demo script, and judging checklist.
- [x] Add bonus publication checklists without claiming unverified work.

## Phase 6 — GitHub

- [x] Initialize `main`, create meaningful commits, and audit secrets.
- [x] Create and push the public GitHub repository: `Zachiran42/after-alert`.

## Environment findings

- Node.js 24 and npm 11 are installed.
- Docker CLI/Compose and the Docker daemon are available; the production image builds successfully.
- Google Cloud CLI 581 is authenticated with project `continuity-ai-hackathon` selected.
- Native Python is not available on PATH, so validation will use Docker unless a bundled runtime is found.
- GitHub CLI is not installed.
- Google ADK 2.7.x is current; Gemini model ID is `gemini-3.5-flash`.

## External blockers

- Real Vertex AI, Firestore, Pub/Sub, and Cloud Run proof require a selected billed Google Cloud project and authenticated Application Default Credentials.
- GitHub repository creation/push requires GitHub authentication or an existing remote.
