def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "product": "03:17"}


def test_backend_golden_demo_api(client):
    response = client.post("/api/demo/start")
    assert response.status_code == 202
    maintenance_id = response.json()["id"]
    detail = client.get(f"/api/maintenance/{maintenance_id}")
    assert detail.json()["status"] == "completed_with_warnings"
    topology = client.get("/api/topology").json()
    nodes = {node["id"]: node for node in topology["nodes"]}
    assert nodes["web01"]["version"] == "1.1.0"
    assert nodes["web02"]["state"] == "rolled_back"


def test_duplicate_event_does_not_repeat_maintenance(client):
    payload = {
        "request": "Approved rolling web and database maintenance tonight",
        "event_id": "evt-fixed-demo",
    }
    first = client.post("/api/maintenance", json=payload)
    second = client.post("/api/maintenance", json=payload)
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/maintenance").json()) == 1


def test_degraded_preflight_scenario_api(client):
    reset = client.post("/api/demo/reset?scenario=degraded-preflight")
    assert reset.status_code == 204
    response = client.post("/api/demo/start")
    detail = client.get(f"/api/maintenance/{response.json()['id']}").json()
    assert detail["status"] == "completed_with_warnings"
    assert detail["actions_executed"] == []
    assert detail["report"]["service_availability_preserved"] is True
