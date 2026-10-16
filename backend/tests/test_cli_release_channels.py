from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.App.Main import app
from src.App.Settings import Settings
from src.Features.Opencode.ContainerManager import ContainerManager


client = TestClient(app)
TOKEN = {"Authorization": "Bearer admin-secret"}
ASSETS = [
    "opencode-project-windows-x64.exe",
    "opencode-project-macos-x64",
    "opencode-project-macos-arm64",
    "opencode-project-linux-x64",
    "install.ps1",
    "install.sh",
]


def release(tag: str, release_id: int, published: str, *, prerelease: bool = False,
            draft: bool = False, assets: list[str] | None = None) -> dict:
    return {
        "id": release_id,
        "tag_name": tag,
        "published_at": published,
        "prerelease": prerelease,
        "draft": draft,
        "assets": [{"name": name} for name in (ASSETS if assets is None else assets)],
    }


class StubReleaseSelector:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error
        self.channels: list[str] = []

    def select(self, channel: str) -> dict:
        self.channels.append(channel)
        if self.error:
            raise self.error
        return self.value


@pytest.fixture(autouse=True)
def restore_app_state():
    previous_settings = app.state.settings
    previous_manager = app.state.container_manager
    previous_selector = getattr(app.state, "cli_release_selector", None)
    yield
    app.state.settings = previous_settings
    app.state.container_manager = previous_manager
    if previous_selector is None:
        if hasattr(app.state, "cli_release_selector"):
            del app.state.cli_release_selector
    else:
        app.state.cli_release_selector = previous_selector


def test_cli_channel_defaults_to_prod_and_rejects_unknown_value(monkeypatch) -> None:
    monkeypatch.delenv("OPENCODE_CLI_CHANNEL", raising=False)
    assert Settings(_env_file=None).opencode_cli_channel == "prod"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, opencode_cli_channel="staging")


def test_install_command_api_uses_selected_release_and_keeps_scripts_on_same_tag() -> None:
    selected = release("cli-dev-20261016.1", 42, "2026-10-16T10:00:00Z", prerelease=True)
    selector = StubReleaseSelector(selected)
    app.state.settings = Settings(opencode_admin_token="admin-secret", opencode_cli_channel="dev")
    app.state.cli_release_selector = selector

    response = client.get("/api/opencode/cli-install-command?environment=linux", headers=TOKEN)

    assert response.status_code == 200
    assert response.json() == {
        "environment": "linux",
        "command": (
            "curl -fsSL 'https://github.com/jason23452/more-opnecode-server/releases/download/"
            "cli-dev-20261016.1/install.sh' | OPENCODE_PROJECT_RELEASE_URL="
            "'https://github.com/jason23452/more-opnecode-server/releases/download/"
            "cli-dev-20261016.1' sh"
        ),
    }
    assert selector.channels == ["dev"]


def test_container_creation_resolves_release_before_creating_container() -> None:
    selector = StubReleaseSelector(error=RuntimeError("GitHub unavailable"))
    manager = Mock(spec=ContainerManager)
    app.state.settings = Settings(opencode_admin_token="admin-secret")
    app.state.cli_release_selector = selector
    app.state.container_manager = manager

    response = client.post("/api/opencode/containers", headers=TOKEN)

    assert response.status_code == 503
    manager.create.assert_not_called()


def test_release_selection_ignores_other_channel_drafts_and_incomplete_assets() -> None:
    from src.Features.Opencode.CliReleases import choose_release

    releases = [
        release("cli-v9.0", 99, "2026-10-16T12:00:00Z", prerelease=True),
        release("cli-v8.0", 80, "2026-10-16T11:00:00Z", prerelease=True),
        release("cli-v7.0", 70, "2026-10-16T10:00:00Z", draft=True),
        release("cli-v6.0", 60, "2026-10-16T09:00:00Z", assets=ASSETS[:-1]),
        release("cli-v5.0", 50, "2026-10-16T08:00:00Z"),
        release("cli-dev-10", 100, "2026-10-16T13:00:00Z", prerelease=True),
    ]

    assert choose_release(releases, "prod")["tag_name"] == "cli-v5.0"
    assert choose_release(releases, "dev")["tag_name"] == "cli-dev-10"


def test_release_selection_sorts_by_published_at_then_release_id() -> None:
    from src.Features.Opencode.CliReleases import choose_release

    releases = [
        release("cli-v100", 10, "2026-10-16T11:00:00Z"),
        release("cli-v2", 11, "2026-10-16T11:00:00Z"),
        release("cli-v999", 12, "2026-10-16T10:00:00Z"),
    ]

    assert choose_release(releases, "prod")["id"] == 11


def test_release_selector_reads_all_pages_when_initial_page_has_no_channel_match(monkeypatch) -> None:
    from src.Features.Opencode.CliReleases import CliReleaseSelector

    pages = {
        "https://api.github.com/repos/jason23452/more-opnecode-server/releases?per_page=100&page=1": [
            release("cli-v1", i, f"2026-10-16T{i % 24:02d}:00:00Z") for i in range(100)
        ],
        "https://api.github.com/repos/jason23452/more-opnecode-server/releases?per_page=100&page=2": [
            release("cli-dev-1", 101, "2026-10-16T12:00:00Z", prerelease=True)
        ],
    }
    opener = Mock(side_effect=lambda request, timeout: pages[request.full_url])
    selector = CliReleaseSelector(opener=opener, clock=lambda: 0)

    assert selector.select("dev")["tag_name"] == "cli-dev-1"
    assert opener.call_count == 2


def test_release_selector_caches_per_channel_and_refreshes_after_expiry() -> None:
    from src.Features.Opencode.CliReleases import CliReleaseSelector

    now = [0.0]
    responses = [
        [release("cli-v1", 1, "2026-10-16T10:00:00Z")],
        [
            release("cli-v2", 2, "2026-10-16T11:00:00Z"),
            release("cli-dev-1", 3, "2026-10-16T12:00:00Z", prerelease=True),
        ],
        [
            release("cli-v3", 4, "2026-10-16T13:00:00Z"),
            release("cli-dev-1", 3, "2026-10-16T12:00:00Z", prerelease=True),
        ],
    ]
    opener = Mock(side_effect=responses)
    selector = CliReleaseSelector(opener=opener, clock=lambda: now[0], cache_seconds=60)

    assert selector.select("prod")["tag_name"] == "cli-v1"
    assert selector.select("prod")["tag_name"] == "cli-v1"
    assert selector.select("dev")["tag_name"] == "cli-dev-1"
    now[0] = 61
    assert selector.select("prod")["tag_name"] == "cli-v3"
    assert opener.call_count == 3


def test_release_selector_does_not_serve_expired_release_when_refresh_fails() -> None:
    from src.Features.Opencode.CliReleases import CliReleaseSelector

    now = [0.0]
    opener = Mock(side_effect=[
        [release("cli-v1", 1, "2026-10-16T10:00:00Z")],
        RuntimeError("GitHub rate limited"),
    ])
    selector = CliReleaseSelector(opener=opener, clock=lambda: now[0])
    assert selector.select("prod")["tag_name"] == "cli-v1"
    now[0] = 31

    with pytest.raises(RuntimeError, match="rate limited"):
        selector.select("prod")


def test_release_selection_failure_returns_503_and_does_not_cross_channels() -> None:
    selector = StubReleaseSelector(error=RuntimeError("no eligible release"))
    app.state.settings = Settings(opencode_admin_token="admin-secret", opencode_cli_channel="prod")
    app.state.cli_release_selector = selector

    response = client.get("/api/opencode/cli-install-command?environment=mac", headers=TOKEN)

    assert response.status_code == 503
    assert selector.channels == ["prod"]
