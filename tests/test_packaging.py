import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from megalodonte_packaging import load_config, Packager
from megalodonte_packaging.cli import main, bump_version
from megalodonte_packaging.credentials import environment_options


class PackagingTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "build/test-temp"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.root = Path(self.temp.name)
        (self.root / "packaging.toml").write_text('''schema_version = 1
[app]
name = "Sample"
version = "1.2.3"
main_class = "example.Main"
version_property = "example.version"
[javafx]
sdk = "sdk"
[runtime]
modules = ["javafx.controls", "jdk.charsets"]
exclude_natives = ["jfxwebkit.dll"]
[profiles.store]
java_options = ["-Dexample.store=true"]
''', encoding="utf-8")
        self.jdk = self.root / "jdk"
        (self.jdk / "bin").mkdir(parents=True)
        (self.jdk / "jmods").mkdir()
        for name in ("java", "jlink", "jpackage", "jdeps"):
            (self.jdk / "bin" / name).touch()
            (self.jdk / "bin" / (name + ".exe")).touch()
        (self.root / "sdk/lib").mkdir(parents=True)
        (self.root / "sdk/lib/javafx.controls.jar").touch()
        self.env = patch.dict(os.environ, {"JAVA_HOME": str(self.jdk)}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def jar(self, relative="build/libs/sample.jar", manifest="Manifest-Version: 1.0\r\n\r\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as jar:
            jar.writestr("META-INF/MANIFEST.MF", manifest)
            jar.writestr("example/Main.class", b"placeholder")
        return path

    def builder(self, platform="windows", profile="default"):
        return Packager(load_config(self.root), profile, platform)

    def test_identity_versions_and_profiles(self):
        builder = self.builder(profile="store")
        (self.root / "gradle.properties").write_text("appVersion=9.9.9\nappPatch=2\n")
        config = load_config(self.root)
        self.assertEqual(config.version, "1.2.3.2")
        self.assertEqual(config.installer_version("msi"), "1.2.3002")
        self.assertEqual(config.installer_version("deb"), "1.2.3.2")
        cmd = builder.jpackage_command(builder.workspace("msi"), "msi")
        self.assertIn("-Dexample.store=true", cmd)
        self.assertIn("--win-upgrade-uuid", cmd)
        self.assertEqual(self.builder().config.upgrade_uuid, self.builder().config.upgrade_uuid)
        with self.assertRaises(ValueError):
            self.builder(profile="unknown")

    def test_classpath_manifest_and_isolated_input(self):
        path = self.root / "packaging.toml"
        path.write_text(path.read_text() + '\n[build]\nmode="classpath"\njar="build/libs/sample.jar"\ndependencies="build/dependencies/*.jar"\n')
        self.jar(manifest="Manifest-Version: 1.0\r\nClass-Path: old.jar\r\n\r\n")
        self.jar("build/dependencies/library with spaces.jar")
        self.jar("build/dependencies/javafx-controls-25.0.1-win.jar")
        builder = self.builder()
        work = builder.workspace("msi")
        builder.prepare_input(work)
        self.assertEqual({p.name for p in (work / "input").iterdir()}, {"app.jar", "library with spaces.jar"})
        with zipfile.ZipFile(work / "input/app.jar") as jar:
            manifest = jar.read("META-INF/MANIFEST.MF").decode()
        self.assertIn("library%20with%20spaces.jar", manifest)
        self.assertNotIn("old.jar", manifest)
        self.assertNotIn("javafx", manifest)
        command = builder.jpackage_command(work, "msi")
        self.assertEqual(command[command.index("--input") + 1], str(work / "input"))
        self.assertEqual(command[command.index("--runtime-image") + 1], str(work / "runtime"))

    def test_ambiguous_jars_are_rejected(self):
        self.jar()
        self.jar("build/libs/sample-sources.jar")
        self.assertEqual(self.builder().find_jar().name, "sample.jar")
        self.jar("build/libs/another.jar")
        with self.assertRaises(ValueError):
            self.builder().find_jar()

    def test_paths_and_cleanup_never_escape_project(self):
        builder = self.builder()
        for path in ("../outside", "."):
            with self.assertRaises(ValueError):
                builder.config.path(path)
        keep = self.root / "dist/old.deb"
        keep.parent.mkdir(); keep.write_text("keep")
        with self.assertRaises(ValueError):
            builder.remove_workspace(keep.parent)
        work = builder.workspace("msi")
        work.mkdir(parents=True)
        builder.remove_workspace(work)
        self.assertEqual(keep.read_text(), "keep")

    def test_dry_run_never_executes_or_reads_secrets(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), patch("subprocess.run", side_effect=AssertionError("must not run")):
            result = main(["--project", str(self.root), "build", "deb", "--dry-run", "--platform", "linux"])
        self.assertEqual(result, 0)
        commands = json.loads(stdout.getvalue())
        self.assertIn("--linux-package-name", commands["jpackage"])
        self.assertFalse((self.root / ".packaging").exists())

    def test_credentials_are_generic_redacted_and_not_copied(self):
        (self.root / ".env").write_text("SECRET_KEY='local secret'\n")
        definitions = [{"environment": "SECRET_KEY", "property": "example.password", "encoding": "base64"}]
        with patch.dict(os.environ, {"SECRET_KEY": "from environment"}):
            self.assertEqual(environment_options(self.root, definitions), ["-Dexample.password=ZnJvbSBlbnZpcm9ubWVudA=="])
        redacted = environment_options(self.root, definitions, redact=True)
        self.assertEqual(redacted, ["-Dexample.password=<from:SECRET_KEY>"])
        self.jar()
        work = self.builder().workspace("msi")
        self.builder().prepare_input(work)
        self.assertFalse((work / "input/.env").exists())

    def test_windows_and_linux_natives_are_copied_separately(self):
        builder = self.builder()
        work = builder.workspace("msi")
        (work / "javafx/bin").mkdir(parents=True)
        (work / "javafx/bin/glass.dll").touch()
        (work / "javafx/bin/jfxwebkit.dll").touch()
        builder.copy_natives(work)
        self.assertTrue((work / "runtime/bin/glass.dll").exists())
        self.assertFalse((work / "runtime/bin/jfxwebkit.dll").exists())
        linux = self.builder(platform="linux")
        work = linux.workspace("deb")
        (work / "javafx/lib").mkdir(parents=True)
        (work / "javafx/lib/libglass.so").touch()
        linux.copy_natives(work)
        self.assertTrue((work / "runtime/lib/libglass.so").exists())

    def test_pipeline_keeps_other_outputs_and_uses_expected_paths(self):
        self.jar()
        builder = self.builder(platform="linux")
        keep = self.root / "dist/old.msi"
        keep.parent.mkdir(); keep.write_text("keep")
        def run(command, **kwargs):
            name = Path(command[0]).name
            if name == "jdeps":
                return subprocess.CompletedProcess(command, 0, "java.base,java.sql\n", "")
            if name == "jlink":
                output = Path(command[command.index("--output") + 1]); output.mkdir()
                self.assertIn("java.sql", command[command.index("--add-modules") + 1])
            if name == "jpackage":
                output = Path(command[command.index("--dest") + 1]); (output / "sample.deb").write_text("installer")
            return subprocess.CompletedProcess(command, 0)
        with patch.object(builder, "run", side_effect=run):
            output = builder.package("deb", skip_build=True)
        self.assertEqual(output.name, "Sample-1.2.3.deb")
        self.assertEqual(keep.read_text(), "keep")
        self.assertFalse(builder.workspace("deb").exists())

    def test_version_bump_preserves_other_properties_and_comments(self):
        (self.root / "gradle.properties").write_text("# keep\nappVersion=1.2.3\nappPatch=0\nappName=sample\n")
        with contextlib.redirect_stdout(io.StringIO()):
            bump_version(self.root, "patch")
            self.assertIn("appPatch=1", (self.root / "gradle.properties").read_text())
            bump_version(self.root, "release", "1.2.4")
        text = (self.root / "gradle.properties").read_text()
        self.assertIn("# keep", text); self.assertIn("appName=sample", text); self.assertIn("appVersion=1.2.4", text)
        with self.assertRaises(ValueError):
            bump_version(self.root, "release", "bad")

    def test_host_mismatch_fails_before_build(self):
        with self.assertRaises(ValueError):
            self.builder(platform="windows").preflight("deb")
        with self.assertRaises(ValueError):
            self.builder(platform="linux").preflight("msi")

    def test_unknown_configuration_keys_are_rejected(self):
        path = self.root / "packaging.toml"
        path.write_text(path.read_text() + '\n[windows]\nupgrad_uuid="typo"\n')
        with self.assertRaisesRegex(ValueError, "windows"):
            load_config(self.root)

    def test_msi_version_order_across_patch_and_next_release(self):
        original = self.root / "packaging.toml"
        (self.root / "gradle.properties").write_text("appPatch=999\n")
        patched = tuple(map(int, load_config(self.root).installer_version("msi").split(".")))
        original.write_text(original.read_text().replace('version = "1.2.3"', 'version = "1.2.4"'))
        (self.root / "gradle.properties").write_text("appPatch=0\n")
        released = tuple(map(int, load_config(self.root).installer_version("msi").split(".")))
        self.assertGreater(released, patched)

    def test_updater_rejects_missing_class_before_packaging(self):
        path = self.root / "packaging.toml"
        path.write_text(path.read_text() + '\n[profiles.updater]\nlauncher_name="Updater"\nlauncher_class="missing.Updater"\n')
        self.jar()
        builder = self.builder(platform="linux", profile="updater")
        with self.assertRaisesRegex(ValueError, "launcher class"):
            builder.package("deb", skip_build=True)

    def test_failed_subprocess_does_not_disclose_command_secrets(self):
        builder = self.builder()
        command = [builder.tool("jpackage"), "--java-options", "-Dpassword=not-for-logs"]
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, command)):
            with self.assertRaises(RuntimeError) as raised:
                builder.run(command)
        self.assertNotIn("not-for-logs", str(raised.exception))


class WorkspaceMigrationTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[3] / "ftp-file-pusher").is_dir(), "Workspace integration only")
    def test_all_twelve_clients_resolve_the_same_implementation(self):
        library = Path(__file__).resolve().parents[1]
        workspace = library.parents[1]
        specification = importlib.util.spec_from_file_location("migration", library / "tools/migrate_workspace.py")
        migration = importlib.util.module_from_spec(specification); specification.loader.exec_module(migration)
        specs = migration.app_specs(workspace)
        self.assertEqual(len(specs), 12)
        for spec in specs:
            root = spec["root"]
            with self.subTest(project=root.name):
                config = load_config(root)
                self.assertNotEqual(config.name, "Plics SW" if "megalodonte-app" in root.name else "invalid")
                result = subprocess.run([sys.executable, str(root / "scripts/package.py"), "show"], capture_output=True, text=True, check=True)
                report = json.loads(result.stdout)
                self.assertEqual(Path(report["library"]).resolve(), (library / "src/megalodonte_packaging").resolve())
                self.assertNotIn("subprocess.run", (root / "scripts/create-msi.py").read_text())


import sys

if __name__ == "__main__":
    unittest.main()
