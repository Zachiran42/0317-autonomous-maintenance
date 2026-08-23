# Four-Minute Demo Script

Target length: **3:55**. Rehearse with a clean demo state. Keep the Cloud Run dashboard open in one tab and Google Cloud Console tabs for Firestore, Pub/Sub, Cloud Run, and Logs Explorer preloaded.

## 0:00–0:25 — The problem

**Show:** Operations dashboard, all three services healthy.

“Incident response is a repetitive workflow, but most automation either stops at recommendations or acts without a clear safety boundary. PROJECT_NAME_TBD is an autonomous responder that investigates, takes permitted actions, verifies the result, and creates an audit record—without waiting for a chat prompt.”

## 0:25–0:45 — Architecture

**Show:** README Mermaid diagram or `docs/ARCHITECTURE.md`.

“An alert enters our Cloud Run API, Pub/Sub starts a background worker, and a Google ADK agent uses Gemini 3.5 Flash through Vertex AI. Its real tools inspect simulated infrastructure and write incidents and observable events to Firestore. A code policy—not a prompt—controls authority.”

## 0:45–2:30 — Recoverable incident

**Show:** Dashboard. Click **Trigger recoverable incident** once, then take your hands away.

“The web API is now unhealthy. From this point, the operator does nothing.”

Follow the activity timeline as it appears:

- Alert received; autonomous investigation starts.
- Health, logs, metrics, and dependency tools run.
- Point out the deadlock evidence and healthy database dependency.
- Runbook/history searches execute.
- Policy check permits a restart of the stateless web API.
- The service card visibly returns to healthy.
- Verification runs after the action.
- The final report is created and status becomes resolved.

“This is an observable action: the simulator state and restart count changed, the result was independently verified, and every step is correlated to one incident ID.”

## 2:30–3:15 — Unsafe incident

**Show:** Click **Trigger unsafe incident** once.

“Now the database reports a checksum mismatch suggesting corruption. The agent still investigates, but a destructive database action is outside its authority.”

Point out:

- Database health/metrics/log evidence.
- Corruption runbook match.
- Red policy event blocking automatic remediation.
- Escalated status and recommended next steps.
- Database restart count remains zero.

“Safe autonomy means acting decisively when bounded and preserving evidence when it is not.”

## 3:15–3:40 — Durable history

**Show:** Google Cloud Console → Firestore → Data → `incidents`, then `agent_events`.

Open the two incident documents. Show final statuses, evidence, actions, verification/escalation, timestamps, tool names, and common incident IDs. Do not show credentials or unrelated project data.

## 3:40–3:55 — Proof of Google Cloud

Quickly show these preloaded screens:

1. **Cloud Run → incident-response-agent → Details:** green deployment, service URL, region, scale-to-zero settings.
2. **Cloud Run → Logs:** a JSON `tool_call` entry containing the incident ID and a successful Vertex-backed workflow entry.
3. **Pub/Sub → Subscriptions → incident-worker:** delivery activity and push endpoint ending in `/api/events/pubsub`.
4. If available, **Vertex AI usage/monitoring:** requests for `gemini-3.5-flash`.

Never claim a screen proves Vertex usage if the model ID/request is not visible.

## 3:55–4:00 — Close

“PROJECT_NAME_TBD turns an alert into a safe, verified outcome—not another message for an operator to process.”

## Recording checklist

- [ ] Cloud Run URL is visible and responds before recording.
- [ ] Production footer says `adk / firestore`.
- [ ] Both demo paths were rehearsed after the latest deployment.
- [ ] Firestore and log tabs are filtered to the demo project.
- [ ] Browser zoom makes incident text legible at 1080p.
- [ ] Recording finishes below 4:00.
- [ ] No secrets, emails, billing details, or unrelated project names are visible.

