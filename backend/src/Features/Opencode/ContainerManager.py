from __future__ import annotations

import io
import re
import secrets
import stat
import subprocess
import textwrap
import threading
import time
import zipfile
from pathlib import Path


class ContainerManager:
    """建立固定規格的 OpenCode 容器與 Quick Tunnel。"""

    def __init__(self, settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._create_lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._latest_urls: dict[str, str] = {}
        self._statuses: dict[str, str] = {}
        self._creating: set[str] = set()
        self._recovering: set[str] = set()
        self._discover()
        self._stop = threading.Event()
        self._monitor = threading.Thread(target=self._monitor_loop, name="opencode-tunnel-monitor", daemon=True)
        self._monitor.start()

    def list(self) -> list[dict[str, str]]:
        return self._discover()

    def get(self, container_id: str) -> dict[str, str] | None:
        return next((container for container in self.list() if container["id"] == container_id), None)

    def _discover(self) -> list[dict[str, str]]:
        result = self._docker("ps", "-aq", "--no-trunc", "--filter", "label=dynamic-opencode=true", check=False)
        if result.returncode != 0:
            return []
        with self._lock:
            creating = set(self._creating)
        containers = []
        for container_id in result.stdout.splitlines():
            if container_id in creating:
                continue
            details = self._inspect(container_id)
            if details is not None:
                containers.append(details)
        present = {container["id"] for container in containers}
        with self._lock:
            self._failures = {key: value for key, value in self._failures.items() if key in present}
            self._latest_urls = {key: value for key, value in self._latest_urls.items() if key in present}
            self._statuses = {key: value for key, value in self._statuses.items() if key in present}
            for container in containers:
                container_id = container["id"]
                container["url"] = self._latest_urls.setdefault(container_id, container["url"])
                container["status"] = self._statuses.setdefault(container_id, container["status"])
            return containers

    def _monitor_loop(self) -> None:
        while not self._stop.wait(max(0.1, self.settings.opencode_tunnel_probe_interval)):
            try:
                self.monitor_once()
            except Exception:
                # A Docker/API transient must not terminate future monitoring.
                continue

    def monitor_once(self) -> None:
        for container in self._discover():
            container_id, url = container["id"], container["url"]
            if not url:
                with self._lock:
                    self._statuses[container_id] = "unhealthy"
                continue
            if self._probe(url):
                with self._lock:
                    self._failures[container_id] = 0
                    self._statuses[container_id] = "healthy"
                continue
            with self._lock:
                failures = self._failures.get(container_id, 0) + 1
                self._failures[container_id] = failures
                should_recover = (
                    failures >= max(1, self.settings.opencode_tunnel_failure_threshold)
                    and container_id not in self._recovering
                )
                if should_recover:
                    self._recovering.add(container_id)
            if not should_recover:
                continue
            try:
                new_url = self._recover_tunnel(container_id, url)
            finally:
                with self._lock:
                    self._recovering.discard(container_id)
            with self._lock:
                if new_url:
                    self._latest_urls[container_id] = new_url
                    self._statuses[container_id] = "healthy"
                    self._failures[container_id] = 0
                    continue
                self._statuses[container_id] = "unhealthy"

    def _recover_tunnel(self, container_id: str, old_url: str) -> str:
        command = "rm -f /tmp/opencode-tunnel-url; : >/tmp/cloudflared.log; pkill -x cloudflared || true"
        restart = self._docker("exec", container_id, "sh", "-c", command, check=False)
        if restart.returncode != 0:
            return ""
        for attempt in range(max(1, self.settings.opencode_tunnel_recovery_attempts)):
            recovered_url = self._wait_for_recovered_tunnel(container_id, old_url)
            if recovered_url:
                return recovered_url
            if attempt + 1 < self.settings.opencode_tunnel_recovery_attempts:
                time.sleep(self.settings.opencode_tunnel_recovery_delay)
        return ""

    def _wait_for_recovered_tunnel(self, container_id: str, old_url: str) -> str:
        deadline = time.monotonic() + min(30, max(1, self.settings.opencode_startup_timeout))
        while time.monotonic() < deadline:
            url = self._read_tunnel_url(container_id, include_container_logs=False)
            if url and url != old_url and self._probe(url):
                self._persist_tunnel_url(container_id, url)
                return url
            time.sleep(0.5)
        return ""

    def _read_tunnel_url(self, container_id: str, include_container_logs: bool = True) -> str:
        result = self._docker("exec", container_id, "sh", "-c", "cat /tmp/cloudflared.log", check=False)
        output = result.stdout
        if include_container_logs and not output:
            output = self._docker("logs", container_id, check=False).stdout
        urls = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", output)
        if urls:
            return urls[-1]
        persisted = self._docker("exec", container_id, "sh", "-c", "cat /tmp/opencode-tunnel-url", check=False)
        persisted_urls = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", persisted.stdout)
        return persisted_urls[-1] if persisted_urls else ""

    def _persist_tunnel_url(self, container_id: str, url: str) -> None:
        try:
            self._docker(
                "exec", container_id, "sh", "-c", f"printf '%s' '{url}' > /tmp/opencode-tunnel-url",
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            # URL persistence is best-effort; the in-memory manager remains usable.
            return

    def _probe(self, url: str) -> bool:
        return self._healthy(url)

    def _inspect(self, container_id: str) -> dict[str, str] | None:
        with self._lock:
            cached_status = self._statuses.get(container_id)
            cached_url = self._latest_urls.get(container_id)
        state = self._docker("inspect", "-f", "{{.State.Running}}", container_id, check=False)
        if state.returncode != 0:
            return None
        url = self._read_tunnel_url(container_id)
        if cached_status is not None:
            return {
                "id": container_id,
                "status": cached_status,
                "url": cached_url or url,
            }
        healthy = state.stdout.strip() == "true" and bool(url) and self._healthy(url)
        return {"id": container_id, "status": "healthy" if healthy else "unhealthy", "url": url}

    def create(self) -> dict[str, str]:
        if not self.settings.opencode_password:
            raise RuntimeError("OpenCode password is not configured")
        with self._create_lock:
            ids = self._docker("ps", "-q", "--no-trunc", "--filter", "label=dynamic-opencode=true").stdout.splitlines()
            if len(ids) >= self.settings.opencode_max_containers:
                raise RuntimeError("container capacity reached")
            self._ensure_image()
            upload_token = secrets.token_urlsafe(32)
            container_id = self._docker(
                "run", "-d", "--label", "dynamic-opencode=true",
                "--label", f"dynamic-opencode-upload-token={upload_token}",
                "--cpus", str(self.settings.opencode_container_cpu),
                "--memory", self.settings.opencode_container_memory,
                "-e", f"OPENCODE_SERVER_PASSWORD={self.settings.opencode_password}",
                "-e", f"OPENCODE_TUNNEL_RETRY_INITIAL_DELAY={self.settings.opencode_tunnel_retry_initial_delay}",
                "-e", f"OPENCODE_TUNNEL_RETRY_MAX_DELAY={self.settings.opencode_tunnel_retry_max_delay}",
                self.settings.opencode_image,
            ).stdout.strip()
            with self._lock:
                self._creating.add(container_id)
        deadline = time.monotonic() + self.settings.opencode_startup_timeout
        try:
            while time.monotonic() < deadline:
                url = self._read_tunnel_url(container_id)
                if url and self._healthy(url):
                    with self._lock:
                        self._latest_urls[container_id] = url
                        self._statuses[container_id] = "healthy"
                        self._failures[container_id] = 0
                        self._creating.discard(container_id)
                    self._persist_tunnel_url(container_id, url)
                    return {"id": container_id, "url": url, "upload_token": upload_token}
                running = self._docker("inspect", "-f", "{{.State.Running}}", container_id, check=False)
                if running.returncode != 0 or running.stdout.strip() != "true":
                    break
                time.sleep(1)
            raise RuntimeError("OpenCode container did not become ready before timeout")
        except Exception:
            self._docker("rm", "-f", container_id, check=False)
            with self._lock:
                self._creating.discard(container_id)
                self._latest_urls.pop(container_id, None)
                self._statuses.pop(container_id, None)
                self._failures.pop(container_id, None)
            raise

    def upload(self, container_id: str, token: str, archive: bytes) -> None:
        managed = self._docker(
            "inspect", "-f", '{{ index .Config.Labels "dynamic-opencode-upload-token" }}',
            container_id, check=False,
        )
        if managed.returncode != 0:
            raise LookupError("managed container not found")
        expected = managed.stdout.strip()
        if not expected:
            raise LookupError("managed container not found")
        if not secrets.compare_digest(token, expected):
            raise PermissionError("invalid upload token")
        try:
            with zipfile.ZipFile(io.BytesIO(archive)) as project:
                entries = project.infolist()
                if len(entries) > 100_000 or sum(item.file_size for item in entries) > 2 * 1024**3:
                    raise ValueError("project archive exceeds extraction limits")
                for item in entries:
                    relative = Path(item.filename)
                    mode = item.external_attr >> 16
                    if relative.is_absolute() or ".." in relative.parts or stat.S_ISLNK(mode):
                        raise ValueError("unsafe project archive path")
        except zipfile.BadZipFile as error:
            raise ValueError("invalid zip archive") from error
        extractor = textwrap.dedent("""
            import os, pathlib, shutil, stat, sys, tempfile, zipfile
            target = pathlib.Path('/workspace/project')
            parent = target.parent
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile() as streamed_archive:
                shutil.copyfileobj(sys.stdin.buffer, streamed_archive)
                streamed_archive.seek(0)
                with zipfile.ZipFile(streamed_archive) as archive:
                    entries = archive.infolist()
                    if len(entries) > 100_000 or sum(item.file_size for item in entries) > 2 * 1024**3:
                        raise ValueError('project archive exceeds extraction limits')
                    checked = []
                    for item in entries:
                        relative = pathlib.PurePosixPath(item.filename)
                        mode = item.external_attr >> 16
                        if relative.is_absolute() or '..' in relative.parts or stat.S_ISLNK(mode):
                            raise ValueError('unsafe project archive path')
                        checked.append((item, relative))
                    staging = pathlib.Path(tempfile.mkdtemp(prefix='.project-upload-', dir=parent))
                    try:
                        for item, relative in checked:
                            destination = staging.joinpath(*relative.parts)
                            destination.resolve().relative_to(staging.resolve())
                            if item.is_dir():
                                destination.mkdir(parents=True, exist_ok=True)
                            else:
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                destination.write_bytes(archive.read(item))
                        if target.exists():
                            shutil.rmtree(target)
                        os.replace(staging, target)
                    finally:
                        if staging.exists():
                            shutil.rmtree(staging)
        """).strip()
        result = subprocess.run(
            ["docker", "exec", "-i", container_id, "python3", "-c", extractor],
            input=archive, capture_output=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError("project archive could not be written into container workspace")

    def delete(self, container_id: str) -> None:
        managed = self._docker(
            "inspect", "-f", "{{ index .Config.Labels \"dynamic-opencode\" }}",
            container_id, check=False,
        )
        if managed.returncode != 0 or managed.stdout.strip() != "true":
            raise LookupError("managed container not found")
        # Removing the container terminates its in-container cloudflared process
        # and deletes its container-local ephemeral work data.
        self._docker("rm", "-f", container_id)
        with self._lock:
            self._latest_urls.pop(container_id, None)
            self._statuses.pop(container_id, None)
            self._failures.pop(container_id, None)
            self._recovering.discard(container_id)

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
