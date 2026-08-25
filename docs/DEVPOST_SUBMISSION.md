# Devpost Submission Draft

Demo video: https://youtu.be/gvNR-WHC1G0

> Local validation and real cloud execution are documented separately. `CLOUD_PROOF.md` records the previous verified production revision. The final dependency-aware hardening is validated locally and in CI but must be redeployed before being described as new cloud proof.

## Inspiration

Infrastructure maintenance often happens after normal working hours. Traditional automation handles the happy path, but the moment a prerequisite is missing, a functional check fails, or rollback becomes necessary, an administrator has to take over.

Administrators stay awake not because every command is difficult. They stay awake because somebody must interpret unexpected evidence and decide whether it is safe to continue.

**03:17 is when no sysadmin wants to be awake.**

## What it does

03:17 is an autonomous after-hours IT change execution system. An administrator submits one approved maintenance request and leaves. The system discovers topology, consults runbooks, creates a structured plan, establishes pre-change evidence, performs permitted changes, verifies every step, replans when reality differs from the plan, rolls back failed changes, and produces a complete audit report.

Its defining architectural pattern is **Autonomous Change with Evidence Gates**. Gemini reasons and proposes. Deterministic code controls authority.

In the golden demonstration, WEB01 updates successfully. WEB02 starts but fails a synthetic functional test with a 24% error rate; 03:17 collects evidence, selects rollback, restores the previous version, and verifies recovery. The database step is then blocked because the web tier no longer has full target-version redundancy. Gemini receives that rejection, replans, and defers the database change. Availability remains preserved with zero human intervention.

## How we built it

- Google ADK presents request, topology, health, metric, log, runbook, history, and capacity tools to Gemini.
- Gemini 3.5 Flash through Vertex AI creates the structured plan and replans after failures/gate rejection.
- Gemini is free to emit different approved-scope plans with explicit dependencies; a semantic validator rejects malformed, cyclic, restricted, or unsafe plan structures.
- Structured replans alter persisted executable state: the WEB02 failure adds a validated rollback objective and the database rejection changes its step to deferred.
- A FastAPI executor advances a validated maintenance state machine.
- Python Evidence Gates enforce prerequisites, thresholds, rollback ownership, and restricted actions.
- A real stateful simulator models load balancing, five nodes, versions, health, metrics, logs, snapshots, and rollback points.
- Pub/Sub starts the workflow asynchronously from one approved request.
- Firestore persists maintenance runs, observable events, action executions, and final reports.
- Cloud Run hosts the API, worker, and React command center with scale-to-zero cost controls.
- A deterministic planner replaces Gemini in unit tests so CI consumes no tokens.

## Challenges we ran into

The main challenge was avoiding two weak extremes: a hard-coded deployment script with decorative AI, or an unconstrained model allowed to mutate infrastructure. We separated planning from execution authority. Gemini handles ambiguity and replanning; tools and Evidence Gates enforce what can actually happen.

The second challenge was making failure the strongest part of the demo. WEB02's deterministic fixture fails only after the service restarts, proving that readiness alone is insufficient. A synthetic transaction and error threshold expose the problem, and rollback changes real simulator state back to the captured version.

The third challenge was showing useful agent activity without exposing private reasoning. The timeline stores only objectives, tools, observations, concise decision summaries, gate outcomes, verification, and results.

## Accomplishments that we're proud of

- A complete event-to-report workflow instead of a chatbot response.
- Genuine state mutation, verification failure, rollback, and rollback verification.
- Database refusal based on specific machine evidence rather than a prompt disclaimer.
- Gemini-driven structured planning/replanning with deterministic action authority.
- Idempotent tools and duplicate event protection.
- A signature Evidence Gate UI that explains why the system did—or did not—act.
- Thirty-five deterministic tests covering alternative plans, dependency validation/scheduling, structured replanning, two scenarios, measured availability, the entire golden scenario, and safety boundaries.

## What we learned

Operational autonomy depends less on generating commands than on proving when each command is safe. Reliable agents need explicit state, narrow tools, external authority, observable evidence, idempotency, verification, reversibility, and honest refusal.

We also learned that a compelling demo should be designed around a deviation from the runbook. The happy path proves automation; the failed path proves agency.

## What's next

We would add authenticated Pub/Sub push, a transactional Firestore run lease, dead-letter handling, OpenTelemetry/Cloud Monitoring, operator RBAC, approval signatures, and narrowly scoped adapters for real change-management and monitoring systems.

Once the core cloud flow is fully verified, the next UX improvement is multimodal request ingestion: Gemini extracts targets, constraints, window, and rollback requirements from a PDF, screenshot, exported ticket image, or plain text.

## Technologies used

Gemini 3.5 Flash, Vertex AI, Google Agent Development Kit, Cloud Run, Firestore, Pub/Sub, Cloud Build, Python 3.12, FastAPI, Pydantic, pytest, Ruff, React, TypeScript, Vite, Docker.

## Verification before submission

- [x] Golden workflow passes deterministic local tests.
- [x] WEB01 state mutation, WEB02 failure/rollback, and DB refusal are covered.
- [x] Frontend production build passes.
- [x] Public Cloud Run URL responds.
- [x] Gemini structured planning and replanning completed through the deployed ADK runtime.
- [x] Firestore persisted run, event, action, and report records.
- [x] Pub/Sub push delivery completed through the deployed subscription.
- [x] Capture polished screenshots of the verified cloud evidence.
- [x] Produce a sub-four-minute English-captioned demo with visible Google Cloud proof.
- [ ] Add repository URL, demo video, and optional technical article/social links.
