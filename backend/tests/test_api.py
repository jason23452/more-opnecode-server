from fastapi.testclient import TestClient

from src.App.Main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id")


def test_http_errors_use_standard_error_shape() -> None:
    response = client.get("/api/route-that-does-not-exist")
    body = response.json()

    assert response.status_code == 404
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_404"
    assert body["error"]["message"] == "Not Found"
    assert body["request_id"] == response.headers["x-request-id"]


def test_request_id_can_be_provided_by_client() -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["x-request-id"] == "test-request-id"
