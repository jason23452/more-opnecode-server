import io
import zipfile

from src.Features.Opencode.upload_receiver import install_archive


def _archive(name: str, content: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, content)
    return output.getvalue()


def test_receiver_replaces_project_only_after_safe_archive_is_installed(tmp_path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / "previous.txt").write_text("preserve me")

    install_archive(_archive("new.txt", "new project"), target)

    assert (target / "new.txt").read_text() == "new project"
    assert not (target / "previous.txt").exists()


def test_receiver_rejects_unsafe_archive_without_changing_existing_project(tmp_path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / "previous.txt").write_text("preserve me")

    try:
        install_archive(_archive("../outside.txt", "unsafe"), target)
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")

    assert (target / "previous.txt").read_text() == "preserve me"
    assert not (tmp_path / "outside.txt").exists()


def test_receiver_rejects_upload_over_single_request_limit(tmp_path) -> None:
    try:
        install_archive(b"x" * 11, tmp_path / "project", max_bytes=10)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("oversized archive must be rejected")
    assert not (tmp_path / "project").exists()
