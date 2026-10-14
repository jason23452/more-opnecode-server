import io
import os
import ssl
import subprocess
import sys
import threading
import zipfile
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from unittest.mock import patch

import certifi
import trustme
from websockets.sync.server import serve

import opencode_project.upload as upload
from opencode_project.upload import create_archive, upload_archive


class UploadTests(unittest.TestCase):
    def test_upload_uses_packaged_trusted_certificate_bundle(self):
        received = []

        class UploadHandler(BaseHTTPRequestHandler):
            def do_PUT(self):
                received.append((self.headers.get("Authorization"), self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(204)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        ca = trustme.CA()
        server_certificate = ca.issue_cert("localhost")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            certificate_path = root / "server.pem"
            key_path = root / "server-key.pem"
            ca_path = root / "trusted-ca.pem"
            server_certificate.cert_chain_pems[0].write_to_path(certificate_path)
            server_certificate.private_key_pem.write_to_path(key_path)
            ca.cert_pem.write_to_path(ca_path)

            server = ThreadingHTTPServer(("127.0.0.1", 0), UploadHandler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate_path, key_path)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(certifi, "where", return_value=str(ca_path)), \
                        patch.dict(os.environ, {"SSL_CERT_FILE": ""}), \
                        patch("opencode_project.upload.time.sleep"):
                    upload_archive(
                        f"https://localhost:{server.server_port}/upload",
                        "upload-capability", b"project archive", retries=1,
                    )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

        self.assertEqual(received, [("Bearer upload-capability", b"project archive")])

    def test_certificate_verification_failure_explains_custom_ca_override(self):
        message = upload._upload_failure_message(
            URLError(ssl.SSLCertVerificationError(1, "unable to get local issuer certificate"))
        )

        self.assertIn("SSL_CERT_FILE", message)
        self.assertNotIn("重新查詢目前的 upload_url", message)

    def test_tui_connection_uses_packaged_trusted_certificate_bundle(self):
        import opencode_project.connect as connect

        received = []

        def handle_connection(websocket):
            try:
                while True:
                    received.append(websocket.recv(timeout=2))
            except Exception:
                return

        ca = trustme.CA()
        server_certificate = ca.issue_cert("localhost", "127.0.0.1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            certificate_path = root / "server.pem"
            key_path = root / "server-key.pem"
            ca_path = root / "trusted-ca.pem"
            server_certificate.cert_chain_pems[0].write_to_path(certificate_path)
            server_certificate.private_key_pem.write_to_path(key_path)
            ca.cert_pem.write_to_path(ca_path)

            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.load_cert_chain(certificate_path, key_path)
            server = serve(handle_connection, "127.0.0.1", 0, ssl=server_context)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            try:
                with patch.object(certifi, "where", return_value=str(ca_path)), \
                        patch.dict(os.environ, {"SSL_CERT_FILE": ""}), \
                        patch.object(connect, "terminal_size", return_value=(80, 24)), \
                        patch.object(connect, "_terminal_input", return_value=b"\x03"):
                    connect.connect_terminal(
                        f"wss://127.0.0.1:{server.socket.getsockname()[1]}/connect",
                        "connect-capability",
                    )
            finally:
                server.shutdown()
                server_thread.join(timeout=2)

        self.assertEqual(received, ['{"type":"resize","columns":80,"rows":24}', b"\x03"])

    def test_tui_certificate_verification_failure_explains_custom_ca_override(self):
        import opencode_project.connect as connect

        with patch.object(
            connect, "websocket_connect",
            side_effect=ssl.SSLCertVerificationError(1, "unable to get local issuer certificate"),
        ):
            with self.assertRaisesRegex(RuntimeError, "TLS 憑證驗證失敗.*SSL_CERT_FILE") as raised:
                connect.connect_terminal("wss://tunnel.example/connect", "connect-token")

        self.assertNotIn("重新查詢目前的 connect_url", str(raised.exception))

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

    def test_archive_preserves_git_history_without_remote_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c",
                            "user.email=test@example.com", "commit", "--allow-empty", "-qm", "initial"], check=True)
            subprocess.run(["git", "-C", str(root), "remote", "add", "origin",
                            "https://alice:secret-token@example.com/team/project.git"], check=True)
            (root / ".git" / "credentials").write_text("https://alice:secret-token@example.com\n")
            (root / "main.py").write_text("print('hello')")

            archive = create_archive(root)
            try:
                with zipfile.ZipFile(archive) as project:
                    names = project.namelist()
                    self.assertTrue(any(name.startswith(".git/objects/") for name in names))
                    self.assertIn(".git/HEAD", names)
                    self.assertNotIn(".git/credentials", names)
                    config = project.read(".git/config").decode()
                    self.assertIn("https://example.com/team/project.git", config)
                    self.assertNotIn("secret-token", config)
            finally:
                archive.unlink()

    def test_archive_redacts_password_in_scp_style_ssh_remote_without_changing_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            remote = "git:scp-secret@git.example:team/repo.git"
            subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote], check=True)

            archive = create_archive(root)
            try:
                with zipfile.ZipFile(archive) as project:
                    config = project.read(".git/config").decode()
                self.assertIn("git@git.example:team/repo.git", config)
                self.assertNotIn("scp-secret", config)
            finally:
                archive.unlink()

    def test_confirmation_redacts_scp_style_password_but_preserves_username_host_and_path(self):
        from opencode_project.cli import prompt_git_credentials

        class TTY(io.StringIO):
            def isatty(self):
                return True

        output = TTY()
        with patch("opencode_project.cli.sys.stdin", TTY("1\n")), patch("opencode_project.cli.sys.stdout", output):
            prompt_git_credentials("git:scp-secret@git.example:team/repo.git", True, "SSH key")

        self.assertIn("git@git.example:team/repo.git", output.getvalue())
        self.assertNotIn("scp-secret", output.getvalue())
        self.assertEqual(upload.sanitize_remote("ssh://git:secret@git.example:2222/team/repo.git"),
                         "ssh://git@git.example:2222/team/repo.git")
        self.assertTrue(upload._ssh_remote("git:scp-secret@git.example:team/repo.git"))

    def test_upload_prompts_before_transmitting_https_remote_credentials(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=("https://git.example/team/repo.git", {"username": "alice", "password": "secret"})), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="send") as prompt, \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            main()

        prompt.assert_called_once()
        project_upload.assert_called_once_with("https://container/upload", "upload-token", b"zip", retries=3)
        credential_upload.assert_called_once_with(
            "https://container/upload", "upload-token", "https://git.example/team/repo.git",
            {"username": "alice", "password": "secret"}, retries=3,
        )

    def test_upload_prompts_and_transmits_available_ssh_key_separately(self):
        from opencode_project.cli import main

        auth = ("git@git.example:team/repo.git", {"private_key": "SSH-PRIVATE-KEY", "key_name": "id_ed25519"})
        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=None), \
                patch("opencode_project.cli.git_ssh_credentials", return_value=auth), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="send") as prompt, \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            main()

        prompt.assert_called_once_with(auth[0], True, "SSH key: id_ed25519")
        project_upload.assert_called_once_with("https://container/upload", "upload-token", b"zip", retries=3)
        credential_upload.assert_called_once_with(
            "https://container/upload", "upload-token", auth[0], auth[1], retries=3,
        )

    def test_ssh_upload_without_available_key_still_offers_project_only_or_cancel(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=None), \
                patch("opencode_project.cli.git_ssh_credentials", return_value=("git@git.example:team/repo.git", {})), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="upload") as prompt, \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            main()

        prompt.assert_called_once_with("git@git.example:team/repo.git", False, "SSH key")
        project_upload.assert_called_once()
        credential_upload.assert_not_called()

    def test_ssh_confirmation_masks_remote_and_offers_explicit_choices(self):
        from opencode_project.cli import prompt_git_credentials

        class TTY(io.StringIO):
            def isatty(self):
                return True

        output = TTY()
        with patch("opencode_project.cli.sys.stdin", TTY("1\n")), \
                patch("opencode_project.cli.sys.stdout", output):
            choice = prompt_git_credentials("ssh://git:secret@git.example/team/repo.git", True, "SSH key: id_ed25519")

        self.assertEqual(choice, "send")
        self.assertIn("SSH key", output.getvalue())
        self.assertIn("[1] 傳送認證並上傳", output.getvalue())
        self.assertIn("[2] 只上傳專案（不帶認證）", output.getvalue())
        self.assertIn("[3] 取消", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_ssh_confirmation_without_key_explains_unavailable_source(self):
        from opencode_project.cli import prompt_git_credentials

        class TTY(io.StringIO):
            def isatty(self):
                return True

        output = TTY()
        with patch("opencode_project.cli.sys.stdin", TTY("2\n")), \
                patch("opencode_project.cli.sys.stdout", output):
            choice = prompt_git_credentials("git@git.example:team/repo.git", False, "SSH key")

        self.assertEqual(choice, "upload")
        self.assertIn("無法取得此 remote 的 SSH key 認證", output.getvalue())
        self.assertIn("[2] 只上傳專案（不帶認證）", output.getvalue())
        self.assertIn("[3] 取消", output.getvalue())
        self.assertNotIn("[1]", output.getvalue())

    def test_ssh_upload_noninteractive_does_not_transmit_detected_key(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=None), \
                patch("opencode_project.cli.git_ssh_credentials", return_value=(
                    "git@git.example:repo.git", {"private_key": "key", "key_name": "id_ed25519"})), \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("opencode_project.cli.sys.stdin") as stdin, \
                patch("opencode_project.cli.sys.stdout") as stdout, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            stdin.isatty.return_value = False
            stdout.isatty.return_value = False
            main()

        project_upload.assert_called_once()
        credential_upload.assert_not_called()

    def test_ssh_key_detection_uses_identity_file_resolved_by_ssh(self):
        from opencode_project.upload import git_ssh_credentials

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            project.mkdir()
            key = Path(temporary) / "id_ed25519"
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nprivate\n-----END OPENSSH PRIVATE KEY-----\n")
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "remote", "add", "origin",
                            "git@git.example:team/repo.git"], check=True)
            original_run = subprocess.run
            with patch("opencode_project.upload.subprocess.run", side_effect=[
                    original_run(["git", "-C", str(project), "remote", "get-url", "origin"],
                                 check=True, capture_output=True, text=True),
                    subprocess.CompletedProcess([], 0, f"hostname git.example\nidentityfile {key}\n", ""),
            ]):
                found = git_ssh_credentials(project)

        self.assertEqual(found, ("git@git.example:team/repo.git", {
            "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nprivate\n-----END OPENSSH PRIVATE KEY-----\n",
            "key_name": "id_ed25519",
        }))

    def test_ssh_agent_identity_is_reported_as_unsupported_instead_of_missing_auth(self):
        from opencode_project.upload import git_ssh_credentials

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "remote", "add", "origin",
                            "git@git.example:team/repo.git"], check=True)
            original_run = subprocess.run

            def run(args, **kwargs):
                if args[0] == "ssh":
                    return subprocess.CompletedProcess(args, 0, "identityfile /missing/key\n", "")
                if args[:2] == ["ssh-add", "-L"]:
                    return subprocess.CompletedProcess(args, 0, "ssh-ed25519 AAAA agent-key\n", "")
                return original_run(args, **kwargs)

            with patch("opencode_project.upload.subprocess.run", side_effect=run), \
                    patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/agent.sock"}):
                detected = git_ssh_credentials(project)

        self.assertIn("ssh-agent", detected[1]["unsupported"])
        self.assertNotIn("private_key", detected[1])

    def test_upload_without_credentials_does_not_offer_or_send_credentials(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=("https://git.example/repo", {})), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="upload") as prompt, \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            main()

        prompt.assert_called_once_with("https://git.example/repo", False)
        project_upload.assert_called_once()
        credential_upload.assert_not_called()

    def test_cancelled_upload_transmits_neither_project_nor_credentials(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive") as archive, \
                patch("opencode_project.cli.git_https_credentials", return_value=("https://git.example/repo", {"username": "a", "password": "b"})), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="cancel"), \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            main()

        archive.assert_not_called()
        project_upload.assert_not_called()
        credential_upload.assert_not_called()

    def test_noninteractive_upload_never_sends_available_credentials(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=("https://git.example/repo", {"username": "a", "password": "b"})), \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials") as credential_upload, \
                patch("opencode_project.cli.sys.stdin") as stdin, \
                patch("opencode_project.cli.sys.stdout") as stdout, \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]):
            stdin.isatty.return_value = False
            stdout.isatty.return_value = False
            main()

        project_upload.assert_called_once()
        credential_upload.assert_not_called()

    def test_https_credentials_are_retrieved_through_git_credential_helper(self):
        from opencode_project.upload import git_https_credentials

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            credential_file = project / "credentials"
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "remote", "add", "origin",
                            "https://git.example:8443/team/private.git"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "credential.helper",
                            f"store --file={credential_file}"], check=True)
            subprocess.run(["git", "-C", str(project), "credential", "approve"],
                           input="protocol=https\nhost=git.example:8443\npath=team/private.git\n"
                                 "username=alice\npassword=helper-secret\n\n",
                           text=True, check=True)

            acquired = git_https_credentials(project)

        self.assertEqual(acquired, (
            "https://git.example:8443/team/private.git",
            {"username": "alice", "password": "helper-secret"},
        ))

    def test_git_credentials_use_separate_authorized_https_request(self):
        import json

        with patch("opencode_project.upload._request", return_value=b"") as request:
            upload.upload_git_credentials(
                "https://container.example/upload", "upload-capability",
                "https://git.example/team/repo.git", {"username": "alice", "password": "secret"},
            )

        target, token, body, method, headers = request.call_args.args
        self.assertEqual(target, "https://container.example/upload/git-credentials")
        self.assertEqual(token, "upload-capability")
        self.assertEqual(method, "PUT")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(body), {
            "remote": "https://git.example/team/repo.git",
            "credentials": {"username": "alice", "password": "secret"},
        })

        with self.assertRaisesRegex(ValueError, "HTTPS"):
            upload.upload_git_credentials("http://container/upload", "token", "https://git.example/repo",
                                          {"username": "a", "password": "b"})

        with patch("opencode_project.upload._request", return_value=b"") as ssh_request:
            upload.upload_git_credentials(
                "https://container.example/upload", "upload-capability", "git@git.example:team/repo.git",
                {"private_key": "private-key", "key_name": "id_ed25519"},
            )
        self.assertEqual(ssh_request.call_args.args[0], "https://container.example/upload/git-credentials")
        self.assertEqual(json.loads(ssh_request.call_args.args[2]), {
            "remote": "git@git.example:team/repo.git",
            "credentials": {"private_key": "private-key", "key_name": "id_ed25519"},
        })

    def test_credential_transfer_failure_fails_upload_command(self):
        from opencode_project.cli import main

        with patch("opencode_project.cli.create_archive", return_value=b"zip"), \
                patch("opencode_project.cli.git_https_credentials", return_value=("https://git.example/repo", {"username": "a", "password": "b"})), \
                patch("opencode_project.cli.prompt_git_credentials", return_value="send"), \
                patch("opencode_project.cli.upload_archive") as project_upload, \
                patch("opencode_project.cli.upload_git_credentials", side_effect=RuntimeError("credential tunnel failed")), \
                patch("sys.argv", ["opencode-project", "upload", "--url", "https://container/upload",
                                    "--token", "upload-token", "--project", "."]), \
                patch("sys.stderr"):
            with self.assertRaises(SystemExit) as error:
                main()

        self.assertEqual(error.exception.code, 1)
        project_upload.assert_called_once()

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

    def test_windows_f9_scan_code_triggers_clipboard_paste(self):
        import opencode_project.connect as connect

        class FakeMsvcrt:
            def __init__(self):
                self.characters = ["\xe0", "C"]
                self.availability = iter([True, True, False])

            def kbhit(self):
                return next(self.availability, False)

            def getwch(self):
                return self.characters.pop(0)

        fake_stdin = unittest.mock.MagicMock()
        fake_stdin.isatty.return_value = True
        with patch.object(connect, "msvcrt", FakeMsvcrt()), \
                patch.object(connect.sys, "stdin", fake_stdin):
            self.assertEqual(connect._terminal_input(), b"\x07")

    def test_posix_f9_sequence_triggers_clipboard_paste(self):
        import opencode_project.connect as connect

        fake_stdin = unittest.mock.MagicMock()
        fake_stdin.buffer.read1.return_value = b"\x1b[20~"
        with patch.object(connect, "msvcrt", None), \
                patch.object(connect.sys, "stdin", fake_stdin), \
                patch.object(connect.select, "select", return_value=([fake_stdin], [], [])):
            self.assertEqual(connect._terminal_input(), b"\x07")

    def test_connect_sends_clipboard_file_as_attachment_frame_instead_of_ctrl_v(self):
        import opencode_project.connect as connect
        from types import SimpleNamespace

        clipboard_file = SimpleNamespace(
            name="clipboard.png", mime_type="image/png", data=b"\x89PNG\r\n\x1a\nimage-data",
        )
        remote = unittest.mock.MagicMock()
        remote.__enter__.return_value = remote
        remote.recv.side_effect = KeyboardInterrupt()
        with patch.object(connect, "terminal_size", return_value=(80, 24)), \
                patch.object(connect, "_terminal_input", return_value=b"\x16"), \
                patch.object(connect, "read_clipboard_files", return_value=[clipboard_file]), \
                patch.object(connect, "websocket_connect", return_value=remote):
            connect.connect_terminal("ws://tunnel.example/connect", "scoped-token")

        file_frame = (
            b"\x00OPENCODE_CLIPBOARD_FILE_V1\x00"
            + b'{"name":"clipboard.png","mime_type":"image/png"}\x00'
            + clipboard_file.data
        )
        self.assertIn(unittest.mock.call(file_frame), remote.send.call_args_list)
        self.assertNotIn(unittest.mock.call(b"\x16"), remote.send.call_args_list)

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
