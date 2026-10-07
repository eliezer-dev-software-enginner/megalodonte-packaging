"""Optional launcher properties sourced from environment/.env, never copied as a file."""
import base64
import os
from pathlib import Path


def dotenv(root: Path) -> dict[str, str]:
    path = root / ".env"
    values = {}
    if path.is_file():
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, separator, value = line.partition("=")
            if not separator or not key.strip():
                raise ValueError(f"Invalid .env line {number}")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            values[key.strip()] = value
    return values


def environment_options(root: Path, definitions: list[dict], *, redact: bool = False) -> list[str]:
    values = None
    result = []
    for definition in definitions:
        key, prop = definition["environment"], definition["property"]
        if redact:
            result.append(f"-D{prop}=<from:{key}>")
            continue
        value = os.environ.get(key)
        if not value:
            if values is None:
                values = dotenv(root)
            value = values.get(key)
        if not value or not value.strip():
            if definition.get("required", True):
                raise ValueError(f"Set {key} in the environment or project .env")
            continue
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} cannot contain newlines")
        encoding = definition.get("encoding", "plain")
        if encoding == "base64":
            value = base64.b64encode(value.encode("utf-8")).decode("ascii")
        elif encoding != "plain":
            raise ValueError(f"Unsupported encoding for {key}")
        result.append(f"-D{prop}={value}")
    return result
