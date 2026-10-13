# JavaFX client GitHub Actions

The reusable [package-javafx.yml](../.github/workflows/package-javafx.yml) workflow builds MSI on Windows and DEB on Linux. A caller supplies its project directory, artifact prefix, optional extra source dependencies, release flag and Linux smoke-test flag. This reusable workflow currently packages DEB and MSI; clients that also need AppImage can invoke the packaging CLI in their own Linux job, as the Megalodonte Git client does.

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

Only declare dependencies that the application actually uses. Supported names are `pack-utilities`, `disgust`, `jsonc-ui`, `script-app` and `simple-clipboard`. `disgust` implies `pack-utilities`; `script-app` implies `jsonc-ui`. The `prepare` command clones `megalodonte-libs` recursively, publishes its libraries to Maven local, then clones and publishes selected extra dependencies in dependency order. The CI sets `ORG_GRADLE_PROJECT_useLocalSources=false` to avoid accidentally depending on a developer's adjacent checkout.

If the caller needs the existing Gobitech administrator settings, it must explicitly forward `GOBITECH_ADMIN_LOGIN` and `GOBITECH_ADMIN_PASSWORD` as secrets. Those values are only available to the packaging job and are not printed. Other applications should not copy those settings into their workflow. Runtime application credentials must be provided at runtime, not baked into a public installer.

## Version and release

For tag builds, `vVERSION` must match the version resolved from `packaging.toml` and `gradle.properties`. With `release: true`, the workflow downloads the two platform artifacts and creates or updates a GitHub Release with `.deb` and `.msi`. The caller needs `contents: write`. With `release: false`, the workflow only uploads Actions artifacts.

The application repository's workflow references this reusable workflow by a Git ref. For reproducibility, pin that ref to a tag or SHA and set the repository or organization variable `MEGALODONTE_PACKAGING_SOURCE` to a wheel or pip Git URL for the same library revision. Without that variable, Python installs this repository's `main` branch. Public source repositories clone over HTTPS; private repositories require Git authentication configured before `prepare`.

## Publication order

1. Publish any changed framework or extra dependency repositories.
2. Publish this packaging library and its reusable workflow.
3. Update and run each application caller.

Local library changes can be tested with Maven local. The helper `tools/configure_client_actions.py` updates callers without copying the packaging pipeline. Run the library tests with `PYTHONPATH=src python -m unittest discover -s tests -v`.
