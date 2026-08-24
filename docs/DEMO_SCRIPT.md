# Four-Minute Demo Script

Target runtime: **3:42**, leaving an 18-second safety margin. Record at 1080p with the browser zoom set so the topology, Evidence Gate, timeline, and final report remain legible. Use the deployed Cloud Run service and preload every proof tab before recording.

## Before recording

1. Close email, billing, credential, and unrelated project tabs.
2. Preload the public dashboard, architecture diagram, Firestore, Pub/Sub, Cloud Run, Logs Explorer, and Vertex AI proof.
3. Filter cloud screens to project `autonomous-maintenance-0317` and the golden maintenance ID.
4. Reset the synthetic environment before the recorded take.
5. Confirm both web nodes show version `1.0.0`, every node is healthy, and the footer shows `adk planner / firestore state`.
6. Start recording only after all tabs have finished loading.

## 0:00-0:20 — The problem

**On screen:** Public 03:17 dashboard, hero and healthy topology.

**Say:**

“Maintenance windows happen while everyone else is asleep. Traditional automation follows the runbook, but when a functional check fails, an administrator still has to investigate, decide, and recover.”

“03:17 handles that deviation autonomously.”

## 0:20-0:42 — The safety model

**On screen:** Architecture diagram, then return to the Evidence Gate panel.

**Say:**

“Gemini 3.5 Flash reasons and replans through Google ADK. It never receives unrestricted execution authority. Deterministic Evidence Gates validate every meaningful action, while Pub/Sub triggers the workflow and Firestore preserves the audit trail.”

“Gemini proposes. Evidence authorizes.”

## 0:42-2:35 — One autonomous execution

**On screen:** Click **Start autonomous maintenance** exactly once. Do not interact again. Follow the topology, live plan, Evidence Gate, and activity timeline with the pointer.

**Say as each state appears:**

“This is one approved maintenance request. Pub/Sub delivers it to the Cloud Run worker.”

“The agent discovers topology, health, capacity, runbooks, and rollback requirements. Gemini returns a structured rolling plan.”

“Pre-flight evidence passes. WEB01 drains while WEB02 preserves service availability. A rollback point is captured before the change.”

“WEB01 updates to version 1.1.0, restarts, passes health and synthetic verification, and safely returns to the load balancer.”

“Now WEB02 drains and updates. Readiness succeeds, but its functional transaction fails: the observed error rate is 24 percent, above the allowed 5 percent.”

“The agent collects logs and metrics. Gemini replans, and the rollback gate proves that this run owns a valid recovery point.”

“WEB02 returns to version 1.0.0, becomes healthy, rejoins the load balancer, and passes rollback verification. No human intervened, and availability remained preserved.”

## 2:35-2:58 — Safe refusal

**On screen:** Keep the database Evidence Gate visible, especially the failed target-version requirements.

**Say:**

“The request also includes database maintenance. Backup and database health pass, but WEB02 is now healthy on its previous version. Target-version redundancy is therefore false.”

“The deterministic gate blocks the database action. Gemini receives that evidence, replans, and safely defers the change. The database remains untouched.”

## 2:58-3:18 — Outcome and auditability

**On screen:** Final maintenance report and autonomous activity timeline.

**Say:**

“The final result is completed with warnings: WEB01 updated, WEB02 rolled back and verified, and the database deferred by policy. The report records the plan, actions, evidence, verification, rollback, final topology, and follow-up—with zero manual intervention.”

## 3:18-3:34 — Real Google Cloud proof

**On screen:** Show each preloaded proof for roughly four seconds: Cloud Run, Firestore, Pub/Sub, then Vertex AI or filtered application logs.

**Say:**

“This is the real deployed path: Cloud Run hosts the service, Firestore persists the run and its 112 structured events, Pub/Sub delivers the approved request, and Vertex AI serves Gemini planning and replanning through Google ADK.”

## 3:34-3:42 — Closing line

**On screen:** Return to the final report.

**Say:**

“03:17 does not just automate the happy path. It handles what happens when the happy path breaks.”

## Recording acceptance checklist

- [ ] Final duration is 3:50 or less.
- [ ] Only one click occurs after the demo begins.
- [ ] Both starting web versions are `1.0.0`.
- [ ] WEB01 `UPDATED + VERIFIED` is visible.
- [ ] WEB02 `ROLLED BACK + VERIFIED` is visible.
- [ ] Database `DEFERRED BY EVIDENCE POLICY` is visible.
- [ ] Service availability `PRESERVED` and human interventions `0` are visible.
- [ ] Footer shows `adk planner / firestore state`.
- [ ] Cloud proof is readable and belongs to `autonomous-maintenance-0317`.
- [ ] No email address, billing data, credential, unrelated project, or private log is visible.
- [ ] Narration describes observable decisions without claiming private chain-of-thought.

## If the live run is too slow

Do not click twice or edit the result. Pause narration briefly while the timeline advances. If the run cannot finish before 3:05, stop the take, reset after obtaining any required cost approval, and record again. Never splice together outcomes from different maintenance IDs while presenting them as one run.
