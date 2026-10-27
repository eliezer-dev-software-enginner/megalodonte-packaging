"""Idempotently wire the known JavaFX applications to the shared library.

This tool changes only packaging configuration and command wrappers. Run from any
directory; --workspace points to the development workspace containing megalodonte-world.
"""
import argparse
from pathlib import Path
import json
import uuid


BOOTSTRAP = '''#!/usr/bin/env python3
"""Thin command adapter; the packaging implementation lives in the shared library."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent.parent


def load_shared_library():
    override = os.environ.get("MEGALODONTE_PACKAGING_HOME")
    if override:
        candidates = [Path(override).resolve() / "src"]
    else:
        candidates = [candidate for parent in (ROOT, *ROOT.parents)
                      for candidate in (parent / "framework/megalodonte-packaging/src",)]
    source = next((p for p in candidates if (p / "megalodonte_packaging").is_dir()), None)
    if override and source is None:
        raise SystemExit("MEGALODONTE_PACKAGING_HOME does not contain the shared library")
    if source is not None:
        sys.path.insert(0, str(source))
    try:
        from megalodonte_packaging.cli import main as cli
    except ModuleNotFoundError as error:
        if error.name != "megalodonte_packaging":
            raise
        raise SystemExit("Install the shared library: python -m pip install -e PATH/TO/megalodonte-packaging") from None
    return cli


def main(arguments=None):
    return load_shared_library()(["--project", str(ROOT), *(sys.argv[1:] if arguments is None else arguments)])


if __name__ == "__main__":
    raise SystemExit(main())
'''


def quoted(value):
    return json.dumps(value, ensure_ascii=False)


def app_specs(workspace):
    world = workspace / "megalodonte-world"
    specs = []
    legacy_uuid = "e3a2b1c4-7d5f-4a8e-9c6b-2f1d0a3e7b8c"
    for name in ("plics-sw", "gobitech-pesagem", "nojo-engine-ui-creator"):
        specs.append(dict(root=world / "applications" / name, version_property="gobitech.appVersion" if name == "gobitech-pesagem" else "plics.appVersion",
                          upgrade_uuid=legacy_uuid, icons=True, store=name != "gobitech-pesagem",
                          flatpak="io.github.eliezerdevsoftwareenginner.gobitech" if name == "gobitech-pesagem" else "io.github.eliezerdevsoftwareenginner.PlicsSW",
                          updater=False))
    demos = [("megalodonte-app1-welcome", "Megalodonte Welcome"), ("megalodonte-app2-counter", "Megalodonte Counter"),
             ("megalodonte-app3-string-lenght", "Megalodonte String Length"), ("megalodonte-app4-hide-seek", "Megalodonte Hide Seek"),
             ("megalodonte-app5-todo-list", "Megalodonte Todo List")]
    for name, display in demos:
        specs.append(dict(root=world / "framework/megalodonte-ecossystem" / name, display=display, icons=True, updater=True,
                          upgrade_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL, "megalodonte:" + name))))
    specs.append(dict(root=world / "applications/Everest", icon_linux="src/main/resources/assets/Logo.png"))
    specs.append(dict(root=world / "applications/megalodonte-cliente", display="Megalodonte Cliente", version="0.1.0",
                      main="megalodonte.script.ScriptLauncher", mode="distribution", tasks=["installDist"],
                      jar="build/install/megalodonte-cliente/lib/megalodonte-cliente-{version}.jar"))
    specs.append(dict(root=workspace / "ftp-file-pusher", display="adb_file_pusher", version="1.0.0", main="my_app.Main",
                      mode="classpath", tasks=["jar", "copyDependencies"], jar="build/libs/adb-file-pusher-{version}.jar",
                      dependencies="build/dependencies/*.jar", icon_linux="src/main/resources/logo_256x256.png"))
    specs.append(dict(root=world / "applications/disgust/disgust-ui", display="Disgust UI", version="1.0.0", main="disgust.ui.Main",
                      mode="distribution", tasks=[":disgust-ui:installDist"],
                      jar="build/install/disgust-ui/lib/disgust-ui-*.jar"))
    return specs


def write_project(spec):
    root = spec["root"]
    if not (root / "build.gradle.kts").is_file():
        raise ValueError(f"Missing JavaFX project: {root}")
    scripts = root / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "package.py").write_text(BOOTSTRAP, encoding="utf-8")
    lines = ["# Only application-specific data; implementation is shared across all clients.", "schema_version = 1", "", "[app]"]
    for key, value in (("name", spec.get("display")), ("version", spec.get("version")), ("main_class", spec.get("main")),
                       ("version_property", spec.get("version_property"))):
        if value:
            lines.append(f"{key} = {quoted(value)}")
    if spec.get("icons"):
        lines.extend(['icon_windows = "src/main/resources/assets/app_ico.ico"', 'icon_linux = "src/main/resources/assets/app_ico.png"'])
    elif spec.get("icon_linux"):
        lines.append("icon_linux = " + quoted(spec["icon_linux"]))
    lines.extend(["", "[build]", "mode = " + quoted(spec.get("mode", "fat-jar")),
                  "tasks = " + quoted(spec.get("tasks", ["clean", "shadowJar"])),
                  "jar = " + quoted(spec.get("jar", "build/libs/*.jar"))])
    if spec.get("dependencies"):
        lines.append("dependencies = " + quoted(spec["dependencies"]))
    lines.extend(["", "[javafx]", 'version = "25.0.1"', "", "[runtime]",
                  'modules = ["javafx.controls", "java.sql", "jdk.zipfs", "java.logging", "java.xml", "jdk.charsets"]',
                  'exclude_natives = ["jfxwebkit.dll"]'])
    lines.extend(["", "[windows]", "upgrade_uuid = " + quoted(spec.get("upgrade_uuid", str(uuid.uuid5(uuid.NAMESPACE_URL, "megalodonte:" + root.name)))),
                  "per_user = true", "", "[linux]", "package_name = " + quoted(root.name.lower()), 'menu_group = "Office"'])
    if spec.get("flatpak"):
        lines.extend(["", "[flatpak]", "manifest = " + quoted(f"flatpak/{spec['flatpak']}.yml")])
    if spec.get("store"):
        lines.extend(["", "[profiles.store]", 'java_options = ["-Dplics.microsoftStore=true"]'])
    if spec.get("updater"):
        lines.extend(["", "# Legacy optional launcher; build rejects it if its class is absent.", "[profiles.updater]",
                      "launcher_name = " + quoted(spec["display"] + " Updater"), 'launcher_class = "my_app.updater.Main"'])
    (root / "packaging.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    commands = {"create-msi.py": ["build", "msi"], "create-deb.py": ["build", "deb"], "create-app-image.py": ["build", "app-image"]}
    if spec.get("store"):
        commands["create-msi-store.py"] = ["build", "msi", "--profile", "store"]
    if spec.get("flatpak") or (scripts / "create-flatpak.py").exists():
        commands["create-flatpak.py"] = ["build", "flatpak"]
    if spec.get("updater"):
        commands["create-msi-with-updater.py"] = ["build", "msi", "--profile", "updater"]
        commands["create-deb-with-updater.py"] = ["build", "deb", "--profile", "updater"]
    for filename, arguments in commands.items():
        content = '#!/usr/bin/env python3\n"""Compatibility command backed by megalodonte-packaging."""\nimport sys\nfrom package import main\n\nif __name__ == "__main__":\n    raise SystemExit(main(' + repr(arguments) + ' + sys.argv[1:]))\n'
        (scripts / filename).write_text(content, encoding="utf-8")
    if (root / "gradle.properties").is_file():
        (scripts / "bump_version.py").write_text('from package import main\nimport sys\n\nif __name__ == "__main__":\n    raise SystemExit(main(["version", *sys.argv[1:]]))\n', encoding="utf-8")
    # These config modules had no consumers outside the migrated wrappers. Keep a
    # lightweight, import-safe view for developers; no packaging algorithm is copied.
    if (scripts / "config.py").exists():
        (scripts / "config.py").write_text('"""Application configuration; use package.py for packaging commands."""\nfrom package import ROOT, load_shared_library\n\nload_shared_library()\nfrom megalodonte_packaging import load_config\nCONFIG = load_config(ROOT)\nAPP_NAME = CONFIG.name\nAPP_VERSION = CONFIG.version\nMAIN_CLASS = CONFIG.main_class\n', encoding="utf-8")
    if (scripts / "updater_config.py").exists():
        (scripts / "updater_config.py").write_text('from config import CONFIG\n\n_profile = CONFIG.profile("updater")\nUPDATER_NAME = _profile["launcher_name"]\nUPDATER_MAIN_CLASS = _profile["launcher_class"]\nUPGRADE_UUID = CONFIG.upgrade_uuid\n', encoding="utf-8")
    ignore = root / ".gitignore"
    content = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
    for entry in ("/.packaging/", "/dist/", "__pycache__/"):
        if entry not in content.splitlines():
            content += "\n" + entry + "\n"
    ignore.write_text(content, encoding="utf-8")
    (scripts / "PACKAGING.md").write_text('''# Empacotamento compartilhado

A implementação está na biblioteca `megalodonte-packaging`, compartilhada por todos os clientes.
`packaging.toml` contém apenas os dados específicos deste aplicativo. A versão vem de
`gradle.properties` quando presente; a configuração não copia os algoritmos da biblioteca.

```sh
python scripts/package.py show
python scripts/create-msi.py --dry-run --platform windows
python scripts/create-deb.py --dry-run --platform linux
python scripts/create-msi.py
python scripts/create-deb.py
```

No workspace, o adaptador encontra automaticamente a mesma biblioteca fonte. Fora dele,
instale-a com `python -m pip install -e CAMINHO/megalodonte-packaging` ou instale seu wheel.
Use Python 3.11+, JDK completo e o SDK JavaFX configurado. MSI exige Windows/WiX;
DEB exige Linux e as ferramentas do jpackage. Não há empacotamento cruzado.

`--smoke-test` abre o aplicativo brevemente; `--open` abre a pasta de saída.
Flatpak não instala automaticamente: acrescente `--install-flatpak` para instalar.
O perfil updater exige que a classe correspondente exista no JAR; o perfil store
apenas acrescenta as opções configuradas para a Microsoft Store.

Veja o README da biblioteca para API Python, configuração completa, CI e versões MSI.
''', encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    specs = app_specs(workspace)
    for spec in specs:
        if not spec["root"].resolve().is_relative_to(workspace):
            raise ValueError("Project outside workspace")
        write_project(spec)
        print(spec["root"].relative_to(workspace))


if __name__ == "__main__":
    main()
