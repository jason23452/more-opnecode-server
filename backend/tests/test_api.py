from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.App.Main import app
from src.App.Settings import Settings
from src.Features.Opencode.ContainerManager import ContainerManager

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


def test_create_opencode_requires_internal_management_token() -> None:
    response = client.post("/api/opencode/containers")

    assert response.status_code == 401


def test_create_opencode_waits_for_ready_container_and_hides_password() -> None:
    manager = Mock(spec=ContainerManager)
    manager.create.return_value = {"id": "oc-123", "url": "https://quiet-fox.trycloudflare.com"}
    app.state.container_manager = manager
    settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")
    app.state.settings = settings

    response = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 201
    assert response.json() == {"id": "oc-123", "url": "https://quiet-fox.trycloudflare.com"}
    assert "shared-secret" not in response.text


def test_create_opencode_reports_capacity_limit_without_starting_container() -> None:
    manager = Mock(spec=ContainerManager)
    manager.create.side_effect = RuntimeError("container capacity reached")
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 503
    manager.create.assert_called_once()


def test_list_opencode_containers_requires_internal_management_token() -> None:
    response = client.get("/api/opencode/containers")

    assert response.status_code == 401


def test_get_opencode_container_requires_internal_management_token() -> None:
    response = client.get("/api/opencode/containers/oc-123")

    assert response.status_code == 401


def test_list_opencode_containers_returns_current_status_and_tunnel_url() -> None:
    manager = Mock(spec=ContainerManager)
    manager.list.return_value = [
        {"id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com"}
    ]
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.get("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 200
    assert response.json() == [
        {"id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com"}
    ]


def test_get_opencode_container_returns_current_status_and_tunnel_url() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = {
        "id": "oc-123", "status": "unhealthy", "url": "https://new-fox.trycloudflare.com"
    }
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/oc-123", headers={"Authorization": "Bearer admin-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "oc-123", "status": "unhealthy", "url": "https://new-fox.trycloudflare.com"
    }


def test_get_opencode_container_returns_not_found_for_unknown_id() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = None
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/missing", headers={"Authorization": "Bearer admin-secret"}
    )

    assert response.status_code == 404
