import socket
import struct
import base64
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve
from websockets.sync.client import connect as websocket_connect

from src.Features.Opencode import ssh_agent_relay
from src.Features.Opencode import upload_receiver


def test_agent_packet_reader_accepts_fragmented_length_and_payload():
    left, right = socket.socketpair()
    try:
        packet = b"\x00\x00\x00\x01\x0b"
        thread = threading.Thread(target=lambda: (right.sendall(packet[:2]), right.sendall(packet[2:])))
        thread.start()

        assert ssh_agent_relay.read_agent_packet(left) == packet
        thread.join()
    finally:
        left.close()
        right.close()


def test_agent_packet_reader_rejects_oversized_packet():
    left, right = socket.socketpair()
    try:
        right.sendall(struct.pack(">I", ssh_agent_relay.MAX_AGENT_PACKET + 1))

        with pytest.raises(ValueError, match="exceeds"):
            ssh_agent_relay.read_agent_packet(left)
    finally:
        left.close()
        right.close()


def test_agent_relay_allows_only_read_sign_and_session_bind_requests():
    def packet(message_type: int, payload: bytes = b"") -> bytes:
        body = bytes([message_type]) + payload
        return struct.pack(">I", len(body)) + body

    extension = b"session-bind@openssh.com"
    extension_request = packet(27, struct.pack(">I", len(extension)) + extension + b"binding-data")

    assert ssh_agent_relay.agent_request_allowed(packet(11))
    assert ssh_agent_relay.agent_request_allowed(packet(13, b"sign-request"))
    assert ssh_agent_relay.agent_request_allowed(extension_request)
    assert not ssh_agent_relay.agent_request_allowed(packet(19))  # Remove all identities.
    assert not ssh_agent_relay.agent_request_allowed(packet(27, struct.pack(">I", 4) + b"evil"))
    assert ssh_agent_relay.agent_response_allowed(packet(13), packet(14, b"signature"))
    assert ssh_agent_relay.agent_response_allowed(packet(13), packet(5))
    assert not ssh_agent_relay.agent_response_allowed(packet(13), packet(12))


def test_agent_tunnel_requires_connect_token_before_creating_socket(tmp_path, monkeypatch):
    marker = tmp_path / "tui-active"
    marker.touch()
    agent_socket = tmp_path / "agent.sock"
    monkeypatch.setenv("OPENCODE_CONNECT_TOKEN", "expected-token")
    monkeypatch.setenv("OPENCODE_TUI_ACTIVE_MARKER", str(marker))
    monkeypatch.setenv("OPENCODE_SSH_AGENT_SOCKET", str(agent_socket))
    server = serve(ssh_agent_relay.relay, "127.0.0.1", 0)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"ws://127.0.0.1:{server.socket.getsockname()[1]}/ssh-agent"
    try:
        with websocket_connect(url, additional_headers={"Authorization": "Bearer wrong-token"}) as connection:
            with pytest.raises(ConnectionClosed) as closed:
                connection.recv(timeout=1)
            assert closed.value.rcvd.code == 4401
        assert not agent_socket.exists()
    finally:
        server.shutdown()
        server_thread.join(timeout=2)


def _wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_local_encrypted_agent_signs_remote_scoped_git_push_and_disconnect_cleans_socket(tmp_path, monkeypatch):
    cli_source = Path(__file__).parents[2] / "cli" / "src"
    sys.path.insert(0, str(cli_source))
    from opencode_project.connect import _forward_agent_requests

    with tempfile.TemporaryDirectory(prefix="agent-relay-") as temporary:
        root = Path(temporary)
        agent_socket = root / "local.sock"
        forwarded_socket = root / "forwarded.sock"
        marker = root / "tui-active"
        marker.touch()
        token = "integration-connect-token"
        monkeypatch.setenv("OPENCODE_CONNECT_TOKEN", token)
        monkeypatch.setenv("OPENCODE_TUI_ACTIVE_MARKER", str(marker))
        monkeypatch.setenv("OPENCODE_SSH_AGENT_SOCKET", str(forwarded_socket))
        monkeypatch.setenv("OPENCODE_SSH_CREDENTIAL_DIR", str(root / "ssh"))
        monkeypatch.setenv("SSH_AUTH_SOCK", str(agent_socket))
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(root / "gitconfig"))

        askpass = root / "askpass"
        askpass.write_text("#!/bin/sh\nprintf '%s\\n' 'loaded-agent-passphrase'\n")
        askpass.chmod(0o700)
        key_path = root / "encrypted-key"
        subprocess.run([
            "ssh-keygen", "-q", "-t", "ed25519", "-N", "loaded-agent-passphrase",
            "-f", str(key_path),
        ], check=True)
        agent = subprocess.Popen(
            ["ssh-agent", "-D", "-a", str(agent_socket)], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        relay_server = None
        relay_thread = None
        client_thread = None
        stop = threading.Event()
        try:
            assert _wait_for(agent_socket.exists)
            agent_env = os.environ | {
                "SSH_AUTH_SOCK": str(agent_socket), "DISPLAY": ":0",
                "SSH_ASKPASS": str(askpass), "SSH_ASKPASS_REQUIRE": "force",
            }
            subprocess.run(["ssh-add", str(key_path)], env=agent_env, check=True,
                           capture_output=True, text=True)
            public_key = subprocess.run(["ssh-add", "-L"], env=agent_env, check=True,
                                        capture_output=True, text=True).stdout.splitlines()[0]

            project = root / "project"
            project.mkdir()
            bare = root / "remote.git"
            subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            remote = "git@git.example:team/repo.git"
            subprocess.run(["git", "-C", str(project), "remote", "add", "origin", remote], check=True)
            (project / "change.txt").write_text("signature request crossed tunnel\n")
            subprocess.run(["git", "-C", str(project), "-c", "user.name=Test", "-c",
                            "user.email=test@example.com", "add", "change.txt"], check=True)
            subprocess.run(["git", "-C", str(project), "-c", "user.name=Test", "-c",
                            "user.email=test@example.com", "commit", "-qm", "initial"], check=True)
            upload_receiver.install_git_ssh_credentials(remote, {"agent_forwarding": True}, project)

            ssh_stub_dir = root / "bin"
            ssh_stub_dir.mkdir()
            ssh_stub = ssh_stub_dir / "ssh"
            ssh_stub.write_text(
                "#!/usr/bin/env python3\n"
                "import base64, os, socket, struct, subprocess, sys\n"
                f"public={public_key!r}.split()\n"
                "blob=base64.b64decode(public[1])\n"
                "def field(value): return struct.pack('>I', len(value))+value\n"
                "payload=b'\\x0d'+field(blob)+field(b'git-push-agent-signature-test')+struct.pack('>I',0)\n"
                "packet=struct.pack('>I',len(payload))+payload\n"
                "agent=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); agent.connect(os.environ['SSH_AUTH_SOCK']); agent.sendall(packet)\n"
                "header=agent.recv(4); size=struct.unpack('>I',header)[0]; data=b''\n"
                "while len(data)<size: data+=agent.recv(size-len(data))\n"
                "assert data[0]==14, data\n"
                f"os.execvp('git-receive-pack',['git-receive-pack',{str(bare)!r}])\n"
            )
            ssh_stub.chmod(0o700)
            relay_server = serve(ssh_agent_relay.relay, "127.0.0.1", 0, max_size=ssh_agent_relay.MAX_AGENT_PACKET + 4)
            relay_thread = threading.Thread(target=relay_server.serve_forever, daemon=True)
            relay_thread.start()
            local_ws = f"ws://127.0.0.1:{relay_server.socket.getsockname()[1]}/connect"
            client_thread = threading.Thread(
                target=_forward_agent_requests, args=(local_ws, token, stop), daemon=True,
            )
            client_thread.start()
            assert _wait_for(forwarded_socket.exists)
            push_env = agent_env | {"PATH": f"{ssh_stub_dir}:{os.environ['PATH']}"}
            pushed = subprocess.run(["git", "-C", str(project), "push", "origin", "HEAD:main"],
                                    env=push_env, capture_output=True, text=True, timeout=15)
            assert pushed.returncode == 0, pushed.stderr
            assert subprocess.run(["git", "--git-dir", str(bare), "rev-parse", "main"],
                                  check=True, capture_output=True, text=True).stdout.strip() == subprocess.run(
                                      ["git", "-C", str(project), "rev-parse", "HEAD"],
                                      check=True, capture_output=True, text=True).stdout.strip()

            denied = subprocess.run(
                [str(root / "ssh" / "git-ssh"), "attacker@git.example", "git-receive-pack 'team/repo.git'"],
                env=push_env, capture_output=True, text=True,
            )
            assert denied.returncode == 126

            stop.set()
            client_thread.join(timeout=3)
            assert not client_thread.is_alive()
            assert _wait_for(lambda: not forwarded_socket.exists())
            marker.unlink()
        finally:
            stop.set()
            marker.unlink(missing_ok=True)
            if client_thread:
                client_thread.join(timeout=2)
            if relay_server:
                relay_server.shutdown()
                relay_thread.join(timeout=2)
            agent.terminate()
            agent.wait(timeout=2)
