# `packaging.toml` reference

```toml
schema_version = 1

[app]
# Optional if gradle.properties supplies appDisplayName/appName/appVersion/appMainClass/appVendor.
name = "Example App"
version = "1.2.3"
main_class = "example.app.Main"
vendor = "Example Company"
version_property = "example.appVersion"
icon_windows = "src/main/resources/assets/app.ico"
icon_linux = "src/main/resources/assets/app.png"
description = "Example description"
copyright = "Copyright 2026"

[build]
mode = "fat-jar"
tasks = ["clean", "shadowJar"]
jar = "build/libs/*.jar"

[javafx]
version = "25.0.1"
# Optional; accepts {platform} and {version}; absolute or project-relative.
# sdk = "java_fx_modules/{platform}-{version}"

[runtime]
modules = ["javafx.controls", "java.sql", "jdk.zipfs", "java.logging", "java.xml", "jdk.charsets"]
java_options = []
exclude_natives = ["jfxwebkit.dll"]

[windows]
upgrade_uuid = "11111111-1111-4111-8111-111111111111"
per_user = true
# installer_version = "1.2.3000"

[linux]
package_name = "example-app"
menu_group = "Office"

[profiles.store]
java_options = ["-Dexample.microsoftStore=true"]

[profiles.updater]
launcher_name = "Example App Updater"
launcher_class = "example.updater.Main"
jpackage_args = []

[flatpak]
manifest = "flatpak/com.example.App.yml"
```

Artifact, staging and output paths resolve from the application root, independent of the invocation directory. Icon paths and JAR globs cannot escape that root. Set the external JavaFX SDK through `javafx.sdk` or `JAVAFX_MODULES_HOME`; the latter must contain `<platform>-<version>/lib`. The library also searches ancestor `java_fx_modules` directories in a workspace. `JAVA_HOME` must point to a complete JDK; a path ending in `bin` is normalized. On Windows, a JDK 25 under Program Files is a fallback when Java is not on `PATH`. WiX 3 can be discovered under Program Files or supplied through `WIX_HOME`/`PATH`.

## Build modes

- `fat-jar`: one application JAR, usually built with Shadow.
- `distribution`: one main JAR and dependency JARs from a Gradle distribution.
- `classpath`: one main JAR and dependencies in an explicit directory.

```toml
[build]
mode = "distribution"
tasks = ["installDist"]
jar = "build/install/example-app/lib/example-app-{version}.jar"
dependencies = "build/install/example-app/lib/*.jar"
```

If `dependencies` is omitted, sibling JARs beside the main JAR are used. The main JAR manifest receives a `Class-Path` containing the dependency names. JavaFX is excluded from that classpath because its modules live in the linked runtime. Dependency JARs are not modified. A signed main JAR is not rewritten because that would invalidate its signature.

## Runtime credentials

The packaging configuration does not accept `runtime.environment_properties`. Never bake credentials into launcher `-D` options: both plain text and Base64 values can be extracted from an installer. Applications should read process environment variables or a private per-user `.env` at runtime. The shared `megalodonte.config.RuntimeEnvironment` helper resolves `%APPDATA%/Megalodonte/<app>/.env` on Windows and `~/.config/megalodonte/<app>/.env` on Linux (respecting `XDG_CONFIG_HOME`). A project-root `.env` is accepted only while running from a source checkout with `packaging.toml`. The build workflow does not need application credentials.

## Versioning

`appVersion` has three numeric components. A nonnegative `appPatch` in `gradle.properties` adds a fourth business-version component when greater than zero. MSI maps its third installer component to `micro*1000+patch`; `major` and `minor` must be at most 255, the mapped component at most 65535, and `patch` below 1000. Override `installer_version` only with a compatible upgrade strategy. Do not change an already distributed application's `upgrade_uuid` without a migration plan.

## Additional launchers and Flatpak

An updater profile requires `launcher_class` to exist in the main JAR. The packaging library does not implement updater logic or generate missing Java classes. Flatpak requires an existing manifest plus `flatpak` and `flatpak-builder` on Linux. Auxiliary files under `flatpak/` are copied to staging beside the generated application image. `--install-flatpak` is required for local installation.
