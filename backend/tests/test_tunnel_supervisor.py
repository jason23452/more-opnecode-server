from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


def test_tunnel_supervisor_retries_quick_tunnel_429_until_url_is_created(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    attempts_file = tmp_path / "cloudflared-attempts"
    log_file = tmp_path / "cloudflared.log"
    fake_cloudflared = bin_dir / "cloudflared"
    fake_cloudflared.write_text(
        "#!/bin/sh\n"
        f"attempts_file='{attempts_file}'\n"
        "attempt=0\n"
        "[ -f \"$attempts_file\" ] && attempt=$(cat \"$attempts_file\")\n"
        "attempt=$((attempt + 1))\n"
        "printf '%s' \"$attempt\" >\"$attempts_file\"\n"
        "if [ \"$attempt\" -eq 1 ]; then\n"
        "  printf '%s\\n' 'quick tunnel provisioning failed with status 429'\n"
        "  exit 1\n"
        "fi\n"
        "printf '%s\\n' 'https://recovered-example.trycloudflare.com'\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    fake_cloudflared.chmod(0o755)

    supervisor = Path(__file__).parents[1] / "src" / "Features" / "Opencode" / "tunnel-supervisor.sh"
    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "OPENCODE_TUNNEL_LOG": str(log_file),
        "OPENCODE_TUNNEL_RETRY_INITIAL_DELAY": "0",
        "OPENCODE_TUNNEL_RETRY_MAX_DELAY": "0",
    }

    process = subprocess.Popen(["sh", str(supervisor)], env=env)
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if log_file.exists() and "recovered-example.trycloudflare.com" in log_file.read_text(encoding="utf-8"):
                break
            time.sleep(0.02)
        else:
            raise AssertionError("Tunnel supervisor did not retry after provisioning returned HTTP 429")

        assert attempts_file.read_text(encoding="utf-8") == "2"
        log = log_file.read_text(encoding="utf-8")
        assert "quick tunnel provisioning failed with status 429" in log
        assert "recovered-example.trycloudflare.com" in log
    finally:
        process.terminate()
        process.wait(timeout=3)
