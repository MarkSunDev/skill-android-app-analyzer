import tempfile
import unittest
from pathlib import Path

from workspace_manager import (
    WorkspaceLimitError,
    create_package_workspace,
    ensure_workspace_capacity,
    resolve_workspace_root,
)


class WorkspaceManagerTests(unittest.TestCase):
    def test_resolve_workspace_root_creates_default_cache_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            workspace_root = resolve_workspace_root(repo_root=repo_root)

            self.assertEqual(
                workspace_root,
                repo_root / ".cache" / "android-app-analyzer",
            )
            self.assertTrue(workspace_root.exists())
            self.assertTrue(workspace_root.is_dir())

    def test_workspace_capacity_warns_when_directory_count_exceeds_soft_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            for index in range(6):
                (workspace_root / f"com.example.{index}").mkdir()

            warning = ensure_workspace_capacity(workspace_root)

            self.assertIsNotNone(warning)
            self.assertIn("6", warning)
            self.assertIn("clear old package workspaces", warning)

    def test_workspace_capacity_raises_when_directory_count_exceeds_hard_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            for index in range(21):
                (workspace_root / f"com.example.{index}").mkdir()

            with self.assertRaises(WorkspaceLimitError) as context:
                ensure_workspace_capacity(workspace_root)

            self.assertIn("21", str(context.exception))
            self.assertIn("clear the cache workspace", str(context.exception))

    def test_create_package_workspace_builds_expected_subdirectories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)

            workspace = create_package_workspace(
                workspace_root=workspace_root,
                package_name="com.example.reader",
            )

            self.assertEqual(workspace.package_dir, workspace_root / "com.example.reader")
            self.assertTrue(workspace.downloads_dir.exists())
            self.assertTrue(workspace.extracted_dir.exists())
            self.assertTrue(workspace.reports_dir.exists())
            self.assertTrue(workspace.temp_dir.exists())


if __name__ == "__main__":
    unittest.main()
