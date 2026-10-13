"""Apply shared Actions and Maven-local utilities coordinates to the twelve clients."""
import argparse
from pathlib import Path


OWNER = "eliezer-dev-software-enginner"
WORKFLOW = f"{OWNER}/megalodonte-packaging/.github/workflows/package-javafx.yml@main"


def client_workflow(name, directory=".", dependencies="", release=True, smoke=False, credentials=False):
    secret_section = """
    secrets:
      GOBITECH_ADMIN_LOGIN: ${{ secrets.GOBITECH_ADMIN_LOGIN }}
      GOBITECH_ADMIN_PASSWORD: ${{ secrets.GOBITECH_ADMIN_PASSWORD }}
""" if credentials else ""
    return f"""name: Package installers
on:
  workflow_dispatch:
  push:
    tags: ['v*']
permissions:
  contents: write
concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: false
jobs:
  package:
    uses: {WORKFLOW}
    with:
      project-directory: {directory}
      artifact-name: {name}
      dependencies: '{dependencies}'
      release: {str(release).lower()}
      smoke-test: {str(smoke).lower()}
{secret_section}"""


def remove_module_workaround(text):
    marker = "extraJavaModuleInfo {"
    if marker in text:
        start = text.index(marker)
        end = text.index("\n}", start) + 2
        text = text[:start] + text[end:]
    text = text.replace('    id("org.gradlex.extra-java-module-info") version "1.14.2"\n', "")
    text = text.replace('// The published utilities JAR lacks module metadata and its v1.0.0 filename\n// cannot yield a valid automatic module name.\n', "")
    return text


def configure(workspace):
    world = workspace / "megalodonte-world"
    clients = [
        (world / "applications/plics-sw", "plics-sw", "pack-utilities disgust jsonc-ui", True, False),
        (world / "applications/gobitech-pesagem", "gobitech", "pack-utilities", True, True),
        (world / "nojo-engine-ui-creator", "nojo-engine-ui-creator", "pack-utilities", False, False),
        (world / "applications/Everest", "everest", "", False, False),
        (world / "applications/megalodonte-cliente", "megalodonte-cliente", "script-app", False, False),
        (workspace / "ftp-file-pusher", "ftp-file-pusher", "simple-clipboard", False, False),
    ]
    for root, name, dependencies, smoke, credentials in clients:
        target = root / ".github/workflows/package.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(client_workflow(name, dependencies=dependencies, smoke=smoke, credentials=credentials), encoding="utf-8")
    ecosystem = world / "framework/megalodonte-ecossystem"
    demos = ["megalodonte-app1-welcome", "megalodonte-app2-counter", "megalodonte-app3-string-lenght",
             "megalodonte-app4-hide-seek", "megalodonte-app5-todo-list"]
    matrix = client_workflow("${{ matrix.app }}", "${{ matrix.app }}", release=False)
    matrix = matrix.replace("  package:\n", "  package:\n    strategy:\n      fail-fast: false\n      matrix:\n        app: [" + ", ".join(demos) + "]\n")
    target = ecosystem / ".github/workflows/package.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(matrix, encoding="utf-8")
    disgust = world / "applications/disgust"
    target = disgust / ".github/workflows/package.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(client_workflow("disgust-ui", "disgust-ui", "pack-utilities", release=False), encoding="utf-8")
    builds = [root / "build.gradle.kts" for root, *_ in clients]
    builds += [ecosystem / demo / "build.gradle.kts" for demo in demos]
    builds += [disgust / "build.gradle.kts", disgust / "disgust-ui/build.gradle.kts"]
    for path in builds:
        text = path.read_text(encoding="utf-8")
        text = text.replace("com.github.eliezer-dev-software-enginner:pack-utilities:v1.0.0", "pack.utilities:pack-utilities:1.0.0")
        # Local publications should always override remote coordinates.
        text = text.replace("    mavenCentral()\n    mavenLocal()", "    mavenLocal()\n    mavenCentral()")
        jitpack = '    maven { url = uri("https://jitpack.io") }'
        if "com.github.anastaciocintra:escpos-coffee" in text:
            text = text.replace('maven { url = uri("https://jitpack.io") }', 'maven {\n        url = uri("https://jitpack.io")\n        content { includeGroup("com.github.anastaciocintra") }\n    }')
        else:
            text = text.replace(jitpack + "\n", "")
        if path.is_relative_to(disgust):
            text = remove_module_workaround(text)
        text = text.replace('        // Only third-party printing support still uses JitPack.\n        // Utilities are resolved exclusively from Maven local.\n\n', '')
        path.write_text(text.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    configure(parser.parse_args().workspace.resolve())
