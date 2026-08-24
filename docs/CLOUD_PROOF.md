# Google Cloud Execution Proof

Verified on 2026-08-24 in project `autonomous-maintenance-0317`.

## Deployment

- Public service: <https://autonomous-maintenance-0317-iywxkz3msa-ew.a.run.app>
- Cloud Run region: `europe-west1`
- Verified revision: `autonomous-maintenance-0317-00002-962`
- Traffic: 100% to the verified revision
- Scaling: zero minimum instances, one maximum instance
- Firestore: Native mode, default database, `eur3`, free tier
- Pub/Sub topic: `maintenance-events`
- Push subscription: `maintenance-worker`
- Runtime configuration: Google ADK, Vertex AI, Gemini 3.5 Flash, Firestore, Pub/Sub

## Golden production run

Maintenance ID: `mw-89e2a37cba1e`

The public API and Firestore audit trail recorded the following terminal result:

- status: `completed_with_warnings`
- WEB01: `completed`, version `1.1.0`, healthy and serving traffic
- WEB02: `rolled_back`, version `1.0.0`, rollback verified healthy and serving traffic
- database: `deferred` because target-version redundancy was no longer satisfied
- final report: `completed`
- availability preserved: `true`
- human interventions: `0`
- structured maintenance events: `112`

The run crossed the real production path:

1. Public Cloud Run API accepted the approved request.
2. Pub/Sub delivered it to the push worker.
3. Firestore persisted the run, actions, gates, events, and report.
4. Gemini through Google ADK created the initial plan.
5. Gemini replanned after WEB02 verification failed.
6. Deterministic Evidence Gates authorized rollback and later rejected database maintenance.
7. The simulator restored WEB02 and verified the previous version.
8. Gemini replanned the rejected database step into a safe deferral.

## Verification responses

- `/api/health`: HTTP 200, `{"status":"ok","product":"03:17"}`
- `/api/config`: HTTP 200 with `adk`, `firestore`, `pubsub`, and `gemini-3.5-flash`
- `/`: HTTP 200 with the production dashboard
- `/api/topology`: HTTP 200 with WEB01 updated and WEB02 rolled back

No private credentials, private logs, or chain-of-thought are included in this proof.
