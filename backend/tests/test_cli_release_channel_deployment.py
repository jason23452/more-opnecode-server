from pathlib import Path
import re


ROOT = Path(__file__).parents[2]


def test_compose_passes_the_cli_channel_with_a_production_default() -> None:
    for name in ("compose.local.yaml", "docker-compose.prod.yaml"):
        compose = (ROOT / name).read_text(encoding="utf-8")

        assert re.search(
            r"(?m)^\s+OPENCODE_CLI_CHANNEL:\s*\$\{OPENCODE_CLI_CHANNEL:-prod\}\s*$",
            compose,
        ), name
        assert "OPENCODE_CLI_RELEASE_URL" not in compose, name


def test_env_example_documents_local_dev_without_a_custom_release_url() -> None:
    example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")

    assert "OPENCODE_CLI_CHANNEL=dev" in example
    assert "OPENCODE_CLI_RELEASE_URL" not in example


def test_backend_docs_explain_channel_selection_and_release_url_migration() -> None:
    docs = (ROOT / "backend" / "README.md").read_text(encoding="utf-8")

    for expected in (
        "OPENCODE_CLI_CHANNEL",
        "預設為 `prod`",
        "`cli-v*`",
        "`cli-dev-*`",
        "OPENCODE_CLI_RELEASE_URL",
        "不再",
        "60 秒",
        "503",
    ):
        assert expected in docs


def test_cli_docs_explain_release_channels_and_manual_update() -> None:
    docs = (ROOT / "cli" / "README.md").read_text(encoding="utf-8")

    for expected in ("cli-v*", "cli-dev-*", "Pre-release", "重新取得", "執行該通道提供的安裝指令"):
        assert expected in docs
