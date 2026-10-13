from pathlib import Path


def test_opencode_image_installs_process_management_tools() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"

    assert "procps" in dockerfile.read_text()


def test_opencode_image_runs_cloudflared_under_retry_supervisor() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"
    contents = dockerfile.read_text()

    assert "COPY tunnel-supervisor.sh /usr/local/bin/tunnel-supervisor.sh" in contents
    assert "/usr/local/bin/tunnel-supervisor.sh" in contents.split("CMD ", 1)[1]


def test_opencode_image_selects_cloudflared_for_supported_target_architectures() -> None:
    dockerfile = Path(__file__).parents[1] / "src/Features/Opencode/Dockerfile"
    contents = dockerfile.read_text()

    assert "ARG TARGETARCH" in contents
    assert "amd64) cloudflared_arch=amd64" in contents
    assert "arm64) cloudflared_arch=arm64" in contents
    assert "Unsupported TARGETARCH" in contents
    assert "cloudflared-linux-${cloudflared_arch}" in contents


def test_opencode_image_routes_upload_and_normal_http_to_separate_container_services() -> None:
    feature_dir = Path(__file__).parents[1] / "src/Features/Opencode"
    dockerfile = (feature_dir / "Dockerfile").read_text()
    ingress = (feature_dir / "ingress.conf").read_text()

    assert "COPY upload_receiver.py /usr/local/bin/opencode-upload-receiver.py" in dockerfile
    assert "location = /upload" in ingress
    assert "proxy_pass http://127.0.0.1:4097/upload" in ingress
    assert "proxy_pass http://127.0.0.1:4096" in ingress
    assert "client_max_body_size 95m" in ingress
