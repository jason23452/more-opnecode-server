from pathlib import Path


def test_opencode_image_installs_process_management_tools() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"

    assert "procps" in dockerfile.read_text()


def test_opencode_image_selects_cloudflared_for_supported_target_architectures() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"
    contents = dockerfile.read_text()

    assert "ARG TARGETARCH" in contents
    assert "amd64) cloudflared_arch=amd64" in contents
    assert "arm64) cloudflared_arch=arm64" in contents
    assert "Unsupported TARGETARCH" in contents
    assert "cloudflared-linux-${cloudflared_arch}" in contents
