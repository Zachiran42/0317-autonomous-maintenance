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
    ReplanResult,
    StepStatus,
)
from app.plan_validation import PlanValidator, apply_replan, next_eligible_step
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
    ) -> ReplanResult: ...


class LocalPlanner(Planner):
    """Deterministic planner used by tests; production swaps in the ADK planner."""

    async def create_plan(
        self, run: MaintenanceRun, tools: MaintenanceTools
    ) -> tuple[list[PlanStep], str]:
        if "web02 only" in run.request.lower():
            return [
                PlanStep(
                    id="web02-update",
                    order=1,
                    target="web02",
                    action="rolling_update",
                    objective="Drain, update, verify, and restore WEB02",
                ),
                PlanStep(
                    id="final-report",
                    order=2,
                    target="report",
                    action="create_report",
                    objective="Persist final evidence and human follow-up",
                    depends_on=["web02-update"],
                ),
            ], "The approved scope contains WEB02 only; unrelated targets are omitted."
        plan = [
            PlanStep(
                id="web01-update",
                order=1,
                target="web01",
                action="rolling_update",
                objective="Drain, update, verify, and restore WEB01",
            ),
            PlanStep(
                id="web02-update",
                order=2,
                target="web02",
                action="rolling_update",
                objective="Update WEB02 only after WEB01 is verified",
                depends_on=["web01-update"],
            ),
            PlanStep(
                id="database-maintenance",
                order=3,
                target="database",
                action="database_maintenance",
                objective="Run approved database maintenance only with full redundancy",
                depends_on=["web01-update", "web02-update"],
            ),
            PlanStep(
                id="final-report",
                order=4,
                target="report",
                action="create_report",
                objective="Persist final evidence and human follow-up",
                depends_on=["web01-update", "web02-update", "database-maintenance"],
            ),
        ]
        return plan, "Rolling web changes minimize risk; database work remains evidence-gated."

    async def replan(
        self, run: MaintenanceRun, observation: dict[str, Any], tools: MaintenanceTools
    ) -> ReplanResult:
        if observation.get("type") == "verification_failure":
            target = str(observation["target"])
            failed = next(
                step
                for step in run.plan
                if step.target == target and step.action == "rolling_update"
            )
            rollback_id = f"{target}-rollback"
            database = next(
                (
                    step.model_copy(deep=True)
                    for step in run.plan
                    if step.action == "database_maintenance"
                ),
                None,
            )
            report = next(
                step.model_copy(deep=True) for step in run.plan if step.action == "create_report"
            )
            next_order = failed.order + 1
            rollback = PlanStep(
                id=rollback_id,
                order=next_order,
                target=target,
                action="rollback",
                objective=f"Restore and verify {target.upper()} from this run's rollback point",
                depends_on=[failed.id],
            )
            updates = [rollback]
            if database:
                database.order = next_order + 1
                database.depends_on = list(dict.fromkeys([*database.depends_on, rollback_id]))
                updates.append(database)
            report.order = next_order + 2 if database else next_order + 1
            report.depends_on = [step.id for step in run.plan if step.action != "create_report"] + [
                rollback_id
            ]
            updates.append(report)
            return ReplanResult(
                summary=(
                    f"{target.upper()} failed functional verification. Add a controlled rollback "
                    "objective and re-evaluate downstream database work afterward."
                ),
                updated_steps=updates,
            )
        database = next(
            (step for step in run.plan if step.action == "database_maintenance"),
            None,
        )
        deferred = [database.id] if database else []
        return ReplanResult(
            summary=(
                "Database maintenance is deferred because target-version redundancy is not "
                "satisfied after the verified rollback."
            ),
            deferred_step_ids=deferred,
        )


class AdkPlanner(Planner):
    """Gemini/ADK planner: probabilistic planning, deterministic execution authority."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.validator = PlanValidator()
        self.capacity_fallback = LocalPlanner()

    @staticmethod
    def _is_capacity_error(exc: Exception) -> bool:
        message = str(exc).upper()
        return "RESOURCE_EXHAUSTED" in message or "429" in message

    @staticmethod
    def _fallback_summary(summary: str) -> str:
        return (
            "Gemini/ADK was invoked but Vertex AI capacity was temporarily exhausted; "
            "the deterministic safe planner produced this executable fallback. "
            f"{summary}"
        )

    async def _run_planner(
        self,
        run: MaintenanceRun,
        tools: MaintenanceTools,
        objective: str,
        *,
        require_steps: bool,
        replan: bool = False,
    ) -> ReplanResult:
        from google.adk import Agent, Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        captured: dict[str, Any] = {}

        def submit_maintenance_plan(
            steps: list[dict[str, Any]],
            summary: str,
            removed_step_ids: list[str] | None = None,
            deferred_step_ids: list[str] | None = None,
        ) -> dict[str, Any]:
            """Submit the concise structured plan/replan after gathering sufficient evidence."""
            captured["steps"] = steps
            captured["summary"] = summary
            captured["removed_step_ids"] = removed_step_ids or []
            captured["deferred_step_ids"] = deferred_step_ids or []
            return {"accepted": True, "step_count": len(steps)}

        instruction = (
            "You are the planner/replanner for 03:17 Autonomous Maintenance Window. Use read tools "
            "when useful. Gemini reasons and proposes; deterministic Evidence Gates authorize all "
            "changes. Never expose private reasoning. Build the safest valid plan necessary for the "
            "approved request; omit unnecessary targets. Each step needs a stable id, positive unique "
            "order, target, supported action, concise objective, and explicit depends_on step IDs. "
            "Supported target/action pairs are web01|web02/rolling_update, database/"
            "database_maintenance, report/create_report, and web01|web02/rollback only after an "
            "observed failed update. The final report must be last and depend on all actionable work. "
            "Never repeat completed work or propose targets outside the approved request. Call "
            "submit_maintenance_plan exactly once. Deterministic validation and Evidence Gates may "
            "still reject a structurally valid proposal."
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
                tools.check_application_availability,
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
        steps: list[PlanStep] = []
        for index, item in enumerate(captured.get("steps", []), 1):
            steps.append(
                PlanStep(
                    id=str(item.get("id") or f"planned-{index}"),
                    order=int(item.get("order", index)),
                    target=str(item.get("target", "")),
                    action=str(item.get("action", "")),
                    objective=str(item.get("objective", "")),
                    depends_on=[str(value) for value in item.get("depends_on", [])],
                )
            )
        result = ReplanResult(
            summary=str(captured["summary"]),
            updated_steps=steps,
            removed_step_ids=[str(value) for value in captured.get("removed_step_ids", [])],
            deferred_step_ids=[str(value) for value in captured.get("deferred_step_ids", [])],
        )
        if not replan:
            result.updated_steps = self.validator.validate(result.updated_steps, run.request)
        else:
            apply_replan(run.plan, result, run.request, self.validator)
        return result

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
                result = await self._run_planner(run, tools, objective, require_steps=True)
                return result.updated_steps, result.summary
            except Exception as exc:
                if self._is_capacity_error(exc):
                    plan, summary = await self.capacity_fallback.create_plan(run, tools)
                    return plan, self._fallback_summary(summary)
                if not isinstance(exc, (RuntimeError, ValueError)):
                    raise
                last_error = exc
        raise RuntimeError(f"Gemini plan failed validation after bounded retries: {last_error}")

    async def replan(
        self, run: MaintenanceRun, observation: dict[str, Any], tools: MaintenanceTools
    ) -> ReplanResult:
        objective = (
            f"Replan maintenance {run.id} after this observable result: {observation}. "
            "Submit only new or changed steps plus removed/deferred IDs as a structured delta. "
            "Preserve completed outcomes, never repeat completed work, and defer unsafe pending work. "
            "If rollback is the safest objective, add a rollback step that still requires "
            "deterministic authorization."
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return await self._run_planner(
                    run, tools, objective, require_steps=False, replan=True
                )
            except Exception as exc:
                if self._is_capacity_error(exc):
                    result = await self.capacity_fallback.replan(run, observation, tools)
                    result.summary = self._fallback_summary(result.summary)
                    return result
                if not isinstance(exc, (RuntimeError, ValueError)):
                    raise
                last_error = exc
        raise RuntimeError(f"Gemini replan failed validation after bounded retries: {last_error}")


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
        self.plan_validator = PlanValidator()
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
        actor: str = "system",
        evidence: dict[str, Any] | None = None,
    ) -> None:
        self.repository.append_event(
            MaintenanceEvent(
                maintenance_id=run.id,
                event_type=event_type,
                actor=actor,
                target=target,
                summary=summary,
                status=status,
                evidence=evidence or {},
            )
        )

    def save(self, run: MaintenanceRun) -> None:
        self.repository.save_run(run)

    def sync_gate(self, run: MaintenanceRun, result: dict[str, Any]) -> None:
        decision = GateDecision.model_validate(result)
        if not any(
            existing.evaluated_at == decision.evaluated_at for existing in run.gate_decisions
        ):
            run.gate_decisions.append(decision)

    def record_availability(self, run: MaintenanceRun, trigger: str) -> dict[str, Any]:
        observation = self.simulator.check_application_availability()
        run.availability_checks += 1
        run.availability_preserved = run.availability_preserved and observation["available"]
        self.save(run)
        self.event(
            run,
            "availability_check",
            f"Availability {'preserved' if observation['available'] else 'violated'} after {trigger}",
            target="web-tier",
            status="success" if observation["available"] else "failed",
            actor="verification",
            evidence={"trigger": trigger, **observation},
        )
        return observation

    async def revise_plan(
        self,
        run: MaintenanceRun,
        observation: dict[str, Any],
        tools: MaintenanceTools,
    ) -> None:
        old_plan = [step.model_dump(mode="json") for step in run.plan]
        result = await self.planner.replan(run, observation, tools)
        run.plan = apply_replan(run.plan, result, run.request, self.plan_validator)
        run.decision_summaries.append(result.summary)
        self.save(run)
        self.event(
            run,
            "plan_revised",
            result.summary,
            target=str(observation.get("target") or "maintenance"),
            actor="agent",
            evidence={
                "triggering_observation": observation,
                "old_plan": old_plan,
                "updated_plan": [step.model_dump(mode="json") for step in run.plan],
                "removed_step_ids": result.removed_step_ids,
                "deferred_step_ids": result.deferred_step_ids,
            },
        )

    async def _execute_web_step(
        self, run: MaintenanceRun, step: PlanStep, tools: MaintenanceTools
    ) -> None:
        target = step.target
        step.status = StepStatus.IN_PROGRESS
        self.save(run)
        self.event(
            run, "objective", f"Starting rolling maintenance on {target.upper()}", target=target
        )

        drain_gate = tools.evaluate_evidence("drain_node", target)
        self.sync_gate(run, drain_gate)
        if drain_gate["outcome"] != GateOutcome.PASS:
            step.status = StepStatus.BLOCKED
            step.decision_summary = drain_gate["summary"]
            self.save(run)
            return
        tools.drain_node(target)
        run.actions_executed.append(f"drain_node:{target}")
        self.record_availability(run, f"drain {target}")
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
        self.record_availability(run, f"maintenance application on {target}")
        await self.pause()
        tools.restart_service(target)
        run.actions_executed.extend([f"apply_maintenance:{target}", f"restart_service:{target}"])
        self.record_availability(run, f"restart {target}")

        run.transition(MaintenanceStatus.VERIFYING)
        self.save(run)
        health = tools.run_health_check(target)
        await self.pause()
        synthetic = tools.run_synthetic_test(target)
        self.record_availability(run, f"functional verification of {target}")
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
            self.record_availability(run, f"restore {target} to service")
            step.status = StepStatus.COMPLETED
            step.decision_summary = "Update verified and node restored to service."
            run.transition(MaintenanceStatus.EXECUTING)
            self.save(run)
            return

        step.status = StepStatus.FAILED
        step.decision_summary = "Functional verification failed; structured replan required."
        run.transition(MaintenanceStatus.REPLANNING)
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
        await self.revise_plan(run, observation, tools)
        run.transition(MaintenanceStatus.EXECUTING)
        self.save(run)

    async def _execute_rollback_step(
        self, run: MaintenanceRun, step: PlanStep, tools: MaintenanceTools
    ) -> None:
        target = step.target
        step.status = StepStatus.IN_PROGRESS
        run.transition(MaintenanceStatus.ROLLING_BACK)
        self.save(run)
        self.event(
            run,
            "objective",
            f"Executing validated rollback objective for {target.upper()}",
            target=target,
            actor="agent",
        )
        rollback_gate = tools.evaluate_evidence("rollback", target)
        self.sync_gate(run, rollback_gate)
        if rollback_gate["outcome"] != GateOutcome.PASS:
            step.status = StepStatus.BLOCKED
            step.decision_summary = rollback_gate["summary"]
            raise PermissionError("Rollback became ineligible after failed verification")
        tools.rollback_change(target)
        run.actions_executed.append(f"rollback_change:{target}")
        self.record_availability(run, f"rollback {target}")
        await self.pause()
        verification = tools.verify_rollback(target)
        self.record_availability(run, f"rollback verification of {target}")
        await self.pause()
        if not verification["passed"]:
            raise RuntimeError("Rollback verification failed")
        failed_update = next(
            item
            for item in run.plan
            if item.target == target
            and item.action == "rolling_update"
            and item.status == StepStatus.FAILED
        )
        failed_update.status = StepStatus.ROLLED_BACK
        failed_update.decision_summary = (
            "Failed update rolled back; previous version verified healthy."
        )
        step.status = StepStatus.COMPLETED
        step.decision_summary = "Deterministic rollback authorization and verification passed."
        run.rollback_information.append(
            {
                "target": target,
                "reason": "Functional verification failed after update",
                "verification": verification,
            }
        )
        self.event(
            run,
            "rollback",
            f"{target.upper()} rollback verified",
            target=target,
            actor="action",
            evidence=verification,
        )
        run.transition(MaintenanceStatus.EXECUTING)
        self.save(run)

    async def _execute_database_step(
        self, run: MaintenanceRun, step: PlanStep, tools: MaintenanceTools
    ) -> None:
        step.status = StepStatus.IN_PROGRESS
        self.save(run)
        database_gate = tools.evaluate_evidence("database_change", "database")
        self.sync_gate(run, database_gate)
        if database_gate["outcome"] != GateOutcome.PASS:
            step.status = StepStatus.BLOCKED
            step.decision_summary = database_gate["summary"]
            run.transition(MaintenanceStatus.REPLANNING)
            self.save(run)
            observation = {
                "type": "gate_rejection",
                "target": "database",
                "decision": database_gate,
            }
            await self.revise_plan(run, observation, tools)
            deferred = next(item for item in run.plan if item.id == step.id)
            run.blocked_operations.append(
                {
                    "target": deferred.target,
                    "reason": deferred.decision_summary,
                }
            )
            self.save(run)
            self.event(
                run,
                "evidence_gate",
                "Database maintenance blocked by Evidence Gate",
                target="database",
                status="blocked",
                actor="policy",
                evidence=database_gate,
            )
            run.transition(MaintenanceStatus.EXECUTING)
            self.save(run)
            return

        tools.apply_database_maintenance()
        run.actions_executed.append("apply_database_maintenance:database")
        step.status = StepStatus.COMPLETED
        step.decision_summary = "Database maintenance completed after all evidence passed."
        self.record_availability(run, "database maintenance")
        self.save(run)

    def _execute_defer_step(self, run: MaintenanceRun, step: PlanStep) -> None:
        step.status = StepStatus.DEFERRED
        step.decision_summary = step.decision_summary or "Deferred by the validated plan."
        run.blocked_operations.append(
            {
                "target": step.target,
                "reason": step.decision_summary,
            }
        )
        self.save(run)

    def _build_report(self, run: MaintenanceRun) -> dict[str, Any]:
        topology = self.simulator.topology()
        events = self.repository.list_events(run.id)
        availability_events = [
            event for event in events if event.event_type == "availability_check"
        ]
        measured_availability = bool(availability_events) and all(
            event.evidence.get("available") is True for event in availability_events
        )
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
                for event in events
                if event.event_type in {"verification", "rollback"}
            ],
            "availability_observations": [
                event.model_dump(mode="json") for event in availability_events
            ],
            "plan_revisions": [
                event.model_dump(mode="json")
                for event in events
                if event.event_type == "plan_revised"
            ],
            "rollback_information": run.rollback_information,
            "blocked_operations": run.blocked_operations,
            "evidence_gate_decisions": [
                gate.model_dump(mode="json") for gate in run.gate_decisions
            ],
            "final_topology_state": topology,
            "decision_summaries": run.decision_summaries,
            "unresolved_items": unresolved,
            "recommended_human_follow_up": [
                f"Review {item['target'].upper()}: {item['reason']}" for item in unresolved
            ],
            "service_availability_preserved": (
                run.availability_preserved and measured_availability
            ),
            "availability_checks": len(availability_events),
            "human_interventions": run.human_interventions,
        }

    def _execute_report_step(
        self, run: MaintenanceRun, step: PlanStep, tools: MaintenanceTools
    ) -> None:
        step.status = StepStatus.COMPLETED
        step.decision_summary = "Final evidence and adaptive plan history persisted."
        warnings = any(
            item.status
            in {
                StepStatus.ROLLED_BACK,
                StepStatus.DEFERRED,
                StepStatus.BLOCKED,
                StepStatus.FAILED,
            }
            for item in run.plan
        )
        final_status = (
            MaintenanceStatus.COMPLETED_WITH_WARNINGS if warnings else MaintenanceStatus.COMPLETED
        )
        run.transition(final_status)
        report = self._build_report(run)
        report["outcome"] = final_status.value
        run.report = report
        self.save(run)
        tools.create_maintenance_report(report)
        self.event(
            run,
            "result",
            "Maintenance window completed from the final dependency-aware plan",
            actor="system",
            evidence={
                "availability_preserved": report["service_availability_preserved"],
                "availability_checks": report["availability_checks"],
                "human_interventions": run.human_interventions,
            },
        )

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
            run.dependency_graph = {node["id"]: node["dependencies"] for node in topology["nodes"]}
            plan, summary = await self.planner.create_plan(run, tools)
            run.plan = self.plan_validator.validate(plan, run.request)
            run.decision_summaries.append(summary)
            self.save(run)
            self.event(
                run,
                "plan",
                "Dependency-aware maintenance plan created",
                actor="agent",
                evidence={
                    "summary": summary,
                    "steps": [step.model_dump(mode="json") for step in run.plan],
                },
            )
            await self.pause()

            run.transition(MaintenanceStatus.PREFLIGHT)
            self.save(run)
            self.record_availability(run, "initial pre-flight observation")
            preflight = tools.evaluate_evidence("maintenance_window", "infrastructure")
            self.sync_gate(run, preflight)
            decision = GateDecision.model_validate(preflight)
            run.initial_evidence = decision.evidence
            if preflight["outcome"] != GateOutcome.PASS:
                reason = "Pre-flight evidence rejected all mutating maintenance work."
                for step in run.plan:
                    if step.action != "create_report" and step.status == StepStatus.PENDING:
                        step.status = StepStatus.DEFERRED
                        step.decision_summary = reason
                        run.blocked_operations.append(
                            {
                                "target": step.target,
                                "reason": reason,
                            }
                        )
                run.transition(MaintenanceStatus.DEFERRED)
                self.save(run)
                self.event(
                    run,
                    "evidence_gate",
                    reason,
                    target="infrastructure",
                    status="blocked",
                    actor="policy",
                    evidence=preflight,
                )
                report_step = next(step for step in run.plan if step.action == "create_report")
                self._execute_report_step(run, report_step, tools)
                return
            if any(step.action == "database_maintenance" for step in run.plan):
                tools.create_snapshot("database")
            self.event(
                run,
                "preflight",
                "All pre-flight Evidence Gates passed",
                actor="policy",
                evidence=preflight,
            )
            await self.pause()
            run.transition(MaintenanceStatus.READY)
            run.transition(MaintenanceStatus.EXECUTING)
            self.save(run)

            iterations = 0
            while run.status == MaintenanceStatus.EXECUTING:
                iterations += 1
                if iterations > max(len(run.plan) * 3, 12):
                    raise RuntimeError("Dynamic scheduler exceeded its bounded execution loop")
                step = next_eligible_step(run.plan)
                if step is None:
                    pending = [item for item in run.plan if item.status == StepStatus.PENDING]
                    if not pending:
                        break
                    for item in pending:
                        if item.action != "create_report":
                            item.status = StepStatus.DEFERRED
                            item.decision_summary = "Deferred because a dependency did not reach a safe terminal outcome."
                    self.save(run)
                    continue
                if step.action == "rolling_update":
                    await self._execute_web_step(run, step, tools)
                elif step.action == "rollback":
                    await self._execute_rollback_step(run, step, tools)
                elif step.action == "database_maintenance":
                    await self._execute_database_step(run, step, tools)
                elif step.action == "defer":
                    self._execute_defer_step(run, step)
                elif step.action == "create_report":
                    self._execute_report_step(run, step, tools)
        except Exception as exc:
            current = self.repository.get_run(run.id) or run
            if MaintenanceStatus.FAILED in ALLOWED_TRANSITIONS[current.status]:
                current.transition(MaintenanceStatus.FAILED)
            self.save(current)
            self.event(current, "error", f"Maintenance workflow failed: {exc}", status="error")
            raise
