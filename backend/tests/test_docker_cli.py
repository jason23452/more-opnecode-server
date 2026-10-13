from src.Features.Opencode import DockerCli


def test_docker_cli_uses_docker_exe_under_wsl_when_available(monkeypatch) -> None:
    monkeypatch.setattr(DockerCli, "is_wsl", lambda: True)
    monkeypatch.setattr(DockerCli.shutil, "which", lambda name: {
        "docker.exe": "/mnt/c/Program Files/Docker/docker.exe",
        "docker": None,
    }.get(name))

    assert DockerCli.docker_command("ps", "-q") == ["/mnt/c/Program Files/Docker/docker.exe", "ps", "-q"]


def test_docker_cli_uses_native_docker_outside_wsl(monkeypatch) -> None:
    monkeypatch.setattr(DockerCli, "is_wsl", lambda: False)
    monkeypatch.setattr(DockerCli.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)

    assert DockerCli.docker_command("ps", "-q") == ["/usr/bin/docker", "ps", "-q"]


def test_docker_cli_converts_wsl_build_context(monkeypatch) -> None:
    monkeypatch.setattr(DockerCli, "is_wsl", lambda: True)
    monkeypatch.setattr(DockerCli.shutil, "which", lambda name: "/usr/bin/docker.exe" if name == "docker.exe" else None)
    monkeypatch.setattr(DockerCli, "docker_path", lambda path: r"\\wsl.localhost\Ubuntu" + path.replace("/", "\\"))

    command = DockerCli.docker_command("build", "-f", "/repo/Dockerfile", "/repo")

    assert command == ["/usr/bin/docker.exe", "build", "-f", r"\\wsl.localhost\Ubuntu\repo\Dockerfile", r"\\wsl.localhost\Ubuntu\repo"]
