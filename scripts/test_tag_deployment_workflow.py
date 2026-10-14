import unittest
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github/workflows/tag-deployment.yml"


class TagDeploymentWorkflowTests(unittest.TestCase):
    def test_deploys_only_version_tags_on_the_production_runner(self):
        workflow = WORKFLOW.read_text()

        self.assertIn('      - "v*"', workflow)
        self.assertIn("runs-on: bojii-system", workflow)
        self.assertNotIn("branches:", workflow)

    def test_updates_the_existing_checkout_without_cleaning_host_configuration(self):
        workflow = WORKFLOW.read_text()

        self.assertIn("/home/bojii/more-opencode-server", workflow)
        self.assertIn('refs/tags/${GITHUB_REF_NAME}', workflow)
        self.assertNotIn("git clean", workflow)

    def test_uses_host_compose_copy_and_fails_fast_with_environment_secrets(self):
        workflow = WORKFLOW.read_text()

        self.assertIn("docker-compose.yaml.prod", workflow)
        self.assertIn("docker-compose.yaml", workflow)
        self.assertIn("docker compose build", workflow)
        self.assertIn("docker compose up -d", workflow)
        self.assertIn("environment: production", workflow)
        self.assertIn("OPENCODE_PASSWORD: ${{ secrets.OPENCODE_PASSWORD }}", workflow)
        self.assertIn("OPENCODE_ADMIN_TOKEN: ${{ secrets.OPENCODE_ADMIN_TOKEN }}", workflow)
        self.assertIn('"${OPENCODE_PASSWORD:?', workflow)
        self.assertIn('"${OPENCODE_ADMIN_TOKEN:?', workflow)
        self.assertIn("set -euo pipefail", workflow)
        self.assertNotIn("continue-on-error: true", workflow)


if __name__ == "__main__":
    unittest.main()
