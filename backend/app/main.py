import base64
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models import CreateMaintenanceRequest, MaintenanceEvent, MaintenanceRun
from app.observability import log_event
from app.runtime import Runtime, build_runtime
from app.simulator import SimulatorScenario


async def process_maintenance(runtime: Runtime, maintenance_id: str) -> None:
    try:
        await runtime.agent.run(maintenance_id)
    except Exception as exc:  # noqa: BLE001 - workflow boundary records unexpected failures
        log_event("workflow_failed", maintenance_id=maintenance_id, error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = build_runtime()
    yield


app = FastAPI(title="03:17 API", version="0.2.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def runtime(request: Request) -> Runtime:
    return request.app.state.runtime


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "03:17"}


@app.get("/api/config")
def public_config(request: Request) -> dict[str, str]:
    value = runtime(request).settings
    return {
        "agent_runtime": value.agent_runtime,
        "persistence_backend": value.persistence_backend,
        "event_backend": value.event_backend,
        "model": value.gemini_model,
    }


@app.get("/api/topology")
def topology(request: Request):
    return runtime(request).simulator.topology()


@app.get("/api/maintenance", response_model=list[MaintenanceRun])
def maintenance_runs(request: Request):
    return runtime(request).repository.list_runs()


@app.get("/api/maintenance/{maintenance_id}", response_model=MaintenanceRun)
def maintenance_run(maintenance_id: str, request: Request):
    result = runtime(request).repository.get_run(maintenance_id)
    if not result:
        raise HTTPException(404, "Maintenance run not found")
    return result


@app.get(
    "/api/maintenance/{maintenance_id}/events",
    response_model=list[MaintenanceEvent],
)
def maintenance_events(maintenance_id: str, request: Request):
    if not runtime(request).repository.get_run(maintenance_id):
        raise HTTPException(404, "Maintenance run not found")
    return runtime(request).repository.list_events(maintenance_id)


@app.post("/api/maintenance", response_model=MaintenanceRun, status_code=202)
async def create_maintenance(
    payload: CreateMaintenanceRequest,
    request: Request,
    background: BackgroundTasks,
):
    current = runtime(request)
    event_id = payload.event_id or f"evt-{uuid4().hex[:12]}"
    for existing in current.repository.list_runs():
        if event_id in existing.processed_event_ids:
            return existing
    run = MaintenanceRun(
        request=payload.request,
        approved=payload.approved,
        processed_event_ids=[event_id],
    )
    current.repository.save_run(run)
    current.repository.append_event(
        MaintenanceEvent(
            maintenance_id=run.id,
            event_type="request_received",
            summary="Approved maintenance request received",
            evidence={"event_id": event_id, "approved": payload.approved},
        )
    )
    if current.publisher:
        current.publisher.publish(run.id, event_id)
    else:
        background.add_task(process_maintenance, current, run.id)
    return run


@app.post("/api/demo/start", response_model=MaintenanceRun, status_code=202)
async def start_golden_demo(request: Request, background: BackgroundTasks):
    return await create_maintenance(CreateMaintenanceRequest(), request, background)


@app.post("/api/demo/reset", status_code=204)
def reset_demo(
    request: Request,
    scenario: SimulatorScenario = SimulatorScenario.GOLDEN,
):
    current = runtime(request)
    current.simulator.reset(scenario)
    current.repository.clear()


@app.post("/api/events/pubsub", status_code=204)
async def receive_pubsub(request: Request):
    envelope = await request.json()
    try:
        payload = json.loads(base64.b64decode(envelope["message"]["data"]).decode())
        maintenance_id = payload["maintenance_id"]
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Malformed Pub/Sub envelope") from exc
    await process_maintenance(runtime(request), maintenance_id)


frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend.exists():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/")
    def dashboard():
        return FileResponse(frontend / "index.html")

    @app.get("/{path:path}")
    def dashboard_fallback(path: str):
        candidate = frontend / path
        return FileResponse(candidate if candidate.is_file() else frontend / "index.html")
