"""GitHub Actions bootstrap: publish dependencies locally before building a client."""
import argparse
import os
from pathlib import Path
import subprocess

from .config import load_config


OWNER = "eliezer-dev-software-enginner"
DEPENDENCIES = {
    "pack-utilities": ("pack-utilities", ["test", "publishToMavenLocal"]),
    "disgust": ("disgust-components", ["publishToMavenLocal", ":disgust-icons:publishToMavenLocal"]),
    "jsonc-ui": ("megalodonte-jsonc-ui", ["test", "publishToMavenLocal"]),
    "script-app": ("megalodonte-script-app", ["test", "publishToMavenLocal"]),
    "simple-clipboard": ("megalodonte-simple-clipboard", ["test", "publishToMavenLocal"]),
}


def run(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def clone(repository, destination, *, submodules=False):
    command = ["git", "clone", "--depth", "1"]
    if submodules:
        command += ["--recurse-submodules"]
    ref = os.environ.get("CI_REF_" + repository.upper().replace("-", "_"))
    if ref:
        command += ["--branch", ref]
    run([*command, f"https://github.com/{OWNER}/{repository}.git", str(destination)], destination.parent)


def prepare(workspace: Path, dependencies: list[str]):
    unknown = set(dependencies) - DEPENDENCIES.keys()
    if unknown:
        raise ValueError(f"Unknown CI dependencies: {', '.join(sorted(unknown))}")
    selected = set(dependencies)
    if "disgust" in selected:
        selected.add("pack-utilities")
    if "script-app" in selected:
        selected.add("jsonc-ui")
    workspace.mkdir(parents=True, exist_ok=True)
    libs = workspace / "megalodonte-libs"
    clone("megalodonte-libs", libs, submodules=True)
    run(["pwsh", "-NoProfile", "-File", str(libs / "install-all.ps1")] if os.name == "nt"
        else ["bash", str(libs / "install-all.sh")], libs)
    # Dependency order matters: utilities -> Disgust, JSONC -> script launcher.
    for name, (repository, tasks) in DEPENDENCIES.items():
        if name not in selected:
            continue
        directory = workspace / repository
        clone(repository, directory)
        wrapper = [str(directory / "gradlew.bat")] if os.name == "nt" else ["bash", str(directory / "gradlew")]
        run([*wrapper, *tasks, "--no-daemon", "--console=plain"], directory)


def metadata(project: Path, output: Path, check_tag=False):
    config = load_config(project)
    if check_tag and os.environ.get("GITHUB_REF_TYPE") == "tag":
        if os.environ.get("GITHUB_REF_NAME") != f"v{config.version}":
            raise ValueError("Release tag must match the version resolved from packaging.toml/gradle.properties")
    with output.open("a", encoding="utf-8") as stream:
        stream.write(f"version={config.version}\nname={config.name}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("prepare")
    bootstrap.add_argument("--workspace", type=Path, required=True)
    bootstrap.add_argument("--dependencies", nargs="*", choices=list(DEPENDENCIES), default=[])
    meta = commands.add_parser("metadata")
    meta.add_argument("--project", type=Path, required=True)
    meta.add_argument("--output", type=Path, required=True)
    meta.add_argument("--check-tag", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.workspace.resolve(), args.dependencies)
    else:
        metadata(args.project.resolve(), args.output, args.check_tag)


if __name__ == "__main__":
    main()
