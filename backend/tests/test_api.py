def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_recoverable_path(client):
    response = client.post("/api/demo/trigger", json={"scenario": "recoverable"})
    assert response.status_code == 202
    incident_id = response.json()["id"]
    detail = client.get(f"/api/incidents/{incident_id}")
    assert detail.json()["status"] == "resolved"
    events = client.get(f"/api/incidents/{incident_id}/events").json()
    assert any(event["tool"] == "restart_service" for event in events)

