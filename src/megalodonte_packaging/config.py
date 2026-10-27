"""Declarative per-application configuration, independent of the invocation directory."""
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
import uuid


def read_properties(path: Path) -> dict[str, str]:
    result = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "!")):
                key, separator, value = line.partition("=")
                if separator:
                    result[key.strip()] = value.strip()
    return result


def composed_version(base: str, patch: int) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", base) or patch < 0:
        raise ValueError("Version must be X.Y.Z and appPatch must be nonnegative")
    return base if patch == 0 else f"{base}.{patch}"


@dataclass(frozen=True)
class PackageConfig:
    root: Path
    data: dict
    properties: dict[str, str]

    @property
    def app(self):
        return self.data.get("app", {})

    @property
    def build(self):
        return self.data.get("build", {})

    @property
    def name(self):
        return self.app.get("name", self.properties.get("appDisplayName", self.properties.get("appName", self.root.name)))

    @property
    def base_version(self):
        return self.app.get("version", self.properties.get("appVersion", "0.1.0"))

    @property
    def patch(self):
        return int(self.properties.get("appPatch", "0") or "0")

    @property
    def version(self):
        return composed_version(self.base_version, self.patch)

    @property
    def main_class(self):
        return self.app.get("main_class", self.properties.get("appMainClass", ""))

    @property
    def vendor(self):
        return self.app.get("vendor", self.properties.get("appVendor", "Megalodonte"))

    @property
    def upgrade_uuid(self):
        # Existing applications explicitly retain their installer identity.
        return self.data.get("windows", {}).get("upgrade_uuid", str(uuid.uuid5(uuid.NAMESPACE_URL, "megalodonte:" + self.root.name)))

    @property
    def modules(self):
        return self.data.get("runtime", {}).get("modules", ["javafx.controls", "java.logging"])

    @property
    def javafx_version(self):
        return self.data.get("javafx", {}).get("version", "25.0.1")

    def profile(self, name: str) -> dict:
        if name == "default":
            return {}
        profiles = self.data.get("profiles", {})
        if name not in profiles:
            raise ValueError(f"Unknown packaging profile: {name}")
        return profiles[name]

    def path(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root) or target == self.root:
            raise ValueError(f"Project path must remain below its root: {relative}")
        return target

    def installer_version(self, kind: str) -> str:
        if kind != "msi":
            return self.version
        override = self.data.get("windows", {}).get("installer_version")
        if override:
            return override
        # Windows MSI accepts only three components. Always map the third component
        # so a new release remains newer than any patches of the previous release.
        major, minor, micro = map(int, self.base_version.split("."))
        if major > 255 or minor > 255 or self.patch >= 1000 or micro * 1000 + self.patch > 65535:
            raise ValueError("MSI version exceeds limits; set windows.installer_version explicitly")
        return f"{major}.{minor}.{micro * 1000 + self.patch}"


def load_config(root: Path | str) -> PackageConfig:
    root = Path(root).resolve()
    path = root / "packaging.toml"
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    allowed = {"schema_version", "app", "build", "javafx", "runtime", "windows", "linux", "flatpak", "profiles"}
    unknown = data.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown packaging sections: {', '.join(sorted(unknown))}")
    if data.get("schema_version") != 1:
        raise ValueError("packaging.toml must declare schema_version = 1")
    fields = {
        "app": {"name", "version", "main_class", "vendor", "version_property", "icon_windows", "icon_linux", "description", "copyright"},
        "build": {"mode", "tasks", "jar", "dependencies"}, "javafx": {"version", "sdk"},
        "runtime": {"modules", "java_options", "exclude_natives"},
        "windows": {"upgrade_uuid", "installer_version", "per_user"}, "linux": {"package_name", "menu_group"},
        "flatpak": {"manifest"},
    }
    for section, names in fields.items():
        table = data.get(section, {})
        if not isinstance(table, dict) or table.keys() - names:
            raise ValueError(f"Unknown or invalid properties in [{section}]")
    for name, profile in data.get("profiles", {}).items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not isinstance(profile, dict) or profile.keys() - {"java_options", "jpackage_args", "launcher_name", "launcher_class"}:
            raise ValueError(f"Invalid profile: {name}")
        if bool(profile.get("launcher_name")) != bool(profile.get("launcher_class")):
            raise ValueError(f"Profile {name} requires launcher_name and launcher_class together")
    for section, key in (("build", "tasks"), ("runtime", "modules"), ("runtime", "java_options"), ("runtime", "exclude_natives")):
        value = data.get(section, {}).get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or "\n" in item or "\r" in item for item in value):
            raise ValueError(f"{section}.{key} must be an array of single-line strings")
    config = PackageConfig(root, data, read_properties(root / "gradle.properties"))
    if not config.main_class or not re.fullmatch(r"[\w.$]+", config.main_class):
        raise ValueError("Declare app.main_class or appMainClass in gradle.properties")
    if not config.name or any(c in config.name for c in '/\\\n\r'):
        raise ValueError("Invalid application display name")
    config.version
    uuid.UUID(config.upgrade_uuid)
    if config.build.get("mode", "fat-jar") not in ("fat-jar", "distribution", "classpath"):
        raise ValueError("build.mode must be fat-jar, distribution or classpath")
    for module in config.modules:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", module):
            raise ValueError(f"Invalid runtime module: {module}")
    return config
