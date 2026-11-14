"""SELECT-only reset inspection; recovery requires this SHA's protected checkpoint."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import host_preflight as host

ROOT = Path("/opt/compass")
APPS = ("proxy", "web", "worker", "beat", "realtime")


def expected_history(baseline):
    return {(p.split("/")[1], Path(p).stem) for p in baseline}


def registered_additions():
    """Additive migrations registered after the release baseline (additive-migrations.json).

    A release database may record any of them, in addition to the complete baseline. Anything
    else beyond the baseline is still unknown history.
    """

    registry = json.loads(Path(__file__).with_name("additive-migrations.json").read_text())
    return expected_history(registry)


def classify_database(baseline, database, additions=frozenset()):
    if not database["migrations_table"]:
        return "empty"
    applied = {tuple(row) for row in database["migrations"]}
    labels = {p.split("/")[1] for p in baseline}
    host.require(
        all(a in labels | {"auth", "contenttypes", "sessions", "admin"} for a, n in applied),
        "Unknown applied migration app",
    )
    owned = {(a, n) for a, n in applied if a in labels}
    expected = expected_history(baseline)
    if expected <= owned <= expected | set(additions):
        host.validate_release_history(baseline, applied, catalog_table=database["catalog_table"])
        return "release"
    if (
        any(n == "0001_canonical_baseline" for a, n in owned)
        and all(
            n == "0001_canonical_baseline"
            or (a in {"group_sessions", "guidance_followups"} and n == "0001_initial")
            or re.fullmatch(r"000[2-9]_[a-z0-9_]+", n)
            for a, n in owned
        )
        and not any("release_baseline" in n or n == "0002_database_guards" for a, n in owned)
    ):
        return "canonical"
    raise host.Refused("Unrecognized/mixed/incomplete database history")


def check_lock(locked):
    path = ROOT / ".live-reset.lock"
    if not path.exists():
        host.require(not locked, "Locked inspection requires the host lock")
        return
    host.require(not path.is_symlink(), "Host lock must be a regular file")
    with path.open("rb") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            host.require(locked, "Host lock is busy")
            host.require(os.fstat(9).st_ino == path.stat().st_ino, "Wrong inherited host lock")
            fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            host.require(not locked, "Caller does not hold the host lock")
            fcntl.flock(handle, fcntl.LOCK_UN)


def checkpoint_path():
    return ROOT / "operator/resets/in-progress.json"


def read_checkpoint(sha, image, domain):
    path = checkpoint_path()
    if not path.exists():
        return None
    metadata = path.lstat()
    host.require(
        stat.S_ISREG(metadata.st_mode)
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and metadata.st_uid == os.getuid(),
        "Unsafe reset checkpoint",
    )
    value = json.loads(path.read_text())
    host.require(
        value["sha"] == sha and value["image"] == image and value["domain"] == domain,
        "Interrupted reset belongs to a different SHA, image or domain",
    )
    return value


def database_snapshot(services):
    pg = services.get("postgres")
    if not pg or not pg["State"]["Running"]:
        return None

    def select(sql, *, maintenance=False):
        return json.loads(
            host.run(
                "docker",
                "exec",
                pg["Id"],
                "sh",
                "-c",
                'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" '
                + ("-d postgres" if maintenance else '-d "$POSTGRES_DB"')
                + ' -At -c "$1"',
                "sh",
                sql,
            )
        )

    raw = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            pg["Id"],
            "sh",
            "-c",
            'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres '
            '-v "database=$POSTGRES_DB" -At',
        ],
        input="SELECT to_json(EXISTS(SELECT 1 FROM pg_database WHERE datname=:'database'));\n",
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    exists = json.loads(raw)
    tables = (
        select(
            "SELECT coalesce(json_agg(table_name), '[]'::json) "
            "FROM information_schema.tables WHERE table_schema='public'"
        )
        if exists
        else []
    )
    migrations = (
        select(
            "SELECT coalesce(json_agg(json_build_array(app,name) ORDER BY app,name), '[]'::json) "
            "FROM django_migrations"
        )
        if "django_migrations" in tables
        else []
    )
    accounts = (
        select("SELECT to_json(count(*)) FROM accounts_user") if "accounts_user" in tables else 0
    )
    domains = (
        select(
            "SELECT coalesce(json_agg(domain ORDER BY domain), '[]'::json) FROM "
            "(SELECT DISTINCT split_part(email,'@',2) AS domain FROM accounts_user "
            "WHERE email LIKE 'stg-%') d"
        )
        if "accounts_user" in tables
        else []
    )
    host.require(
        all(re.fullmatch(r"[a-z0-9.-]+", d) for d in domains),
        "Unsafe dataset email domain in database",
    )
    return {
        "migrations_table": "django_migrations" in tables,
        "migrations": migrations,
        "migration_count": len(migrations),
        "account_count": accounts,
        "email_domains": domains,
        "catalog_table": int("organization_cataloginitialization" in tables),
    }


def inspect(candidate, *, locked=False, recovery=False):
    host.validate_host()
    check_lock(locked)
    checkpoint = read_checkpoint(
        os.environ["DEPLOY_SHA"], os.environ["IMAGE"], os.environ.get("DATASET_EMAIL_DOMAIN", "")
    )
    host.require(
        not recovery or checkpoint is not None, "Recovery requires the protected checkpoint"
    )
    volumes = {
        name: host.docker_json("volume", "inspect", name)[0] for name, _ in host.VOLUMES.values()
    }
    names = host.run("docker", "volume", "ls", "--format", "{{.Name}}").splitlines()
    host.require(
        not {"compass_postgres_data", "compass_redis_data"} & set(names),
        "Pre-canonical storage reappeared",
    )
    network = host.docker_json("network", "inspect", host.NETWORK)[0]
    host.require(bool(network.get("Created")), "Network creation identity missing")
    ids = host.run("docker", "ps", "-aq").split()
    containers = host.docker_json("inspect", *ids) if ids else []
    reset_oneoffs = []
    if recovery:
        retained = []
        for container in containers:
            labels = container["Config"].get("Labels") or {}
            if (
                labels.get("com.docker.compose.project") == host.PROJECT
                and labels.get("com.docker.compose.oneoff") == "True"
            ):
                selected = host.docker_json("image", "inspect", os.environ["IMAGE"])[0]
                host.require(
                    labels.get("com.docker.compose.service") == "web"
                    and container["Name"].startswith("/compass-web-run-")
                    and container["Image"] == selected["Id"]
                    and set(container["NetworkSettings"]["Networks"]) == {host.NETWORK}
                    and not any(m["Type"] == "volume" for m in container["Mounts"]),
                    "Foreign or unverified interrupted one-off",
                )
                reset_oneoffs.append(
                    {"id": container["Id"], "running": container["State"]["Running"]}
                )
            else:
                retained.append(container)
        containers = retained
    services = host.validate_resources(
        volumes,
        network,
        containers,
        candidate,
        reset=True,
        recovery=recovery,
    )
    # Even on recovery, configuration cannot redirect the reset to another database/broker.
    endpoints = services.copy()
    if "postgres" not in endpoints:
        endpoints["postgres"] = {
            "Config": {
                "Env": [
                    f"{k}={v}" for k, v in candidate["services"]["postgres"]["environment"].items()
                ]
            }
        }
    host.validate_endpoints(endpoints, candidate, reset=True)
    realtime = candidate["services"]["realtime"]["environment"]
    host.require(
        bool(realtime.get("REALTIME_ALLOWED_ORIGINS", "").strip()),
        "REALTIME_ALLOWED_ORIGINS is required",
    )
    host.require(
        realtime.get("REDIS_HOST", "redis") == "redis"
        and str(realtime.get("REDIS_PORT", "6379")) == "6379",
        "Realtime broker endpoint changed",
    )
    if checkpoint:
        host.require(
            checkpoint["before"]["network"]["id"] == network["Id"]
            and checkpoint["before"]["network"]["created"] == network["Created"],
            "Checkpoint network identity changed",
        )
    baseline = json.loads(Path(__file__).with_name("baseline-sha256.json").read_text())
    try:
        database = database_snapshot(services)
    except subprocess.CalledProcessError:
        host.require(recovery, "Database cannot be inspected")
        database = None
    if database is None:
        host.require(recovery, "PostgreSQL unavailable")
        database_class = "interrupted-unavailable"
    else:
        additions = registered_additions()
        try:
            database_class = classify_database(baseline, database, additions)
        except host.Refused:
            owned = {
                (a, n)
                for a, n in database["migrations"]
                if a in {p.split("/")[1] for p in baseline}
            }
            host.require(
                recovery
                and owned <= expected_history(baseline) | additions
                and all(
                    a
                    in {p.split("/")[1] for p in baseline}
                    | {"auth", "contenttypes", "sessions", "admin"}
                    for a, n in database["migrations"]
                ),
                "Unrecognized database history; recovery refused",
            )
            database_class = "interrupted-release"
    revision = None
    try:
        selector = host.read_selector()
        revisions = {Path(p).parent.name for p in selector["COMPOSE_FILE"].split(":")}
        if len(revisions) == 1:
            revision = revisions.pop()
    except (OSError, host.Refused):
        pass  # The original selector is reported only when safely readable.
    return {
        "database_class": database_class,
        "counts": {
            k: database[k] if database else None for k in ("migration_count", "account_count")
        },
        "email_domains": database["email_domains"] if database else [],
        "current_revision": revision,
        "realtime_running": bool(services.get("realtime", {}).get("State", {}).get("Running")),
        "containers": {
            name: {"id": c["Id"], "running": c["State"]["Running"]}
            for name, c in sorted(services.items())
        },
        "volumes": {
            name: {
                "created": v["CreatedAt"],
                "labels": {
                    k: v["Labels"][k]
                    for k in ("com.docker.compose.project", "com.docker.compose.volume")
                },
            }
            for name, v in volumes.items()
        },
        "network": {
            "name": network["Name"],
            "id": network["Id"],
            "created": network["Created"],
            "labels": {
                k: network["Labels"][k]
                for k in ("com.docker.compose.project", "com.docker.compose.network")
            },
        },
        "recovery": recovery,
        "reset_oneoffs": sorted(reset_oneoffs, key=lambda c: c["id"]),
        "configuration_names_checked": ["REALTIME_ALLOWED_ORIGINS"],
    }


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                inspect(
                    json.loads(Path(sys.argv[1]).read_text()),
                    locked="--locked" in sys.argv,
                    recovery="--recovery" in sys.argv,
                ),
                sort_keys=True,
            )
        )
    except host.Refused as exc:
        sys.exit(f"Reset preflight refused: {exc}")
    except Exception as exc:
        sys.exit(
            f"Reset preflight could not be verified ({type(exc).__name__}); no reset permitted"
        )
