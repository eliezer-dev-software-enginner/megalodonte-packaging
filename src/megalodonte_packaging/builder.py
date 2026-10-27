"""Common Gradle -> application input -> JavaFX/jlink -> jpackage pipeline."""
from pathlib import Path
import os
import re
import shlex
import shutil
import subprocess
import sys
import platform as host_platform
import zipfile

from .config import PackageConfig


class Packager:
    def __init__(self, config: PackageConfig, profile: str = "default", platform: str | None = None):
        self.config = config
        self.profile_name = profile
        self.profile = config.profile(profile)
        self.platform = platform or ("windows" if os.name == "nt" else "linux" if sys.platform.startswith("linux") else "unsupported")
        if self.platform not in ("windows", "linux"):
            raise ValueError("Supported build hosts are Windows and Linux")

    def java_home(self) -> Path:
        configured = os.environ.get("JAVA_HOME")
        if configured:
            home = Path(configured).resolve()
            return home.parent if home.name.lower() == "bin" else home
        executable = shutil.which("java")
        if executable:
            return Path(executable).resolve().parent.parent
        if self.platform == "windows":
            homes = sorted(Path(os.environ.get("ProgramFiles", "C:/Program Files"), "Java").glob("jdk-25*"))
            if homes:
                return homes[-1].resolve()
        raise ValueError("Set JAVA_HOME to a full JDK (jlink, jdeps and jpackage are required)")

    def tool(self, name: str) -> str:
        return str(self.java_home() / "bin" / (name + (".exe" if self.platform == "windows" else "")))

    def environment(self) -> dict[str, str]:
        env = {**os.environ, "JAVA_HOME": str(self.java_home())}
        if self.platform == "windows" and not (shutil.which("wix") or shutil.which("light.exe")):
            locations = []
            if os.environ.get("WIX_HOME"):
                locations.append(Path(os.environ["WIX_HOME"]) / "bin")
            for key in ("ProgramFiles(x86)", "ProgramFiles"):
                locations.extend(Path(os.environ.get(key, "C:/Program Files (x86)" if key.endswith("(x86)") else "C:/Program Files")).glob("WiX Toolset v*/bin"))
            directory = next((p for p in locations if (p / "light.exe").is_file() and (p / "candle.exe").is_file()), None)
            if directory:
                env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
        return env

    def javafx_dir(self) -> Path:
        sdk = self.config.data.get("javafx", {}).get("sdk")
        if sdk:
            return (self.config.root / sdk.format(platform=self.platform, version=self.config.javafx_version)).resolve()
        env = os.environ.get("JAVAFX_MODULES_HOME")
        if env:
            candidate = Path(env).resolve() / f"{self.platform}-{self.config.javafx_version}"
            if (candidate / "lib/javafx.controls.jar").is_file():
                return candidate
        for parent in (self.config.root, *self.config.root.parents):
            for directory in (parent / "java_fx_modules", parent / "megalodonte-world/java_fx_modules"):
                candidate = directory / f"{self.platform}-{self.config.javafx_version}"
                if candidate.is_dir():
                    return candidate
        raise ValueError(f"Set JAVAFX_MODULES_HOME or javafx.sdk for JavaFX {self.config.javafx_version}")

    def workspace(self, kind: str) -> Path:
        if kind not in ("msi", "deb", "app-image", "appimage", "flatpak"):
            raise ValueError(f"Unsupported package type: {kind}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.profile_name):
            raise ValueError("Invalid profile name")
        return self.config.path(f".packaging/{kind}-{self.profile_name}")

    def remove_workspace(self, path: Path):
        path = path.resolve()
        base = self.config.path(".packaging")
        if path == base or not path.is_relative_to(base):
            raise ValueError("Refusing to remove a path outside the packaging workspace")
        if path.exists():
            shutil.rmtree(path)

    def run(self, command: list[str], **kwargs):
        try:
            return subprocess.run(command, cwd=kwargs.pop("cwd", self.config.root), check=True, **kwargs)
        except subprocess.CalledProcessError as error:
            # Do not print launcher credential values contained in command arguments.
            raise RuntimeError(f"{Path(command[0]).name} failed (exit {error.returncode})") from None

    def java_options(self, *, redact: bool = False) -> list[str]:
        options = ["--enable-native-access=javafx.graphics,ALL-UNNAMED", "--add-modules=javafx.controls"]
        version_property = self.config.app.get("version_property")
        if version_property:
            options.append(f"-D{version_property}={self.config.version}")
        runtime = self.config.data.get("runtime", {})
        options.extend(runtime.get("java_options", []))
        options.extend(self.profile.get("java_options", []))
        return options

    def gradle_command(self) -> list[str]:
        wrapper = self.config.root / ("gradlew.bat" if self.platform == "windows" else "gradlew")
        if not wrapper.is_file():
            wrapper = next((parent / wrapper.name for parent in self.config.root.parents if (parent / wrapper.name).is_file()), wrapper)
        tasks = self.config.build.get("tasks", ["clean", "shadowJar"])
        command = [str(wrapper)] if self.platform == "windows" else ["bash", str(wrapper)]
        if os.environ.get("ORG_GRADLE_PROJECT_useLocalSources") == "false":
            # Pass explicitly: Windows Gradle does not reliably expose this environment
            # property while evaluating settings.gradle.kts in GitHub Actions.
            command.append("-PuseLocalSources=false")
        return command + tasks

    def find_jar(self) -> Path:
        pattern = self.config.build.get("jar", "build/libs/*.jar").format(version=self.config.version)
        self.config.path(pattern)
        jars = sorted(p for p in self.config.root.glob(pattern) if p.is_file() and not p.name.endswith(("-sources.jar", "-javadoc.jar", "-tests.jar")))
        if len(jars) != 1:
            raise ValueError(f"Expected exactly one application JAR matching {pattern}; found {len(jars)}")
        return jars[0]

    def prepare_input(self, work: Path):
        directory = work / "input"
        directory.mkdir(parents=True)
        jar = self.find_jar()
        target = directory / "app.jar"
        shutil.copy2(jar, target)
        if self.config.build.get("mode", "fat-jar") == "fat-jar":
            return
        dependencies = self.config.build.get("dependencies", str(jar.parent.relative_to(self.config.root) / "*.jar"))
        self.config.path(dependencies)
        names = []
        for dependency in sorted(self.config.root.glob(dependencies)):
            if dependency.resolve() == jar.resolve() or dependency.name.startswith("javafx-"):
                continue
            if not dependency.is_file() or dependency.suffix != ".jar":
                continue
            if dependency.name == "app.jar":
                raise ValueError("Dependency conflicts with the staged application JAR")
            shutil.copy2(dependency, directory / dependency.name)
            names.append(dependency.name)
        self._classpath_manifest(target, names)

    @staticmethod
    def _classpath_manifest(jar: Path, dependencies: list[str]):
        # A thin application JAR keeps dependencies reachable even when jpackage only
        # adds the main JAR to the launcher's classpath. Do not modify dependency JARs.
        replacement = jar.with_suffix(".tmp")
        with zipfile.ZipFile(jar) as source, zipfile.ZipFile(replacement, "w") as output:
            manifest = source.read("META-INF/MANIFEST.MF").decode("utf-8") if "META-INF/MANIFEST.MF" in source.namelist() else "Manifest-Version: 1.0\n"
            unfolded = re.sub(r"\r?\n ", "", manifest)
            unfolded = re.sub(r"(?im)^Class-Path:.*(?:\r?\n)?", "", unfolded)
            main, *sections = re.split(r"\r?\n\r?\n", unfolded)
            from urllib.parse import quote
            value = "Class-Path: " + " ".join(quote(name) for name in dependencies)
            chunks = []
            while value:
                size = 70 if not chunks else 69
                chunks.append(("" if not chunks else " ") + value[:size])
                value = value[size:]
            updated = main.rstrip("\r\n") + "\r\n" + "\r\n".join(chunks) + "\r\n\r\n"
            if sections:
                updated += "\r\n\r\n".join(sections)
            for info in source.infolist():
                if info.filename.upper() == "META-INF/MANIFEST.MF":
                    continue
                if re.fullmatch(r"META-INF/[^/]+\.(SF|RSA|DSA)", info.filename, re.I):
                    raise ValueError("Cannot modify a signed main application JAR")
                output.writestr(info, source.read(info.filename))
            output.writestr("META-INF/MANIFEST.MF", updated.encode("utf-8"))
        replacement.replace(jar)

    def jlink_command(self, work: Path, modules: set[str] | None = None) -> list[str]:
        separator = ";" if self.platform == "windows" else ":"
        path = f"{work / 'javafx/lib'}{separator}{self.java_home() / 'jmods'}"
        return [self.tool("jlink"), "--module-path", path, "--add-modules", ",".join(sorted(modules or set(self.config.modules))),
                "--bind-services", "--no-header-files", "--no-man-pages", "--output", str(work / "runtime")]

    def link_runtime(self, work: Path):
        modules = set(self.config.modules)
        command = [self.tool("jdeps"), "--multi-release", "base", "--print-module-deps", "--ignore-missing-deps",
                   "--module-path", str(work / "javafx/lib"), "--class-path", str(work / "input/*"), str(work / "input/app.jar")]
        try:
            result = self.run(command, capture_output=True, text=True)
            for line in reversed(result.stdout.splitlines()):
                if re.fullmatch(r"[a-zA-Z0-9_.]+(?:,[a-zA-Z0-9_.]+)*", line.strip()):
                    modules.update(line.strip().split(",")); break
        except RuntimeError:
            print("jdeps could not infer modules; using the explicit runtime.modules configuration.")
        self.run(self.jlink_command(work, modules))

    def copy_javafx(self, work: Path):
        sdk = self.javafx_dir()
        shutil.copytree(sdk / "lib", work / "javafx/lib")
        if (sdk / "bin").is_dir():
            shutil.copytree(sdk / "bin", work / "javafx/bin")

    def copy_natives(self, work: Path):
        suffix, target = (".dll", "bin") if self.platform == "windows" else (".so", "lib")
        exclude = {name.lower() for name in self.config.data.get("runtime", {}).get("exclude_natives", [])}
        if "javafx.web" in self.config.modules and any("webkit" in name for name in exclude):
            raise ValueError("Cannot exclude WebKit natives when javafx.web is required")
        destination = work / "runtime" / target
        destination.mkdir(parents=True, exist_ok=True)
        for location in (work / "javafx/lib", work / "javafx/bin"):
            if location.exists():
                for native in location.glob(f"*{suffix}*"):
                    if native.name.lower() not in exclude:
                        shutil.copy2(native, destination / native.name)

    def jpackage_command(self, work: Path, kind: str, *, redact: bool = False) -> list[str]:
        command = [self.tool("jpackage"), "--input", str(work / "input"), "--name", self.config.name,
                   "--app-version", self.config.installer_version(kind), "--vendor", self.config.vendor,
                   "--main-jar", "app.jar", "--main-class", self.config.main_class,
                   "--dest", str(work / "output"), "--type", kind, "--runtime-image", str(work / "runtime")]
        icon = self.config.app.get("icon_windows" if self.platform == "windows" else "icon_linux")
        if icon and not (self.platform == "linux" and kind == "app-image" and Path(icon).suffix.lower() == ".svg"):
            command += ["--icon", str(self.config.path(icon))]
        for key in ("description", "copyright"):
            value = self.config.app.get(key, self.config.properties.get("app" + key.title()))
            if value:
                command += ["--" + key, value]
        for option in self.java_options(redact=redact):
            command += ["--java-options", option]
        if kind == "msi":
            command += ["--win-menu", "--win-shortcut", "--win-upgrade-uuid", self.config.upgrade_uuid]
            if self.config.data.get("windows", {}).get("per_user", True):
                command.append("--win-per-user-install")
        elif kind == "deb":
            linux = self.config.data.get("linux", {})
            name = linux.get("package_name", re.sub(r"[^a-z0-9+.-]+", "-", self.config.root.name.lower()).strip("-"))
            if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", name):
                raise ValueError("Invalid Debian package name")
            command += ["--linux-shortcut", "--linux-menu-group", linux.get("menu_group", self.config.properties.get("appLinuxMenuGroup", "Utility")),
                        "--linux-package-name", name]
        if self.profile.get("launcher_class"):
            command += ["--add-launcher", f"{self.profile['launcher_name']}={work / 'launcher.properties'}"]
        command.extend(self.profile.get("jpackage_args", []))
        return command

    def preflight(self, kind: str):
        if (kind == "msi" and self.platform != "windows") or (kind in ("deb", "flatpak", "appimage") and self.platform != "linux"):
            raise ValueError("Build MSI on Windows and DEB/Flatpak/AppImage on Linux; cross-packaging is not supported")
        for name in ("java", "jdeps", "jlink", "jpackage"):
            if not Path(self.tool(name)).is_file():
                raise ValueError(f"Missing JDK tool: {name}")
        if kind == "msi":
            path = self.environment().get("PATH", "")
            if not (shutil.which("wix", path=path) or (shutil.which("light.exe", path=path) and shutil.which("candle.exe", path=path))):
                raise ValueError("Install WiX Toolset for MSI (or set WIX_HOME)")
        if not (self.javafx_dir() / "lib/javafx.controls.jar").is_file():
            raise ValueError(f"JavaFX SDK {self.config.javafx_version} is missing javafx.controls.jar")
        for key in ("icon_windows" if self.platform == "windows" else "icon_linux",):
            if self.config.app.get(key) and not self.config.path(self.config.app[key]).is_file():
                raise ValueError(f"Configured icon does not exist: {self.config.app[key]}")
        self.java_options()
        if kind == "flatpak":
            for tool in ("flatpak", "flatpak-builder"):
                if not shutil.which(tool):
                    raise ValueError(f"Install {tool} before creating Flatpak")
            flatpak = self.config.data.get("flatpak", {})
            if not flatpak.get("manifest") or not self.config.path(flatpak["manifest"]).is_file():
                raise ValueError("Configure an existing flatpak.manifest for this application")
        if kind == "appimage":
            self.appimagetool()

    def appimagetool(self) -> Path:
        explicit = os.environ.get("APPIMAGETOOL")
        if explicit:
            tool = Path(explicit).expanduser().resolve()
            if not tool.is_file():
                raise ValueError(f"APPIMAGETOOL not found: {tool}")
            return tool
        installed = shutil.which("appimagetool")
        if installed:
            return Path(installed).resolve()
        arch = host_platform.machine()
        for parent in (self.config.root, *self.config.root.parents):
            candidate = parent / "applications/megalodonte-engine/build/tools" / f"appimagetool-{arch}.AppImage"
            if candidate.is_file():
                return candidate
        raise ValueError("Set APPIMAGETOOL to an existing appimagetool or install it on PATH")

    def appimage_command(self, appdir: Path, output: Path) -> list[str]:
        return [str(self.appimagetool()), "--no-appstream", "--mksquashfs-opt", "-processors", "--mksquashfs-opt", "2", str(appdir), str(output)]

    def build_appimage(self, work: Path, image: Path, destination: Path) -> Path:
        """Assemble an AppImage using the selected profile in its output filename."""
        appdir = work / "AppDir"
        shutil.copytree(image, appdir)
        launcher = appdir / "bin" / self.config.name
        if not launcher.is_file():
            raise ValueError(f"jpackage launcher missing: {launcher}")
        (appdir / "AppRun").write_text(
            '#!/bin/sh\nAPPDIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
            + 'exec "$APPDIR/bin/"' + shlex.quote(self.config.name) + ' "$@"\n', encoding="utf-8")
        (appdir / "AppRun").chmod(0o755)
        desktop = appdir / "megalodonte.desktop"
        desktop.write_text("[Desktop Entry]\nType=Application\nName=" + self.config.name
                           + "\nExec=AppRun\nIcon=megalodonte\nCategories=Development;\nTerminal=false\n", encoding="utf-8")
        icon = self.config.app.get("icon_linux")
        if icon:
            shutil.copy2(self.config.path(icon), appdir / ("megalodonte" + Path(icon).suffix.lower()))
        else:
            raise ValueError("AppImage requires app.icon_linux (PNG or SVG)")
        shutil.copy2(appdir / ("megalodonte" + Path(icon).suffix.lower()), appdir / ".DirIcon")
        profile_suffix = "" if self.profile_name == "default" else f"-{self.profile_name}"
        final = destination / f"{self.config.name}-{self.config.version}{profile_suffix}-{host_platform.machine()}.AppImage"
        temporary = final.with_name(final.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        try:
            env = {**self.environment(), "ARCH": host_platform.machine(), "APPIMAGE_EXTRACT_AND_RUN": "1"}
            self.run(self.appimage_command(appdir, temporary), env=env)
            temporary.chmod(0o755)
            os.replace(temporary, final)
        finally:
            temporary.unlink(missing_ok=True)
        return final

    def smoke_test(self, work: Path):
        command = [str(work / "runtime/bin" / ("java.exe" if self.platform == "windows" else "java")),
                   *self.java_options(), "-cp", str(work / "input/app.jar"), self.config.main_class]
        process = subprocess.Popen(command, cwd=self.config.root)
        try:
            process.wait(timeout=5)
            if process.returncode != 0:
                raise RuntimeError(f"Packaged runtime smoke test failed (exit {process.returncode})")
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()

    def package(self, kind: str, *, skip_build=False, smoke=False, open_folder=False, keep_work=False, install_flatpak=False) -> Path:
        self.preflight(kind)
        work = self.workspace(kind)
        self.remove_workspace(work)
        if not skip_build:
            self.run(self.gradle_command(), env=self.environment())
        self.prepare_input(work)
        launcher_class = self.profile.get("launcher_class")
        if launcher_class:
            with zipfile.ZipFile(work / "input/app.jar") as jar:
                if launcher_class.replace(".", "/") + ".class" not in jar.namelist():
                    raise ValueError(f"Additional launcher class not present in the main JAR: {launcher_class}")
            (work / "launcher.properties").write_text(f"main-jar=app.jar\nmain-class={launcher_class}\n", encoding="utf-8")
        self.copy_javafx(work)
        self.link_runtime(work)
        self.copy_natives(work)
        if smoke:
            self.smoke_test(work)
        native_kind = "app-image" if kind in ("flatpak", "appimage") else kind
        (work / "output").mkdir()
        self.run(self.jpackage_command(work, native_kind), env=self.environment())
        destination = self.config.path("dist")
        destination.mkdir(exist_ok=True)
        profile_suffix = "" if self.profile_name == "default" else f"-{self.profile_name}"
        if kind == "appimage":
            created = work / "output" / self.config.name
            final = self.build_appimage(work, created, destination)
        elif native_kind == "app-image":
            created = work / "output" / self.config.name
            final = destination / f"{self.config.name}-{self.config.version}{profile_suffix}"
            if final.exists():
                raise ValueError(f"Output already exists: {final}; remove it explicitly before rebuilding")
            shutil.move(str(created), final)
        else:
            created = list((work / "output").glob(f"*.{kind}"))
            if len(created) != 1:
                raise ValueError("jpackage did not create exactly one installer")
            final = destination / f"{self.config.name}-{self.config.version}{profile_suffix}.{kind}"
            os.replace(created[0], final)
        if kind == "flatpak":
            flatpak = self.config.data["flatpak"]
            staging = self.config.path(".packaging/flatpak-input")
            self.remove_workspace(staging)
            shutil.copytree(self.config.path("flatpak"), staging, ignore=shutil.ignore_patterns("app-image", "_build", ".flatpak-builder"))
            shutil.copytree(final, staging / "app-image")
            manifest = staging / Path(flatpak["manifest"]).name
            command = ["flatpak-builder", "--user", "--force-clean"]
            if install_flatpak:
                command.append("--install")
            command += [str(staging / "_build"), str(manifest)]
            self.run(command, cwd=staging)
        if not keep_work:
            self.remove_workspace(work)
        if open_folder and not os.environ.get("CI"):
            if self.platform == "windows":
                os.startfile(destination)
            elif shutil.which("xdg-open"):
                subprocess.run(["xdg-open", str(destination)], check=False)
        return final

    def launch_appimage(self, output: Path) -> Path:
        if self.platform != "linux" or output.suffix != ".AppImage" or not output.is_file():
            raise ValueError("Only an existing Linux AppImage can be launched")
        log = self.config.path("dist/appimage-run.log")
        with log.open("wb") as stream:
            process = subprocess.Popen([str(output)], cwd=self.config.root,
                                       env={**self.environment(), "APPIMAGE_EXTRACT_AND_RUN": "1"},
                                       stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        try:
            code = process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            return log
        raise RuntimeError(f"AppImage exited during startup (exit {code}); inspect {log}")
