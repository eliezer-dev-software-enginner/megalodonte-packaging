"""Generate one client workflow, or replay the historical workspace migration."""
import argparse
from pathlib import Path


OWNER = "eliezer-dev-software-enginner"
WORKFLOW = f"{OWNER}/megalodonte-packaging/.github/workflows/package-javafx.yml@main"
DEPENDENCIES = {"pack-utilities", "disgust", "jsonc-ui", "script-app", "simple-clipboard"}


def client_workflow(name, directory=".", dependencies="", release=True, smoke=False):
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
"""


def configure_client(project, artifact, dependencies="", smoke=True, release=True, force=False):
    """Create the standard caller without replacing a hand-maintained workflow."""
    unknown = set(dependencies.split()) - DEPENDENCIES
    if unknown:
        raise ValueError(f"Unknown dependencies: {', '.join(sorted(unknown))}")
    if not (project / "packaging.toml").is_file() or not (project / "scripts/package.py").is_file():
        raise ValueError("Project needs packaging.toml and scripts/package.py")
    target = project / ".github/workflows/package.yml"
    if target.exists() and not force:
        raise FileExistsError(f"Workflow already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(client_workflow(artifact, dependencies=dependencies, release=release, smoke=smoke), encoding="utf-8")
    return target


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
        (world / "applications/plics-sw", "plics-sw", "pack-utilities disgust jsonc-ui", True),
        (world / "applications/gobitech-pesagem", "gobitech", "pack-utilities jsonc-ui", True),
        (world / "nojo-engine-ui-creator", "nojo-engine-ui-creator", "pack-utilities", False),
        (world / "applications/Everest", "everest", "", False),
        (world / "applications/megalodonte-cliente", "megalodonte-cliente", "script-app", False),
        (workspace / "ftp-file-pusher", "ftp-file-pusher", "simple-clipboard", False),
    ]
    for root, name, dependencies, smoke in clients:
        target = root / ".github/workflows/package.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(client_workflow(name, dependencies=dependencies, smoke=smoke), encoding="utf-8")
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
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--workspace", type=Path, help="Replay the historical multi-project migration")
    location.add_argument("--project", type=Path, help="Create one standard application workflow")
    parser.add_argument("--artifact", help="Artifact name for --project")
    parser.add_argument("--dependencies", default="", help="Space-separated extra Megalodonte dependencies")
    parser.add_argument("--no-smoke-test", action="store_true")
    parser.add_argument("--no-release", action="store_true")
    parser.add_argument("--force", action="store_true", help="Replace an existing workflow")
    args = parser.parse_args()
    if args.project:
        if not args.artifact:
            parser.error("--artifact is required with --project")
        print(configure_client(args.project.resolve(), args.artifact, args.dependencies,
                               not args.no_smoke_test, not args.no_release, args.force))
    else:
        configure(args.workspace.resolve())
