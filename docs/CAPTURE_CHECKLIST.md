# Submission Capture Checklist

Use 16:9 captures at 1920x1080 or higher. Keep the project name visible where it proves Google Cloud usage, but crop all account, billing, email, token, and credential information.

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

## Final review

- [ ] Every image is readable without browser zoom.
- [ ] All product images belong to the same golden run where possible.
- [ ] The displayed maintenance ID matches the evidence being claimed.
- [ ] No billing balance, email, credential, token, request header, or unrelated resource is visible.
- [ ] Images do not expose private chain-of-thought; concise decision summaries are acceptable.
- [ ] Captions explain the outcome instead of merely naming the screen.
- [ ] At least one image proves failure, one proves recovery, and one proves safe refusal.

Capturing existing screens is read-only. Starting or resetting another production run may invoke billable cloud services and requires explicit cost approval first.
