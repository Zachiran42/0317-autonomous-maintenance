import pytest

from app.models import (
    GateOutcome,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceStatus,
    StepStatus,
    TransitionError,
)
from app.simulator import SimulatorScenario
from app.tools import MaintenanceTools


def new_run(runtime) -> MaintenanceRun:
    return runtime.repository.save_run(
        MaintenanceRun(request="Approved rolling web and database maintenance")
    )


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


def test_planner_read_tools_return_recoverable_unknown_target(runtime):
    run = new_run(runtime)
    tools = MaintenanceTools(runtime.simulator, runtime.repository, runtime.gate).bind(run.id)

    for reader in (tools.get_service_health, tools.get_metrics, tools.get_recent_logs):
        result = reader("report")
        assert result["available"] is False
        assert result["target"] == "report"
        assert "web02" in result["allowed_targets"]
        assert "Unknown infrastructure node" in result["error"]


@pytest.mark.asyncio
async def test_structured_plan_creation(runtime):
    result = await completed_run(runtime)
    assert [step.target for step in result.plan] == [
        "web01",
        "web02",
        "web02",
        "database",
        "report",
    ]
    assert result.plan[0].action == "rolling_update"
    assert result.plan[2].action == "rollback"


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
        "web02_target",
        "full_redundancy",
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
    failed = [
        event for event in events if event.event_type == "verification" and event.target == "web02"
    ]
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
    assert any(
        event.event_type == "evidence_gate" and event.status == "blocked" for event in events
    )


@pytest.mark.asyncio
async def test_structured_replans_change_persisted_plan(runtime):
    result = await completed_run(runtime)
    revisions = [
        event
        for event in runtime.repository.list_events(result.id)
        if event.event_type == "plan_revised"
    ]
    assert len(revisions) == 2
    first = revisions[0].evidence
    assert len(first["updated_plan"]) > len(first["old_plan"])
    assert any(step["action"] == "rollback" for step in first["updated_plan"])
    assert revisions[1].evidence["deferred_step_ids"] == ["database-maintenance"]
    assert next(step for step in result.plan if step.id == "database-maintenance").status == (
        StepStatus.DEFERRED
    )
    assert next(step for step in result.plan if step.id == "final-report").status == (
        StepStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_alternative_web_only_plan_executes_without_database(runtime):
    run = runtime.repository.save_run(
        MaintenanceRun(request="Update WEB02 only. Do not perform database maintenance.")
    )
    await runtime.agent.run(run.id)
    result = runtime.repository.get_run(run.id)
    assert result is not None
    assert {step.target for step in result.plan} == {"web02", "report"}
    assert all(step.action != "database_maintenance" for step in result.plan)
    assert result.status == MaintenanceStatus.COMPLETED_WITH_WARNINGS


@pytest.mark.asyncio
async def test_degraded_preflight_refuses_mutation_and_still_reports(runtime):
    runtime.simulator.reset(SimulatorScenario.DEGRADED_PREFLIGHT)
    result = await completed_run(runtime)
    assert result.status == MaintenanceStatus.COMPLETED_WITH_WARNINGS
    assert result.actions_executed == []
    assert result.report is not None
    assert all(
        step.status == StepStatus.DEFERRED for step in result.plan if step.action != "create_report"
    )


def test_availability_check_is_measured_and_false_is_sticky(runtime):
    run = new_run(runtime)
    baseline = runtime.agent.record_availability(run, "baseline")
    assert baseline == {
        "available": True,
        "healthy_serving_web_nodes": 2,
        "required_serving_web_nodes": 1,
        "serving_targets": ["web01", "web02"],
        "global_error_rate": 0.1,
    }
    runtime.simulator.drain_node("web01")
    runtime.simulator.drain_node("web02")
    outage = runtime.agent.record_availability(run, "forced outage")
    assert outage["available"] is False
    runtime.simulator.reset()
    runtime.agent.record_availability(run, "recovery")
    persisted = runtime.repository.get_run(run.id)
    assert persisted is not None
    assert persisted.availability_preserved is False


@pytest.mark.asyncio
async def test_availability_events_back_the_golden_report(runtime):
    result = await completed_run(runtime)
    events = runtime.repository.list_events(result.id)
    checks = [event for event in events if event.event_type == "availability_check"]
    assert checks
    assert result.availability_checks == len(checks)
    assert all(event.evidence["available"] for event in checks)
    assert result.report["availability_checks"] == len(checks)
    assert result.report["service_availability_preserved"] is True


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
    runtime.repository.append_event(
        MaintenanceEvent(maintenance_id=run.id, event_type="test", summary="persisted")
    )
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
