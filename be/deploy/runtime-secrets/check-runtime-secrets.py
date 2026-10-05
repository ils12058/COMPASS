#!/usr/bin/env python3
"""Host preflight: secret metadata and runtime assignment names/pointers only."""

from __future__ import annotations

import argparse
import pwd
import re
import sys
from pathlib import Path

from runtime_secrets import (
    SECRET_FILES,
    URL_SETTINGS,
    SecretCheckError,
    check_directory,
    check_file,
)


def assignments(env_file: Path) -> dict[str, str]:
    result = {}
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        raise SecretCheckError("runtime env: unreadable") from None
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", line)
        if not match:
            raise SecretCheckError(f"runtime env: unsupported assignment at line {number}")
        name, value = match.groups()
        if name in result:
            raise SecretCheckError(f"runtime env: duplicate assignment at line {number}")
        result[name] = value.strip()
    return result


def literal_pointer(value: str) -> str:
    # Only literal paths are supported: do not evaluate shell syntax or interpolation.
    match = re.fullmatch(r"(?:'([^']*)'|\"([^\"]*)\"|([^\s'\"#]+))(?:\s+#.*)?", value)
    return next((group for group in match.groups() if group is not None), "") if match else ""


def check_runtime(directory: Path, env_file: Path, owner_uid: int) -> None:
    check_directory(directory, owner_uid)
    for setting in SECRET_FILES:
        check_file(directory, setting, owner_uid)
    values = assignments(env_file)
    forbidden = (*SECRET_FILES, *URL_SETTINGS, *(f"{name}_FILE" for name in URL_SETTINGS))
    for name in (*forbidden, "DEMO_ACCOUNT_PASSWORD", "DEMO_ACCOUNT_PASSWORD_FILE"):
        if name in values:
            raise SecretCheckError(f"{name}: forbidden in long-running runtime env")
    for setting, filename in SECRET_FILES.items():
        name = f"{setting}_FILE"
        if name not in values or literal_pointer(values[name]) != f"/run/secrets/{filename}":
            raise SecretCheckError(f"{name}: expected literal /run/secrets/{filename} pointer")
    if "COMPASS_SECRETS_DIR" in values:
        if literal_pointer(values["COMPASS_SECRETS_DIR"]) != str(directory):
            raise SecretCheckError("COMPASS_SECRETS_DIR: does not match checked directory")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-dir", type=Path, default=Path("/opt/compass/secrets"))
    parser.add_argument("--env-file", type=Path, default=Path("/opt/compass/.env"))
    parser.add_argument("--owner", default="compass")
    args = parser.parse_args()
    try:
        owner_uid = pwd.getpwnam(args.owner).pw_uid
        check_runtime(args.secrets_dir, args.env_file, owner_uid)
    except KeyError:
        print("runtime secrets: deployment owner does not exist", file=sys.stderr)
        return 1
    except SecretCheckError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Runtime secret metadata and file-only configuration verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
