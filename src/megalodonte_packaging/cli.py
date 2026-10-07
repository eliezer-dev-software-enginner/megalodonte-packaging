"""CLI shared by every project wrapper and the installed console entry point."""
import argparse
import json
from pathlib import Path
import re
import sys

from . import __version__
from .builder import Packager
from .config import load_config, read_properties, composed_version


def bump_version(root: Path, action: str, value: str | None = None):
    path = root / "gradle.properties"
    content = path.read_text(encoding="utf-8")
    props = read_properties(path)
    base, patch = props["appVersion"], int(props.get("appPatch", "0") or "0")
    old = composed_version(base, patch)
    if action == "patch":
        updates = {"appPatch": str(patch + 1)}
        new = composed_version(base, patch + 1)
    else:
        if value is None:
            raise ValueError("release requires X.Y.Z")
        new = composed_version(value, 0)
        updates = {"appVersion": value, "appPatch": "0"}
    for key, replacement in updates.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{key}={replacement}", content)
        else:
            content = content.rstrip("\n") + f"\n{key}={replacement}\n"
    path.write_text(content, encoding="utf-8")
    print(f"Version: {old} -> {new}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Shared JavaFX installer pipeline")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--version", action="version", version=f"megalodonte-packaging {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    describe = commands.add_parser("show", help="Show configuration and implementation path without reading credentials")
    describe.add_argument("--profile", default="default")
    package = commands.add_parser("build")
    package.add_argument("kind", choices=("msi", "deb", "app-image", "flatpak"))
    package.add_argument("--profile", default="default")
    package.add_argument("--platform", choices=("windows", "linux"), help="For dry-run previews only")
    package.add_argument("--dry-run", action="store_true", help="Print commands without builds, deletes or credential reads")
    package.add_argument("--skip-build", action="store_true")
    package.add_argument("--smoke-test", action="store_true", help="Briefly launch the generated runtime")
    package.add_argument("--open", action="store_true", help="Open the output folder after successful packaging")
    package.add_argument("--keep-work", action="store_true")
    package.add_argument("--install-flatpak", action="store_true", help="Explicitly install Flatpak for the current user")
    bump = commands.add_parser("version")
    bump.add_argument("action", choices=("patch", "release"))
    bump.add_argument("value", nargs="?")
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            bump_version(args.project.resolve(), args.action, args.value)
            return 0
        config = load_config(args.project)
        builder = Packager(config, args.profile, getattr(args, "platform", None))
        if args.command == "show":
            print(json.dumps({"library_version": __version__, "library": str(Path(__file__).resolve().parent),
                              "project": str(config.root), "name": config.name, "version": config.version,
                              "main_class": config.main_class, "profile": args.profile,
                              "build_tasks": config.build.get("tasks", ["clean", "shadowJar"]), "java_options": builder.java_options(redact=True)}, ensure_ascii=False, indent=2))
        elif args.dry_run:
            work = builder.workspace(args.kind)
            print(json.dumps({"gradle": builder.gradle_command(), "jlink": builder.jlink_command(work),
                              "jpackage": builder.jpackage_command(work, "app-image" if args.kind == "flatpak" else args.kind, redact=True)}, indent=2))
        else:
            if args.platform:
                raise ValueError("--platform is allowed only with --dry-run")
            output = builder.package(args.kind, skip_build=args.skip_build, smoke=args.smoke_test,
                                     open_folder=args.open, keep_work=args.keep_work, install_flatpak=args.install_flatpak)
            print(f"Created: {output}")
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f"Packaging error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
