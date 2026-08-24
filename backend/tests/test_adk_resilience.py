from unittest.mock import AsyncMock

import pytest

from app.agent import AdkPlanner
from app.models import MaintenanceRun


@pytest.mark.asyncio
async def test_capacity_error_uses_safe_initial_plan_fallback(runtime):
    planner = AdkPlanner("gemini-test")
    planner._run_planner = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
    )
    run = MaintenanceRun(request="Update the web tier and database", approved=True)

    plan, summary = await planner.create_plan(run, AsyncMock())

    assert [step.action for step in plan] == [
        "rolling_update",
        "rolling_update",
        "database_maintenance",
        "create_report",
    ]
    assert "capacity was temporarily exhausted" in summary
    planner._run_planner.assert_awaited_once()


@pytest.mark.asyncio
async def test_capacity_error_uses_safe_replan_fallback(runtime):
    planner = AdkPlanner("gemini-test")
    planner._run_planner = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
    )
    run = MaintenanceRun(request="Update the web tier and database", approved=True)
    run.plan, _ = await planner.capacity_fallback.create_plan(run, AsyncMock())

    result = await planner.replan(
        run,
        {"type": "verification_failure", "target": "web02"},
        AsyncMock(),
    )

    assert any(step.action == "rollback" for step in result.updated_steps)
    assert "capacity was temporarily exhausted" in result.summary
    planner._run_planner.assert_awaited_once()
