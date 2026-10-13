# Migration to the shared packaging library

Earlier application repositories contained independent Python scripts for configuration and native installer creation. The shared library now owns the pipeline. Existing `create-msi.py`, `create-deb.py`, `create-flatpak.py` and version helpers can remain as thin adapters while callers migrate to `scripts/package.py`. Application database tools, development servers and simulators are outside this migration.

## Application migration checklist

1. Add `packaging.toml` with `schema_version = 1`, a stable application name, main class, build mode, JavaFX version and native icon paths.
2. Replace copied packaging algorithms with an adapter that calls `megalodonte_packaging.cli.main` for the application root. Keep application-specific runtime options in TOML.
3. Preserve the existing Windows `upgrade_uuid` and the intended installer-version sequence. An accidental change can break upgrades of previously installed versions.
4. Declare extra launchers only when their classes are present in the main JAR. Keep Flatpak manifest and application IDs aligned with the existing distribution.
5. Validate `show` and `--dry-run` on both platforms, then build the native installers on their respective hosts. Check that the application starts and its runtime configuration resolves correctly.
6. For CI, call the reusable workflow or invoke the shared CLI; publish framework dependencies before the client. Pin the workflow and Python package to the same revision for reproducible releases.

The library can read `appVersion` and `appPatch` from `gradle.properties`, and `packaging.toml` can override application-specific details. `config.py` adapters should expose metadata only; internal helper copies should be removed. Example projects must use their own name and icons rather than inheriting another application's identity.

## Runtime credentials

Values supplied through `runtime.environment_properties` become launcher JVM properties and can be inspected in the installed package. Base64 only changes representation; it does not hide a secret. Keep true credentials outside the installer and read them from the runtime environment or a protected local configuration source. Never print or commit a project's `.env`.

## Shared source and release order

Publish changed dependency repositories, then this packaging repository, then consuming application workflows. `MEGALODONTE_PACKAGING_SOURCE` can select a wheel or pinned Git revision. If left unset, the reusable workflow installs `main` from this repository. The source checkout and reusable workflow should refer to the same revision to avoid release differences.
