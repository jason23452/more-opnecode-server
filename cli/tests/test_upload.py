import io
import zipfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opencode_project.upload import create_archive, upload_archive


class UploadTests(unittest.TestCase):
    def test_archive_omits_default_build_and_dependency_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "main.py").write_text("print('hello')")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "package.js").write_text("large")
            (root / "dist").mkdir()
            (root / "dist" / "bundle.js").write_text("large")

            archive = create_archive(root)
            try:
                with zipfile.ZipFile(archive) as project:
                    self.assertEqual(project.namelist(), ["main.py"])
            finally:
                archive.unlink()

    def test_upload_retries_failed_transfer_using_same_container_capability(self):
        responses = [OSError("connection interrupted"), 204]

        def send(*args, **kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch("opencode_project.upload._send", side_effect=send) as sender:
            upload_archive("https://api.example/upload", "private-token", b"archive", retries=2)

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(sender.call_args_list[0].args, sender.call_args_list[1].args)

    def test_archive_above_single_request_limit_uses_chunk_protocol(self):
        import json
        with patch("opencode_project.upload._request", side_effect=[
            json.dumps({"session_id": "a" * 32}).encode(), b"", b"", b"", b"",
        ]) as request, patch("opencode_project.upload.CHUNK_BYTES", 32 * 1024 * 1024):
            from opencode_project.upload import MAX_UPLOAD_BYTES
            upload_archive("https://container.trycloudflare.com/upload", "token", b"x" * (MAX_UPLOAD_BYTES + 1))
        self.assertEqual(request.call_count, 5)

    def test_large_archive_is_chunked_and_refreshes_tunnel_target_after_failure(self):
        import json
        import opencode_project.upload as upload
        monkey = unittest.mock.patch.multiple(upload, MAX_UPLOAD_BYTES=4, CHUNK_BYTES=3)
        with monkey, patch("opencode_project.upload._request") as request, \
                patch("opencode_project.upload._refresh_target", return_value="https://new.example") as refresh, \
                patch("opencode_project.upload.time.sleep"):
            request.side_effect = [
                json.dumps({"session_id": "a" * 32}).encode(),
                OSError("old Tunnel failed"), b"", b"", b"", b"",
            ]
            upload.upload_archive("https://old.example/upload", "token", b"abcdefgh", retries=2,
                                  refresh_url="https://control/upload-target")

        refresh.assert_called_once_with("https://control/upload-target", "token")
        chunk_calls = [call for call in request.call_args_list if "/chunks/" in call.args[0]]
        self.assertEqual([call.args[0].rsplit("/", 1)[1] for call in chunk_calls], ["0", "0", "1", "2"])
        self.assertTrue(all("api" not in call.args[0] for call in chunk_calls))
        session_payload = json.loads(request.call_args_list[0].args[2])
        self.assertRegex(session_payload["session_id"], r"^[0-9a-f]{32}$")

    def test_refresh_target_normalizes_upload_endpoint_to_tunnel_root(self):
        import json
        from opencode_project.upload import _refresh_target
        with patch("opencode_project.upload._request", return_value=json.dumps({
            "upload_url": "https://fresh.example/upload",
        }).encode()):
            self.assertEqual(_refresh_target("https://control/target", "token"), "https://fresh.example")

    def test_lost_session_creation_response_retries_with_same_idempotency_metadata(self):
        import json
        import opencode_project.upload as upload
        with patch.multiple(upload, MAX_UPLOAD_BYTES=1, CHUNK_BYTES=3), \
                patch("opencode_project.upload._request") as request, \
                patch("opencode_project.upload.time.sleep"):
            request.side_effect = [OSError("response lost"), json.dumps({"session_id": "f" * 32}).encode(), b"", b"", b""]
            upload.upload_archive("https://container/upload", "token", b"abcd", retries=2)
        first, retry = (json.loads(call.args[2]) for call in request.call_args_list[:2])
        self.assertEqual(first, retry)

    def test_connect_relays_terminal_input_and_displays_remote_output(self):
        from opencode_project.connect import connect_terminal

        remote = unittest.mock.MagicMock()
        remote.__enter__.return_value = remote
        remote.recv.side_effect = [b"remote TUI", KeyboardInterrupt()]
        with patch("opencode_project.connect.websocket_connect", return_value=remote) as connector, \
                patch("opencode_project.connect._terminal_input", return_value=None):
            connect_terminal("ws://api/connect", "scoped-token")
        connector.assert_called_once_with(
            "ws://api/connect", additional_headers={"Authorization": "Bearer scoped-token"},
            max_size=None, ping_interval=20,
        )
        self.assertEqual(remote.recv.call_count, 2)

    def test_upload_then_connect_only_connects_after_successful_upload(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.upload_archive") as upload, \
                patch("opencode_project.cli.connect_terminal") as connect, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://api/upload",
                                    "--token", "upload-token", "--project", ".", "--connect-url",
                                    "wss://api/connect", "--connect-token", "connect-token"]):
            main()
        self.assertLess(upload.call_count, 2)
        connect.assert_called_once_with("wss://api/connect", "connect-token")


if __name__ == "__main__":
    unittest.main()
