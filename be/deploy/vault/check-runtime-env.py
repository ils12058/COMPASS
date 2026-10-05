"""Reject secret-bearing deployment env assignments before creating any containers."""

import re
import runpy
import sys
from pathlib import Path

inventory = runpy.run_path(str(Path(__file__).with_name("migrate-runtime-secrets.py")))["SECRETS"]
forbidden = set(inventory) | {
    "REDIS_URL",
    "REDIS_CACHE_URL",
    "REDIS_RATE_LIMIT_URL",
    "REDIS_IDEMPOTENCY_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "DEMO_ACCOUNT_PASSWORD",
    "DEMO_ACCOUNT_PASSWORD_FILE",
}
forbidden |= {
    f"{name}_FILE" for name in forbidden if name.endswith("_URL") or name.endswith("BACKEND")
}


def validate_assignments(content: str) -> None:
    seen = set()
    for line in content.splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=", line)
        if not match:
            continue
        name = match[1]
        if name in forbidden:
            raise ValueError(f"{name} must be removed from the runtime environment file")
        if name in {f"{setting}_FILE" for setting in inventory}:
            if name in seen:
                raise ValueError(f"{name} has duplicate runtime assignments")
            seen.add(name)
    for setting in inventory:
        if f"{setting}_FILE" not in seen:
            raise ValueError(f"{setting}_FILE is missing from the runtime environment file")


if __name__ == "__main__":
    try:
        validate_assignments(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, IndexError):
        raise SystemExit("Runtime environment file is unavailable or invalid") from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print("Runtime environment assignment names are safe")
