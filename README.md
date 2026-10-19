# Megalodonte Packaging

`megalodonte-packaging` is the shared Python library for native JavaFX installers. It owns the Gradle → application input → `jdeps`/`jlink` → `jpackage` pipeline, versioning, launcher profiles, and AppImage assembly. Application repositories keep only `packaging.toml` and a thin command adapter; they do not copy packaging algorithms.

The [codebase guide](docs/CODEBASE.md) maps each Python module to its responsibility and public API.

## Supported hosts and outputs

| Build host | Outputs | Required tools |
| --- | --- | --- |
| Linux | AppImage, DEB, Flatpak, application image | Python 3.11+, JDK with JMODs, matching JavaFX SDK; AppImage needs `appimagetool`, DEB needs `fakeroot`, Flatpak needs `flatpak` and `flatpak-builder` |
| Windows | MSI | Python 3.11+, JDK with JMODs, matching JavaFX SDK, WiX Toolset |

Cross-packaging is not supported. The JavaFX SDK version must match the application's `packaging.toml`. The library has no Python runtime dependencies.

The application repository needs a `packaging.toml` and a build that produces the configured application JAR or distribution. A Gradle wrapper (`gradlew` on Linux or `gradlew.bat` on Windows) must be in the application root or an ancestor directory. Set `JAVA_HOME` to a complete JDK and configure the JavaFX SDK through `javafx.sdk` or `JAVAFX_MODULES_HOME` as described in the [configuration reference](docs/CONFIGURATION.md). Flatpak builds also require an existing manifest declared in `packaging.toml`.

## Workspace use

Install this checkout once and run the shared command from any application repository with `packaging.toml`:

```sh
python -m pip install -e /path/to/megalodonte-packaging
megalodonte-package --project . show
megalodonte-package --project . build appimage --run
megalodonte-package --project . build deb
megalodonte-package --project . build msi --dry-run --platform windows
```

Use an absolute application path from any working directory:

```sh
megalodonte-package --project /path/to/application show
megalodonte-package --project /path/to/application build deb
```

`show` prints the library version, implementation path and resolved application metadata. It does not expose credentials.

## Commands and options

```sh
megalodonte-package --project . build appimage --run
megalodonte-package --project . build app-image
megalodonte-package --project . build deb
megalodonte-package --project . build msi
megalodonte-package --project . build msi --profile store
megalodonte-package --project . build flatpak --install-flatpak
megalodonte-package --project . version patch
megalodonte-package --project . version release 1.2.0
```

Profiles must be declared by the application. `--dry-run` prints commands without building, deleting files or reading credentials. `--platform windows|linux` is available only with `--dry-run`. `--skip-build` reuses a Gradle output; `--smoke-test` briefly launches the generated runtime; `--keep-work` retains staging. `--open` opens the output directory outside CI. `--run` launches an AppImage and writes `dist/appimage-run.log`. `--install-flatpak` explicitly allows local installation; the default only builds.

`version patch` increments `appPatch` in the application's `gradle.properties`. `version release X.Y.Z` sets `appVersion` and resets `appPatch` to zero in that file.

## Configuration

An application owns `packaging.toml` (`schema_version = 1`). It declares its name, main class, build mode, JavaFX version, icons, runtime modules, native exclusions, package metadata and optional profiles. Version and vendor can also come from `gradle.properties`. See [the configuration reference](docs/CONFIGURATION.md) and [migration notes](docs/MIGRATION.md).

```python
from pathlib import Path
from megalodonte_packaging import Packager, load_config

config = load_config(Path('/path/to/application'))
output = Packager(config).package('msi')
```

The pipeline accepts a fat JAR or a distribution with separate dependency JARs. JavaFX and the linked runtime stay separate from the application input. Ambiguous application JAR selection fails explicitly; source, documentation and test JARs are excluded. `.env` is never copied into the installer.

Staging is confined to `.packaging/<kind>-<profile>/` under the application root. Outputs go to `dist/`; building one format does not remove the others. Rebuilding the same installer replaces that file. An existing application-image directory must be removed explicitly. Failures keep staging for diagnosis.

For MSI, the three-field installer version maps `major.minor.micro` plus an optional patch to `major.minor.(micro*1000+patch)`. The business version and file name retain the original application version. Applications can override `windows.installer_version` when needed.

## Continuous integration

The reusable [JavaFX package workflow](.github/workflows/package-javafx.yml) builds on Linux and Windows. Applications call it from their own repository; `MEGALODONTE_PACKAGING_SOURCE` can point to a pinned Git revision or a published wheel. Without that variable, the workflow installs this repository's `main` branch. The workflow uses the WiX version available on the Windows runner, avoiding a downgrade of an already installed toolset. See [GitHub Actions integration](docs/GITHUB_ACTIONS.md).

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover configuration, Windows/Linux command construction, staging, classpaths, native libraries, versions, redaction and output preservation. They do not install applications or use real credentials.
