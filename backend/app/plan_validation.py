from __future__ import annotations

from collections import defaultdict

from app.models import PlanStep, ReplanResult, StepStatus


class PlanValidationError(ValueError):
    """Raised when a planner proposal is outside the approved semantic envelope."""


SUPPORTED_COMBINATIONS: set[tuple[str, str]] = {
    ("web01", "rolling_update"),
    ("web02", "rolling_update"),
    ("web01", "rollback"),
    ("web02", "rollback"),
    ("web01", "defer"),
    ("web02", "defer"),
    ("database", "database_maintenance"),
    ("database", "defer"),
    ("report", "create_report"),
}
TERMINAL_STATUSES = {
    StepStatus.COMPLETED,
    StepStatus.FAILED,
    StepStatus.ROLLED_BACK,
    StepStatus.DEFERRED,
    StepStatus.BLOCKED,
}
SATISFIED_DEPENDENCY_STATUSES = {StepStatus.COMPLETED, StepStatus.ROLLED_BACK}


def approved_targets(request: str) -> set[str]:
    """Derive the maximum approved target scope from the submitted request."""
    text = request.lower()
    targets = {"report"}
    if "web02 only" in text:
        targets.add("web02")
    elif "web01 only" in text:
        targets.add("web01")
    elif "web" in text:
        targets.update({"web01", "web02"})
    elif "web01" in text:
        targets.add("web01")
    elif "web02" in text:
        targets.add("web02")
    if "database" in text and "do not perform database" not in text:
        targets.add("database")
    return targets


class PlanValidator:
    """Validates plan admissibility; runtime Evidence Gates separately authorize actions."""

    def validate(
        self,
        steps: list[PlanStep],
        request: str,
        *,
        existing_plan: list[PlanStep] | None = None,
    ) -> list[PlanStep]:
        if not steps:
            raise PlanValidationError("Plan must contain at least one step")

        normalized = [step.model_copy(deep=True) for step in steps]
        ids = [step.id for step in normalized]
        if len(ids) != len(set(ids)):
            raise PlanValidationError("Plan step IDs must be unique")
        orders = [step.order for step in normalized]
        if len(orders) != len(set(orders)) or any(order < 1 for order in orders):
            raise PlanValidationError("Plan step order values must be unique positive integers")

        allowed_scope = approved_targets(request)
        existing = {step.id: step for step in existing_plan or []}
        targets_to_ids: dict[str, list[str]] = defaultdict(list)
        for step in normalized:
            targets_to_ids[step.target].append(step.id)
            if (step.target, step.action) not in SUPPORTED_COMBINATIONS:
                raise PlanValidationError(
                    f"Unsupported or restricted plan step: {step.target}/{step.action}"
                )
            if step.target not in allowed_scope:
                raise PlanValidationError(f"Target outside approved change scope: {step.target}")
            if not step.objective.strip():
                raise PlanValidationError(f"Step {step.id} requires an objective")
            if step.action == "rollback" and not any(
                prior.target == step.target
                and prior.action == "rolling_update"
                and prior.status
                in {StepStatus.IN_PROGRESS, StepStatus.FAILED, StepStatus.ROLLED_BACK}
                for prior in existing.values()
            ):
                raise PlanValidationError(
                    f"Rollback proposal for {step.target} has no failed owned change context"
                )

        id_set = set(ids)
        for step in normalized:
            resolved: list[str] = []
            for dependency in step.depends_on:
                if dependency in id_set:
                    resolved.append(dependency)
                elif len(targets_to_ids.get(dependency, [])) == 1:
                    resolved.append(targets_to_ids[dependency][0])
                else:
                    raise PlanValidationError(
                        f"Step {step.id} depends on missing or ambiguous step {dependency}"
                    )
            if step.id in resolved:
                raise PlanValidationError(f"Step {step.id} cannot depend on itself")
            step.depends_on = list(dict.fromkeys(resolved))

        self._reject_cycles(normalized)
        reports = [step for step in normalized if step.action == "create_report"]
        if len(reports) != 1:
            raise PlanValidationError("A valid plan requires exactly one terminal report step")
        report = reports[0]
        actionable_ids = {step.id for step in normalized if step.id != report.id}
        if set(report.depends_on) != actionable_ids or report.order != max(orders):
            raise PlanValidationError(
                "The report must be last and depend on every actionable plan step"
            )

        rolling = [step for step in normalized if step.action == "rolling_update"]
        if len(rolling) > 1 and not self._rolling_updates_are_serialized(rolling):
            raise PlanValidationError("Rolling updates must be dependency-serialized")
        rolling_ids = {step.id for step in rolling}
        for database in (step for step in normalized if step.action == "database_maintenance"):
            if not rolling_ids.issubset(set(database.depends_on)):
                raise PlanValidationError(
                    "Database maintenance must depend on all planned web-tier updates"
                )
        return sorted(normalized, key=lambda step: step.order)

    @staticmethod
    def _reject_cycles(steps: list[PlanStep]) -> None:
        dependencies = {step.id: set(step.depends_on) for step in steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise PlanValidationError("Plan dependency graph contains a cycle")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in dependencies:
            visit(step_id)

    @staticmethod
    def _rolling_updates_are_serialized(steps: list[PlanStep]) -> bool:
        ids = {step.id for step in steps}
        edges = sum(1 for step in steps for dependency in step.depends_on if dependency in ids)
        return edges >= len(steps) - 1


def next_eligible_step(plan: list[PlanStep]) -> PlanStep | None:
    """Select pending work whose dependency outcomes permit this specific action."""
    by_id = {step.id: step for step in plan}
    for step in sorted(plan, key=lambda item: item.order):
        if step.status != StepStatus.PENDING:
            continue
        dependencies = [by_id[dependency].status for dependency in step.depends_on]
        if step.action in {"create_report", "defer", "rollback"}:
            if all(status in TERMINAL_STATUSES for status in dependencies):
                return step
        elif all(status in SATISFIED_DEPENDENCY_STATUSES for status in dependencies):
            return step
    return None


def apply_replan(
    plan: list[PlanStep],
    result: ReplanResult,
    request: str,
    validator: PlanValidator,
) -> list[PlanStep]:
    """Apply a planner delta while preserving authoritative completed outcomes."""
    current = {step.id: step.model_copy(deep=True) for step in plan}
    immutable = {StepStatus.COMPLETED, StepStatus.ROLLED_BACK}

    for step_id in result.removed_step_ids:
        existing = current.get(step_id)
        if existing and existing.status in immutable | {StepStatus.IN_PROGRESS}:
            raise PlanValidationError(f"Cannot remove authoritative step outcome {step_id}")
        current.pop(step_id, None)

    for proposed in result.updated_steps:
        existing = current.get(proposed.id)
        update = proposed.model_copy(deep=True)
        if existing and existing.status in immutable:
            if (
                existing.target != update.target
                or existing.action != update.action
                or existing.status != update.status
            ):
                raise PlanValidationError(
                    f"Cannot rewrite authoritative step outcome {proposed.id}"
                )
            update.status = existing.status
            update.decision_summary = existing.decision_summary
        elif existing:
            update.status = existing.status
            update.decision_summary = existing.decision_summary
        else:
            update.status = StepStatus.PENDING
        current[update.id] = update

    for step_id in result.deferred_step_ids:
        if step_id not in current:
            raise PlanValidationError(f"Cannot defer unknown step {step_id}")
        step = current[step_id]
        if step.status in immutable:
            raise PlanValidationError(f"Cannot defer authoritative step outcome {step_id}")
        step.status = StepStatus.DEFERRED
        step.decision_summary = result.summary

    return validator.validate(list(current.values()), request, existing_plan=plan)
