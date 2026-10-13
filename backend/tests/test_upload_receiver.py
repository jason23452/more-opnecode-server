import io
import zipfile
import pytest

from src.Features.Opencode.upload_receiver import install_archive, UploadSessions


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


def test_chunked_session_installs_only_after_all_verified_chunks(tmp_path, monkeypatch) -> None:
    import src.Features.Opencode.upload_receiver as receiver
    archive = _archive("new.txt", "complete project")
    chunk_size = (len(archive) + 1) // 2
    monkeypatch.setattr(receiver, "CHUNK_BYTES", chunk_size)
    target = tmp_path / "project"
    target.mkdir()
    (target / "old.txt").write_text("keep until finalize")
    sessions = UploadSessions(target, tmp_path / "sessions", max_bytes=100_000)
    session = sessions.create(len(archive), (len(archive) + chunk_size - 1) // chunk_size, __import__("hashlib").sha256(archive).hexdigest())

    sessions.put_chunk(session, 1, archive[chunk_size:], __import__("hashlib").sha256(archive[chunk_size:]).hexdigest())
    assert (target / "old.txt").read_text() == "keep until finalize"
    with pytest.raises(ValueError, match="Missing"):
        sessions.finalize(session)
    sessions.put_chunk(session, 0, archive[:chunk_size], __import__("hashlib").sha256(archive[:chunk_size]).hexdigest())

    sessions.finalize(session)

    assert (target / "new.txt").read_text() == "complete project"
    assert not (target / "old.txt").exists()


def test_chunked_session_retries_identical_chunk_and_rejects_conflict(tmp_path, monkeypatch) -> None:
    import src.Features.Opencode.upload_receiver as receiver
    monkeypatch.setattr(receiver, "CHUNK_BYTES", 3)
    sessions = UploadSessions(tmp_path / "project", tmp_path / "sessions", max_bytes=100)
    session = sessions.create(3, 1, "0" * 64)
    import hashlib
    digest = hashlib.sha256(b"abc").hexdigest()
    sessions.put_chunk(session, 0, b"abc", digest)
    sessions.put_chunk(session, 0, b"abc", digest)
    with pytest.raises(ValueError, match="conflict"):
        sessions.put_chunk(session, 0, b"xyz", hashlib.sha256(b"xyz").hexdigest())


def test_chunked_session_rejects_corrupt_chunk_without_touching_workspace(tmp_path, monkeypatch) -> None:
    import hashlib
    import src.Features.Opencode.upload_receiver as receiver
    monkeypatch.setattr(receiver, "CHUNK_BYTES", 3)
    target = tmp_path / "project"
    target.mkdir()
    (target / "existing.txt").write_text("preserved")
    sessions = UploadSessions(target, tmp_path / "sessions", max_bytes=10)
    session = sessions.create(3, 1, hashlib.sha256(b"abc").hexdigest())

    with pytest.raises(ValueError, match="Corrupt chunk"):
        sessions.put_chunk(session, 0, b"bad", hashlib.sha256(b"abc").hexdigest())

    assert (target / "existing.txt").read_text() == "preserved"
