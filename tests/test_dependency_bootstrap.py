import subprocess
import unittest

from dependency_bootstrap import (
    DependencyBootstrapError,
    DependencySpec,
    build_manual_install_command,
    ensure_dependencies,
)


class DependencyBootstrapTests(unittest.TestCase):
    def test_manual_install_command_uses_current_python(self):
        command = build_manual_install_command(
            [
                DependencySpec("requests"),
                DependencySpec("beautifulsoup4", "bs4"),
            ]
        )
        self.assertIn("requests beautifulsoup4", command)
        self.assertIn("-m pip install", command)

    def test_skip_install_when_dependencies_are_present(self):
        calls = []

        def importer(_name):
            return object()

        def runner(*_args, **_kwargs):
            calls.append("runner-called")
            return subprocess.CompletedProcess([], 0, "", "")

        ensure_dependencies(
            [DependencySpec("requests")],
            importer=importer,
            runner=runner,
            printer=lambda *_args: None,
        )

        self.assertEqual(calls, [])

    def test_install_missing_dependency_and_retry_import(self):
        installed = {"ready": False}

        def importer(name):
            if name == "requests" and not installed["ready"]:
                raise ImportError(name)
            return object()

        def runner(*_args, **_kwargs):
            installed["ready"] = True
            return subprocess.CompletedProcess([], 0, "", "")

        ensure_dependencies(
            [DependencySpec("requests")],
            importer=importer,
            runner=runner,
            printer=lambda *_args: None,
        )

        self.assertTrue(installed["ready"])

    def test_raise_clear_error_when_pip_install_fails(self):
        def importer(_name):
            raise ImportError("missing")

        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 1, "", "network error")

        with self.assertRaises(DependencyBootstrapError) as context:
            ensure_dependencies(
                [DependencySpec("androguard")],
                importer=importer,
                runner=runner,
                printer=lambda *_args: None,
            )

        self.assertIn("Automatic Python dependency installation failed", str(context.exception))
        self.assertIn("pip install androguard", str(context.exception))


if __name__ == "__main__":
    unittest.main()
