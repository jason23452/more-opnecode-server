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

            with zipfile.ZipFile(io.BytesIO(archive)) as project:
                self.assertEqual(project.namelist(), ["main.py"])

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

    def test_upload_reports_single_request_size_limit_before_network_transfer(self):
        from opencode_project.upload import MAX_UPLOAD_BYTES

        with patch("opencode_project.upload._send") as sender:
            with self.assertRaisesRegex(ValueError, "單次上傳上限"):
                upload_archive("https://container.trycloudflare.com/upload", "token", b"x" * (MAX_UPLOAD_BYTES + 1))
        sender.assert_not_called()

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
