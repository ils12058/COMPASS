"""Reuse the immutable Redis entrypoint's password normalization without revealing it."""

import subprocess
import sys
from pathlib import Path


def reset_program():
    source = (Path(__file__).parents[1] / "runtime-secrets/redis-start.sh").read_text()
    reader = source[source.index("read_password() {") : source.index("\ncase ")]
    return (
        "set -eu\numask 077\nsecret=/run/secrets/redis_password\n"
        + reader
        + '\nREDISCLI_AUTH="$(read_password raw)"\nexport REDISCLI_AUTH\n'
        + "redis-cli --no-auth-warning FLUSHALL\nunset REDISCLI_AUTH\n"
    )


if __name__ == "__main__":
    try:
        subprocess.run(
            ["docker", "exec", "-i", sys.argv[1], "sh"],
            input=reset_program(),
            text=True,
            check=True,
        )
    except Exception as exc:
        sys.exit(f"Redis reset failed ({type(exc).__name__}); applications remain fenced")
