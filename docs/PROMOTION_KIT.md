# 03:17 Promotion Kit

This material is ready for the optional public-content and social-post scoring opportunities. Publication must remain public through the end of judging.

## Technical article

### Gemini Proposes. Evidence Authorizes: Building a Safe Autonomous Maintenance Agent

I created this article for the purpose of entering **03:17 — Autonomous Maintenance Window** in the **All Things Agentic Hackathon**.

Infrastructure maintenance is often described as a sequence of commands: drain a node, install an update, verify health, and return it to service. That description hides the difficult part. Real maintenance windows diverge from the runbook. A health check fails, an error rate rises, or the remaining capacity is no longer sufficient for the next step. At 03:17, the operator is not awake because the commands are complicated; the operator is awake because somebody must judge whether it is safe to continue.

03:17 turns that judgment loop into an autonomous, asynchronous workflow. An approved request arrives through Pub/Sub. A FastAPI worker running on Cloud Run loads the current topology and operational context, then a Gemini 3.5 Flash agent built with Google ADK creates a structured rolling plan. The system executes each eligible step, observes the result, persists its audit trail in Firestore, and asks Gemini to replan when reality diverges from the plan.

The central design decision is a strict separation between reasoning and authority:

> Gemini proposes. Evidence authorizes.

Gemini interprets the request, chooses useful observations, creates the initial plan, and adapts it after failures. It never receives unrestricted permission to mutate infrastructure. Deterministic Python code validates every proposed target and action. Evidence Gates decide whether a meaningful change is allowed, and the state machine rejects invalid transitions.

This separation matters because a convincing explanation is not proof that an operation is safe. Before an update, the gate checks health, capacity, approval scope, and rollback requirements. Before a rollback, it verifies that the current run owns a valid recovery point. Before database maintenance, it confirms that the web tier still provides the required target-version redundancy. Every decision is observable and stored with the maintenance and action identifiers.

The demonstration deliberately follows a failure path rather than a perfect deployment. WEB01 updates and verifies successfully. WEB02 installs the new version, but its synthetic functional test reports a 24% error rate. The agent collects logs and metrics, Gemini replans, and the rollback gate proves that a valid recovery point belongs to this run. WEB02 returns to its previous version and recovery is verified.

That rollback changes what is safe next. The database step now fails its Evidence Gate because the web tier no longer has full target-version redundancy. Gemini receives the rejection as an observation and replans the remaining work into a safe deferral. The database stays untouched, availability is preserved, and the final report records the completed, rolled-back, and deferred outcomes with zero human intervention.

The deployed stack is intentionally small but real:

- Gemini 3.5 Flash through Vertex AI for planning and replanning.
- Google ADK for the agent and its scoped observation tools.
- Cloud Run for the API, worker, and React command center.
- Pub/Sub for asynchronous delivery of approved maintenance requests.
- Firestore for persistent runs, events, decisions, and action records.
- Deterministic Evidence Gates, state transitions, validation, and idempotency in Python.

The most important lesson was that safe agentic software is not created by asking a model to be careful. Safety becomes testable when model output is treated as a proposal flowing through explicit policy, evidence, ownership, and state-transition controls. The model handles ambiguity. The executor handles authority.

The second lesson was to make failure the center of the demo. A happy-path script can look autonomous even when it contains little adaptive reasoning. A visible failure, verified rollback, new constraint, rejected action, and revised plan demonstrate that the agent is responding to the world rather than replaying a transcript.

03:17 is a synthetic maintenance environment and cannot affect real infrastructure. That boundary makes the full workflow safe to inspect while preserving the architecture needed for production hardening: authenticated delivery, transactional claiming, dead-letter handling, and a persistent simulator adapter.

The project, live demonstration, architecture, and complete source are available here:

- Devpost: https://devpost.com/software/03-17-autonomous-maintenance
- GitHub: https://github.com/Zachiran42/0317-autonomous-maintenance
- Live application: https://autonomous-maintenance-0317-iywxkz3msa-ew.a.run.app
- Video: https://youtu.be/W3wTHvAmYUU

## Social post

I built **03:17 — Autonomous Maintenance Window** for the #AllThingsAgenticHackathon.

It uses Gemini 3.5 + Google ADK to plan and replan after failures, while deterministic Evidence Gates retain authority over every infrastructure change.

In the live demo, one node updates, another fails verification and rolls back, then the database change is safely refused—all without human intervention.

Gemini proposes. Evidence authorizes.

Devpost: https://devpost.com/software/03-17-autonomous-maintenance

GitHub: https://github.com/Zachiran42/0317-autonomous-maintenance

Demo: https://youtu.be/W3wTHvAmYUU

## Publication checklist

- Publish the technical article on a public platform such as dev.to, Medium, or a public blog.
- Keep the first-paragraph hackathon disclosure intact.
- Add the final public article URL to the Devpost optional-contribution field.
- Publish the social post on LinkedIn, X, Instagram, or Facebook.
- Keep the exact hashtag `#AllThingsAgenticHackathon`.
- Add the public social-post URL to Devpost.
