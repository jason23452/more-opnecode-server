from unittest.mock import Mock
from subprocess import CompletedProcess
import threading

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


def test_opencode_management_docs_expose_bearer_authorization_scheme() -> None:
    schema = app.openapi()
    create_operation = schema["paths"]["/api/opencode/containers"]["post"]

    assert create_operation["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert all(
        parameter["name"].lower() != "authorization"
        for parameter in create_operation.get("parameters", [])
    )


def test_create_opencode_waits_for_ready_container_and_hides_password() -> None:
    manager = Mock(spec=ContainerManager)
    manager.create.return_value = {
        "id": "oc-123", "url": "https://quiet-fox.trycloudflare.com",
        "upload_token": "container-upload-token", "connect_token": "container-connect-token",
    }
    app.state.container_manager = manager
    settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")
    app.state.settings = settings

    response = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 201
    assert response.json() == {
        "id": "oc-123", "url": "https://quiet-fox.trycloudflare.com",
        "upload_url": "https://quiet-fox.trycloudflare.com/upload",
        "upload_token": "container-upload-token",
        "cli_install_commands": {
            "windows_powershell": "$env:OPENCODE_PROJECT_RELEASE_URL = 'https://github.com/jason23452/more-opnecode-server/releases/latest/download'; irm 'https://github.com/jason23452/more-opnecode-server/releases/latest/download/install.ps1' | iex",
            "macos": "curl -fsSL 'https://github.com/jason23452/more-opnecode-server/releases/latest/download/install.sh' | OPENCODE_PROJECT_RELEASE_URL='https://github.com/jason23452/more-opnecode-server/releases/latest/download' sh",
            "linux": "curl -fsSL 'https://github.com/jason23452/more-opnecode-server/releases/latest/download/install.sh' | OPENCODE_PROJECT_RELEASE_URL='https://github.com/jason23452/more-opnecode-server/releases/latest/download' sh",
        },
        "upload_command": "opencode-project upload --url https://quiet-fox.trycloudflare.com/upload --token=container-upload-token --project .",
        "connect_url": "wss://quiet-fox.trycloudflare.com/connect",
        "connect_token": "container-connect-token",
        "connect_command": "opencode-project connect --url wss://quiet-fox.trycloudflare.com/connect --token=container-connect-token",
    }
    assert "shared-secret" not in response.text


def test_create_opencode_uses_configured_cli_release_url() -> None:
    manager = Mock(spec=ContainerManager)
    manager.create.return_value = {
        "id": "oc-123", "url": "https://quiet-fox.trycloudflare.com",
        "upload_token": "container-upload-token", "connect_token": "container-connect-token",
    }
    app.state.container_manager = manager
    app.state.settings = Settings(
        opencode_admin_token="admin-secret",
        opencode_cli_release_url="https://downloads.example/cli/latest/download/",
    )

    response = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 201
    assert response.json()["cli_install_commands"] == {
        "windows_powershell": (
            "$env:OPENCODE_PROJECT_RELEASE_URL = 'https://downloads.example/cli/latest/download'; "
            "irm 'https://downloads.example/cli/latest/download/install.ps1' | iex"
        ),
        "macos": (
            "curl -fsSL 'https://downloads.example/cli/latest/download/install.sh' | "
            "OPENCODE_PROJECT_RELEASE_URL='https://downloads.example/cli/latest/download' sh"
        ),
        "linux": (
            "curl -fsSL 'https://downloads.example/cli/latest/download/install.sh' | "
            "OPENCODE_PROJECT_RELEASE_URL='https://downloads.example/cli/latest/download' sh"
        ),
    }


def test_upload_target_control_endpoint_is_removed() -> None:
    manager = Mock(spec=ContainerManager)
    app.state.container_manager = manager
    app.state.settings = Settings()
    response = client.get("/api/opencode/containers/oc-123/upload-target")
    assert response.status_code == 404
    assert not hasattr(manager, "upload_target")


def test_management_api_does_not_expose_a_tui_websocket_relay() -> None:
    manager = Mock(spec=ContainerManager)
    app.state.container_manager = manager

    response = client.get("/api/opencode/containers/oc-123/connect")

    assert response.status_code == 404


def test_create_opencode_upload_command_passes_leading_dash_token_safely() -> None:
    manager = Mock(spec=ContainerManager)
    manager.create.return_value = {
        "id": "oc-123", "url": "https://quiet-fox.trycloudflare.com",
        "upload_token": "-token-starting-with-dash", "connect_token": "connect-token",
    }
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert response.status_code == 201
    assert response.json()["upload_command"] == (
        "opencode-project upload --url https://quiet-fox.trycloudflare.com/upload "
        "--token=-token-starting-with-dash --project ."
    )


def test_management_api_does_not_expose_or_relay_upload_payload() -> None:
    manager = Mock(spec=ContainerManager)
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")
    response = client.put(
        "/api/opencode/containers/oc-123/upload",
        content=b"project archive",
        headers={"Authorization": "Bearer container-upload-token"},
    )

    assert response.status_code == 404
    assert not hasattr(manager, "upload")


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
    assert "pkill -x cloudflared" in restart_command
    assert "cloudflared tunnel" not in restart_command
    assert "rm -f /tmp/opencode-tunnel-url" in restart_command
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

    assert manager._docker.call_count == 1
    assert all(call.args[0] == "exec" for call in manager._docker.call_args_list)
    assert manager._statuses["oc-1"] == "unhealthy"
    assert all("rm" not in call.args for call in manager._docker.call_args_list)


def test_tunnel_recovery_restarts_again_when_new_tunnel_never_becomes_ready(monkeypatch) -> None:
    manager = ContainerManager(Settings(
        opencode_password="secret", opencode_tunnel_recovery_attempts=3,
        opencode_tunnel_recovery_delay=0,
    ))
    manager._docker = Mock(return_value=CompletedProcess([], 0, "", ""))
    manager._wait_for_recovered_tunnel = Mock(return_value="")
    monkeypatch.setattr("src.Features.Opencode.ContainerManager.time.sleep", lambda _: None)

    recovered = manager._recover_tunnel("oc-1", "https://old.trycloudflare.com")

    assert recovered == ""
    assert manager._docker.call_count == 1
    assert manager._wait_for_recovered_tunnel.call_count == 3


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


def test_recovery_persists_new_url_after_external_probe_succeeds(monkeypatch) -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_startup_timeout=1))
    manager._read_tunnel_url = Mock(return_value="https://fresh.trycloudflare.com")
    manager._probe = Mock(return_value=True)
    manager._persist_tunnel_url = Mock()
    monkeypatch.setattr("src.Features.Opencode.ContainerManager.time.sleep", lambda _: None)

    recovered = manager._wait_for_recovered_tunnel("oc-1", "https://old.trycloudflare.com")

    assert recovered == "https://fresh.trycloudflare.com"
    manager._persist_tunnel_url.assert_called_once_with("oc-1", recovered)


def test_container_manager_rediscovers_recovered_url_after_manager_restart() -> None:
    recovered_url = "https://fresh.trycloudflare.com"
    manager = ContainerManager(Settings(opencode_password="secret"))
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "oc-1\n", ""),
        CompletedProcess([], 0, "true\n", ""),
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, recovered_url + "\n", ""),
    ])
    manager._healthy = Mock(return_value=True)

    rediscovered = manager.list()

    assert rediscovered == [{"id": "oc-1", "status": "healthy", "url": recovered_url}]
    assert manager._docker.call_args_list[4].args == (
        "exec", "oc-1", "sh", "-c", "cat /tmp/opencode-tunnel-url",
    )


def test_container_manager_create_applies_configured_cpu_memory_and_capacity_limit() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_container_cpu=1.5,
                                        opencode_container_memory="3g", opencode_max_containers=2))
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "existing\n", ""),
        CompletedProcess([], 0, "new-container\n", ""),
        CompletedProcess([], 0, "", ""),
    ])
    manager._ensure_image = Mock()
    manager._read_tunnel_url = Mock(return_value="https://new.trycloudflare.com")
    manager._healthy = Mock(return_value=True)

    result = manager.create()

    assert result["id"] == "new-container"
    assert result["url"] == "https://new.trycloudflare.com"
    assert result["upload_token"]
    run_args = manager._docker.call_args_list[1].args
    assert "--cpus" in run_args and "1.5" in run_args
    assert "--memory" in run_args and "3g" in run_args
    token_label = next(arg for arg in run_args if arg.startswith("dynamic-opencode-upload-token="))
    assert len(token_label.partition("=")[2]) >= 32


def test_create_rebuilds_cached_opencode_image_when_build_context_changes() -> None:
    settings = Settings(opencode_password="secret", opencode_image="dynamic-opencode:latest")
    manager = ContainerManager(settings)
    docker_calls: list[tuple[str, ...]] = []
    image_label = ["old-build-context-digest"]
    container_count = [0]

    def docker(*args: str, **kwargs) -> CompletedProcess:
        docker_calls.append(args)
        if args[:2] == ("ps", "-q"):
            return CompletedProcess(args, 0, "", "")
        if args[:2] == ("image", "inspect"):
            return CompletedProcess(args, 0, image_label[0] + "\n", "")
        if args[0] == "build":
            image_label[0] = next(arg.partition("=")[2] for arg in args
                                  if arg.startswith("dynamic-opencode-build-hash="))
            return CompletedProcess(args, 0, "", "")
        if args[0] == "run":
            container_count[0] += 1
            return CompletedProcess(args, 0, f"new-container-{container_count[0]}\n", "")
        if args[0] == "exec":
            return CompletedProcess(args, 0, "", "")
        raise AssertionError(f"Unexpected Docker command: {args}")

    manager._docker = Mock(side_effect=docker)
    manager._read_tunnel_url = Mock(return_value="https://new.trycloudflare.com")
    manager._healthy = Mock(return_value=True)

    try:
        created = manager.create()
        manager.create()
    finally:
        manager.close()

    build_indexes = [index for index, call in enumerate(docker_calls) if call[0] == "build"]
    run_indexes = [index for index, call in enumerate(docker_calls) if call[0] == "run"]
    assert len(build_indexes) == 1
    assert build_indexes[0] < run_indexes[0]
    assert len(run_indexes) == 2
    assert created["id"] == "new-container-1"


def test_create_then_immediate_list_keeps_initialized_tunnel_healthy() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_admin_token="admin-secret"))
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, "new-container\n", ""),
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, "new-container\n", ""),
        CompletedProcess([], 0, "true\n", ""),
        CompletedProcess([], 0, "", ""),
        CompletedProcess([], 0, "https://new.trycloudflare.com\n", ""),
    ])
    manager._ensure_image = Mock()
    manager._read_tunnel_url = Mock(return_value="https://new.trycloudflare.com")
    manager._healthy = Mock(return_value=True)
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="secret", opencode_admin_token="admin-secret")

    created = client.post("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})
    listed = client.get("/api/opencode/containers", headers={"Authorization": "Bearer admin-secret"})

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json() == [{
        "id": "new-container", "status": "healthy", "url": "https://new.trycloudflare.com",
        "upload_url": "https://new.trycloudflare.com/upload",
        "connect_url": "wss://new.trycloudflare.com/connect",
    }]
    assert manager._healthy.call_count == 1


def test_api_status_remains_healthy_until_configured_probe_failure_threshold() -> None:
    manager = ContainerManager(Settings(
        opencode_password="secret", opencode_admin_token="admin-secret",
        opencode_tunnel_failure_threshold=2, opencode_tunnel_recovery_attempts=0,
    ))
    manager._docker = Mock(side_effect=lambda *args, **kwargs: CompletedProcess(
        [], 0, "oc-1\n" if args[0] == "ps" else "true\n", "",
    ))
    manager._inspect = Mock(return_value={
        "id": "oc-1", "status": "unhealthy", "url": "https://old.trycloudflare.com",
    })
    manager._probe = Mock(return_value=False)
    manager._recover_tunnel = Mock(return_value="")
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="secret", opencode_admin_token="admin-secret")
    manager._latest_urls["oc-1"] = "https://old.trycloudflare.com"
    manager._statuses["oc-1"] = "healthy"

    before_threshold = client.get("/api/opencode/containers/oc-1", headers={
        "Authorization": "Bearer admin-secret",
    })
    manager.monitor_once()
    first_failure = client.get("/api/opencode/containers/oc-1", headers={
        "Authorization": "Bearer admin-secret",
    })
    manager.monitor_once()
    second_failure = client.get("/api/opencode/containers/oc-1", headers={
        "Authorization": "Bearer admin-secret",
    })

    assert before_threshold.json()["status"] == "healthy"
    assert first_failure.json()["status"] == "healthy"
    assert second_failure.json()["status"] == "unhealthy"


def test_list_and_get_remain_available_while_tunnel_recovery_is_blocked() -> None:
    manager = ContainerManager(Settings(
        opencode_password="secret", opencode_tunnel_failure_threshold=1,
    ))
    entered_recovery = threading.Event()
    finish_recovery = threading.Event()
    queries_finished = threading.Event()
    query_results: list[tuple[list[dict[str, str]], dict[str, str] | None]] = []
    monitor = threading.Thread(target=manager.monitor_once)
    old_url = "https://old.trycloudflare.com"
    new_url = "https://new.trycloudflare.com"
    manager._docker = Mock(return_value=CompletedProcess([], 0, "oc-1\n", ""))
    manager._inspect = Mock(return_value={"id": "oc-1", "status": "healthy", "url": old_url})
    manager._probe = Mock(return_value=False)

    def blocked_recovery(container_id: str, url: str) -> str:
        entered_recovery.set()
        assert finish_recovery.wait(timeout=3)
        return new_url

    manager._recover_tunnel = blocked_recovery
    manager._latest_urls["oc-1"] = old_url
    manager._statuses["oc-1"] = "healthy"

    try:
        monitor.start()
        assert entered_recovery.wait(timeout=1)

        def query_manager() -> None:
            query_results.append((manager.list(), manager.get("oc-1")))
            queries_finished.set()

        query = threading.Thread(target=query_manager)
        query.start()
        assert queries_finished.wait(timeout=0.5), "list/get blocked behind tunnel recovery"
        query.join(timeout=1)
        assert query_results == [(
            [{"id": "oc-1", "status": "healthy", "url": old_url}],
            {"id": "oc-1", "status": "healthy", "url": old_url},
        )]

        finish_recovery.set()
        monitor.join(timeout=1)
        assert manager.get("oc-1") == {"id": "oc-1", "status": "healthy", "url": new_url}
    finally:
        finish_recovery.set()
        monitor.join(timeout=1)
        manager.close()


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


def test_container_manager_discovers_full_docker_ids() -> None:
    full_id = "eb48dc1fde54" + "0" * 52
    manager = ContainerManager(Settings())
    manager._docker = Mock(return_value=CompletedProcess([], 0, f"{full_id}\n", ""))
    manager._inspect = Mock(return_value={
        "id": full_id, "status": "healthy", "url": "https://full-id.trycloudflare.com",
    })

    containers = manager.list()

    assert containers[0]["id"] == full_id
    assert manager._docker.call_args.args == (
        "ps", "-aq", "--no-trunc", "--filter", "label=dynamic-opencode=true",
    )


def test_container_manager_uses_full_ids_when_checking_creation_capacity() -> None:
    manager = ContainerManager(Settings(opencode_password="secret", opencode_max_containers=2))
    full_id = "eb48dc1fde54" + "0" * 52
    manager._docker = Mock(side_effect=[
        CompletedProcess([], 0, f"{full_id}\n", ""),
        CompletedProcess([], 0, "new-container\n", ""),
        CompletedProcess([], 0, "", ""),
    ])
    manager._ensure_image = Mock()
    manager._read_tunnel_url = Mock(return_value="https://new.trycloudflare.com")
    manager._healthy = Mock(return_value=True)

    manager.create()

    assert manager._docker.call_args_list[0].args == (
        "ps", "-q", "--no-trunc", "--filter", "label=dynamic-opencode=true",
    )


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
    assert response.json() == [{
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
        "upload_url": "https://quiet-fox.trycloudflare.com/upload",
        "connect_url": "wss://quiet-fox.trycloudflare.com/connect",
    }]
    assert "upload_token" not in response.text and "connect_token" not in response.text


def test_get_opencode_container_returns_current_status_and_tunnel_url() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = {"id": "oc-123", "status": "unhealthy", "url": "https://new-fox.trycloudflare.com"}
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/oc-123", headers={"Authorization": "Bearer admin-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "oc-123", "status": "unhealthy", "url": "https://new-fox.trycloudflare.com",
        "upload_url": "https://new-fox.trycloudflare.com/upload",
        "connect_url": "wss://new-fox.trycloudflare.com/connect",
    }
    assert "upload_token" not in response.text and "connect_token" not in response.text


def test_get_opencode_container_returns_platform_commands_without_exposing_tokens() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = {
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
    }
    manager.get_command_tokens.return_value = {
        "upload_token": "upload-secret", "connect_token": "connect-secret",
    }
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/oc-123?environment=windows",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
        "upload_url": "https://quiet-fox.trycloudflare.com/upload",
        "connect_url": "wss://quiet-fox.trycloudflare.com/connect",
        "upload_command": (
            "opencode-project upload --url 'https://quiet-fox.trycloudflare.com/upload' "
            "--token='upload-secret' --project ."
        ),
        "connect_command": (
            "opencode-project connect --url 'wss://quiet-fox.trycloudflare.com/connect' "
            "--token='connect-secret'"
        ),
    }
    assert "upload_token" not in response.json()
    assert "connect_token" not in response.json()
    manager.get_command_tokens.assert_called_once_with("oc-123")


def test_get_opencode_container_without_environment_preserves_existing_response() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = {
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
    }
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/oc-123", headers={"Authorization": "Bearer admin-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
        "upload_url": "https://quiet-fox.trycloudflare.com/upload",
        "connect_url": "wss://quiet-fox.trycloudflare.com/connect",
    }
    manager.get_command_tokens.assert_not_called()


def test_get_opencode_container_accepts_mac_and_linux_environments() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = {
        "id": "oc-123", "status": "healthy", "url": "https://quiet-fox.trycloudflare.com",
    }
    manager.get_command_tokens.return_value = {
        "upload_token": "upload-secret", "connect_token": "connect-secret",
    }
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    for environment in ("mac", "linux"):
        response = client.get(
            f"/api/opencode/containers/oc-123?environment={environment}",
            headers={"Authorization": "Bearer admin-secret"},
        )

        assert response.status_code == 200
        assert response.json()["upload_command"] == (
            "opencode-project upload --url https://quiet-fox.trycloudflare.com/upload "
            "--token=upload-secret --project ."
        )
        assert response.json()["connect_command"] == (
            "opencode-project connect --url wss://quiet-fox.trycloudflare.com/connect "
            "--token=connect-secret"
        )


def test_cli_install_command_api_returns_command_for_selected_environment() -> None:
    app.state.settings = Settings(
        opencode_admin_token="admin-secret",
        opencode_cli_release_url="https://downloads.example/cli/latest/download",
    )

    response = client.get(
        "/api/opencode/cli-install-command?environment=mac",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "environment": "mac",
        "command": (
            "curl -fsSL 'https://downloads.example/cli/latest/download/install.sh' | "
            "OPENCODE_PROJECT_RELEASE_URL='https://downloads.example/cli/latest/download' sh"
        ),
    }


def test_cli_install_command_api_supports_all_environments() -> None:
    app.state.settings = Settings(
        opencode_admin_token="admin-secret",
        opencode_cli_release_url="https://downloads.example/cli/latest/download",
    )
    expected = {
        "windows": (
            "$env:OPENCODE_PROJECT_RELEASE_URL = 'https://downloads.example/cli/latest/download'; "
            "irm 'https://downloads.example/cli/latest/download/install.ps1' | iex"
        ),
        "mac": (
            "curl -fsSL 'https://downloads.example/cli/latest/download/install.sh' | "
            "OPENCODE_PROJECT_RELEASE_URL='https://downloads.example/cli/latest/download' sh"
        ),
        "linux": (
            "curl -fsSL 'https://downloads.example/cli/latest/download/install.sh' | "
            "OPENCODE_PROJECT_RELEASE_URL='https://downloads.example/cli/latest/download' sh"
        ),
    }

    for environment, command in expected.items():
        response = client.get(
            f"/api/opencode/cli-install-command?environment={environment}",
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert response.status_code == 200
        assert response.json() == {"environment": environment, "command": command}


def test_cli_install_command_api_validates_environment() -> None:
    app.state.settings = Settings(opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/cli-install-command?environment=windows-xp",
        headers={"Authorization": "Bearer admin-secret"},
    )

    assert response.status_code == 422


def test_get_opencode_container_returns_not_found_for_unknown_id() -> None:
    manager = Mock(spec=ContainerManager)
    manager.get.return_value = None
    app.state.container_manager = manager
    app.state.settings = Settings(opencode_password="shared-secret", opencode_admin_token="admin-secret")

    response = client.get(
        "/api/opencode/containers/missing", headers={"Authorization": "Bearer admin-secret"}
    )

    assert response.status_code == 404
