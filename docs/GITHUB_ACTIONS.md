# JavaFX client GitHub Actions

The reusable [package-javafx.yml](../.github/workflows/package-javafx.yml) workflow builds MSI on Windows and AppImage and DEB on Linux. A caller supplies its project directory, artifact prefix, optional extra source dependencies, release flag and Linux smoke-test flag.

For a new application, create `packaging.toml`, then generate the caller before the first commit. A local script adapter is optional; the shared CLI accepts `--project` directly:

```bash
python tools/configure_client_actions.py --project /path/to/app --artifact my-application --dependencies 'script-app'
```

The generator refuses to overwrite an existing workflow unless `--force` is given. Register the application in the workspace manifest and run `python tools/verify-workspace.py`; that audit rejects packaged applications with no Actions caller. The historical `--workspace` mode is only for replaying the original migration.

## Caller

```yaml
name: Package installers
on:
  workflow_dispatch:
  push:
    tags: ['v*']
permissions:
  contents: write
jobs:
  package:
    uses: eliezer-dev-software-enginner/megalodonte-packaging/.github/workflows/package-javafx.yml@main
    with:
      project-directory: .
      artifact-name: my-application
      dependencies: 'jsonc-ui'
      release: true
      smoke-test: true
```

Only declare extra dependencies that the application actually uses. Supported names are `pack-utilities`, `disgust`, `jsonc-ui`, `script-app` and `simple-clipboard`. `disgust` implies `pack-utilities`; `script-app` implies `jsonc-ui`. The `prepare` command clones and publishes the six desktop framework libraries in dependency order, then clones and publishes selected extra dependencies. The separate portable reactivity library is not part of desktop CI. CI sets `ORG_GRADLE_PROJECT_useLocalSources=false` to avoid accidentally depending on a developer's adjacent checkout.

Do not forward application credentials to this workflow. The installer contains no project `.env`; each installation supplies credentials through its process environment or a protected per-user `.env` at runtime.

## Version and release

For tag builds, `vVERSION` must match the version resolved from `packaging.toml` and `gradle.properties`. With `release: true`, the workflow downloads the platform artifacts and creates or updates a GitHub Release with `.AppImage`, `.deb` and `.msi`. The caller needs `contents: write`. With `release: false`, the workflow only uploads Actions artifacts.

The application repository's workflow references this reusable workflow by a Git ref. For reproducibility, pin that ref to a tag or SHA and set the repository or organization variable `MEGALODONTE_PACKAGING_SOURCE` to a wheel or pip Git URL for the same library revision. Without that variable, Python installs this repository's `main` branch. Public source repositories clone over HTTPS; private repositories require Git authentication configured before `prepare`.

## Publication order

1. Publish any changed framework or extra dependency repositories.
2. Publish this packaging library and its reusable workflow.
3. Update and run each application caller.

Local library changes can be tested with Maven local. The helper `tools/configure_client_actions.py` updates callers without copying the packaging pipeline. Run the library tests with `PYTHONPATH=src python -m unittest discover -s tests -v`.
