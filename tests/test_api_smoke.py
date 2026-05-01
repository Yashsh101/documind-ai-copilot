from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_reports_service_status():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "DocuMind API"


def test_root_serves_static_app():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
