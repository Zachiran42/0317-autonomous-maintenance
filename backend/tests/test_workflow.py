import pytest

from app.models import AgentEvent, Incident, IncidentStatus
from app.policy import PolicyDecision
from app.tools import IncidentTools


@pytest.mark.asyncio
async def test_recoverable_incident_is_resolved(runtime):
    service = runtime.simulator.trigger("recoverable")
    incident = runtime.repository.save_incident(
        Incident(service_id=service.id, scenario="recoverable", trigger="test alert")
    )
    await runtime.agent.run(incident.id)
    result = runtime.repository.get_incident(incident.id)
    assert result.status == IncidentStatus.RESOLVED
    assert result.report["outcome"] == "resolved_automatically"
    assert runtime.simulator.get("web-api").restart_count == 1
    assert result.verification == "Service healthy after restart"


@pytest.mark.asyncio
async def test_unsafe_incident_is_escalated_without_restart(runtime):
    service = runtime.simulator.trigger("unsafe")
    incident = runtime.repository.save_incident(
        Incident(service_id=service.id, scenario="unsafe", trigger="test alert")
    )
    await runtime.agent.run(incident.id)
    result = runtime.repository.get_incident(incident.id)
    assert result.status == IncidentStatus.ESCALATED
    assert result.escalation["severity"] == "critical"
    assert runtime.simulator.get("database").restart_count == 0


def test_action_policy_rejects_database_restart(runtime):
    decision = runtime.policy.evaluate("restart_stateless_service", service_id="database")
    assert decision.decision == PolicyDecision.ESCALATE
    with pytest.raises(PermissionError):
        runtime.policy.enforce("restart_stateless_service", service_id="database")


def test_restart_tool_and_verification(runtime):
    service = runtime.simulator.trigger("recoverable")
    incident = runtime.repository.save_incident(
        Incident(service_id=service.id, scenario="recoverable", trigger="test")
    )
    tools = IncidentTools(runtime.simulator, runtime.repository, runtime.policy).bind(incident.id)
    assert tools.restart_service("web-api")["restart_count"] == 1
    assert tools.verify_service_health("web-api")["healthy"] is True


def test_incident_and_event_persistence(runtime):
    incident = runtime.repository.save_incident(
        Incident(service_id="web-api", scenario="recoverable", trigger="test")
    )
    runtime.repository.append_event(
        AgentEvent(incident_id=incident.id, event_type="test", summary="stored")
    )
    assert runtime.repository.get_incident(incident.id).id == incident.id
    assert runtime.repository.list_events(incident.id)[0].summary == "stored"


def test_failed_tool_execution_is_recorded(runtime):
    incident = runtime.repository.save_incident(
        Incident(service_id="web-api", scenario="recoverable", trigger="test")
    )
    tools = IncidentTools(runtime.simulator, runtime.repository, runtime.policy).bind(incident.id)
    with pytest.raises(KeyError):
        tools.get_service_health("missing")
    assert runtime.repository.list_events(incident.id)[0].status == "error"

