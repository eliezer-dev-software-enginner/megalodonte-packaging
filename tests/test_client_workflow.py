
"""Guard the standard caller used when a new application is created."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "tools/configure_client_actions.py"
SPEC = importlib.util.spec_from_file_location("configure_client_actions", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ClientWorkflowTests(unittest.TestCase):

    def test_generates_packaging_caller_and_refuses_accidental_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)

            (app / "packaging.toml").write_text(
                "schema_version = 1\n",
                encoding="utf-8",
            )

            (app / "scripts").mkdir()

            (app / "scripts/package.py").write_text(
                "# adapter\n",
                encoding="utf-8",
            )

            workflow = MODULE.configure_client(
                app,
                "hponto",
                "pack-utilities",
            )

            source = workflow.read_text(encoding="utf-8")

            self.assertIn(
                "megalodonte-packaging/.github/workflows/package-javafx.yml@main",
                source,
            )

            self.assertIn(
                "dependencies: 'pack-utilities'",
                source,
            )

            self.assertIn("smoke-test: true", source)

            # Existing workflows must not be overwritten accidentally.
            with self.assertRaises(FileExistsError):
                MODULE.configure_client(
                    app,
                    "hponto",
                    "pack-utilities",
                )

            # Unknown dependencies must be rejected.
            with self.assertRaises(ValueError):
                MODULE.configure_client(
                    app,
                    "hponto",
                    "typo",
                    force=True,
                )

    def test_rejects_removed_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)

            for dependency in ("script-app", "jsonc-ui"):
                with self.subTest(dependency=dependency):
                    with self.assertRaises(ValueError):
                        MODULE.configure_client(
                            app,
                            "hponto",
                            dependency,
                        )


if __name__ == "__main__":
    unittest.main()
