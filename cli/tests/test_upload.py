import io
import os
import subprocess
import sys
import zipfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opencode_project.upload import create_archive, upload_archive


class UploadTests(unittest.TestCase):
    def test_help_uses_unicode_output_when_system_encoding_cannot_render_chinese(self):
        environment = os.environ | {"PYTHONIOENCODING": "cp1252"}
        result = subprocess.run(
            [sys.executable, "-m", "opencode_project.cli", "--help"],
            cwd=Path(__file__).parents[1], env=environment,
            capture_output=True, text=True, encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("上傳專案資料夾", result.stdout)

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

    def test_stale_tunnel_failure_explains_manual_management_query_and_reuse_of_token(self):
        with patch("opencode_project.upload._send", side_effect=OSError("network unavailable")), \
                patch("opencode_project.upload.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "管理 API.*upload_url.*原容器 upload token"):
                upload_archive("https://stale.example/upload", "original-token", b"archive", retries=1)

    def test_chunked_upload_failure_uses_same_management_query_guidance(self):
        import opencode_project.upload as upload

        with patch.multiple(upload, MAX_UPLOAD_BYTES=1, CHUNK_BYTES=3), \
                patch("opencode_project.upload._request", side_effect=OSError("network unavailable")), \
                patch("opencode_project.upload.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "管理 API.*upload_url.*原容器 upload token"):
                upload.upload_archive("https://stale.example/upload", "original-token", b"archive", retries=1)

    def test_upload_help_does_not_offer_management_refresh_option(self):
        result = subprocess.run(
            [sys.executable, "-m", "opencode_project.cli", "upload", "--help"],
            cwd=Path(__file__).parents[1], capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--refresh-url", result.stdout)

    def test_archive_above_single_request_limit_uses_chunk_protocol(self):
        import json
        with patch("opencode_project.upload._request", side_effect=[
            json.dumps({"session_id": "a" * 32}).encode(), b"", b"", b"", b"",
        ]) as request, patch("opencode_project.upload.CHUNK_BYTES", 32 * 1024 * 1024):
            from opencode_project.upload import MAX_UPLOAD_BYTES
            upload_archive("https://container.trycloudflare.com/upload", "token", b"x" * (MAX_UPLOAD_BYTES + 1))
        self.assertEqual(request.call_count, 5)

    def test_large_archive_retries_only_the_supplied_tunnel_target(self):
        import json
        import opencode_project.upload as upload
        monkey = unittest.mock.patch.multiple(upload, MAX_UPLOAD_BYTES=4, CHUNK_BYTES=3)
        with monkey, patch("opencode_project.upload._request") as request, \
                patch("opencode_project.upload.time.sleep"):
            request.side_effect = [
                json.dumps({"session_id": "a" * 32}).encode(),
                OSError("old Tunnel failed"), b"", b"", b"", b"",
            ]
            upload.upload_archive("https://old.example/upload", "token", b"abcdefgh", retries=2)

        self.assertTrue(all(call.args[0].startswith("https://old.example/") for call in request.call_args_list))
        chunk_calls = [call for call in request.call_args_list if "/chunks/" in call.args[0]]
        self.assertEqual([call.args[0].rsplit("/", 1)[1] for call in chunk_calls], ["0", "0", "1", "2"])
        session_payload = json.loads(request.call_args_list[0].args[2])
        self.assertRegex(session_payload["session_id"], r"^[0-9a-f]{32}$")

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
            max_size=None, ping_interval=20, close_timeout=2,
        )
        self.assertEqual(remote.recv.call_count, 2)

    def test_connect_sends_initial_size_and_only_changed_sizes_as_text_controls(self):
        import opencode_project.connect as connect

        remote = unittest.mock.MagicMock()
        remote.__enter__.return_value = remote
        sizes = iter([(100, 30), (100, 30), (120, 40)])
        remote.recv.side_effect = [TimeoutError(), TimeoutError(), KeyboardInterrupt()]
        with patch.object(connect, "terminal_size", side_effect=lambda: next(sizes)), \
                patch.object(connect, "websocket_connect", return_value=remote), \
                patch.object(connect, "_terminal_input", return_value=b""):
            connect.connect_terminal("ws://api/connect", "scoped-token")

        self.assertEqual(remote.send.call_args_list, [
            unittest.mock.call('{"type":"resize","columns":100,"rows":30}'),
            unittest.mock.call('{"type":"resize","columns":120,"rows":40}'),
        ])

    def test_windows_terminal_query_replies_are_not_forwarded_to_remote_tui(self):
        import opencode_project.connect as connect

        query_reply = "\x1b[?2026;2$y"

        class FakeMsvcrt:
            def __init__(self):
                self.characters = list(query_reply)

            def kbhit(self):
                return bool(self.characters)

            def getwch(self):
                return self.characters.pop(0)

        class FakeStdin:
            def isatty(self):
                return True

        remote = unittest.mock.MagicMock()
        remote.__enter__.return_value = remote
        remote.recv.side_effect = KeyboardInterrupt()
        with patch.object(connect, "msvcrt", FakeMsvcrt()), \
                patch.object(connect, "termios", None), \
                patch.object(connect.sys, "stdin", FakeStdin()), \
                patch.object(connect, "websocket_connect", return_value=remote):
            connect.connect_terminal("ws://tunnel.example/connect", "scoped-token")

        self.assertNotIn(unittest.mock.call(query_reply.encode("utf-8")), remote.send.call_args_list)

    def test_windows_terminal_query_replies_are_not_forwarded_as_user_input(self):
        import opencode_project.connect as connect

        terminal_input = "ok\x1b[?2026;2$y\x1b[1;1R\x1b[4;600;1200t\x1b]10;rgb:0c0c/0c0c/0c0c\x07x"

        class FakeMsvcrt:
            def __init__(self):
                self.characters = list(terminal_input)

            def kbhit(self):
                return bool(self.characters)

            def getwch(self):
                return self.characters.pop(0)

        with patch.object(connect, "msvcrt", FakeMsvcrt()), \
                patch.object(connect.sys, "stdin") as stdin, \
                patch.object(connect, "terminal_size", return_value=(80, 24)):
            stdin.isatty.return_value = True
            self.assertEqual(connect._terminal_input(), b"okx")

    def test_windows_arrow_key_scan_code_is_buffered_until_next_input_poll(self):
        import opencode_project.connect as connect

        class FakeMsvcrt:
            def __init__(self):
                self.characters = [character for key in ("H", "P", "M", "K")
                                   for character in ("\xe0", key)]
                self.availability = iter([True, False, True, False] * 4)

            def kbhit(self):
                return next(self.availability, False)

            def getwch(self):
                return self.characters.pop(0)

        fake_stdin = unittest.mock.MagicMock()
        fake_stdin.isatty.return_value = True
        with patch.object(connect, "msvcrt", FakeMsvcrt()), \
                patch.object(connect.sys, "stdin", fake_stdin):
            for expected in (b"\x1b[A", b"\x1b[B", b"\x1b[C", b"\x1b[D"):
                with self.subTest(expected=expected):
                    self.assertEqual(connect._terminal_input(), b"")
                    self.assertEqual(connect._terminal_input(), expected)

    def test_connect_reports_same_known_close_code_message_for_closed_and_failed_connections(self):
        from opencode_project.connect import connect_terminal

        expected = {
            4401: "連線授權無效或已撤銷，請使用最新的容器連線資訊。",
            4404: "找不到此 OpenCode 容器。",
            4409: "此容器已有 TUI 工作階段，請稍後重試。",
        }
        for code, message in expected.items():
            with self.subTest(code=code):
                with patch("opencode_project.connect.websocket_connect", side_effect=RuntimeError(f"closed with code {code}")):
                    with self.assertRaisesRegex(RuntimeError, message):
                        connect_terminal("ws://api/connect", "token")

                from websockets.exceptions import ConnectionClosedError
                from websockets.frames import Close

                closed = ConnectionClosedError(Close(code, "closed"), None)
                remote = unittest.mock.MagicMock()
                remote.__enter__.return_value = remote
                remote.recv.side_effect = closed
                with patch("opencode_project.connect.websocket_connect", return_value=remote), \
                        patch("opencode_project.connect._terminal_input", return_value=b""):
                    with self.assertRaisesRegex(RuntimeError, message):
                        connect_terminal("ws://api/connect", "token")

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
