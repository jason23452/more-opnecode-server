from pathlib import Path
from unittest.mock import MagicMock

from src.Features.Opencode import tui_relay


def test_clipboard_file_frame_is_saved_and_pasted_as_project_file_reference(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tui_relay, "PROJECT", tmp_path / "project")
    content = b"arbitrary-file-content"
    metadata = b'{"name":"screenshot.png","mime_type":"image/png"}'
    frame = tui_relay.CLIPBOARD_FILE_PREFIX + metadata + b"\x00" + content
    stdin = MagicMock()

    handled = tui_relay._handle_clipboard_file(frame, stdin)

    assert handled is True
    file_path = next((tmp_path / "project").glob("clipboard-*-screenshot.png"))
    assert file_path.read_bytes() == content
    stdin.write.assert_called_once_with(
        b"\x1b[200~ @" + file_path.name.encode() + b"\x1b[201~"
    )
    stdin.flush.assert_called_once_with()


def test_clipboard_file_frame_rejects_path_traversal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tui_relay, "PROJECT", tmp_path / "project")
    stdin = MagicMock()
    frame = tui_relay.CLIPBOARD_FILE_PREFIX + b'{"name":"../secret.txt","mime_type":"text/plain"}\x00secret'

    handled = tui_relay._handle_clipboard_file(frame, stdin)

    assert handled is True
    assert not (tmp_path / "project").exists()
    stdin.write.assert_not_called()
