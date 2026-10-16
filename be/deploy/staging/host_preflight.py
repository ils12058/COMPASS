"""Fail closed on the verified canonical staging host; no Docker mutation commands."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

BASELINE = "d86ddc08285f16740848dc5880d9d2285e7dbce8"
PROJECT = "compass"
NETWORK = "compass_canonical_d86ddc08"
VOLUMES = {
    "postgres_data": ("compass_postgres_canonical_d86ddc08", "2026-10-16T21:31:13Z"),
    "redis_data": ("compass_redis_canonical_d86ddc08", "2026-10-16T21:31:13Z"),
    "caddy_data": ("compass_caddy_data", "2026-09-20T05:47:56Z"),
    "caddy_config": ("compass_caddy_config", "2026-09-20T05:47:56Z"),
}
APP_SERVICES = {"web", "worker", "beat", "realtime"}


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def run(*args, env=None):
    return subprocess.run(args, check=True, text=True, capture_output=True, env=env).stdout


def docker_json(*args):
    return json.loads(run("docker", *args))


def read_selector(path=Path("/opt/compass/.deploy.env")):
    allowed = {"COMPASS_IMAGE", "COMPASS_SECRETS_DIR", "COMPOSE_FILE", "COMPOSE_PROFILES"}
    result = {}
    for line in path.read_text().splitlines():
        require("=" in line, "Selector is not a canonical assignment file")
        key, value = line.split("=", 1)
        require(key in allowed and key not in result, "Unknown/duplicate deployment selector")
        require(
            re.fullmatch(r"[a-zA-Z0-9_./:@,-]*", value) is not None, "Unsafe deployment selector"
        )
        result[key] = value
    require(set(result) == allowed, "Incomplete deployment selector")
    require(
        re.fullmatch(
            r"(sha256:[0-9a-f]{64}|registry.digitalocean.com/compass/compass-backend:[0-9a-f]{40}@sha256:[0-9a-f]{64})",
            result["COMPASS_IMAGE"],
        )
        is not None,
        "Mutable image selector",
    )
    require(result["COMPASS_SECRETS_DIR"] == "/opt/compass/secrets", "Unexpected secrets directory")
    require(result["COMPOSE_PROFILES"] in ("", "realtime"), "Unknown Compose profile")
    for filename in result["COMPOSE_FILE"].split(":"):
        require(
            re.fullmatch(
                r"/opt/compass/releases/[0-9a-f]{40}/compose\.(staging|live-reset)\.yaml", filename
            )
            is not None,
            "Unexpected manifest selection",
        )
        require(Path(filename).is_file(), "Selected manifest missing/fenced")
    return result


def validate_resources(volumes, network, containers, candidate):
    require(candidate["name"] == PROJECT, "Wrong Compose project")
    for key, (name, created) in VOLUMES.items():
        config = candidate["volumes"][key]
        require(
            config.get("external") is True and config["name"] == name,
            "Persistent resource selection changed",
        )
        resource = volumes[name]
        require(
            resource["Name"] == name
            and resource["CreatedAt"] == created
            and resource["Driver"] == "local",
            "Missing/replaced persistent volume",
        )
        labels = resource.get("Labels") or {}
        require(
            labels.get("com.docker.compose.project") == PROJECT
            and labels.get("com.docker.compose.volume") == key,
            "Volume ownership mismatch",
        )
    require(
        candidate["networks"]["default"].get("name") == NETWORK
        and candidate["networks"]["default"].get("external") is True,
        "Network selection changed",
    )
    require(
        network["Name"] == NETWORK
        and network.get("Labels", {}).get("com.docker.compose.project") == PROJECT
        and network["Labels"].get("com.docker.compose.network") == "default",
        "Network ownership mismatch",
    )
    names = {value[0] for value in VOLUMES.values()}
    services = {}
    for c in containers:
        labels = c["Config"].get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        owns = labels.get("com.docker.compose.project") == PROJECT
        touches = NETWORK in c["NetworkSettings"]["Networks"] or any(
            m.get("Name") in names for m in c["Mounts"]
        )
        if not owns:
            require(not touches, "Foreign container uses canonical resources")
            continue
        require(
            service in APP_SERVICES | {"postgres", "redis", "proxy"} and service not in services,
            "Unknown/duplicate COMPASS process",
        )
        require(
            labels.get("com.docker.compose.oneoff") == "False", "One-off COMPASS process exists"
        )
        require(
            c["State"]["Running"]
            and c["State"].get("Health", {}).get("Status", "healthy") == "healthy",
            "Current runtime is not healthy",
        )
        require(set(c["NetworkSettings"]["Networks"]) == {NETWORK}, "Runtime network mismatch")
        require(c["Name"] == f"/compass-{service}-1", "Unexpected service/container identity")
        expected = {
            "postgres": {"/var/lib/postgresql/data": VOLUMES["postgres_data"][0]},
            "redis": {"/data": VOLUMES["redis_data"][0]},
            "proxy": {"/data": VOLUMES["caddy_data"][0], "/config": VOLUMES["caddy_config"][0]},
        }.get(service, {})
        actual = {m["Destination"]: m["Name"] for m in c["Mounts"] if m["Type"] == "volume"}
        require(actual == expected, "Runtime persistent mounts differ")
        services[service] = c
    require(
        {"web", "worker", "beat", "postgres", "redis", "proxy"} <= services.keys(),
        "Required runtime services missing",
    )
    return services


def validate_endpoints(services, candidate):
    postgres = dict(item.split("=", 1) for item in services["postgres"]["Config"]["Env"])
    desired = candidate["services"]["postgres"]["environment"]
    require(
        all(postgres.get(key) == value for key, value in desired.items()),
        "Running PostgreSQL configuration differs from candidate",
    )
    for name in ("web", "worker", "beat"):
        environment = candidate["services"][name]["environment"]
        require(
            environment.get("POSTGRES_HOST", "postgres") == "postgres"
            and str(environment.get("POSTGRES_PORT", "5432")) == "5432"
            and environment.get("POSTGRES_DB", "compass") == postgres["POSTGRES_DB"]
            and environment.get("POSTGRES_USER", "compass") == postgres["POSTGRES_USER"],
            "Application database endpoint differs from initialized PostgreSQL",
        )
        require(
            environment.get("REDIS_HOST", "redis") == "redis"
            and str(environment.get("REDIS_PORT", "6379")) == "6379",
            "Application broker endpoint differs from canonical Redis",
        )


def normalize_infrastructure(service):
    # Only release-relative bind source paths can differ. Their contents are checked separately.
    encoded = json.dumps(service, sort_keys=True)
    return re.sub(r"/opt/compass/releases/[0-9a-f]{40}/", "/CANONICAL-RELEASE/", encoded)


def inspect(candidate):
    with urllib.request.urlopen("http://169.254.169.254/metadata/v1/id", timeout=3) as response:
        require(response.read().decode().strip() == "602091909", "Wrong DigitalOcean Droplet")
    require(Path("/opt/compass").resolve() == Path("/opt/compass"), "Unexpected deployment root")
    require(
        not Path("/opt/compass/.deployment-freeze").exists(), "Operator deployment freeze is active"
    )
    selector = read_selector()
    volumes = {name: docker_json("volume", "inspect", name)[0] for name, _ in VOLUMES.values()}
    for old in ("compass_postgres_data", "compass_redis_data"):
        require(
            old not in run("docker", "volume", "ls", "--format", "{{.Name}}").splitlines(),
            "Pre-canonical storage reappeared",
        )
    network = docker_json("network", "inspect", NETWORK)[0]
    ids = run("docker", "ps", "-aq").split()
    require(bool(ids), "Runtime missing")
    services = validate_resources(volumes, network, docker_json("inspect", *ids), candidate)
    validate_endpoints(services, candidate)
    selected_image = docker_json("image", "inspect", selector["COMPASS_IMAGE"])[0]
    revision = None
    for name in APP_SERVICES & services.keys():
        c = services[name]
        require(c["Image"] == selected_image["Id"], "Current image/selector mismatch")
        image = docker_json("image", "inspect", c["Image"])[0]
        value = image["Config"].get("Labels", {}).get("org.opencontainers.image.revision", "")
        require(re.fullmatch("[0-9a-f]{40}", value) is not None, "Immutable build revision missing")
        require(revision in (None, value), "Mixed application revisions")
        revision = value
    require(
        all(Path(f).parent.name == revision for f in selector["COMPOSE_FILE"].split(":")),
        "Current release/revision mismatch",
    )
    require(
        ("realtime" in services) == (selector["COMPOSE_PROFILES"] == "realtime"),
        "Realtime profile mismatch",
    )
    env = {**os.environ, **selector}
    current = json.loads(
        run(
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--profile",
            "realtime",
            "config",
            "--format",
            "json",
            env=env,
        )
    )
    for name in ("postgres", "redis"):
        require(
            normalize_infrastructure(current["services"][name])
            == normalize_infrastructure(candidate["services"][name]),
            "Database/broker service change requires coordinated infrastructure review",
        )
    current_redis_script = next(
        m["Source"]
        for m in services["redis"]["Mounts"]
        if m["Destination"] == "/usr/local/bin/compass-redis-start"
    )
    candidate_redis_script = next(
        m["source"]
        for m in candidate["services"]["redis"]["volumes"]
        if m["target"] == "/usr/local/bin/compass-redis-start"
    )
    require(
        Path(current_redis_script).read_bytes() == Path(candidate_redis_script).read_bytes(),
        "Redis entrypoint change requires coordinated infrastructure review",
    )
    # Check the old database before even creating a candidate one-off; psql is SELECT-only.
    sql = (
        "SELECT json_build_object('migrations',"
        "(SELECT json_agg(json_build_array(app,name)) FROM django_migrations),"
        "'accounts',(SELECT count(*) FROM accounts_user),"
        "'retired',(SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name IN "
        "('privacy_governance_dispositioncase','privacy_governance_dispositionhold',"
        "'privacy_governance_operationalretentionrule')))"
    )
    raw = run(
        "docker",
        "exec",
        services["postgres"]["Id"],
        "sh",
        "-c",
        'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"',
        "sh",
        sql,
    )
    database = json.loads(raw)
    baseline = json.loads(Path(__file__).with_name("baseline-sha256.json").read_text())
    labels = {p.split("/")[1] for p in baseline}
    applied = {tuple(x) for x in database["migrations"]}
    require(
        all((a, "0001_canonical_baseline") in applied for a in labels),
        "Canonical database not initialized",
    )
    require(
        not any(
            a in labels and n.startswith("0001") and n != "0001_canonical_baseline"
            for a, n in applied
        ),
        "Pre-canonical migration history",
    )
    require(
        database["accounts"] > 0 and database["retired"] == 0, "Canonical population/schema missing"
    )
    return {
        "current_revision": revision,
        "current_image": selector["COMPASS_IMAGE"],
        "realtime": "realtime" in services,
        "app_containers": {
            name: c["Id"] for name, c in services.items() if name in APP_SERVICES | {"proxy"}
        },
        "accounts": database["accounts"],
    }


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(json.loads(Path(sys.argv[1]).read_text()))))
    except Refused as exc:
        sys.exit(f"Canonical staging preflight refused: {exc}")
    except Exception as exc:
        sys.exit(
            f"Canonical staging preflight could not be verified ({type(exc).__name__}); "
            "no runtime mutation permitted"
        )
