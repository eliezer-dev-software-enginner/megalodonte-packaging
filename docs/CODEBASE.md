# Packaging codebase

`megalodonte-packaging` exposes `PackageConfig`, `load_config` and `Packager` from its Python package. The CLI is `megalodonte-package` or `python -m megalodonte_packaging`; application adapters pass `--project <root>` to the same entry point. The library does not import an application at runtime.

| Source | Responsibility |
| --- | --- |
| [`config.py`](../src/megalodonte_packaging/config.py) | Parse and validate `packaging.toml`, `gradle.properties`, paths, profiles and composite versions. |
| [`builder.py`](../src/megalodonte_packaging/builder.py) | Preflight tools and platform, run Gradle, prepare inputs, link a runtime, call `jpackage` and assemble AppImage/Flatpak output. |
| [`credentials.py`](../src/megalodonte_packaging/credentials.py) | Resolve declared environment properties, encode where requested and redact sensitive command previews. |
| [`cli.py`](../src/megalodonte_packaging/cli.py) | Dispatch `show`, `build` and `version` with safe argument parsing and error reporting. |
| [`ci.py`](../src/megalodonte_packaging/ci.py) | Clone and publish framework/dependency sources for CI and resolve release metadata. |
| [`__main__.py`](../src/megalodonte_packaging/__main__.py) | `python -m` entry point. |
| [`__init__.py`](../src/megalodonte_packaging/__init__.py) | Public Python API and version. |

The CLI catches configuration, OS and subprocess failures and avoids printing credential-bearing command arguments. `Packager.package` confines staging to `.packaging` under the application root. `preflight` verifies the host platform and required JDK, JavaFX and installer tools before destructive workspace cleanup. Tests under [`tests/`](../tests) cover both platform command plans without installing native packages.

See [configuration](CONFIGURATION.md), [CI integration](GITHUB_ACTIONS.md) and [migration](MIGRATION.md).
