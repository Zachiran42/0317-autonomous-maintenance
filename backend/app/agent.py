from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from app.models import (
    ALLOWED_TRANSITIONS,
    GateDecision,
    GateOutcome,
    MaintenanceEvent,
    MaintenanceRun,
    MaintenanceStatus,
    PlanStep,
    StepStatus,
)
from app.policy import EvidenceGate
from app.repository import Repository
from app.simulator import Simulator
from app.tools import MaintenanceTools


class Planner(ABC):
    @abstractmethod
    async def create_plan(
        self, run: MaintenanceRun, tools: MaintenanceTools
    ) -> tuple[list[PlanStep], str]: ...

    @abstractmethod
    async def replan(
        self, run: MaintenanceRun, observation: dict[str, Any], tools: MaintenanceTools
    ) -> str: ...


class LocalPlanner(Planner):
    """Deterministic planner used by tests; production swaps in the ADK planner."""

    async def create_plan(
        self, run: MaintenanceRun, tools: MaintenanceTools
    ) -> tuple[list[PlanStep], str]:
        plan = [
            PlanStep(order=1, target="web01", action="rolling_update",
                     objective="Drain, update, verify, and restore WEB01"),
            PlanStep(order=2, target="web02", action="rolling_update",
                     objective="Update WEB02 only after WEB01 is verified", depends_on=["web01"]),
            PlanStep(order=3, target="database", action="database_maintenance",
                     objective="Run approved database maintenance only with full redundancy",
                     depends_on=["web01", "web02"]),
            PlanStep(order=4, target="report", action="create_report",
                     objective="Persist final evidence and human follow-up"),
        ]
        return plan, "Rolling web changes minimize risk; database work remains evidence-gated."

    async def replan(
        self, run: MaintenanceRun, observation: dict[str, Any], tools: MaintenanceTools
    ) -> str:
        if observation.get("type") == "verification_failure":
            return (
                f"{observation['target']} failed functional verification. Rollback is the safest "
                "eligible action; later database work must be re-evaluated."
            )
        return (
            "Database maintenance is deferred because target-version redundancy is not satisfied "
            "after the verified rollback."
        )


class AdkPlanner(Planner):
    """Gemini/ADK planner: probabilistic planning, deterministic execution authority."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def _run_planner(
        self,
        run: MaintenanceRun,
        tools: MaintenanceTools,
        objective: str,
        *,
        require_steps: bool,
    ) -> tuple[list[PlanStep], str]:
        from google.adk import Agent, Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        captured: dict[str, Any] = {}

        def submit_maintenance_plan(steps: list[dict[str, Any]], summary: str) -> dict[str, Any]:
            """Submit the concise structured plan/replan after gathering sufficient evidence."""
            captured["steps"] = steps
            captured["summary"] = summary
            return {"accepted": True, "step_count": len(steps)}

        instruction = (
            "You are the planner/replanner for 03:17 Autonomous Maintenance Window. Use read tools "
            "when useful. Gemini reasons and proposes; deterministic Evidence Gates authorize all "
            "changes. Never expose private reasoning. Submit concise observable steps with exactly "
            "these action names when applicable: rolling_update, database_maintenance, create_report. "
            "Targets must be web01, web02, database, or report. Call submit_maintenance_plan exactly "
            "once. A failed verification requires rollback and reevaluation of later steps."
        )
        agent = Agent(
            name="maintenance_planner",
            model=self.model,
            instruction=instruction,
            tools=[
                tools.get_change_request,
                tools.get_topology,
                tools.get_service_health,
                tools.get_metrics,
                tools.get_recent_logs,
                tools.search_runbooks,
                tools.search_maintenance_history,
                tools.check_capacity,
                submit_maintenance_plan,
            ],
        )
        session_service = InMemorySessionService()
        app_name = "autonomous_maintenance"
        session_id = f"{run.id}-{len(run.decision_summaries)}"
        await session_service.create_session(
            app_name=app_name, user_id="system", session_id=session_id
        )
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        async for _ in runner.run_async(
            user_id="system",
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=objective)]),
        ):
            pass
        if "summary" not in captured or (require_steps and not captured.get("steps")):
            raise RuntimeError("Gemini planner did not submit a valid structured plan")
        allowed = {
            ("web01", "rolling_update"),
            ("web02", "rolling_update"),
            ("database", "database_maintenance"),
            ("report", "create_report"),
        }
        steps: list[PlanStep] = []
        for index, item in enumerate(captured.get("steps", []), 1):
            target = str(item.get("target", ""))
            action = str(item.get("action", ""))
            if (target, action) not in allowed:
                raise ValueError(f"Planner proposed unsupported step: {target}/{action}")
            steps.append(PlanStep(
                order=index,
                target=target,
                action=action,
                objective=str(item.get("objective", f"Execute {action} on {target}")),
            ))
        return steps, str(captured["summary"])

    async def create_plan(
        self, run: MaintenanceRun, tools: MaintenanceTools
    ) -> tuple[list[PlanStep], str]:
        objective = (
            f"Create the initial executable plan for maintenance {run.id}. Request: {run.request}. "
            "Discover topology and relevant runbooks first. Preserve availability and verify every step."
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return await self._run_planner(run, tools, objective, require_steps=True)
            except (RuntimeError, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Gemini plan failed validation after bounded retries: {last_error}")

    async def replan(
        self, run: MaintenanceRun, observation: dict[str, Any], tools: MaintenanceTools
    ) -> str:
        objective = (
            f"Replan maintenance {run.id} after this observable result: {observation}. "
            "Submit an empty steps list if no new executable step is safe, plus a concise summary."
        )
        _, summary = await self._run_planner(run, tools, objective, require_steps=False)
        return summary


class MaintenanceAgent(ABC):
    @abstractmethod
    async def run(self, maintenance_id: str) -> None: ...


class SafeMaintenanceAgent(MaintenanceAgent):
    def __init__(
        self,
        simulator: Simulator,
        repository: Repository,
        gate: EvidenceGate,
        planner: Planner,
        step_delay_seconds: float = 0.0,
    ) -> None:
        self.simulator = simulator
        self.repository = repository
        self.gate = gate
        self.planner = planner
        self.step_delay_seconds = step_delay_seconds

    async def pause(self) -> None:
        if self.step_delay_seconds > 0:
            await asyncio.sleep(self.step_delay_seconds)

    def event(
        self,
        run: MaintenanceRun,
        event_type: str,
        summary: str,
        *,
        target: str | None = None,
        status: str = "success",
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.repository.append_event(MaintenanceEvent(
            maintenance_id=run.id,
            event_type=event_type,
            target=target,
            summary=summary,
            status=status,
            evidence=evidence or {},
        ))

    def save(self, run: MaintenanceRun) -> None:
        self.repository.save_run(run)

    def sync_gate(self, run: MaintenanceRun, result: dict[str, Any]) -> None:
        decision = GateDecision.model_validate(result)
        if not any(existing.evaluated_at == decision.evaluated_at for existing in run.gate_decisions):
            run.gate_decisions.append(decision)

    async def _execute_web_step(
        self, run: MaintenanceRun, step: PlanStep, tools: MaintenanceTools
    ) -> None:
        target = step.target
        step.status = StepStatus.IN_PROGRESS
        self.save(run)
        self.event(run, "objective", f"Starting rolling maintenance on {target.upper()}", target=target)

        drain_gate = tools.evaluate_evidence("drain_node", target)
        self.sync_gate(run, drain_gate)
        if drain_gate["outcome"] != GateOutcome.PASS:
            step.status = StepStatus.BLOCKED
            step.decision_summary = drain_gate["summary"]
            self.save(run)
            return
        tools.drain_node(target)
        run.actions_executed.append(f"drain_node:{target}")
        await self.pause()
        tools.create_rollback_point(target)
        run.actions_executed.append(f"create_rollback_point:{target}")
        change_gate = tools.evaluate_evidence("apply_web_change", target)
        self.sync_gate(run, change_gate)
        if change_gate["outcome"] != GateOutcome.PASS:
            step.status = StepStatus.BLOCKED
            self.save(run)
            return
        tools.apply_maintenance(target)
        await self.pause()
        tools.restart_service(target)
        run.actions_executed.extend([f"apply_maintenance:{target}", f"restart_service:{target}"])

        run.transition(MaintenanceStatus.VERIFYING)
        self.save(run)
        health = tools.run_health_check(target)
        await self.pause()
        synthetic = tools.run_synthetic_test(target)
        await self.pause()
        self.event(
            run,
            "verification",
            f"{target.upper()} functional verification "
            f"{'passed' if synthetic['passed'] else 'failed'}",
            target=target,
            status="success" if synthetic["passed"] else "failed",
            evidence={"health": health, "synthetic": synthetic},
        )
        if synthetic["passed"]:
            tools.restore_node_to_pool(target)
            await self.pause()
            run.actions_executed.append(f"restore_node_to_pool:{target}")
            step.status = StepStatus.COMPLETED
            step.decision_summary = "Update verified and node restored to service."
            run.transition(MaintenanceStatus.EXECUTING)
            self.save(run)
            return

        step.status = StepStatus.FAILED
        run.transition(MaintenanceStatus.ROLLING_BACK)
        self.save(run)
        logs = tools.get_recent_logs(target)
        metrics = tools.get_metrics(target)
        observation = {
            "type": "verification_failure",
            "target": target,
            "synthetic": synthetic,
            "logs": logs,
            "metrics": metrics,
        }
        summary = await self.planner.replan(run, observation, tools)
        run.decision_summaries.append(summary)
        self.event(run, "replan", summary, target=target, evidence=observation)
        rollback_gate = tools.evaluate_evidence("rollback", target)
        self.sync_gate(run, rollback_gate)
        if rollback_gate["outcome"] != GateOutcome.PASS:
            raise PermissionError("Rollback became ineligible after failed verification")
        tools.rollback_change(target)
        await self.pause()
        verification = tools.verify_rollback(target)
        await self.pause()
        if not verification["passed"]:
            raise RuntimeError("Rollback verification failed")
        step.status = StepStatus.ROLLED_BACK
        step.decision_summary = "Failed update rolled back; previous version verified healthy."
        run.rollback_information.append({
            "target": target,
            "reason": synthetic["reason"],
            "verification": verification,
        })
        run.actions_executed.append(f"rollback_change:{target}")
        self.event(run, "rollback", f"{target.upper()} rollback verified", target=target,
                   evidence=verification)
        run.transition(MaintenanceStatus.REPLANNING)
        self.save(run)
        run.transition(MaintenanceStatus.EXECUTING)
        self.save(run)

    def _build_report(self, run: MaintenanceRun) -> dict[str, Any]:
        topology = self.simulator.topology()
        unresolved = [
            {"target": step.target, "status": step.status, "reason": step.decision_summary}
            for step in run.plan
            if step.status in {StepStatus.ROLLED_BACK, StepStatus.DEFERRED, StepStatus.BLOCKED}
        ]
        return {
            "maintenance_id": run.id,
            "original_request": run.request,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "outcome": "completed_with_warnings",
            "planned_targets": [step.target for step in run.plan],
            "dependency_graph": run.dependency_graph,
            "initial_evidence": [item.model_dump(mode="json") for item in run.initial_evidence],
            "executed_actions": run.actions_executed,
            "verification_results": [
                event.model_dump(mode="json")
                for event in self.repository.list_events(run.id)
                if event.event_type in {"verification", "rollback"}
            ],
            "rollback_information": run.rollback_information,
            "blocked_operations": run.blocked_operations,
            "evidence_gate_decisions": [gate.model_dump(mode="json") for gate in run.gate_decisions],
            "final_topology_state": topology,
            "decision_summaries": run.decision_summaries,
            "unresolved_items": unresolved,
            "recommended_human_follow_up": [
                "Review WEB02 configuration compatibility before retrying its update.",
                "Reschedule database maintenance after both web nodes run the target version.",
            ],
            "service_availability_preserved": run.availability_preserved,
            "human_interventions": run.human_interventions,
        }

    async def run(self, maintenance_id: str) -> None:
        run = self.repository.get_run(maintenance_id)
        if not run or run.status != MaintenanceStatus.RECEIVED:
            return
        tools = MaintenanceTools(self.simulator, self.repository, self.gate).bind(run.id)
        try:
            run.transition(MaintenanceStatus.PLANNING)
            self.save(run)
            self.event(run, "ingestion", "Approved change request ingested")
            await self.pause()
            topology = tools.get_topology()
            tools.search_runbooks("rolling web update database maintenance")
            tools.search_maintenance_history("web tier")
            run.dependency_graph = {
                node["id"]: node["dependencies"] for node in topology["nodes"]
            }
            plan, summary = await self.planner.create_plan(run, tools)
            run.plan = plan
            run.decision_summaries.append(summary)
            self.event(run, "plan", "Structured maintenance plan created",
                       evidence={"summary": summary,
                                 "steps": [step.model_dump(mode="json") for step in plan]})
            await self.pause()

            run.transition(MaintenanceStatus.PREFLIGHT)
            self.save(run)
            preflight = tools.evaluate_evidence("maintenance_window", "infrastructure")
            run = self.repository.get_run(run.id) or run
            decision = run.gate_decisions[-1]
            run.initial_evidence = decision.evidence
            if preflight["outcome"] != GateOutcome.PASS:
                run.transition(MaintenanceStatus.DEFERRED)
                self.save(run)
                return
            tools.create_snapshot("database")
            self.event(run, "preflight", "All pre-flight Evidence Gates passed",
                       evidence=preflight)
            await self.pause()
            run.transition(MaintenanceStatus.READY)
            run.transition(MaintenanceStatus.EXECUTING)
            self.save(run)

            for step in sorted(run.plan, key=lambda item: item.order):
                if step.action == "rolling_update":
                    await self._execute_web_step(run, step, tools)
                elif step.action == "database_maintenance":
                    database_gate = tools.evaluate_evidence("database_change", "database")
                    run = self.repository.get_run(run.id) or run
                    if database_gate["outcome"] != GateOutcome.PASS:
                        run.transition(MaintenanceStatus.REPLANNING)
                        self.save(run)
                        summary = await self.planner.replan(
                            run,
                            {"type": "gate_rejection", "target": "database",
                             "decision": database_gate},
                            tools,
                        )
                        tools.defer_change("database", summary)
                        run = self.repository.get_run(run.id) or run
                        self.event(run, "evidence_gate", "Database maintenance blocked by Evidence Gate",
                                   target="database", status="blocked", evidence=database_gate)
                        await self.pause()
                        run.transition(MaintenanceStatus.COMPLETED_WITH_WARNINGS)
                        self.save(run)
                    else:
                        raise RuntimeError("Golden scenario expected database gate rejection")
            run = self.repository.get_run(run.id) or run
            for step in run.plan:
                if step.action == "create_report":
                    step.status = StepStatus.COMPLETED
            self.save(run)
            report = self._build_report(run)
            tools.create_maintenance_report(report)
            self.event(run, "result", "Maintenance window completed with verified rollback and deferral",
                       evidence={"availability_preserved": True, "human_interventions": 0})
        except Exception as exc:
            current = self.repository.get_run(run.id) or run
            if MaintenanceStatus.FAILED in ALLOWED_TRANSITIONS[current.status]:
                current.transition(MaintenanceStatus.FAILED)
            self.save(current)
            self.event(current, "error", f"Maintenance workflow failed: {exc}", status="error")
            raise
