from pathlib import Path
import re


WORKFLOWS = Path(__file__).parents[2] / ".github" / "workflows"
ASSETS = {
    "opencode-project-windows-x64.exe",
    "opencode-project-macos-x64",
    "opencode-project-macos-arm64",
    "opencode-project-linux-x64",
    "install.ps1",
    "install.sh",
}


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_dev_workflow_is_tag_only_and_uses_the_dev_tag_pattern():
    content = workflow("cli-dev-release.yml")

    assert re.search(r"(?m)^\s+push:\s*$", content)
    assert re.search(r'(?m)^\s+- "cli-dev-\*"\s*$', content)
    assert not re.search(r"(?m)^\s+branches:\s*$", content)
    assert not re.search(r'(?m)^\s+- "cli-v\*"\s*$', content)


def test_dev_workflow_builds_and_publishes_all_release_assets_after_builds():
    content = workflow("cli-dev-release.yml")

    assert "python -m pytest cli/tests -q" in content
    assert content.count("runner:") == 4
    assert "windows-latest" in content
    assert "macos-15-intel" in content
    assert "macos-15" in content
    assert "ubuntu-latest" in content
    assert "--help" in content
    assert re.search(r"(?ms)^  publish:.*?^    needs: build\s*$", content)
    for asset in ASSETS:
        assert asset in content


def test_dev_release_is_prerelease_and_never_the_latest_release():
    content = workflow("cli-dev-release.yml")

    assert "--prerelease" in content
    assert "--latest=false" in content
    assert "--draft" in content
    assert "--verify-tag" in content


def test_prod_workflow_keeps_its_tag_pattern_and_marks_release_as_latest():
    content = workflow("cli-release.yml")

    assert re.search(r'(?m)^\s+- "cli-v\*"\s*$', content)
    assert not re.search(r'(?m)^\s+- "cli-dev-\*"\s*$', content)
    assert "python -m pytest cli/tests -q" in content
    assert content.count("runner:") == 4
    assert "windows-latest" in content
    assert "macos-15-intel" in content
    assert "macos-15" in content
    assert "ubuntu-latest" in content
    assert "--help" in content
    assert re.search(r"(?ms)^  publish:.*?^    needs: build\s*$", content)
    for asset in ASSETS:
        assert asset in content
    assert "--latest" in content
    assert "--draft" in content
    assert "--verify-tag" in content
    assert not re.search(r"(?m)^\s+--prerelease\s*$", content)
