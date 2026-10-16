import json
import logging
import threading
import time
from datetime import datetime
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
_REPOSITORY_RELEASES = "https://api.github.com/repos/jason23452/more-opnecode-server/releases"
_ASSET_NAMES = frozenset({
    "opencode-project-windows-x64.exe",
    "opencode-project-macos-x64",
    "opencode-project-macos-arm64",
    "opencode-project-linux-x64",
    "install.ps1",
    "install.sh",
})


def choose_release(releases: list[dict], channel: str) -> dict:
    if channel not in {"prod", "dev"}:
        raise ValueError("OPENCODE_CLI_CHANNEL must be 'prod' or 'dev'")
    prefix = "cli-v" if channel == "prod" else "cli-dev-"
    eligible = []
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("draft") or not release.get("published_at"):
            continue
        if not tag.startswith(prefix) or (channel == "prod" and release.get("prerelease")):
            continue
        assets = {asset.get("name") for asset in release.get("assets", [])}
        if not _ASSET_NAMES.issubset(assets):
            continue
        published_at = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
        eligible.append((published_at, int(release["id"]), release))
    if not eligible:
        raise LookupError(f"No complete CLI release available for {channel} channel")
    return max(eligible, key=lambda item: (item[0], item[1]))[2]


class CliReleaseSelector:
    def __init__(self, opener=urlopen, clock=time.monotonic, cache_seconds: int = 30):
        self._opener = opener
        self._clock = clock
        self._cache_seconds = min(cache_seconds, 60)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def _request_page(self, page: int) -> list[dict]:
        url = f"{_REPOSITORY_RELEASES}?per_page=100&page={page}"
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "opencode-project"})
        response = self._opener(request, timeout=8)
        if isinstance(response, list):
            return response
        with response:
            return json.load(response)

    def select(self, channel: str) -> dict:
        if channel not in {"prod", "dev"}:
            raise ValueError("OPENCODE_CLI_CHANNEL must be 'prod' or 'dev'")
        with self._lock:
            cached = self._cache.get(channel)
            now = self._clock()
            if cached and now < cached[0]:
                return cached[1]
            releases: list[dict] = []
            page = 1
            try:
                while True:
                    batch = self._request_page(page)
                    releases.extend(batch)
                    if len(batch) < 100:
                        break
                    page += 1
                selected = choose_release(releases, channel)
            except Exception:
                logger.exception("GitHub CLI release lookup failed for %s", channel)
                raise
            self._cache[channel] = (now + self._cache_seconds, selected)
            return selected
