"""Opt-in black-box test requiring Docker and outbound Cloudflare access."""

import os
import pty
import select
import tempfile
import subprocess
import sys
import time
import uuid

import httpx
import pytest
from src.Features.Opencode.DockerCli import docker_command


def _wait_for_healthy_container(query, expected_url: str, timeout: float, interval: float) -> dict:
    deadline = time.monotonic() + timeout
    last_container = None
    while time.monotonic() < deadline:
        last_container = query()
        if last_container.get("status") == "healthy" and last_container.get("url") == expected_url:
            return last_container
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    pytest.fail(
        f"Container did not recover within {timeout}s "
        f"(expected healthy URL {expected_url!r}; last response: {last_container!r})"
    )


def test_wait_for_healthy_container_retries_until_status_and_url_match() -> None:
    responses = iter([
        {"id": "container-1", "status": "unhealthy", "url": "https://new.trycloudflare.com"},
        {"id": "container-1", "status": "healthy", "url": "https://new.trycloudflare.com"},
    ])
    queried = []

    result = _wait_for_healthy_container(
        lambda: queried.append(True) or next(responses),
        expected_url="https://new.trycloudflare.com",
        timeout=1,
        interval=0,
    )

    assert result["status"] == "healthy"
    assert result["url"] == "https://new.trycloudflare.com"
    assert len(queried) == 2


def test_external_probe_retries_transient_network_error_and_non_200() -> None:
    responses = iter([
        httpx.ConnectError("network unavailable"),
        503,
        200,
    ])
    attempts = []

    def get(url: str, *, auth: tuple[str, str], timeout: float) -> httpx.Response:
        attempts.append(url)
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return httpx.Response(result)

    response = _probe_external_url(
        "https://new.trycloudflare.com",
        "password",
        timeout=1,
        interval=0,
        get=get,
    )

    assert response.status_code == 200
    assert len(attempts) == 3


def _probe_external_url(
    url: str,
    password: str,
    timeout: float = 75,
    interval: float = 2,
    get=httpx.get,
) -> httpx.Response:
    deadline = time.monotonic() + timeout
    last_failure = "no response"
    while True:
        try:
            response = get(url + "/", auth=("opencode", password), timeout=20)
            if response.status_code == 200:
                return response
            last_failure = f"HTTP {response.status_code}"
        except httpx.HTTPError as error:
            last_failure = f"{type(error).__name__}: {error}"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            pytest.fail(f"external URL {url!r} did not return HTTP 200 within {timeout}s (last failure: {last_failure})")
        time.sleep(min(interval, remaining))


def _assert_tunnel_no_longer_serves(url: str, password: str, timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    last_status = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url + "/", auth=("opencode", password), timeout=5)
            last_status = response.status_code
            if response.status_code != 200:
                return
        except httpx.HTTPError:
            return
        time.sleep(1)
    pytest.fail(f"deleted tunnel continued serving HTTP 200 for {timeout}s (last status: {last_status})")


@pytest.mark.skipif(os.getenv("OPENCODE_DOCKER_E2E") != "1", reason="requires Docker daemon and Cloudflare Quick Tunnel")
def test_upload_cli_isolated_and_deleted_with_managed_container() -> None:
    api_port = int(os.getenv("OPENCODE_E2E_API_PORT", "18081"))
    admin_token = os.getenv("OPENCODE_ADMIN_TOKEN", "integration-admin-token")
    password = os.getenv("OPENCODE_PASSWORD", "integration-opencode-password")
    env = os.environ | {
        "OPENCODE_ADMIN_TOKEN": admin_token,
        "OPENCODE_PASSWORD": password,
        "OPENCODE_IMAGE": f"dynamic-opencode-upload-e2e:{uuid.uuid4().hex[:8]}",
        "OPENCODE_STARTUP_TIMEOUT": "300",
        "OPENCODE_MAX_CONTAINERS": "20",
        "OPENCODE_UPLOAD_MAX_BYTES": "1048576",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.App.Main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{api_port}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    managed_ids: list[str] = []
    tui_process = None
    try:
        deadline = time.monotonic() + 30
        last_failure = "backend did not start"
        while time.monotonic() < deadline:
            try:
                health = httpx.get(base_url + "/api/health", timeout=1)
                if health.status_code == 200:
                    break
                last_failure = f"health returned HTTP {health.status_code}: {health.text}"
            except httpx.HTTPError as error:
                last_failure = f"{type(error).__name__}: {error}"
            time.sleep(0.25)
        else:
            pytest.fail(f"backend did not start within 30s: {last_failure}")

        created = httpx.post(base_url + "/api/opencode/containers", headers=headers, timeout=360)
        assert created.status_code == 201, f"create failed: HTTP {created.status_code}: {created.text}"
        payload = created.json()
        target_id = payload["id"]
        managed_ids.append(target_id)
        second_created = httpx.post(base_url + "/api/opencode/containers", headers=headers, timeout=360)
        assert second_created.status_code == 201, f"second create failed: HTTP {second_created.status_code}: {second_created.text}"
        second_id = second_created.json()["id"]
        managed_ids.append(second_id)
        assert target_id != second_id, f"API returned duplicate container ids: {target_id}"
        assert payload["upload_url"] == payload["url"].rstrip("/") + "/upload"
        assert payload["connect_url"] == payload["url"].replace("https://", "wss://").rstrip("/") + "/connect"
        assert "localhost:8000" not in payload["connect_url"]
        assert payload["connect_token"]
        assert payload["upload_target_url"].endswith(f"/api/opencode/containers/{target_id}/upload-target")
        assert httpx.put(
            base_url + f"/api/opencode/containers/{target_id}/upload", content=b"must not relay",
            headers={"Authorization": f"Bearer {payload['upload_token']}"}, timeout=10,
        ).status_code == 404, "management API must not expose a project body relay"
        assert _probe_external_url(payload["url"], password).status_code == 200

        wrong_target = httpx.put(
            payload["upload_url"], content=b"wrong container capability",
            headers={"Authorization": f"Bearer {second_created.json()['upload_token']}"}, timeout=30,
        )
        assert wrong_target.status_code == 401, f"foreign container token was accepted: {wrong_target.status_code}"

        with tempfile.TemporaryDirectory(prefix="opencode-upload-e2e-") as project:
            marker = f"uploaded-{uuid.uuid4().hex}"
            marker_path = os.path.join(project, "upload-marker.txt")
            with open(marker_path, "w", encoding="utf-8") as source:
                source.write(marker)
            cli_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../cli"))
            installation = subprocess.run(
                ["uv", "tool", "install", "--python", sys.executable, "--quiet", cli_root],
                capture_output=True, text=True,
            )
            assert installation.returncode == 0, (
                f"uv tool install failed (exit {installation.returncode}):\n"
                f"stdout:\n{installation.stdout}\nstderr:\n{installation.stderr}"
            )
            tool_bin = subprocess.run(["uv", "tool", "dir", "--bin"], capture_output=True, text=True)
            assert tool_bin.returncode == 0, (
                f"uv tool dir --bin failed: stdout={tool_bin.stdout!r}, stderr={tool_bin.stderr!r}"
            )
            cli_executable = os.path.join(tool_bin.stdout.strip(), "opencode-project")
            unauthorized = subprocess.run(
                [cli_executable, "connect", "--url", payload["connect_url"], "--token=wrong-token"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            )
            assert unauthorized.returncode != 0 and "授權無效" in unauthorized.stderr, (
                f"invalid TUI token was not rejected clearly: exit={unauthorized.returncode}, "
                f"stderr={unauthorized.stderr!r}"
            )
            uploaded_once = subprocess.run(
                [cli_executable, "upload", "--url", payload["upload_url"],
                 f"--token={payload['upload_token']}", "--project", project],
                capture_output=True, text=True, timeout=60,
            )
            assert uploaded_once.returncode == 0, (
                f"CLI direct Tunnel upload failed: exit={uploaded_once.returncode}, "
                f"stdout={uploaded_once.stdout!r}, stderr={uploaded_once.stderr!r}"
            )
            oversized_file = os.path.join(project, "oversized.bin")
            with open(oversized_file, "wb") as source:
                source.write(os.urandom(96 * 1024 * 1024))
            large_upload = subprocess.run(
                [cli_executable, "upload", "--url", "https://stale.invalid/upload",
                 f"--token={payload['upload_token']}", "--refresh-url", payload["upload_target_url"],
                 "--project", project],
                capture_output=True, text=True, timeout=300,
            )
            assert large_upload.returncode == 0, (
                f"large chunked upload failed: exit={large_upload.returncode}, stderr={large_upload.stderr!r}"
            )
            installed_size = subprocess.run(
                docker_command("exec", target_id, "stat", "-c", "%s", "/workspace/project/oversized.bin"),
                capture_output=True, text=True,
            )
            assert installed_size.returncode == 0 and installed_size.stdout.strip() == str(96 * 1024 * 1024), (
                "large archive was not fully installed: "
                f"exit={installed_size.returncode}, stdout={installed_size.stdout!r}, stderr={installed_size.stderr!r}"
            )
            os.unlink(oversized_file)
            terminal_master, terminal_slave = pty.openpty()
            tui_process = subprocess.Popen(
                [cli_executable, "upload",
                 "--url", payload["upload_url"], f"--token={payload['upload_token']}", "--project", project,
                 "--connect-url", payload["connect_url"], "--connect-token", payload["connect_token"]],
                stdin=terminal_slave, stdout=terminal_slave, stderr=terminal_slave,
            )
            os.close(terminal_slave)
            terminal_output = bytearray()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and tui_process.poll() is None:
                readable, _, _ = select.select([terminal_master], [], [], 0.2)
                if readable:
                    try:
                        terminal_output.extend(os.read(terminal_master, 65536))
                    except OSError:
                        break
                if b"OpenCode" in terminal_output or b"opencode" in terminal_output:
                    break
            assert tui_process.poll() is None, (
                "upload-then-connect CLI exited before entering remote TUI: "
                f"{bytes(terminal_output[-4000:])!r}"
            )
            assert b"OpenCode" in terminal_output or b"opencode" in terminal_output, (
                "remote TUI did not emit identifiable OpenCode output: "
                f"{bytes(terminal_output[-4000:])!r}"
            )
            uploaded_during_session = subprocess.run(
                docker_command("exec", target_id, "cat", "/workspace/project/upload-marker.txt"),
                capture_output=True, text=True,
            )
            assert uploaded_during_session.returncode == 0 and uploaded_during_session.stdout == marker, (
                "one-command upload/connect entered the TUI without the project being present: "
                f"exit={uploaded_during_session.returncode}, stdout={uploaded_during_session.stdout!r}, "
                f"stderr={uploaded_during_session.stderr!r}"
            )
            busy = subprocess.run(
                [cli_executable, "connect", "--url", payload["connect_url"],
                 f"--token={payload['connect_token']}"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            )
            assert busy.returncode != 0 and "已有 TUI 工作階段" in busy.stderr, (
                f"second TUI session was not clearly refused: exit={busy.returncode}, stderr={busy.stderr!r}"
            )
            os.write(terminal_master, b"\x03")
            tui_process.wait(timeout=10)
            tui_process = None
            os.close(terminal_master)

            reconnect_master, reconnect_slave = pty.openpty()
            reconnect = subprocess.Popen(
                [cli_executable, "connect", "--url", payload["connect_url"], f"--token={payload['connect_token']}"],
                stdin=reconnect_slave, stdout=reconnect_slave, stderr=reconnect_slave,
            )
            os.close(reconnect_slave)
            reconnect_output = bytearray()
            reconnect_deadline = time.monotonic() + 20
            while time.monotonic() < reconnect_deadline and reconnect.poll() is None:
                readable, _, _ = select.select([reconnect_master], [], [], 0.2)
                if readable:
                    try:
                        reconnect_output.extend(os.read(reconnect_master, 65536))
                    except OSError:
                        break
                if b"OpenCode" in reconnect_output or b"opencode" in reconnect_output:
                    break
            assert reconnect.poll() is None and (b"OpenCode" in reconnect_output or b"opencode" in reconnect_output), (
                "TUI could not reconnect after the prior session disconnected: "
                f"exit={reconnect.poll()}, output={bytes(reconnect_output[-4000:])!r}"
            )
            os.write(reconnect_master, b"\x03")
            reconnect.wait(timeout=10)
            os.close(reconnect_master)

        uploaded = subprocess.run(
            docker_command("exec", target_id, "cat", "/workspace/project/upload-marker.txt"),
            capture_output=True, text=True,
        )
        assert uploaded.returncode == 0 and uploaded.stdout == marker, (
            f"target container did not contain uploaded marker {marker!r}: "
            f"exit={uploaded.returncode}, stdout={uploaded.stdout!r}, stderr={uploaded.stderr!r}"
        )
        absent = subprocess.run(
            docker_command("exec", second_id, "test", "!", "-e", "/workspace/project/upload-marker.txt"),
            capture_output=True, text=True,
        )
        assert absent.returncode == 0, (
            f"uploaded marker leaked into second container {second_id}: "
            f"stdout={absent.stdout!r}, stderr={absent.stderr!r}"
        )

        deleted = httpx.delete(base_url + f"/api/opencode/containers/{target_id}", headers=headers, timeout=30)
        assert deleted.status_code == 204, f"delete failed: HTTP {deleted.status_code}: {deleted.text}"
        managed_ids.remove(target_id)
        inspect = subprocess.run(docker_command("inspect", target_id), capture_output=True, text=True)
        assert inspect.returncode != 0, (
            f"deleted container {target_id} still exists: stdout={inspect.stdout!r}, stderr={inspect.stderr!r}"
        )
        second_check = subprocess.run(
            docker_command("exec", second_id, "test", "!", "-e", "/workspace/project/upload-marker.txt"),
            capture_output=True, text=True,
        )
        assert second_check.returncode == 0, (
            f"second container changed after target deletion: stderr={second_check.stderr!r}"
        )
    finally:
        if tui_process and tui_process.poll() is None:
            tui_process.terminate()
            tui_process.wait(timeout=10)
        for container_id in managed_ids:
            try:
                response = httpx.delete(base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=30)
                if response.status_code not in (204, 404):
                    subprocess.run(docker_command("rm", "-f", container_id), check=False, capture_output=True)
            except httpx.HTTPError:
                subprocess.run(docker_command("rm", "-f", container_id), check=False, capture_output=True)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@pytest.mark.skipif(os.getenv("OPENCODE_DOCKER_E2E") != "1", reason="requires Docker daemon and Cloudflare Quick Tunnel")
def test_management_api_creates_reachable_opencode_quick_tunnel() -> None:
    api_port = int(os.getenv("OPENCODE_E2E_API_PORT", "18080"))
    admin_token = os.getenv("OPENCODE_ADMIN_TOKEN", "integration-admin-token")
    password = os.getenv("OPENCODE_PASSWORD", "integration-opencode-password")
    env = os.environ | {
        "OPENCODE_ADMIN_TOKEN": admin_token,
        "OPENCODE_PASSWORD": password,
        "OPENCODE_IMAGE": f"dynamic-opencode-e2e:{uuid.uuid4().hex[:8]}",
        "OPENCODE_STARTUP_TIMEOUT": "300",
        "OPENCODE_MAX_CONTAINERS": "20",
        "OPENCODE_TUNNEL_PROBE_INTERVAL": "2",
        "OPENCODE_TUNNEL_FAILURE_THRESHOLD": "2",
        "OPENCODE_TUNNEL_RECOVERY_ATTEMPTS": "3",
        "OPENCODE_TUNNEL_RECOVERY_DELAY": "2",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.App.Main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{api_port}"
    container_id = None
    second_container_id = None
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(base_url + "/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            pytest.fail("backend did not start within 30 seconds")
        response = httpx.post(base_url + "/api/opencode/containers", headers={"Authorization": f"Bearer {admin_token}"}, timeout=360)
        assert response.status_code == 201, response.text
        payload = response.json()
        container_id = payload["id"]
        assert "url" in payload
        assert payload["upload_token"]
        assert payload["upload_url"] == payload["url"].rstrip("/") + "/upload"
        assert password not in response.text
        reachable = _probe_external_url(payload["url"], password)
        assert reachable.status_code == 200
        with tempfile.TemporaryDirectory() as project:
            project_path = os.path.join(project, "upload-marker.txt")
            marker = f"uploaded-{uuid.uuid4().hex}"
            with open(project_path, "w", encoding="utf-8") as source:
                source.write(marker)
            cli_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../cli"))
            subprocess.run(
                ["uv", "pip", "install", "--python", sys.executable, "--quiet", cli_root],
                check=True,
            )
            subprocess.run([
                sys.executable, "-m", "opencode_project.cli", "upload",
                "--url", payload["upload_url"], f"--token={payload['upload_token']}",
                "--project", project,
            ], check=True)
            assert subprocess.run([
                *docker_command("exec", container_id, "cat", "/workspace/project/upload-marker.txt"),
            ], capture_output=True, text=True, check=True).stdout == marker
        second = httpx.post(
            base_url + "/api/opencode/containers", headers={"Authorization": f"Bearer {admin_token}"},
            timeout=360,
        )
        assert second.status_code == 201, second.text
        second_container_id = second.json()["id"]
        assert second_container_id != container_id
        assert subprocess.run([
            *docker_command("exec", second_container_id, "test", "!", "-e"),
            "/workspace/project/upload-marker.txt",
        ], capture_output=True).returncode == 0
        headers = {"Authorization": f"Bearer {admin_token}"}
        invalid_headers = {"Authorization": "Bearer invalid-management-token"}
        for method, path in (
            (httpx.get, "/api/opencode/containers"),
            (httpx.get, f"/api/opencode/containers/{container_id}"),
            (httpx.delete, f"/api/opencode/containers/{container_id}"),
        ):
            for credentials in (None, invalid_headers):
                response = method(
                    base_url + path, headers=credentials, timeout=20,
                )
                assert response.status_code == 401, response.text
        listed = httpx.get(base_url + "/api/opencode/containers", headers=headers, timeout=20)
        assert listed.status_code == 200, listed.text
        assert payload["id"] in {container["id"] for container in listed.json()}
        listed_container = next(container for container in listed.json() if container["id"] == payload["id"])
        assert listed_container["status"] == "healthy"
        assert listed_container["url"] == payload["url"]
        queried = httpx.get(base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=20)
        assert queried.status_code == 200, queried.text
        assert queried.json()["url"] == payload["url"]

        marker = f"tunnel-recovery-{uuid.uuid4().hex}"
        subprocess.run(docker_command("exec", container_id, "sh", "-c", f"printf '%s' '{marker}' >/tmp/opencode-retention-marker"), check=True)
        subprocess.run(docker_command("exec", container_id, "sh", "-c", "pkill -x cloudflared"), check=True)
        deadline = time.monotonic() + 180
        recovered_url = payload["url"]
        while time.monotonic() < deadline:
            current = httpx.get(base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=20)
            assert current.status_code == 200, current.text
            recovered_url = current.json()["url"]
            if recovered_url != payload["url"] and current.json()["status"] == "healthy":
                break
            time.sleep(2)
        else:
            pytest.fail("Tunnel did not recover to a new healthy URL")
        reachable = _probe_external_url(recovered_url, password)
        assert reachable.status_code == 200
        assert subprocess.run(
            docker_command("exec", container_id, "sh", "-c", f"test \"$(cat /tmp/opencode-retention-marker)\" = '{marker}'"),
            capture_output=True,
        ).returncode == 0
        listed_after_recovery = httpx.get(base_url + "/api/opencode/containers", headers=headers, timeout=20).json()
        retained = next(container for container in listed_after_recovery if container["id"] == container_id)
        assert retained["url"] == recovered_url
        assert retained["status"] == "healthy"

        process.terminate()
        process.wait(timeout=10)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.App.Main:app", "--host", "127.0.0.1", "--port", str(api_port)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(base_url + "/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            pytest.fail("backend did not restart within 30 seconds")
        recovered_list = httpx.get(base_url + "/api/opencode/containers", headers=headers, timeout=20)
        assert recovered_list.status_code == 200, recovered_list.text
        assert payload["id"] in {container["id"] for container in recovered_list.json()}
        rediscovered = next(container for container in recovered_list.json() if container["id"] == payload["id"])
        assert rediscovered["url"] == recovered_url

        def query_rediscovered_container() -> dict:
            response = httpx.get(
                base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=20
            )
            assert response.status_code == 200, response.text
            return response.json()

        _wait_for_healthy_container(
            query_rediscovered_container,
            expected_url=recovered_url,
            timeout=30,
            interval=1,
        )

        deleted = httpx.delete(
            base_url + f"/api/opencode/containers/{container_id}",
            headers=headers, timeout=30,
        )
        assert deleted.status_code == 204
        assert subprocess.run(docker_command("inspect", container_id), capture_output=True).returncode != 0
        _assert_tunnel_no_longer_serves(recovered_url, password)
        missing = httpx.delete(
            base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=10,
        )
        assert missing.status_code == 404
    finally:
        if container_id:
            subprocess.run(docker_command("rm", "-f", container_id), check=False, capture_output=True)
        if second_container_id:
            subprocess.run(docker_command("rm", "-f", second_container_id), check=False, capture_output=True)
        process.terminate()
        process.wait(timeout=10)
