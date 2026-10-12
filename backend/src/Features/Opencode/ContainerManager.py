import re
import subprocess
import threading
import time
from pathlib import Path


class ContainerManager:
    """建立固定規格的 OpenCode 容器與 Quick Tunnel。"""

    def __init__(self, settings):
        self.settings = settings
        self._lock = threading.Lock()

    def create(self) -> dict[str, str]:
        if not self.settings.opencode_password:
            raise RuntimeError("OpenCode password is not configured")
        with self._lock:
            ids = self._docker("ps", "-q", "--filter", "label=dynamic-opencode=true").stdout.splitlines()
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
                logs = self._docker("logs", container_id, check=False).stdout
                urls = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", logs)
                if urls and self._healthy(urls[-1]):
                    return {"id": container_id, "url": urls[-1]}
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
