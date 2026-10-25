#!/usr/bin/env python3
"""One firewall lease around trusted SSH, exact-source upload and the guarded rollout."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

FW = "3d6403c7-9acc-4faf-b6a4-fa5bb092e108"
DROPLET = 602091909
PROJECT = "1bb58307-ec9c-4af1-98c4-4177c636e567"
BASELINE = "d86ddc08285f16740848dc5880d9d2285e7dbce8"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def api(*args):
    return json.loads(
        run("doctl", *args, "--output", "json", capture_output=True, text=True).stdout
    )


def validate_cloud(firewall, droplets, resources):
    if not (
        firewall["id"] == FW and firewall["droplet_ids"] == [DROPLET] and not firewall.get("tags")
    ):
        raise RuntimeError("Wrong staging firewall attachment")
    matches = [d for d in droplets if d["id"] == DROPLET and d["name"] == "compass-staging-api-01"]
    if len(matches) != 1 or not any(
        n["type"] == "public" and n["ip_address"] == "157.245.60.65"
        for n in matches[0]["networks"]["v4"]
    ):
        raise RuntimeError("Wrong staging Droplet")
    if f"do:droplet:{DROPLET}" not in {r["urn"] for r in resources}:
        raise RuntimeError("Droplet is not in the expected project/account")


def contains_rule(firewall, cidr):
    return any(
        r["protocol"] == "tcp"
        and r["ports"] == "22"
        and cidr in r.get("sources", {}).get("addresses", [])
        for r in firewall["inbound_rules"]
    )


def close_firewall(statefile):
    if not statefile.exists():
        return
    state = json.loads(statefile.read_text())
    if (
        state["firewall"] != FW
        or str(ipaddress.IPv4Network(state["cidr"])) != state["cidr"]
        or not state["cidr"].endswith("/32")
    ):
        raise RuntimeError("Invalid firewall ownership state")
    if state["created"]:
        current = api("compute", "firewall", "get", FW)[0]
        if contains_rule(current, state["cidr"]):
            run(
                "doctl",
                "compute",
                "firewall",
                "remove-rules",
                FW,
                "--inbound-rules",
                f"protocol:tcp,ports:22,address:{state['cidr']}",
            )
        if contains_rule(api("compute", "firewall", "get", FW)[0], state["cidr"]):
            raise RuntimeError("Temporary SSH access remains")
    statefile.unlink()


def open_firewall(statefile):
    firewall = api("compute", "firewall", "get", FW)[0]
    validate_cloud(
        firewall, api("compute", "droplet", "list"), api("projects", "resources", "list", PROJECT)
    )
    with urllib.request.urlopen("https://api.ipify.org", timeout=15) as response:
        address = ipaddress.IPv4Address(response.read().decode().strip())
        if not address.is_global:
            raise RuntimeError("SSH source must be the actual public IPv4")
        cidr = str(address) + "/32"
    created = not contains_rule(firewall, cidr)
    # Record ownership before requesting the mutation, including an uncertain API timeout.
    statefile.write_text(json.dumps({"firewall": FW, "cidr": cidr, "created": created}))
    statefile.chmod(0o600)
    if created:
        run(
            "doctl",
            "compute",
            "firewall",
            "add-rules",
            FW,
            "--inbound-rules",
            f"protocol:tcp,ports:22,address:{cidr}",
        )
    print(f"SSH lease: exact {cidr}; created={created}", flush=True)


def ssh_options():
    directory = Path(os.environ["STAGING_SSH_DIR"])
    return [
        "-i",
        str(directory / "id_ed25519"),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={directory / 'known_hosts'}",
    ]


def deploy():
    sha, image = os.environ["DEPLOY_SHA"], os.environ["IMAGE"]
    catalog_action = os.environ.get("ORG_CATALOG_ACTION", "check")
    if catalog_action not in {"check", "adopt", "seed"}:
        raise RuntimeError("Invalid explicit catalog initialization action")
    if not re.fullmatch("[0-9a-f]{40}", sha) or not re.fullmatch(
        rf"registry.digitalocean.com/compass/compass-backend:{sha}@sha256:[0-9a-f]{{64}}", image
    ):
        raise RuntimeError("Non-immutable candidate image")
    for key, value in {
        "DEPLOY_PATH": "/opt/compass",
        "STAGING_DEPLOY_USER": "compass",
        "STAGING_DEPLOY_PORT": "22",
        "STAGING_DEPLOY_HOST": "157.245.60.65",
        "STAGING_FIREWALL_ID": FW,
    }.items():
        if os.environ.get(key) != value:
            raise RuntimeError(f"Unexpected {key}")
    for key in ("APP_VERSION", "BUILD_TIME"):
        if not re.fullmatch("[a-zA-Z0-9.+:-]+", os.environ[key]):
            raise RuntimeError("Unsafe build metadata")
    run("git", "merge-base", "--is-ancestor", BASELINE, sha)
    release = f"/opt/compass/releases/{sha}"
    target = "compass@157.245.60.65"
    ssh = ["ssh", *ssh_options(), "-p", "22", target]
    scp = ["scp", *ssh_options(), "-P", "22"]
    sources = {
        "compose.staging.yaml": Path("be/compose.staging.yaml"),
        "Caddyfile": Path("be/Caddyfile"),
        **{
            f"deploy/staging/{p.name}": p
            for p in Path("be/deploy/staging").iterdir()
            if p.is_file()
        },
        **{
            f"deploy/runtime-secrets/{name}": Path("be/deploy/runtime-secrets") / name
            for name in ["redis-start.sh", "check-runtime-secrets.py", "runtime_secrets.py"]
        },
    }
    existing = run(
        *ssh,
        "test -d /opt/compass && test -f /opt/compass/.env && "
        f"if test -d {release}; then echo existing; "
        f"else mkdir -m 750 {release}; echo new; fi",
        capture_output=True,
        text=True,
    ).stdout.strip()
    try:
        if existing == "existing":
            # Retry only byte-identical staged files. Never overwrite active/failed manifests.
            hashes = run(
                *ssh,
                "sha256sum " + " ".join(f"{release}/{name}" for name in sources),
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            if [line.split()[0] for line in hashes] != [
                hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.values()
            ]:
                raise RuntimeError("Existing release differs; operator review required")
        else:
            run(
                *ssh,
                f"mkdir -p {release}/deploy/runtime-secrets {release}/deploy/staging "
                f"&& ln -s ../../.env {release}/.env",
            )
            for destination, source in sources.items():
                run(*scp, str(source), f"{target}:{release}/{destination}")
        metadata = (
            f"DEPLOY_SHA={sha} IMAGE={image} "
            f"APP_VERSION={os.environ['APP_VERSION']} BUILD_TIME={os.environ['BUILD_TIME']} "
            f"ORG_CATALOG_ACTION={catalog_action}"
        )
        command = f"{metadata} bash {release}/deploy/staging/deploy.sh"
        result = run(*ssh, command + " preflight", capture_output=True, text=True)
        # stderr contains only the runtime-secret check summary. Never print rendered env/config.
        print(result.stderr, end="")
        snapshot = json.loads(result.stdout)
        run("git", "merge-base", "--is-ancestor", BASELINE, snapshot["current_revision"])
        run("git", "merge-base", "--is-ancestor", snapshot["current_revision"], sha)
        print(
            json.dumps(
                {
                    "destination_verified": True,
                    "current_revision": snapshot["current_revision"],
                    "candidate_revision": sha,
                    "realtime": snapshot["realtime"],
                }
            ),
            flush=True,
        )
        tip = run(
            "git",
            "ls-remote",
            "--refs",
            "origin",
            "refs/heads/staging",
            capture_output=True,
            text=True,
        ).stdout.split()
        if not tip or tip[0] != sha:
            raise RuntimeError("Staging moved during the build/preflight; no runtime mutation")
        if snapshot["current_revision"] == sha:
            if snapshot["current_image"] != image:
                raise RuntimeError(
                    "Same revision has a different immutable image; refuse replacement"
                )
            print("Exact immutable revision is already healthy; no runtime mutation")
            return
        run(*ssh, f"mkdir -p {release}/.registry && chmod 700 {release}/.registry")
        run(
            *scp,
            os.environ["STAGING_REGISTRY_PULL_CONFIG"],
            f"{target}:{release}/.registry/config.json",
        )
        run(*ssh, f"chmod 600 {release}/.registry/config.json")
        run(*ssh, command + " deploy")
    finally:
        # A remote deploy failure or SSH disconnect must not strand registry credentials.
        run(*ssh, f"rm -rf {release}/.registry; rm -f {release}/.candidate-config.json")


def main():
    os.umask(0o077)
    statefile = Path(os.environ["RUNNER_TEMP"]) / "compass-staging-firewall.json"
    if sys.argv[1:] == ["--cleanup"]:
        close_firewall(statefile)
        return
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    try:
        open_firewall(statefile)
        deploy()
    finally:
        close_firewall(statefile)


if __name__ == "__main__":
    main()
