from __future__ import annotations

import re
import subprocess
import threading
import time
from pathlib import Path


class ContainerManager:
    """建立固定規格的 OpenCode 容器與 Quick Tunnel。"""

    def __init__(self, settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._failures: dict[str, int] = {}
        self._latest_urls: dict[str, str] = {}
        self._statuses: dict[str, str] = {}
        self._discover()
        self._stop = threading.Event()
        self._monitor = threading.Thread(target=self._monitor_loop, name="opencode-tunnel-monitor", daemon=True)
        self._monitor.start()

    def list(self) -> list[dict[str, str]]:
        with self._lock:
            return self._discover()

    def get(self, container_id: str) -> dict[str, str] | None:
        return next((container for container in self.list() if container["id"] == container_id), None)

    def _discover(self) -> list[dict[str, str]]:
        result = self._docker("ps", "-aq", "--no-trunc", "--filter", "label=dynamic-opencode=true", check=False)
        if result.returncode != 0:
            return []
        containers = []
        for container_id in result.stdout.splitlines():
            details = self._inspect(container_id)
            if details is not None:
                details["url"] = self._latest_urls.get(container_id, details["url"])
                details["status"] = self._statuses.get(container_id, details["status"])
                self._latest_urls[container_id] = details["url"]
                self._statuses[container_id] = details["status"]
                containers.append(details)
        present = {container["id"] for container in containers}
        self._failures = {key: value for key, value in self._failures.items() if key in present}
        self._latest_urls = {key: value for key, value in self._latest_urls.items() if key in present}
        self._statuses = {key: value for key, value in self._statuses.items() if key in present}
        return containers

    def _monitor_loop(self) -> None:
        while not self._stop.wait(max(0.1, self.settings.opencode_tunnel_probe_interval)):
            try:
                self.monitor_once()
            except Exception:
                # A Docker/API transient must not terminate future monitoring.
                continue

    def monitor_once(self) -> None:
        with self._lock:
            for container in self._discover():
                container_id, url = container["id"], container["url"]
                if not url:
                    self._statuses[container_id] = "unhealthy"
                    continue
                if self._probe(url):
                    self._failures[container_id] = 0
                    self._statuses[container_id] = "healthy"
                    continue
                failures = self._failures.get(container_id, 0) + 1
                self._failures[container_id] = failures
                if failures < max(1, self.settings.opencode_tunnel_failure_threshold):
                    continue
                new_url = self._recover_tunnel(container_id, url)
                if new_url:
                    self._latest_urls[container_id] = new_url
                    self._statuses[container_id] = "healthy"
                    self._failures[container_id] = 0
                    continue
                self._statuses[container_id] = "unhealthy"

    def _recover_tunnel(self, container_id: str, old_url: str) -> str:
        command = "pkill cloudflared || true; : >/tmp/cloudflared.log; cloudflared tunnel --url http://127.0.0.1:4096 >/tmp/cloudflared.log 2>&1 &"
        for attempt in range(max(1, self.settings.opencode_tunnel_recovery_attempts)):
            result = self._docker("exec", container_id, "sh", "-c", command, check=False)
            if result.returncode == 0:
                return self._wait_for_recovered_tunnel(container_id, old_url)
            if attempt + 1 < self.settings.opencode_tunnel_recovery_attempts:
                time.sleep(self.settings.opencode_tunnel_recovery_delay)
        return ""

    def _wait_for_recovered_tunnel(self, container_id: str, old_url: str) -> str:
        deadline = time.monotonic() + min(30, max(1, self.settings.opencode_startup_timeout))
        while time.monotonic() < deadline:
            url = self._read_tunnel_url(container_id, include_container_logs=False)
            if url and url != old_url and self._probe(url):
                return url
            time.sleep(0.5)
        return ""

    def _read_tunnel_url(self, container_id: str, include_container_logs: bool = True) -> str:
        result = self._docker("exec", container_id, "sh", "-c", "cat /tmp/cloudflared.log", check=False)
        output = result.stdout
        if include_container_logs and not output:
            output = self._docker("logs", container_id, check=False).stdout
        urls = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", output)
        return urls[-1] if urls else ""

    def _probe(self, url: str) -> bool:
        return self._healthy(url)

    def _inspect(self, container_id: str) -> dict[str, str] | None:
        state = self._docker("inspect", "-f", "{{.State.Running}}", container_id, check=False)
        if state.returncode != 0:
            return None
        url = self._read_tunnel_url(container_id)
        healthy = state.stdout.strip() == "true" and bool(url) and self._healthy(url)
        return {"id": container_id, "status": "healthy" if healthy else "unhealthy", "url": url}

    def create(self) -> dict[str, str]:
        if not self.settings.opencode_password:
            raise RuntimeError("OpenCode password is not configured")
        with self._lock:
            ids = self._docker("ps", "-q", "--no-trunc", "--filter", "label=dynamic-opencode=true").stdout.splitlines()
            if len(ids) >= self.settings.opencode_max_containers:
                raise RuntimeError("container capacity reached")
            self._ensure_image()
            container_id = self._docker(
                "run", "-d", "--label", "dynamic-opencode=true",
                "--cpus", str(self.settings.opencode_container_cpu),
                "--memory", self.settings.opencode_container_memory,
                "-e", f"OPENCODE_SERVER_PASSWORD={self.settings.opencode_password}",
                self.settings.opencode_image,
            ).stdout.strip()
        deadline = time.monotonic() + self.settings.opencode_startup_timeout
        try:
            while time.monotonic() < deadline:
                url = self._read_tunnel_url(container_id)
                if url and self._healthy(url):
                    return {"id": container_id, "url": url}
                running = self._docker("inspect", "-f", "{{.State.Running}}", container_id, check=False)
                if running.returncode != 0 or running.stdout.strip() != "true":
                    break
                time.sleep(1)
            raise RuntimeError("OpenCode container did not become ready before timeout")
        except Exception:
            self._docker("rm", "-f", container_id, check=False)
            raise

    def delete(self, container_id: str) -> None:
        with self._lock:
            managed = self._docker(
                "inspect", "-f", "{{ index .Config.Labels \"dynamic-opencode\" }}",
                container_id, check=False,
            )
            if managed.returncode != 0 or managed.stdout.strip() != "true":
                raise LookupError("managed container not found")
            # Removing the container terminates its in-container cloudflared process
            # and deletes its container-local ephemeral work data.
            self._docker("rm", "-f", container_id)

    def _healthy(self, url: str) -> bool:
        try:
            response = subprocess.run(
                ["curl", "-fsS", "-u", f"opencode:{self.settings.opencode_password}", "--max-time", "5", url + "/"],
                capture_output=True, text=True, timeout=7,
            )
            return response.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def close(self) -> None:
        self._stop.set()
        if hasattr(self, "_monitor"):
            self._monitor.join(timeout=2)

    def _ensure_image(self) -> None:
        exists = self._docker("image", "inspect", self.settings.opencode_image, check=False)
        if exists.returncode != 0:
            dockerfile = Path(__file__).with_name("Dockerfile")
            self._docker("build", "-t", self.settings.opencode_image, "-f", str(dockerfile), str(dockerfile.parent), timeout=None)

    @staticmethod
    def _docker(*args: str, check: bool = True, timeout: int | None = 30) -> subprocess.CompletedProcess:
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Docker command failed")
        return result
