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
            (app / "packaging.toml").write_text("schema_version = 1\n")
            (app / "scripts").mkdir()
            (app / "scripts/package.py").write_text("# adapter\n")
            workflow = MODULE.configure_client(app, "hponto", "script-app")
            source = workflow.read_text()
            self.assertIn("megalodonte-packaging/.github/workflows/package-javafx.yml@main", source)
            self.assertIn("dependencies: 'script-app'", source)
            self.assertIn("smoke-test: true", source)
            with self.assertRaises(FileExistsError):
                MODULE.configure_client(app, "hponto", "script-app")
            with self.assertRaises(ValueError):
                MODULE.configure_client(app, "hponto", "typo", force=True)


if __name__ == "__main__":
    unittest.main()
