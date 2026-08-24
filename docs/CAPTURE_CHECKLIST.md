# Submission Capture Checklist

Use 16:9 captures, preferably at 1920x1080 and never below 1280x720. Keep the project name visible where it proves Google Cloud usage, but crop all account, billing, email, token, and credential information.

## Captured evidence

- [ ] P1 initial command center — requires a reset and must wait for explicit cost approval.
- [x] P2 WEB02 functional verification failure — `screenshots/02-verification-failure.png`.
- [x] P3 verified rollback and replan — `screenshots/03-verified-rollback.png`.
- [x] P4 blocked database Evidence Gate — `screenshots/04-database-gate-blocked.png`.
- [x] P5 final maintenance report — `screenshots/05-final-report.png`.
- [x] G1 healthy Cloud Run revision with 100% traffic — `screenshots/06-cloud-run.png`.
- [x] G2 persisted Firestore verification evidence — `screenshots/07-firestore-audit.png`.
- [x] G3 active Pub/Sub push subscription and endpoint — `screenshots/08-pubsub-delivery.png`.
- [x] G4 structured Cloud Run logs correlated by maintenance ID — `screenshots/10-structured-maintenance-logs.png`.
- [x] G5 Gemini 3.5 Flash requests through the Vertex AI backend — `screenshots/09-vertex-gemini-proof.png`.

## Required product captures

| ID | Screen | Required visible evidence | Suggested use |
|---|---|---|---|
| P1 | Initial command center | Healthy topology, approved request, both web nodes at `1.0.0`, system armed | Devpost hero image |
| P2 | WEB02 failure | WEB02 failed verification, 24% observed error rate, 5% threshold, activity timeline | Technical proof |
| P3 | Rollback result | WEB01 updated, WEB02 rolled back and healthy, both serving traffic | Autonomy proof |
| P4 | Database Evidence Gate | Gate marked `BLOCKED`, failed target-version redundancy, database unchanged | Safety proof |
| P5 | Final report | Updated, rolled back, deferred, availability preserved, zero interventions | Devpost outcome image |

## Required Google Cloud captures

| ID | Console screen | Required visible evidence | Privacy check |
|---|---|---|---|
| G1 | Cloud Run service | Service name, region `europe-west1`, healthy revision, public URL, 100% traffic | Hide account identity |
| G2 | Firestore Data | Golden maintenance ID and representative run/event/action/report documents | Expand only non-sensitive fields |
| G3 | Pub/Sub subscription | `maintenance-worker`, topic `maintenance-events`, push delivery endpoint | Ensure no unrelated resources appear |
| G4 | Logs Explorer | Golden maintenance ID plus planning, replanning, gate, or completion summary | Exclude access tokens and request headers |
| G5 | Vertex AI evidence | Gemini model/request evidence associated with the deployed flow | Do not claim a metric that is not visible |

## Optional captures

- Architecture diagram showing the separation between Gemini reasoning and deterministic authority.
- GitHub repository landing page with tests, architecture, and live-demo link.
- Mobile or narrow-screen dashboard only if the layout remains fully readable.

## Recommended Devpost order

1. P5 — final outcome communicates the product immediately.
2. P2 — controlled failure proves this is more than a deployment script.
3. P4 — deterministic refusal establishes safety.
4. G1 — public Google Cloud deployment.
5. G2 or G4 — durable auditability and real agent execution.
6. Architecture diagram — explains how the system works.

## File naming

Use predictable names before uploading:

- `01-command-center.png`
- `02-verification-failure.png`
- `03-verified-rollback.png`
- `04-database-gate-blocked.png`
- `05-final-report.png`
- `06-cloud-run.png`
- `07-firestore-audit.png`
- `08-pubsub-delivery.png`
- `09-vertex-gemini-proof.png`
- `10-structured-maintenance-logs.png`

## Final review

- [x] Every captured image is readable without browser zoom.
- [x] All product images belong to the verified golden run.
- [x] The displayed maintenance ID matches the correlated cloud evidence.
- [x] No billing balance, email, credential, token, request header, or unrelated resource is visible.
- [x] Images do not expose private chain-of-thought; concise decision summaries are acceptable.
- [x] Captions explain the outcome instead of merely naming the screen.
- [x] The set proves failure, recovery, and safe refusal.

Capturing existing screens is read-only. Starting or resetting another production run may invoke billable cloud services and requires explicit cost approval first.
