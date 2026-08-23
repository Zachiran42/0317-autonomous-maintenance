# Four-Minute Demo Script

Target: **3:55**, one unedited golden run. Preload the 03:17 Cloud Run URL plus Cloud Run, Firestore, Pub/Sub, and Logs Explorer tabs. Reset the synthetic environment before recording.

## 0:00–0:20 — Hook

**Show:** 03:17 command center, healthy topology, approved request.

“I'm a systems administrator. Maintenance windows happen when everyone else is asleep. Automation handles the easy path, but when reality deviates from the runbook, somebody still has to stay awake.”

“03:17 closes that gap.”

## 0:20–0:40 — Concept

**Show:** README architecture diagram, then Evidence Gate panel.

“Gemini reasons and replans through Google ADK. Deterministic Evidence Gates authorize every meaningful action. Every action is verified, and failed changes are reversible.”

## 0:40–2:45 — Live autonomous execution

**Show:** Click **Start autonomous maintenance** once. Do not interact again.

Narrate only observable state:

- “The approved change request enters through Pub/Sub.”
- “Gemini discovers topology and runbooks, then submits a structured rolling plan.”
- “Pre-flight proves health, capacity, approval, and backup evidence.”
- “WEB01 drains. WEB02 carries traffic.”
- “A rollback point is captured before the update.”
- “WEB01 updates, restarts, passes health and synthetic verification, then returns to the pool.”
- “The plan advances to WEB02.”
- “WEB02 drains, updates, and restarts—but its functional test fails.”
- “The error rate is 24%, above the 5% threshold. The agent gathers logs and metrics.”
- “Gemini replans. The rollback gate confirms this maintenance owns the change and has verified rollback state.”
- “WEB02 returns to version 1.0.0, healthy and back in the pool. Rollback verification passes.”

Point to the topology node states and timeline rather than clicking around.

## 2:45–3:15 — Database Evidence Gate

**Show:** Database Evidence Gate panel.

“The approved request also includes database maintenance. Backup and database health pass. WEB01 is on the target version. But WEB02 is healthy on the previous version, so target-version redundancy fails.”

“The gate blocks the action. Gemini receives the evidence, replans, and safely defers database maintenance. The database remains unchanged.”

## 3:15–3:35 — Audit report

**Show:** Final outcome panel, then Firestore Data.

“The final report records the original request, plan, dependency graph, evidence, actions, verification, rollback, blocked operation, final topology, short decision summaries, and follow-up.”

Open `maintenance_runs`, `maintenance_events`, and `action_executions`. Show the shared maintenance ID and action IDs. Do not show credentials or unrelated project data.

## 3:35–3:50 — Google Cloud proof

Show preloaded screens quickly:

1. **Cloud Run → autonomous-maintenance-0317:** green revision, service URL, min instances 0, max 2.
2. **Logs Explorer:** structured event with maintenance ID and a Gemini planning/replanning summary.
3. **Pub/Sub → maintenance-worker:** delivery activity and `/api/events/pubsub` endpoint.
4. **Vertex AI monitoring/logs:** visible `gemini-3.5-flash` request evidence.

Do not claim Vertex proof unless the model/request is visible.

## 3:50–4:00 — Finish

“03:17 doesn't automate the happy path. It handles what happens when the happy path breaks.”

“Sleep through the maintenance window.”

## Recording checklist

- [ ] Production footer shows `adk planner / firestore state`.
- [ ] All nodes start healthy and both web versions start at 1.0.0.
- [ ] Demo pacing shows every lifecycle state clearly.
- [ ] WEB02 rollback and database blocked gate are legible at 1080p.
- [ ] Firestore, Cloud Run, Pub/Sub, and Vertex proof tabs are prefiltered.
- [ ] No emails, billing data, credentials, or unrelated project information is visible.
- [ ] Recording ends before 4:00.

