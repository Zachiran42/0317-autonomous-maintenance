# Google Cloud Execution Proof

Verified on 2026-08-24 in project `autonomous-maintenance-0317`.

## Evidence boundary

This document proves the final hardened revision `autonomous-maintenance-0317-00006-m8m` and the two production runs recorded below. Earlier revision `00002-962` and run `mw-89e2a37cba1e` remain historical evidence for the submitted video only. Revisions `00004-b7m` and `00005-xqq` exposed model-capacity and invalid-plan failure paths before any mutation; both findings were corrected in `00006-m8m` and remain preserved in the Cloud Run revision history.

## Deployment

- Public service: <https://autonomous-maintenance-0317-iywxkz3msa-ew.a.run.app>
- Cloud Run region: `europe-west1`
- Verified revision: `autonomous-maintenance-0317-00006-m8m`
- Recorded proof traffic: 100% to revision `00006-m8m`
- Scaling: zero minimum instances, one maximum instance
- Firestore: Native mode, default database, `eur3`, free tier
- Pub/Sub topic: `maintenance-events`
- Push subscription: `maintenance-worker`
- Runtime configuration: Google ADK, Vertex AI, Gemini 3.5 Flash, Firestore, Pub/Sub

## Golden production run

Maintenance ID: `mw-2a513a7fa486`

The public API and Firestore audit trail recorded the following terminal result:

- status: `completed_with_warnings`
- WEB01: `completed`, version `1.1.0`, healthy and serving traffic
- WEB02: `rolled_back`, version `1.0.0`, rollback verified healthy and serving traffic
- database: `deferred` because target-version redundancy was no longer satisfied
- final report: `completed`
- availability preserved: `true`
- human interventions: `0`
- structured maintenance events: `152`
- structured plan revisions: `2`
- measured availability checks: `12`
- workflow error events: `0`

The run crossed the real production path:

1. Public Cloud Run API accepted the approved request.
2. Pub/Sub delivered it to the push worker.
3. Firestore persisted the run, actions, gates, events, and report.
4. Gemini through Google ADK attempted the initial plan and both replans.
5. The semantic validator rejected non-conforming model proposals without weakening policy.
6. The production resilience path recorded the rejection and selected the deterministic safe plan or delta.
7. Deterministic Evidence Gates authorized rollback and later rejected database maintenance.
8. The simulator restored WEB02 and verified the previous version.
9. The second structured delta deferred the rejected database step safely.

## Degraded pre-flight production run

Maintenance ID: `mw-a53cd26a3690`

- status: `completed_with_warnings`
- structured maintenance events: `54`
- mutation actions executed: `0`
- WEB01, WEB02, and database work: `deferred`
- final report: `completed`
- availability preserved: `true`
- human interventions: `0`

This scenario proves that unsafe initial service health causes refusal before mutation while the audit and reporting path still completes.

## Model resilience observation

During final verification, Vertex AI first returned `429 RESOURCE_EXHAUSTED`, then produced structurally invalid proposals on later attempts. Revision `00006-m8m` handles both conditions explicitly: Gemini/ADK is still invoked, but deterministic validation remains authoritative and a transparent safe fallback prevents model availability or format quality from becoming execution authority. The fallback reason is persisted in `decision_summaries`.

## Verification responses

- `/api/health`: HTTP 200, `{"status":"ok","product":"03:17"}`
- `/api/config`: HTTP 200 with `adk`, `firestore`, `pubsub`, and `gemini-3.5-flash`
- `/`: HTTP 200 with the production dashboard
- `/api/topology`: HTTP 200 with WEB01 updated and WEB02 rolled back

No private credentials, private logs, or chain-of-thought are included in this proof.
