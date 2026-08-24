import pytest

from app.models import PlanStep, StepStatus
from app.plan_validation import PlanValidationError, PlanValidator, next_eligible_step

REQUEST = "Update the web tier and perform approved database maintenance"


def golden_plan() -> list[PlanStep]:
    return [
        PlanStep(
            id="web01-update",
            order=1,
            target="web01",
            action="rolling_update",
            objective="Update WEB01",
        ),
        PlanStep(
            id="web02-update",
            order=2,
            target="web02",
            action="rolling_update",
            objective="Update WEB02",
            depends_on=["web01-update"],
        ),
        PlanStep(
            id="database-maintenance",
            order=3,
            target="database",
            action="database_maintenance",
            objective="Maintain database",
            depends_on=["web01-update", "web02-update"],
        ),
        PlanStep(
            id="final-report",
            order=4,
            target="report",
            action="create_report",
            objective="Create report",
            depends_on=["web01-update", "web02-update", "database-maintenance"],
        ),
    ]


def test_golden_plan_is_valid():
    assert len(PlanValidator().validate(golden_plan(), REQUEST)) == 4


def test_valid_alternative_plan_is_accepted():
    plan = [
        PlanStep(
            id="web02-update",
            order=1,
            target="web02",
            action="rolling_update",
            objective="Update only WEB02",
        ),
        PlanStep(
            id="final-report",
            order=2,
            target="report",
            action="create_report",
            objective="Create report",
            depends_on=["web02-update"],
        ),
    ]
    validated = PlanValidator().validate(
        plan, "Update WEB02 only. Do not perform database maintenance."
    )
    assert [(step.target, step.action) for step in validated] == [
        ("web02", "rolling_update"),
        ("report", "create_report"),
    ]


@pytest.mark.parametrize(
    ("target", "action"),
    [("database", "delete_database"), ("unknown", "rolling_update")],
)
def test_unsupported_action_or_target_is_rejected(target: str, action: str):
    plan = golden_plan()
    plan[0].target = target
    plan[0].action = action
    with pytest.raises(PlanValidationError):
        PlanValidator().validate(plan, REQUEST)


def test_missing_dependency_is_rejected():
    plan = golden_plan()
    plan[1].depends_on = ["missing-step"]
    with pytest.raises(PlanValidationError, match="missing"):
        PlanValidator().validate(plan, REQUEST)


def test_cyclic_dependency_is_rejected():
    plan = golden_plan()
    plan[0].depends_on = ["web02-update"]
    with pytest.raises(PlanValidationError, match="cycle"):
        PlanValidator().validate(plan, REQUEST)


def test_scheduler_respects_dependencies():
    plan = golden_plan()
    assert next_eligible_step(plan).id == "web01-update"
    plan[0].status = StepStatus.COMPLETED
    assert next_eligible_step(plan).id == "web02-update"


def test_blocked_dependency_prevents_unsafe_child_but_not_terminal_report():
    plan = golden_plan()
    plan[0].status = StepStatus.COMPLETED
    plan[1].status = StepStatus.BLOCKED
    plan[2].status = StepStatus.DEFERRED
    assert next_eligible_step(plan).id == "final-report"
