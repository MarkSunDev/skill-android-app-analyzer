import json
import unittest
from pathlib import Path


class PackageManifestTests(unittest.TestCase):
    def test_package_files_include_gemini_extension_manifest(self):
        repo_root = Path(__file__).resolve().parents[1]
        package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))

        self.assertIn("gemini-extension.json", package_json["files"])


if __name__ == "__main__":
    unittest.main()
