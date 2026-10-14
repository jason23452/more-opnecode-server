import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
DEPLOY_SCRIPT = ROOT / "scripts/deploy-production.sh"


def run(command, *, cwd, env=None):
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)


class ProductionDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.checkout = self.root / "checkout"
        run(["git", "init", "--bare", str(self.remote)], cwd=self.root).check_returncode()
        run(["git", "init", str(self.checkout)], cwd=self.root).check_returncode()
        run(["git", "config", "user.email", "deploy-test@example.com"], cwd=self.checkout).check_returncode()
        run(["git", "config", "user.name", "Deploy Test"], cwd=self.checkout).check_returncode()
        (self.checkout / "docker-compose.prod.yaml").write_text("tagged production compose\n")
        (self.checkout / "scripts").mkdir()
        (self.checkout / "scripts/deploy-production.sh").write_text(DEPLOY_SCRIPT.read_text())
        (self.checkout / "scripts/deploy-production.sh").chmod(0o755)
        (self.checkout / ".gitignore").write_text(".env\ndocker-compose.yaml\n")
        (self.checkout / ".env").write_text("host-local-setting=preserve\n")
        (self.checkout / "docker-compose.yaml").write_text("host-local-compose=preserve\n")
        run(["git", "add", ".gitignore", "docker-compose.prod.yaml", "scripts/deploy-production.sh"], cwd=self.checkout).check_returncode()
        run(["git", "commit", "-m", "release"], cwd=self.checkout).check_returncode()
        run(["git", "tag", "v1.2.3"], cwd=self.checkout).check_returncode()
        run(["git", "remote", "add", "origin", str(self.remote)], cwd=self.checkout).check_returncode()
        run(["git", "push", "origin", "HEAD", "refs/tags/v1.2.3"], cwd=self.checkout).check_returncode()
        (self.checkout / "docker-compose.prod.yaml").write_text("newer branch compose\n")
        run(["git", "commit", "-am", "newer than release tag"], cwd=self.checkout).check_returncode()
        run(["git", "push", "origin", "HEAD"], cwd=self.checkout).check_returncode()
        run(["git", "checkout", "--detach", "HEAD"], cwd=self.checkout).check_returncode()
        (self.checkout / "docker-compose.yaml").write_text("host-local-compose=preserve\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.docker_log = self.root / "docker.log"
        docker = self.bin / "docker"
        docker.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\nexit "${DOCKER_EXIT:-0}"\n')
        docker.chmod(0o755)
        self.env = os.environ | {
            "DEPLOY_REPOSITORY": str(self.checkout),
            "DEPLOY_REMOTE": str(self.remote),
            "DEPLOY_TAG": "v1.2.3",
            "OPENCODE_PASSWORD": "throwaway-password",
            "OPENCODE_ADMIN_TOKEN": "731942",
            "DOCKER_LOG": str(self.docker_log),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
        }

    def tearDown(self):
        self.temp.cleanup()

    def deploy(self, **updates):
        return run(["bash", str(self.checkout / "scripts/deploy-production.sh")], cwd=self.root, env=self.env | updates)

    def test_checks_out_tag_copies_compose_preserves_host_settings_and_runs_compose(self):
        result = self.deploy()

        self.assertEqual(result.returncode, 0, f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertEqual(run(["git", "describe", "--tags", "--exact-match"], cwd=self.checkout).stdout.strip(), "v1.2.3")
        self.assertEqual((self.checkout / "docker-compose.yaml").read_text(), "tagged production compose\n")
        env_lines = (self.checkout / ".env").read_text().splitlines()
        self.assertIn("host-local-setting=preserve", env_lines)
        self.assertIn("OPENCODE_PASSWORD='throwaway-password'", env_lines)
        self.assertIn("OPENCODE_ADMIN_TOKEN='731942'", env_lines)
        self.assertEqual((self.checkout / ".env").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("throwaway-password", result.stdout + result.stderr)
        self.assertNotIn("731942", result.stdout + result.stderr)
        self.assertEqual(self.docker_log.read_text().splitlines(), ["compose pull", "compose up -d --remove-orphans"])

    def test_compose_failure_propagates(self):
        result = self.deploy(DOCKER_EXIT="47")

        self.assertEqual(result.returncode, 47)

    def test_initializes_empty_deployment_directory_and_preserves_local_settings(self):
        deployment = self.root / "new-deployment"
        deployment.mkdir()
        (deployment / ".env").write_text("host-local-setting=preserve\n")

        result = self.deploy(DEPLOY_REPOSITORY=str(deployment))

        self.assertEqual(result.returncode, 0, f"stdout={result.stdout}\nstderr={result.stderr}")
        self.assertEqual(run(["git", "describe", "--tags", "--exact-match"], cwd=deployment).stdout.strip(), "v1.2.3")
        self.assertEqual((deployment / "docker-compose.yaml").read_text(), "tagged production compose\n")
        env_lines = (deployment / ".env").read_text().splitlines()
        self.assertIn("host-local-setting=preserve", env_lines)
        self.assertIn("OPENCODE_PASSWORD='throwaway-password'", env_lines)
        self.assertIn("OPENCODE_ADMIN_TOKEN='731942'", env_lines)
        self.assertEqual((deployment / ".env").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.docker_log.read_text().splitlines(), ["compose pull", "compose up -d --remove-orphans"])


if __name__ == "__main__":
    unittest.main()
