import pytest

from app.models import (
    GateOutcome,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceStatus,
    StepStatus,
    TransitionError,
)
from app.tools import MaintenanceTools


def new_run(runtime) -> MaintenanceRun:
    return runtime.repository.save_run(MaintenanceRun(request="Approved rolling web and database maintenance"))


async def completed_run(runtime) -> MaintenanceRun:
    run = new_run(runtime)
    await runtime.agent.run(run.id)
    result = runtime.repository.get_run(run.id)
    assert result is not None
    return result


@pytest.mark.asyncio
async def test_request_ingestion_is_persisted(runtime):
    run = new_run(runtime)
    await runtime.agent.run(run.id)
    events = runtime.repository.list_events(run.id)
    assert any(event.event_type == "ingestion" for event in events)


def test_dependency_discovery(runtime):
    topology = runtime.simulator.topology()
    nodes = {node["id"]: node for node in topology["nodes"]}
    assert nodes["web01"]["dependencies"] == ["worker", "database"]
    assert {"source": "worker", "target": "database"} in topology["edges"]
    assert all(isinstance(edge, dict) for edge in topology["edges"])


@pytest.mark.asyncio
async def test_structured_plan_creation(runtime):
    result = await completed_run(runtime)
    assert [step.target for step in result.plan] == ["web01", "web02", "database", "report"]
    assert result.plan[0].action == "rolling_update"


def test_allowed_evidence_gate(runtime):
    run = new_run(runtime)
    decision = runtime.gate.evaluate("drain_node", "web01", run.id)
    assert decision.outcome == GateOutcome.PASS


@pytest.mark.asyncio
async def test_denied_database_evidence_gate(runtime):
    result = await completed_run(runtime)
    decision = next(gate for gate in result.gate_decisions if gate.gate == "database_change")
    assert decision.outcome == GateOutcome.FAIL
    assert {item.key for item in decision.evidence if not item.passed} >= {
        "web02_target", "full_redundancy"
    }


@pytest.mark.asyncio
async def test_web01_successful_maintenance(runtime):
    result = await completed_run(runtime)
    web01 = runtime.simulator.get("web01")
    step = next(item for item in result.plan if item.target == "web01")
    assert web01.version == web01.desired_version
    assert web01.in_load_balancer is True
    assert step.status == StepStatus.COMPLETED


@pytest.mark.asyncio
async def test_web02_verification_failure_is_observed(runtime):
    result = await completed_run(runtime)
    events = runtime.repository.list_events(result.id)
    failed = [event for event in events if event.event_type == "verification" and event.target == "web02"]
    assert failed and failed[0].status == "failed"
    assert failed[0].evidence["synthetic"]["error_rate"] == 24.0


@pytest.mark.asyncio
async def test_web02_is_rolled_back(runtime):
    result = await completed_run(runtime)
    web02 = runtime.simulator.get("web02")
    step = next(item for item in result.plan if item.target == "web02")
    assert web02.version == "1.0.0"
    assert step.status == StepStatus.ROLLED_BACK
    assert result.rollback_information[0]["target"] == "web02"


@pytest.mark.asyncio
async def test_rollback_verification(runtime):
    result = await completed_run(runtime)
    verification = result.rollback_information[0]["verification"]
    assert verification["passed"] is True
    assert verification["in_load_balancer"] is True


@pytest.mark.asyncio
async def test_database_action_rejected_after_degraded_evidence(runtime):
    result = await completed_run(runtime)
    database = runtime.simulator.get("database")
    step = next(item for item in result.plan if item.target == "database")
    assert database.version == "15.4"
    assert step.status == StepStatus.DEFERRED
    assert result.blocked_operations[0]["target"] == "database"


@pytest.mark.asyncio
async def test_replanning_after_gate_rejection(runtime):
    result = await completed_run(runtime)
    assert any("Database maintenance is deferred" in text for text in result.decision_summaries)
    events = runtime.repository.list_events(result.id)
    assert any(event.event_type == "evidence_gate" and event.status == "blocked" for event in events)


def test_action_idempotency(runtime):
    run = new_run(runtime)
    tools = MaintenanceTools(runtime.simulator, runtime.repository, runtime.gate).bind(run.id)
    first = tools.create_snapshot()
    second = tools.create_snapshot()
    assert first == second
    events = runtime.repository.list_events(run.id)
    assert any(event.event_type == "idempotent_replay" for event in events)


def test_repository_persistence(runtime):
    run = new_run(runtime)
    runtime.repository.append_event(MaintenanceEvent(
        maintenance_id=run.id, event_type="test", summary="persisted"
    ))
    assert runtime.repository.get_run(run.id).id == run.id
    assert runtime.repository.list_events(run.id)[0].summary == "persisted"


def test_invalid_state_transition_is_rejected():
    run = MaintenanceRun(request="Approved change request long enough")
    with pytest.raises(TransitionError):
        run.transition(MaintenanceStatus.COMPLETED)


def test_forbidden_tool_action(runtime):
    run = new_run(runtime)
    tools = MaintenanceTools(runtime.simulator, runtime.repository, runtime.gate).bind(run.id)
    with pytest.raises(PermissionError):
        tools.attempt_restricted_action("delete_database")


@pytest.mark.asyncio
async def test_complete_golden_scenario(runtime):
    result = await completed_run(runtime)
    assert result.status == MaintenanceStatus.COMPLETED_WITH_WARNINGS
    assert result.human_interventions == 0
    assert result.availability_preserved is True
    assert result.report["service_availability_preserved"] is True
    assert result.report["outcome"] == "completed_with_warnings"
