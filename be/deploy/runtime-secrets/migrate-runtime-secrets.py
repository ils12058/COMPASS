#!/usr/bin/env python3
"""Operator-only export/compare of current effective configuration; never rotate values."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path

from runtime_secrets import (
    REQUIRED_SECRETS,
    SECRET_FILES,
    SecretCheckError,
    check_directory,
    check_file,
)

# Works from be/ on the host or /app in the existing application image.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path.cwd()))
from compass.common.config import env  # noqa: E402


def effective_values() -> dict[str, bytes]:
    values = {}
    for setting in SECRET_FILES:
        value = env(setting, "")
        if setting in REQUIRED_SECRETS and not value:
            raise SecretCheckError(f"{setting}: required effective value is missing")
        # The generic file reader normalizes CR/CRLF and strips final line endings.
        # Refuse an unrepresentable direct value rather than silently changing it.
        if "\r" in value or value.endswith("\n") or "\x00" in value:
            raise SecretCheckError(f"{setting}: cannot preserve exact value through _FILE")
        values[setting] = value.encode("utf-8")
    return values


def export_values(directory: Path, values: dict[str, bytes]) -> None:
    check_directory(directory, os.getuid())
    if any(os.path.lexists(directory / filename) for filename in SECRET_FILES.values()):
        raise SecretCheckError("export: destination files already exist; refusing to overwrite")
    for setting, filename in SECRET_FILES.items():
        fd, temporary = tempfile.mkstemp(prefix=".provision-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(values[setting])
                output.flush()
                os.fsync(output.fileno())
                os.fchmod(output.fileno(), 0o444)
            # Publish atomically without replacing a file created concurrently.
            os.link(temporary, directory / filename)
        finally:
            os.unlink(temporary)


def compare_values(directory: Path, values: dict[str, bytes]) -> bool:
    check_directory(directory, os.getuid())
    mismatches = []
    for setting, filename in SECRET_FILES.items():
        check_file(directory, setting, os.getuid())
        fd = os.open(directory / filename, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise SecretCheckError(f"{filename}: must be a regular file")
            if source.read() != values[setting]:
                mismatches.append(setting)
    for setting in mismatches:
        print(f"{setting}: mismatch", file=sys.stderr)
    return not mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("export", "compare"))
    parser.add_argument("--secrets-dir", type=Path, default=Path("/opt/compass/secrets"))
    args = parser.parse_args()
    try:
        values = effective_values()
        if args.mode == "export":
            export_values(args.secrets_dir, values)
            print("Exported 15 exact effective values; no values or digests printed")
        elif compare_values(args.secrets_dir, values):
            print("All 15 effective values match exactly")
        else:
            return 1
    except (ValueError, OSError, UnicodeError) as exc:
        message = (
            str(exc)
            if isinstance(exc, SecretCheckError)
            else "migration: configuration or IO failure"
        )
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
