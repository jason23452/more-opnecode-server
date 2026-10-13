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


if __name__ == "__main__":
    unittest.main()
