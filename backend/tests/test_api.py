from unittest.mock import Mock
from subprocess import CompletedProcess

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
    assert "container capacity reached" not in response.text
    manager.create.assert_called_once()


def test_management_api_returns_safe_error_for_unexpected_manager_failure() -> None:
    manager = Mock(spec=ContainerManager)
    manager.list.side_effect = RuntimeError("docker socket /run/secrets/token failed")
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.get("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 503
    assert "docker socket" not in response.text
    assert "token" not in response.text


def test_delete_opencode_requires_internal_management_token() -> None:
    response = client.delete("/api/opencode/containers/oc-123")

    assert response.status_code == 401


def test_list_opencode_containers_requires_internal_management_token() -> None:
    response = client.get("/api/opencode/containers")

    assert response.status_code == 401


def test_delete_opencode_removes_managed_container() -> None:
    manager = Mock(spec=ContainerManager)
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.delete(
        "/api/opencode/containers/oc-123",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 204
    manager.delete.assert_called_once_with("oc-123")


def test_delete_opencode_reports_unknown_container() -> None:
    manager = Mock(spec=ContainerManager)
    manager.delete.side_effect = LookupError("managed container not found")
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.delete(
        "/api/opencode/containers/not-managed",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 404


def test_delete_opencode_reports_removal_failure() -> None:
    manager = Mock(spec=ContainerManager)
    manager.delete.side_effect = RuntimeError("Docker removal failed")
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.delete(
        "/api/opencode/containers/oc-123",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 503


def test_container_manager_deletes_managed_container_and_its_runtime_data() -> None:
    manager = ContainerManager(Settings())
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "true\n", ""),
        CompletedProcess([], 0, "", ""),
    ])

    manager.delete("oc-managed")

    assert manager._docker.call_args_list[0].args == (
        "inspect", "-f", '{{ index .Config.Labels "dynamic-opencode" }}', "oc-managed",
    )
    assert manager._docker.call_args_list[1].args == ("rm", "-f", "oc-managed")


def test_container_manager_refuses_to_delete_unmanaged_container() -> None:
    manager = ContainerManager(Settings())
    manager._docker = Mock(return_value=CompletedProcess([], 0, "other\n", ""))

    try:
        manager.delete("not-managed")
    except LookupError:
        pass
    else:
        raise AssertionError("unmanaged containers must not be deleted")

    manager._docker.assert_called_once()


def test_tunnel_recovery_waits_for_consecutive_probe_failures_and_reuses_container() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_tunnel_failure_threshold=2))
    manager._discover = Mock(side_effect=lambda: [{
        "id": "oc-1", "status": manager._statuses.get("oc-1", "healthy"),
        "url": manager._latest_urls.get("oc-1", "https://old.trycloudflare.com"),
    }])
    manager._probe = Mock(side_effect=[False, False, True])
    manager._docker = Mock(return_value=CompletedProcess([], 0, "", ""))
    manager._wait_for_recovered_tunnel = Mock(return_value="https://new.trycloudflare.com")

    manager.monitor_once()
    manager._docker.assert_not_called()
    manager.monitor_once()

    assert "https://old.trycloudflare.com" in manager._wait_for_recovered_tunnel.call_args.args
    assert manager._wait_for_recovered_tunnel.call_args.args[0] == "oc-1"
    restart_command = manager._docker.call_args.args[4]
    assert ": >/tmp/cloudflared.log" in restart_command
    assert manager.get("oc-1")["url"] == "https://new.trycloudflare.com"
    assert manager.get("oc-1")["status"] == "healthy"


def test_failed_tunnel_retries_report_unhealthy_without_removing_container() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_tunnel_failure_threshold=1,
                                        opencode_tunnel_recovery_attempts=2))
    manager._discover = Mock(return_value=[{"id": "oc-1", "status": "unhealthy", "url": "https://old.trycloudflare.com"}])
    manager._probe = Mock(return_value=False)
    manager._docker = Mock(return_value=CompletedProcess([], 1, "", "failed"))

    manager.monitor_once()

    assert manager._docker.call_count == 2
    assert all(call.args[0] == "exec" for call in manager._docker.call_args_list)
    assert manager._statuses["oc-1"] == "unhealthy"
    assert all("rm" not in call.args for call in manager._docker.call_args_list)


def test_recovery_ignores_stale_url_and_probes_a_distinct_new_url(monkeypatch) -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_startup_timeout=1))
    manager._read_tunnel_url = Mock(side_effect=[
        "https://old.trycloudflare.com", "https://fresh.trycloudflare.com",
    ])
    manager._probe = Mock(side_effect=[True])
    monkeypatch.setattr("src.Features.Opencode.ContainerManager.time.sleep", lambda _: None)

    recovered = manager._wait_for_recovered_tunnel("oc-1", "https://old.trycloudflare.com")

    assert recovered == "https://fresh.trycloudflare.com"
    manager._probe.assert_called_once_with("https://fresh.trycloudflare.com")


def test_container_manager_create_applies_configured_cpu_memory_and_capacity_limit() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_container_cpu=1.5,
                                        opencode_container_memory="3g", opencode_max_containers=2))
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "existing\n", ""),
        CompletedProcess([], 0, "new-container\n", ""),
    ])
    manager._ensure_image = Mock()
    manager._read_tunnel_url = Mock(return_value="https://new.trycloudflare.com")
    manager._healthy = Mock(return_value=True)

    result = manager.create()

    assert result == {"id": "new-container", "url": "https://new.trycloudflare.com"}
    run_args = manager._docker.call_args_list[1].args
    assert "--cpus" in run_args and "1.5" in run_args
    assert "--memory" in run_args and "3g" in run_args


def test_container_manager_rejects_creation_at_configured_capacity() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_max_containers=1))
    manager._docker = Mock(return_value=CompletedProcess([], 0, "existing\n", ""))
    manager._ensure_image = Mock()

    try:
        manager.create()
    except RuntimeError as error:
        assert "capacity reached" in str(error)
    else:
        raise AssertionError("container capacity must be enforced")

    manager._ensure_image.assert_not_called()


def test_container_manager_cleans_up_container_when_initialization_times_out() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_startup_timeout=0))
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, "new-container\n", ""),
        CompletedProcess([], 0, "", ""),
    ])
    manager._ensure_image = Mock()

    try:
        manager.create()
    except RuntimeError as error:
        assert "did not become ready" in str(error)
    else:
        raise AssertionError("initialization timeout must fail")

    assert manager._docker.call_args_list[-1].args == ("rm", "-f", "new-container")


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
