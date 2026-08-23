import base64
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models import AgentEvent, Incident, TriggerRequest
from app.observability import log_event
from app.runtime import Runtime, build_runtime


async def process_incident(runtime: Runtime, incident_id: str) -> None:
    try:
        await runtime.agent.run(incident_id)
    except Exception as exc:  # noqa: BLE001 - workflow boundary records every unexpected failure
        log_event("workflow_failed", incident_id=incident_id, error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = build_runtime()
    yield


app = FastAPI(title="AfterAlert API", version="0.1.0", lifespan=lifespan)
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
    return {"status": "ok"}


@app.get("/api/config")
def public_config(request: Request) -> dict[str, Any]:
    value = runtime(request).settings
    return {
        "agent_runtime": value.agent_runtime,
        "persistence_backend": value.persistence_backend,
        "event_backend": value.event_backend,
        "model": value.gemini_model,
    }


@app.get("/api/services")
def services(request: Request):
    return runtime(request).simulator.list_services()


@app.get("/api/incidents", response_model=list[Incident])
def incidents(request: Request):
    return runtime(request).repository.list_incidents()


@app.get("/api/incidents/{incident_id}", response_model=Incident)
def incident(incident_id: str, request: Request):
    result = runtime(request).repository.get_incident(incident_id)
    if not result:
        raise HTTPException(404, "Incident not found")
    return result


@app.get("/api/incidents/{incident_id}/events", response_model=list[AgentEvent])
def events(incident_id: str, request: Request):
    if not runtime(request).repository.get_incident(incident_id):
        raise HTTPException(404, "Incident not found")
    return runtime(request).repository.list_events(incident_id)


@app.post("/api/demo/trigger", response_model=Incident, status_code=202)
async def trigger(payload: TriggerRequest, request: Request, background: BackgroundTasks):
    current = runtime(request)
    service = current.simulator.trigger(payload.scenario)
    incident = Incident(
        service_id=service.id,
        scenario=payload.scenario,
        trigger=f"Automated alert: {service.id} is {service.health}",
    )
    current.repository.save_incident(incident)
    current.repository.append_event(
        AgentEvent(
            incident_id=incident.id,
            event_type="alert",
            summary=incident.trigger,
        )
    )
    if current.publisher:
        current.publisher.publish(incident.id)
    else:
        background.add_task(process_incident, current, incident.id)
    return incident


@app.post("/api/demo/reset", status_code=204)
def reset(request: Request):
    current = runtime(request)
    current.simulator.reset()
    current.repository.clear()


@app.post("/api/events/pubsub", status_code=204)
async def receive_pubsub(request: Request):
    """Receive a Pub/Sub push envelope; duplicate deliveries are safe."""
    envelope = await request.json()
    try:
        encoded = envelope["message"]["data"]
        payload = json.loads(base64.b64decode(encoded).decode())
        incident_id = payload["incident_id"]
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Malformed Pub/Sub envelope") from exc
    await process_incident(runtime(request), incident_id)


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
