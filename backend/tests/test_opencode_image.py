from pathlib import Path


def test_opencode_image_installs_process_management_tools() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"

    assert "procps" in dockerfile.read_text()
