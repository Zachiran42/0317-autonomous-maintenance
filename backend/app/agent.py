from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import AgentEvent, HealthState, Incident, IncidentStatus
from app.policy import ActionPolicy, PolicyDecision
from app.repository import Repository
from app.simulator import Simulator
from app.tools import IncidentTools


class AgentRuntime(ABC):
    @abstractmethod
    async def run(self, incident_id: str) -> None: ...


class LocalRuleAgent(AgentRuntime):
    """Deterministic offline runtime for tests; production uses AdkAgentRuntime."""

    def __init__(self, simulator: Simulator, repository: Repository, policy: ActionPolicy) -> None:
        self.simulator = simulator
        self.repository = repository
        self.policy = policy

    def event(self, incident: Incident, event_type: str, summary: str, **data: object) -> None:
        self.repository.append_event(
            AgentEvent(
                incident_id=incident.id,
                event_type=event_type,
                summary=summary,
                data=dict(data),
            )
        )

    async def run(self, incident_id: str) -> None:
        incident = self.repository.get_incident(incident_id)
        if not incident or incident.status not in {IncidentStatus.QUEUED, IncidentStatus.FAILED}:
            return
        tools = IncidentTools(self.simulator, self.repository, self.policy).bind(incident.id)
        try:
            incident.status = IncidentStatus.INVESTIGATING
            self.repository.save_incident(incident)
            self.event(incident, "decision", "Agent started autonomous investigation")

            health = tools.get_service_health(incident.service_id)
            logs = tools.get_recent_logs(incident.service_id)
            metrics = tools.get_metrics(incident.service_id)
            dependencies = tools.get_dependency_health(incident.service_id)
            incident.tools_used += [
                "get_service_health", "get_recent_logs", "get_metrics", "get_dependency_health"
            ]
            incident.evidence = [
                f"Health: {health['health']}",
                f"Error rate: {metrics['error_rate']}%",
                *logs["logs"],
                f"Dependencies: {dependencies}",
            ]

            service = self.simulator.get(incident.service_id)
            if service.fault == "worker_deadlock":
                incident.probable_cause = "Stateless web worker deadlock"
                tools.search_runbooks("worker deadlock")
                tools.search_previous_incidents("worker deadlock")
                incident.tools_used += ["search_runbooks", "search_previous_incidents"]
                decision = self.policy.evaluate(
                    "restart_stateless_service", service_id=incident.service_id
                )
                self.event(
                    incident,
                    "policy_check",
                    f"Policy check: restart {decision.decision}",
                    reason=decision.reason,
                )
                if decision.decision != PolicyDecision.ALLOW:
                    raise PermissionError(decision.reason)
                incident.status = IncidentStatus.REMEDIATING
                self.repository.save_incident(incident)
                tools.restart_service(incident.service_id)
                incident.tools_used.append("restart_service")
                incident.actions.append(f"Restarted {incident.service_id}")
                incident.status = IncidentStatus.VERIFYING
                self.repository.save_incident(incident)
                verification = tools.verify_service_health(incident.service_id)
                incident.tools_used.append("verify_service_health")
                if not verification["healthy"]:
                    raise RuntimeError("Post-remediation verification failed")
                incident.verification = "Service healthy after restart"
                incident.status = IncidentStatus.RESOLVED
                self.repository.save_incident(incident)
                report = {
                    "outcome": "resolved_automatically",
                    "probable_cause": incident.probable_cause,
                    "evidence": incident.evidence,
                    "actions": incident.actions,
                    "verification": incident.verification,
                }
                tools.create_incident_report(report)
                incident.tools_used.append("create_incident_report")
                self.event(incident, "result", "Incident resolved automatically")
            elif service.fault == "data_corruption":
                incident.probable_cause = "Possible database data corruption"
                runbook = tools.search_runbooks("checksum data corruption")
                incident.tools_used.append("search_runbooks")
                decision = self.policy.evaluate("modify_database_records", service_id="database")
                self.event(
                    incident,
                    "policy_check",
                    "Policy blocked destructive database remediation",
                    reason=decision.reason,
                )
                escalation = {
                    "severity": "critical",
                    "reason": decision.reason,
                    "evidence": incident.evidence,
                    "recommended_next_steps": runbook["matches"],
                }
                tools.escalate_incident(escalation)
                incident.tools_used.append("escalate_incident")
                incident.escalation = escalation
                incident.status = IncidentStatus.ESCALATED
                self.repository.save_incident(incident)
                self.event(incident, "result", "Incident escalated without destructive action")
            else:
                raise RuntimeError("No safe remediation strategy matched the observed evidence")
        except Exception as exc:
            incident.status = IncidentStatus.FAILED
            self.repository.save_incident(incident)
            self.repository.append_event(
                AgentEvent(
                    incident_id=incident.id,
                    event_type="error",
                    summary=f"Agent workflow failed: {exc}",
                    status="error",
                )
            )
            raise


class AdkAgentRuntime(AgentRuntime):
    """Genuine Google ADK runtime backed by Gemini on Vertex AI."""

    def __init__(
        self,
        simulator: Simulator,
        repository: Repository,
        policy: ActionPolicy,
        model: str,
    ) -> None:
        self.simulator = simulator
        self.repository = repository
        self.policy = policy
        self.model = model

    async def run(self, incident_id: str) -> None:
        from google.adk import Agent, Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        incident = self.repository.get_incident(incident_id)
        if not incident or incident.status != IncidentStatus.QUEUED:
            return
        incident.status = IncidentStatus.INVESTIGATING
        self.repository.save_incident(incident)
        tools = IncidentTools(self.simulator, self.repository, self.policy).bind(incident.id)
        root_agent = Agent(
            name="incident_response_agent",
            model=self.model,
            instruction=(
                "You autonomously resolve simulated IT incidents. Investigate with tools, correlate "
                "evidence, search runbooks/history, and take only policy-enforced actions. Stateless "
                "services may be restarted. Never attempt destructive database/security actions; call "
                "escalate_incident with evidence instead. Always verify remediation and call "
                "create_incident_report or escalate_incident. Return concise action summaries only."
            ),
            tools=[
                tools.get_service_health,
                tools.get_recent_logs,
                tools.get_metrics,
                tools.get_dependency_health,
                tools.search_runbooks,
                tools.search_previous_incidents,
                tools.restart_service,
                tools.verify_service_health,
                tools.create_incident_report,
                tools.escalate_incident,
            ],
        )
        session_service = InMemorySessionService()
        app_name = "incident_response"
        user_id = "system"
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=incident.id
        )
        runner = Runner(agent=root_agent, app_name=app_name, session_service=session_service)
        prompt = (
            f"Incident {incident.id}: {incident.trigger}. Affected service: {incident.service_id}. "
            "Complete the workflow now without waiting for an operator."
        )
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=incident.id,
                new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
            ):
                if event.is_final_response() and event.content:
                    text = " ".join(part.text for part in event.content.parts if part.text)
                    self.repository.append_event(
                        AgentEvent(
                            incident_id=incident.id,
                            event_type="decision",
                            summary=text[:500],
                        )
                    )
            incident = self.repository.get_incident(incident.id) or incident
            if incident.escalation:
                incident.status = IncidentStatus.ESCALATED
            elif incident.report:
                service = self.simulator.get(incident.service_id)
                incident.status = (
                    IncidentStatus.RESOLVED
                    if service.health == HealthState.HEALTHY
                    else IncidentStatus.FAILED
                )
            else:
                incident.status = IncidentStatus.FAILED
            self.repository.save_incident(incident)
        except Exception:
            incident.status = IncidentStatus.FAILED
            self.repository.save_incident(incident)
            raise

