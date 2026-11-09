"""Small reset actions and protected, content-free recovery/receipt state."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import host_preflight as host
import reset_preflight as preflight
import reset_redis


def compose():
    return [
        "docker",
        "compose",
        "--project-name",
        "compass",
        "-f",
        str(Path.cwd() / "compose.staging.yaml"),
    ]


def quiet(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def atomic_json(path, value):
    host.require(not path.is_symlink(), "Unsafe reset state path")
    temporary = path.with_suffix(path.suffix + ".next")
    if temporary.exists():
        metadata = temporary.lstat()
        host.require(
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and stat.S_IMODE(metadata.st_mode) == 0o600,
            "Unsafe interrupted state write",
        )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        os.chmod(temporary, 0o600)
        json.dump(value, output, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def protected_directory():
    directory = preflight.checkpoint_path().parent
    for parent in (directory.parent, directory):
        if not parent.exists():
            parent.mkdir(mode=0o700)
        s = parent.lstat()
        host.require(
            stat.S_ISDIR(s.st_mode)
            and s.st_uid == os.getuid()
            and stat.S_IMODE(s.st_mode) == 0o700,
            "Unsafe operator reset directory",
        )
    return directory


def checkpoint():
    existing = preflight.read_checkpoint(
        os.environ["DEPLOY_SHA"], os.environ["IMAGE"], os.environ["DATASET_EMAIL_DOMAIN"]
    )
    snapshot = json.loads(Path(".reset-preflight.locked.json").read_text())
    if existing:
        host.require(
            all(existing["before"][k] == snapshot[k] for k in ("volumes", "network")),
            "Checkpoint resource identity changed",
        )
        return
    directory = protected_directory()
    atomic_json(
        directory / "in-progress.json",
        {
            "sha": os.environ["DEPLOY_SHA"],
            "image": os.environ["IMAGE"],
            "domain": os.environ["DATASET_EMAIL_DOMAIN"],
            "before": snapshot,
            "started_at": datetime.now(UTC).isoformat(),
        },
    )


def service_ids():
    ids = host.run(
        "docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=compass"
    ).split()
    return (
        {
            c["Config"]["Labels"]["com.docker.compose.service"]: c
            for c in host.docker_json("inspect", *ids)
            if c["Config"]["Labels"].get("com.docker.compose.oneoff") == "False"
        }
        if ids
        else {}
    )


def fence():
    services = service_ids()
    ids = [services[k]["Id"] for k in preflight.APPS if k in services]
    snapshot = json.loads(Path(".reset-preflight.locked.json").read_text())
    oneoffs = [c["id"] for c in snapshot.get("reset_oneoffs", [])]
    failed = False
    if ids or oneoffs:
        try:
            quiet("docker", "update", "--restart=no", *ids, *oneoffs)
            quiet("docker", "stop", "--timeout", "30", *ids, *oneoffs)
        except subprocess.CalledProcessError:
            # Old work is explicitly discarded: removal is the fallback fence, never restart.
            failed = True
            quiet("docker", "rm", "-f", *ids, *oneoffs)
        else:
            if oneoffs:
                quiet("docker", "rm", "-f", *oneoffs)
    host.require(
        not any(c["State"]["Running"] for k, c in service_ids().items() if k in preflight.APPS),
        "App process remains running",
    )
    host.require(not failed, "App stop/restart-policy failed; containers removed, rerun reset")


def wait_storage():
    for _ in range(90):
        services = service_ids()
        if all(
            services.get(k, {}).get("State", {}).get("Running")
            and services[k]["State"].get("Health", {}).get("Status") == "healthy"
            for k in ("postgres", "redis")
        ):
            return
        time.sleep(2)
    raise host.Refused("Storage failed to become healthy; rerun the same reset")


def recover_storage():
    services = service_ids()
    missing = [
        k
        for k in ("postgres", "redis")
        if not services.get(k, {}).get("State", {}).get("Running")
        or services[k]["State"].get("Health", {}).get("Status") != "healthy"
    ]
    if missing:
        # Full identity/configuration checks and the exact-SHA checkpoint have already passed.
        quiet(*compose(), "up", "-d", "--no-deps", "--force-recreate", "--pull", "never", *missing)
        wait_storage()


def empty_database():
    pg = service_ids()["postgres"]["Id"]
    quiet(
        "docker",
        "exec",
        "-i",
        pg,
        "sh",
        "-c",
        'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres '
        '-v "database=$POSTGRES_DB" -v "owner=$POSTGRES_USER"',
        input=Path("deploy/staging/reset_database.sql").read_text(),
    )


def empty_redis():
    quiet(
        "docker",
        "exec",
        "-i",
        service_ids()["redis"]["Id"],
        "sh",
        input=reset_redis.reset_program(),
    )


def image():
    candidate = json.loads(Path(".candidate-config.json").read_text())
    for service in ("postgres", "redis", "proxy"):
        host.docker_json("image", "inspect", candidate["services"][service]["image"])
    labels = host.docker_json("image", "inspect", os.environ["IMAGE"])[0]["Config"]["Labels"]
    host.require(
        all(
            labels.get(k) == os.environ[v]
            for k, v in {
                "org.opencontainers.image.revision": "DEPLOY_SHA",
                "org.opencontainers.image.version": "APP_VERSION",
                "org.opencontainers.image.created": "BUILD_TIME",
            }.items()
        ),
        "Candidate image metadata mismatch",
    )


def settings_check():
    candidate = json.loads(Path(".candidate-config.json").read_text())
    env = candidate["services"]["web"]["environment"]
    host.require(env.get("APP_ENV") == "live-staging", "Candidate must load live-staging settings")
    host.require(env.get("COMPASS_PORTAL_ORIGIN", "").strip(), "COMPASS_PORTAL_ORIGIN is required")
    # Metadata permits empty Handoff contents; reset requires a usable keyring.
    for name in ("counselor_handoff_summary_encryption_keys", "guidance_followup_encryption_keys"):
        host.require(
            (preflight.ROOT / "secrets" / name).read_text().strip(),
            f"{name}: non-empty keyring required for reset",
        )
    quiet(
        *compose(),
        "run",
        "--rm",
        "--no-deps",
        "--pull",
        "never",
        "-T",
        "web",
        "python",
        "manage.py",
        "check",
        "--deploy",
        input="",
    )
    if os.environ.get("DATASET_EMAIL_DOMAIN"):
        environment = {
            **os.environ,
            "STAGING_SEED_EMAIL_DOMAIN": os.environ["DATASET_EMAIL_DOMAIN"],
        }
        quiet(
            *compose(),
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "-T",
            "-e",
            "STAGING_SEED_EMAIL_DOMAIN",
            "-e",
            "STAGING_SEED_ONBOARDING_EMAIL",
            "web",
            "python",
            "-c",
            "import django; django.setup(); "
            "from compass.staging_seed.config import load_config; "
            "load_config(app_env='live-staging')",
            input="",
            env=environment,
        )
    print("Candidate settings loaded; deployment checks passed (no database tags)", file=sys.stderr)


def seed(mode):
    environment = {
        **os.environ,
        "STAGING_SEED_ENABLED": "true",
        "STAGING_SEED_EMAIL_DOMAIN": os.environ["DATASET_EMAIL_DOMAIN"],
    }
    arguments = ["-e", "STAGING_SEED_ENABLED", "-e", "STAGING_SEED_EMAIL_DOMAIN"]
    onboarding = environment.get("STAGING_SEED_ONBOARDING_EMAIL", "")
    if onboarding:
        arguments += ["-e", "STAGING_SEED_ONBOARDING_EMAIL"]
    else:
        environment.pop("STAGING_SEED_ONBOARDING_EMAIL", None)
        print(
            "STAGING_SEED_ONBOARDING_EMAIL absent; continuing without onboarding delivery",
            file=sys.stderr,
        )
    result = quiet(
        *compose(),
        "run",
        "--rm",
        "--no-deps",
        "--pull",
        "never",
        "-T",
        *arguments,
        "web",
        "python",
        "manage.py",
        "seed_staging_dataset",
        mode,
        input="",
        env=environment,
    )
    if mode == "verify":
        host.require("Verification PASSED." in result.stdout, "Seeder did not confirm verification")
        sections = []
        for line in result.stdout.splitlines():
            match = re.fullmatch(
                r"  ([A-Za-z][A-Za-z /-]*?)\s+(\d+) passed,\s+(\d+) failed,\s+(\d+) warnings", line
            )
            if match:
                name, passed, failed, warnings = match.groups()
                sections.append(
                    {
                        "name": name.strip(),
                        "passed": int(passed),
                        "failed": int(failed),
                        "warnings": int(warnings),
                    }
                )
        host.require(
            bool(sections) and all(s["failed"] == 0 for s in sections),
            "Missing/failed seed verification sections",
        )
        atomic_json(Path(".reset-verify.json"), {"passed": True, "sections": sections})
        print(
            "Staging Dataset v1 verification passed; counts come from the candidate manifest",
            file=sys.stderr,
        )
    else:
        print("Staging Dataset v1 seeded; no credentials issued", file=sys.stderr)


def receipt():
    state = preflight.read_checkpoint(
        os.environ["DEPLOY_SHA"], os.environ["IMAGE"], os.environ["DATASET_EMAIL_DOMAIN"]
    )
    after = json.loads(Path(".reset-after.json").read_text())
    verification = json.loads(Path(".reset-verify.json").read_text())
    now = datetime.now(UTC)
    value = {
        "sha": state["sha"],
        "image_digest": state["image"].split("@")[1],
        "database_class_before": state["before"]["database_class"],
        "counts_before": state["before"]["counts"],
        "counts_after": {
            "migration_count": after["migration_count"],
            "account_count": after["accounts"],
        },
        "seed_verify": verification,
        "started_at": state["started_at"],
        "completed_at": now.isoformat(),
    }
    path = protected_directory() / f"{state['sha']}-{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    atomic_json(path, value)
    # Print only the whitelisted receipt; clear the recovery fence only after durable completion.
    print(json.dumps(value, sort_keys=True))
    preflight.checkpoint_path().unlink()


if __name__ == "__main__":
    try:
        actions = {
            "checkpoint": checkpoint,
            "fence": fence,
            "image": image,
            "wait-storage": wait_storage,
            "recover-storage": recover_storage,
            "empty-database": empty_database,
            "empty-redis": empty_redis,
            "settings-check": settings_check,
            "seed": lambda: seed("seed"),
            "verify": lambda: seed("verify"),
            "receipt": receipt,
        }
        actions[sys.argv[1]]()
    except host.Refused as exc:
        sys.exit(f"Reset refused: {exc}")
    except Exception as exc:
        # Includes settings/seeder/psql errors: never echo stdout/stderr or adapter exception text.
        sys.exit(f"Reset action failed ({type(exc).__name__}); see reset recovery runbook")
