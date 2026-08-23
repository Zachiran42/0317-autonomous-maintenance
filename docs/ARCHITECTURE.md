# 03:17 Architecture

## System topology

```mermaid
flowchart TD
    UI[React dashboard<br/>topology + plan + evidence + report] --> API[FastAPI API<br/>Cloud Run]
    API -->|maintenance.created| PUB[Pub/Sub topic]
    PUB -->|push delivery| WORKER[Maintenance worker]
    WORKER --> EXEC[Safe maintenance executor]
    EXEC --> ADK[Google ADK planner / replanner]
    ADK --> GEMINI[Gemini 3.5 Flash<br/>Vertex AI]
    GEMINI -->|structured plan| EXEC
    EXEC --> GATE[Evidence Gate engine]
    GATE -->|PASS| TOOLS[Scoped tools]
    GATE -->|FAIL observation| ADK
    TOOLS --> SIM[Stateful infrastructure simulator]
    TOOLS --> VERIFY[Health + synthetic checks]
    VERIFY -->|failure| ROLLBACK[Rollback eligibility gate]
    ROLLBACK --> SIM
    EXEC --> FIRESTORE[(Firestore)]
    FIRESTORE --> RUNS[maintenance_runs]
    FIRESTORE --> EVENTS[maintenance_events]
    FIRESTORE --> ACTIONS[action_executions]
    FIRESTORE --> REPORTS[embedded final reports]
```

## Responsibility split

| Component | Responsible for | Never responsible for |
|---|---|---|
| Gemini / ADK | Interpreting requests, selecting observations, structured planning, replanning, concise explanations | Direct authority over dangerous changes |
| Safe executor | Selecting the next eligible persisted step, bounded loop, workflow status | Inventing evidence |
| Evidence Gate | Thresholds, authorization, rollback eligibility, fail-closed decisions | Natural-language reasoning |
| Tools | Validated state reads/mutations, idempotency, structured results, errors | Arbitrary shell or unrestricted infrastructure access |
| Simulator | Real synthetic node state and fault injection | Fake UI outcomes |
| Repository | Durable run, event, action, and report state | Hidden model reasoning |

## Stateful execution

```text
RECEIVED → PLANNING → PREFLIGHT → READY → EXECUTING
                                             |
                                             v
                                         VERIFYING
                                         /       \
                                      PASS       FAIL
                                       |           |
                                  EXECUTING   ROLLING_BACK
                                                   |
                                                   v
                                              REPLANNING
                                                   |
                                                   v
                                     COMPLETED_WITH_WARNINGS
```

Every transition is validated against an explicit transition map. Invalid transitions raise `TransitionError` and are covered by tests.

## Dynamic planning

The deployed planner is a Google ADK agent using Gemini. It may call request, topology, health, metric, log, runbook, history, and capacity tools. It must submit a structured plan through `submit_maintenance_plan`. Target/action combinations are validated before execution.

After failed verification, the executor sends the observed synthetic result, logs, and metrics back to the planner. The resulting concise replan is persisted. After the database gate rejection, the failed evidence is again returned to the planner and the database step is deferred.

Tests substitute `LocalPlanner` for Gemini. It implements the same planner interface but is explicitly identified as a deterministic test runtime.

## Evidence Gates

The engine evaluates four visible gates:

1. **Maintenance window:** approved request, all initial health, minimum capacity, recent verified backup.
2. **Drain node:** enough remaining healthy web capacity.
3. **Apply web change:** target drained and verified rollback point present.
4. **Rollback:** rollback point exists and the current maintenance owns the changed state.
5. **Database change:** backup, DB health, both target versions healthy, full redundancy, global error threshold.

The golden run intentionally fails the last gate because WEB02 was restored to its previous version.

## Idempotency and resumption

- API event IDs deduplicate repeated request ingestion.
- Mutating tools use `{maintenance_id}:{action}:{target}` keys.
- Successful repeated mutations return their stored result and emit an `idempotent_replay` event.
- Only `RECEIVED` runs are claimed by the process, preventing completed Pub/Sub redeliveries from repeating work.
- Firestore stores runs, events, and action executions independently of Cloud Run instance lifetime.

Before multi-instance production use, run claiming should be upgraded to a Firestore transaction/lease. This limitation is intentionally documented rather than hidden.

## Failure handling

- Malformed or unsupported Gemini plan steps fail validation.
- Initial planning uses two bounded attempts.
- Tool exceptions emit error events and propagate.
- Failed functional verification cannot be converted into success; it triggers rollback evaluation.
- Failed rollback verification marks the run failed.
- Restricted or unknown actions fail closed.
- Pub/Sub/Cloud Run provide transport retries; tool idempotency prevents repeated mutations.

## Observability and privacy

Events include `maintenance_id`, `action_id`, event type, target, status, timestamp, tool, and structured evidence. They expose actions and observations, never private chain-of-thought.

See [SAFETY_MODEL.md](SAFETY_MODEL.md) and [architecture.svg](architecture.svg).

