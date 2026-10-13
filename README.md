# Megalodonte Packaging

`megalodonte-packaging` is the shared Python library for native JavaFX installers. It owns the Gradle → application input → `jdeps`/`jlink` → `jpackage` pipeline, versioning, launcher profiles, and AppImage assembly. Application repositories keep only `packaging.toml` and a thin command adapter; they do not copy packaging algorithms.

The [codebase guide](docs/CODEBASE.md) maps each Python module to its responsibility and public API.

## Supported hosts and outputs

| Build host | Outputs | Required tools |
| --- | --- | --- |
| Linux | AppImage, DEB, Flatpak, application image | Python 3.11+, JDK with JMODs, matching JavaFX SDK; AppImage needs `appimagetool`, DEB needs `fakeroot`, Flatpak needs Flatpak Builder |
| Windows | MSI | Python 3.11+, JDK with JMODs, matching JavaFX SDK, WiX Toolset |

Cross-packaging is not supported. The JavaFX SDK version must match the application's `packaging.toml`. The library has no Python runtime dependencies.

## Workspace use

From an application repository that has `packaging.toml` and `scripts/package.py`:

```sh
python scripts/package.py show
python scripts/package.py build appimage --run
python scripts/package.py build deb
python scripts/package.py build msi --dry-run --platform windows
```

The adapter discovers the shared checkout, or uses `MEGALODONTE_PACKAGING_HOME` when set. Outside this workspace, install the library in a virtual environment:

```sh
python -m pip install -e /path/to/megalodonte-packaging
megalodonte-package --project /path/to/application show
megalodonte-package --project /path/to/application build deb
```

`show` prints the library version, implementation path and resolved application metadata. It does not expose credentials.

## Commands and options

```sh
python scripts/package.py build appimage --run
python scripts/package.py build app-image
python scripts/package.py build deb
python scripts/package.py build msi
python scripts/package.py build msi --profile store
python scripts/package.py build flatpak --install-flatpak
python scripts/package.py version patch
python scripts/package.py version release 1.2.0
```

Profiles must be declared by the application. `--dry-run` prints commands without building, deleting files or reading credentials. `--platform windows|linux` is available only with `--dry-run`. `--skip-build` reuses a Gradle output; `--smoke-test` briefly launches the generated runtime; `--keep-work` retains staging. `--open` opens the output directory outside CI. `--run` launches an AppImage and writes `dist/appimage-run.log`. `--install-flatpak` explicitly allows local installation; the default only builds.

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
