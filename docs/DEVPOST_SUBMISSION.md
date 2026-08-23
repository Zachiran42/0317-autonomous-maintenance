# Devpost Submission Draft

> Verification status: local implementation and automated tests are complete. Replace every `[VERIFY AFTER DEPLOYMENT]` marker only after capturing evidence from the real Google Cloud project.

## Inspiration

IT teams lose valuable time repeating the same incident workflow: receive an alert, gather evidence, consult runbooks, choose a safe action, verify recovery, and write a report. Routine failures often wait for a human even when the remediation is known. We wanted to demonstrate responsible autonomy: an agent that acts when the risk is bounded and deliberately stops when it is not.

## What it does

PROJECT_NAME_TBD is an event-driven autonomous IT incident response system. A service alert starts a background workflow. A Google ADK agent running Gemini 3.5 Flash inspects health, metrics, logs, dependencies, runbooks, and incident history through real tools. It chooses a remediation, passes it through a code-enforced action policy, performs permitted actions, verifies the outcome, and stores an auditable incident record.

The recoverable demonstration injects a deadlocked worker in a stateless web API. The agent independently investigates, restarts the service, verifies recovery, and records the result. The unsafe demonstration injects database checksum corruption. The agent preserves evidence, performs no database change, and creates a precise escalation.

## How we built it

- FastAPI and Python 3.12 provide the API, worker, simulator, policy, tools, and repository interfaces.
- Google Agent Development Kit exposes ten typed incident tools to Gemini.
- Gemini 3.5 Flash runs through Vertex AI in production mode.
- Pub/Sub delivers incident events asynchronously to the worker.
- Firestore persists incidents and observable agent events.
- Cloud Run hosts the API, dashboard, and worker endpoint with scale-to-zero cost controls.
- React, TypeScript, and Vite provide the live operations dashboard.
- A deterministic local agent and in-memory repository keep tests reproducible and token-free.

## Challenges we ran into

The central challenge was demonstrating real autonomy without surrendering safety to a prompt. We separated decision-making from authority: Gemini can select tools, but action tools enforce explicit policy in code. We also designed local fallbacks so judges can reproduce the workflow without enterprise systems or cloud credentials, while retaining a genuine Google Cloud production path.

Another challenge was showing agent work without exposing private reasoning. We created an event model containing only tool calls, observations, short decision summaries, policy outcomes, and verified results.

## Accomplishments that we're proud of

- A complete event-to-verification workflow rather than a conversational answer.
- Observable state changes in a reproducible simulated infrastructure.
- Fail-closed policy enforcement that blocks database and destructive operations.
- An evidence-rich escalation demonstrating that safe autonomy includes knowing when not to act.
- Automated coverage of both scenarios and the security boundary.
- A compact dashboard that makes the autonomous workflow understandable in under four minutes.

## What we learned

Reliable operational agents need more than a capable model. They need narrow tools, an external authority boundary, idempotency, verification, durable history, and a UI that communicates evidence rather than hidden reasoning. Local/cloud abstractions also made the system easier to test without weakening the production architecture.

## What's next

After the hackathon we would add authenticated Pub/Sub push, transactional worker leases, dead-letter queues, Cloud Monitoring/OpenTelemetry, operator RBAC, approval workflows, and narrowly scoped connectors for real monitoring platforms. We would expand the scenario library and evaluate remediation quality against a labeled incident corpus.

## Technologies used

Google ADK, Gemini 3.5 Flash, Vertex AI, Cloud Run, Firestore, Pub/Sub, Cloud Build, Python 3.12, FastAPI, Pydantic, pytest, React, TypeScript, Vite, Docker.

## Verification before submission

- [ ] `[VERIFY AFTER DEPLOYMENT]` Public Cloud Run URL works.
- [ ] `[VERIFY AFTER DEPLOYMENT]` Gemini tool calls appear in Vertex AI / application logs.
- [ ] `[VERIFY AFTER DEPLOYMENT]` Firestore incident and event documents are visible.
- [ ] `[VERIFY AFTER DEPLOYMENT]` Pub/Sub topic and push subscription deliver an event.
- [ ] Replace `PROJECT_NAME_TBD` with the final human-selected name.
- [ ] Add repository, demo video, and optional article/social links.

