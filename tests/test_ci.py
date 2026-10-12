import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from megalodonte_packaging.ci import clone, metadata, prepare


class CiTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1] / "build/test-temp"
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_transitive_dependencies_are_published_in_order(self):
        with patch("megalodonte_packaging.ci.clone") as checkout, patch("megalodonte_packaging.ci.run") as run:
            prepare(self.root, ["disgust", "script-app", "simple-clipboard"])
        self.assertEqual([call.args[0] for call in checkout.call_args_list], [
            "megalodonte-libs", "pack-utilities", "disgust-components", "megalodonte-jsonc-ui",
            "megalodonte-script-app", "megalodonte-simple-clipboard"])
        self.assertTrue(checkout.call_args_list[0].kwargs["submodules"])
        self.assertEqual(run.call_args_list[1].args[0][-4:-2], ["test", "publishToMavenLocal"])
        self.assertIn(":disgust-icons:publishToMavenLocal", run.call_args_list[2].args[0])

    def test_unknown_dependency_is_rejected_before_checkout(self):
        with patch("megalodonte_packaging.ci.clone") as checkout:
            with self.assertRaises(ValueError):
                prepare(self.root, ["unknown"])
            checkout.assert_not_called()

    def test_checkout_can_pin_a_source_ref(self):
        with patch.dict(os.environ, {"CI_REF_PACK_UTILITIES": "v1.2.3"}), patch("megalodonte_packaging.ci.run") as run:
            clone("pack-utilities", self.root / "utilities")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--branch") + 1], "v1.2.3")

    def test_metadata_uses_toml_display_name_and_composed_version(self):
        (self.root / "packaging.toml").write_text('schema_version=1\n[app]\nname="Plics SW"\n', encoding="utf-8")
        (self.root / "gradle.properties").write_text("appName=plics-sw\nappVersion=1.1.5\nappPatch=2\nappMainClass=my_app.Main\n", encoding="utf-8")
        output = self.root / "output"
        with patch.dict(os.environ, {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v1.1.5.2"}):
            metadata(self.root, output, check_tag=True)
        self.assertEqual(output.read_text(), "version=1.1.5.2\nname=Plics SW\n")
        with patch.dict(os.environ, {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": "v1.1.6"}):
            with self.assertRaises(ValueError):
                metadata(self.root, self.root / "invalid", check_tag=True)
        self.assertFalse((self.root / "invalid").exists())


if __name__ == "__main__":
    unittest.main()
