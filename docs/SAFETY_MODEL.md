# Safety Model

## Principle

Gemini can propose and explain. Deterministic code grants or denies authority.

## Action categories

### READ

Automatically allowed: request, topology, health, metrics, logs, dependencies, runbooks, history, and capacity.

### SAFE CHANGE

Allowed only through the relevant Evidence Gate: snapshot, drain, rollback point, approved update, restart, verification, pool restore, report, and defer.

### ROLLBACK

Allowed only when:

- a verified rollback point exists;
- the current maintenance ID owns the changed target;
- the rollback operation is scoped to that target;
- the result is independently verified.

### RESTRICTED

Always rejected: database deletion, backup deletion, auditing disablement, credential changes, security-control removal, destructive schema changes, arbitrary shell execution, and every unknown action.

## Evidence invariants

- A node cannot be drained unless another healthy node carries minimum capacity.
- A web change cannot run while the node is still serving traffic.
- A web change cannot run without rollback state.
- An unhealthy node cannot return to the pool.
- A rollback cannot affect state created by another maintenance run.
- Database work requires two healthy target-version web nodes, not merely two healthy nodes.
- Unknown evidence gates fail closed.

## Observable refusal

The database gate in the golden scenario records each individual requirement. Backup, database health, WEB01, and global errors pass. WEB02 target version and full target-version redundancy fail. The database version remains unchanged and the plan step becomes `DEFERRED`.

## No hidden reasoning

Stored/displayed data is limited to objectives, tool invocations, results, short decision summaries, evidence, policy decisions, verification, rollback, and final recommendations. Private Gemini reasoning is never requested for display and never persisted.

## Synthetic scope

All hosts, logs, metrics, tickets, versions, and runbooks are generated. There is no employer name, real hostname, credential, private ticket, production data, or proprietary script.

