"""Opt-in black-box test requiring Docker and outbound Cloudflare access."""

import os
import subprocess
import sys
import time
import uuid

import httpx
import pytest


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
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.App.Main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{api_port}"
    container_id = None
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
        assert password not in response.text
        reachable = httpx.get(payload["url"] + "/", auth=("opencode", password), timeout=20)
        assert reachable.status_code == 200
        headers = {"Authorization": f"Bearer {admin_token}"}
        listed = httpx.get(base_url + "/api/opencode/containers", headers=headers, timeout=20)
        assert listed.status_code == 200, listed.text
        assert payload["id"] in {container["id"] for container in listed.json()}
        listed_container = next(container for container in listed.json() if container["id"] == payload["id"])
        assert listed_container["status"] == "healthy"
        assert listed_container["url"] == payload["url"]
        queried = httpx.get(base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=20)
        assert queried.status_code == 200, queried.text
        assert queried.json()["url"] == payload["url"]

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
        assert rediscovered["status"] == "healthy"
        assert rediscovered["url"] == payload["url"]
        recovered_query = httpx.get(
            base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=20
        )
        assert recovered_query.status_code == 200, recovered_query.text
        assert recovered_query.json()["url"] == payload["url"]

        deleted = httpx.delete(
            base_url + f"/api/opencode/containers/{container_id}",
            headers=headers, timeout=30,
        )
        assert deleted.status_code == 204
        assert subprocess.run(["docker", "inspect", container_id], capture_output=True).returncode != 0
        with pytest.raises(httpx.HTTPError):
            httpx.get(payload["url"] + "/", auth=("opencode", password), timeout=10)
        missing = httpx.delete(
            base_url + f"/api/opencode/containers/{container_id}", headers=headers, timeout=10,
        )
        assert missing.status_code == 404
    finally:
        if container_id:
            subprocess.run(["docker", "rm", "-f", container_id], check=False, capture_output=True)
        process.terminate()
        process.wait(timeout=10)
