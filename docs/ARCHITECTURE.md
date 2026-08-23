# Architecture

## Runtime topology

```text
Browser dashboard
       |
       v
Cloud Run / FastAPI -----> Firestore (incidents + agent_events)
       |
       +---- publish incident.created ----> Pub/Sub
                                               |
                                               v
                                    Cloud Run push worker
                                               |
                                               v
                                      Google ADK Agent
                                               |
                                               v
                              Gemini 3.5 Flash / Vertex AI
                                               |
                          +--------------------+--------------------+
                          |                    |                    |
                    observation tools     search tools       action tools
                          |                    |                    |
                          +-----------> code action policy <-------+
                                               |
                                               v
                                     simulated services
                                               |
                                               v
                                         verification
```

## Boundaries

- **API boundary:** accepts deterministic demo events and serves observable state. It does not decide remediations.
- **Event boundary:** Pub/Sub decouples alert intake from autonomous execution. Local development substitutes a FastAPI background task.
- **Agent boundary:** Google ADK presents real Python functions to Gemini. The model selects tools; prompt text alone is never the security boundary.
- **Policy boundary:** `ActionPolicy` is checked inside action tools. Unknown and destructive actions fail closed.
- **Infrastructure boundary:** `Simulator` exposes realistic health, metrics, logs, dependencies, and state changes without real enterprise access.
- **Persistence boundary:** Firestore stores incident summaries and append-only observable events. Tests use the same repository interface in memory.

## Data model

`incidents/{incident_id}` stores trigger, status, probable cause, evidence, tools, actions, verification, escalation, and final report.

`agent_events/{event_id}` stores incident ID, timestamp, event type, public summary, tool name, result/error status, and structured result data.

No private model reasoning or credentials are persisted.

## Safety invariants

1. Database restarts are rejected even though stateless service restarts are allowed.
2. Destructive, credential, firewall, database-write, and security-disable operations always escalate.
3. Unknown actions escalate by default.
4. Unsafe scenario state remains unchanged except for investigation records.
5. Resolution requires a post-action health verification.

## Failure handling

- A tool exception emits an error event, is logged with the incident ID, and propagates.
- An uncaught workflow error marks the incident `failed`.
- Pub/Sub delivery is idempotent because the worker only starts `queued` incidents.
- Cloud Run and Pub/Sub provide platform delivery retries; action idempotency prevents repeated completed remediations.
- Firestore state survives Cloud Run instance recycling.
- The local deterministic runtime makes CI reliable and free of model cost.

## Production hardening after the hackathon

- Require authenticated Pub/Sub push with a dedicated service account.
- Add a lease/transaction when claiming queued incidents for multi-instance race protection.
- Configure dead-letter topics and alerting for repeated failures.
- Add OpenTelemetry traces and Cloud Monitoring dashboards.
- Replace the simulator with narrowly scoped adapters to real monitoring/remediation systems.
- Add operator identity, RBAC, retention rules, and field-level redaction.

