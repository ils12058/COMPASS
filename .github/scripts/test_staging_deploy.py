"""Safety-boundary tests without Docker, credentials, provider traffic or live changes."""

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import run_staging_deploy as runner
from read_doctl_tag_digest import existing_digest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "host_guard", ROOT / "be/deploy/staging/host_preflight.py"
)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


class RegistryTagParserTests(unittest.TestCase):
    def setUp(self):
        self.expected = "a" * 40
        self.digest = "sha256:" + "b" * 64

    def test_existing_sha_tag_returns_its_manifest_digest(self):
        payload = [
            {
                "registry_name": "compass",
                "repository": "compass-backend",
                "tag": self.expected,
                "manifest_digest": self.digest,
            }
        ]
        self.assertEqual(existing_digest(payload, self.expected), self.digest)

    def test_absent_sha_tag_is_empty_and_omitted_empty_tag_is_supported(self):
        payload = [
            {"tag": "c" * 40, "manifest_digest": self.digest},
            # doctl's JSON marshaler omits Go string fields tagged `omitempty`.
            {"manifest_digest": self.digest},
        ]
        self.assertEqual(existing_digest(payload, self.expected), "")

    def test_malformed_tag_responses_fail_closed(self):
        malformed = [
            {},
            ["not a tag record"],
            [{"tag": self.expected}],
            [{"tag": self.expected, "manifest_digest": "not-a-digest"}],
            [{"tag": None, "manifest_digest": self.digest}],
        ]
        for payload in malformed:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                existing_digest(payload, self.expected)

    def test_duplicate_sha_tag_fails_closed(self):
        payload = [
            {"tag": self.expected, "manifest_digest": self.digest},
            {"tag": self.expected, "manifest_digest": self.digest},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            existing_digest(payload, self.expected)

    def test_workflow_preserves_immutable_sha_and_digest_verification(self):
        workflow = (ROOT / ".github/workflows/deploy-staging.yml").read_text()
        self.assertIn("read_doctl_tag_digest.py \"$tags\" \"$DEPLOY_SHA\"", workflow)
        self.assertIn('image="registry.digitalocean.com/$DO_REGISTRY_NAME/$DO_REGISTRY_REPOSITORY:$DEPLOY_SHA"', workflow)
        self.assertIn('[[ -z "$existing_digest" || "$existing_digest" == "$digest" ]]', workflow)
        self.assertIn('[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]', workflow)


def fixture():
    config = {
        "name": "compass",
        "volumes": {k: {"name": v[0], "external": True} for k, v in host.VOLUMES.items()},
        "networks": {"default": {"name": host.NETWORK, "external": True}},
    }
    volumes = {
        v[0]: {
            "Name": v[0],
            "CreatedAt": v[1],
            "Driver": "local",
            "Labels": {"com.docker.compose.project": "compass", "com.docker.compose.volume": k},
        }
        for k, v in host.VOLUMES.items()
    }
    network = {
        "Name": host.NETWORK,
        "Labels": {
            "com.docker.compose.project": "compass",
            "com.docker.compose.network": "default",
        },
    }
    containers = []
    mounts = {
        "postgres": [("/var/lib/postgresql/data", "postgres_data")],
        "redis": [("/data", "redis_data")],
        "proxy": [("/data", "caddy_data"), ("/config", "caddy_config")],
    }
    for name in ["web", "worker", "beat", "realtime", "postgres", "redis", "proxy"]:
        containers.append(
            {
                "Name": "/compass-" + name + "-1",
                "Config": {
                    "Labels": {
                        "com.docker.compose.project": "compass",
                        "com.docker.compose.service": name,
                        "com.docker.compose.oneoff": "False",
                    }
                },
                "State": {"Running": True},
                "NetworkSettings": {"Networks": {host.NETWORK: {}}},
                "Mounts": [
                    {"Type": "volume", "Destination": dest, "Name": host.VOLUMES[key][0]}
                    for dest, key in mounts.get(name, [])
                ],
            }
        )
    return volumes, network, containers, config


class DestinationTests(unittest.TestCase):
    def test_exact_initialized_resource_contract_passes(self):
        values = fixture()
        values[3]["networks"]["default"]["ipam"] = {}
        self.assertEqual(len(host.validate_resources(*values)), 7)

    def test_wrong_or_replaced_resource_never_passes(self):
        for change in [
            "project",
            "name",
            "external",
            "creation",
            "ownership",
            "network",
            "mount",
            "missing_web",
            "duplicate",
            "foreign",
            "oneoff",
            "stopped",
        ]:
            with self.subTest(change=change):
                volumes, network, containers, config = fixture()
                if change == "project":
                    config["name"] = "different"
                if change == "name":
                    config["volumes"]["postgres_data"]["name"] = "compass_postgres_data"
                if change == "external":
                    config["volumes"]["redis_data"]["external"] = False
                if change == "creation":
                    volumes[host.VOLUMES["postgres_data"][0]]["CreatedAt"] = "new empty volume"
                if change == "ownership":
                    volumes[host.VOLUMES["caddy_data"][0]]["Labels"][
                        "com.docker.compose.project"
                    ] = "other"
                if change == "network":
                    network["Labels"]["com.docker.compose.project"] = "other"
                if change == "mount":
                    containers[4]["Mounts"][0]["Name"] = "compass_postgres_data"
                if change == "missing_web":
                    containers = containers[1:]
                if change == "duplicate":
                    containers.append(copy.deepcopy(containers[0]))
                if change == "foreign":
                    c = copy.deepcopy(containers[0])
                    c["Config"]["Labels"]["com.docker.compose.project"] = "other"
                    containers.append(c)
                if change == "oneoff":
                    containers[0]["Config"]["Labels"]["com.docker.compose.oneoff"] = "True"
                if change == "stopped":
                    containers[2]["State"]["Running"] = False
                with self.assertRaises(host.Refused):
                    host.validate_resources(volumes, network, containers, config)

    def test_realtime_optional_unrelated_container_allowed(self):
        v, n, c, config = fixture()
        c = [x for x in c if x["Name"] != "/compass-realtime-1"]
        unrelated = {
            "Config": {"Labels": {}},
            "NetworkSettings": {"Networks": {"other": {}}},
            "Mounts": [],
        }
        c.append(unrelated)
        self.assertEqual(len(host.validate_resources(v, n, c, config)), 6)

    def test_environment_cannot_redirect_candidate_to_another_database_or_broker(self):
        services = {
            "postgres": {"Config": {"Env": ["POSTGRES_DB=compass", "POSTGRES_USER=compass"]}}
        }
        candidate = {
            "services": {
                "postgres": {"environment": {"POSTGRES_DB": "compass", "POSTGRES_USER": "compass"}},
                **{key: {"environment": {}} for key in ["web", "worker", "beat"]},
            }
        }
        host.validate_endpoints(services, candidate)
        for key, value in [
            ("POSTGRES_DB", "other"),
            ("POSTGRES_HOST", "external.example"),
            ("REDIS_HOST", "external.example"),
            ("REDIS_PORT", "6380"),
        ]:
            modified = copy.deepcopy(candidate)
            modified["services"]["web"]["environment"][key] = value
            with self.subTest(key=key), self.assertRaises(host.Refused):
                host.validate_endpoints(services, modified)

    def test_infrastructure_comparison_ignores_only_release_path(self):
        a = {
            "image": "postgres:17",
            "volumes": [{"source": "/opt/compass/releases/" + ("a" * 40) + "/file"}],
        }
        b = copy.deepcopy(a)
        b["volumes"][0]["source"] = "/opt/compass/releases/" + ("b" * 40) + "/file"
        self.assertEqual(host.normalize_infrastructure(a), host.normalize_infrastructure(b))
        b["image"] = "postgres:18"
        self.assertNotEqual(host.normalize_infrastructure(a), host.normalize_infrastructure(b))

    def test_selector_is_data_never_shell(self):
        good = (
            "COMPASS_IMAGE=sha256:"
            + ("a" * 64)
            + "\nCOMPASS_SECRETS_DIR=/opt/compass/secrets\nCOMPOSE_FILE=/opt/compass/releases/"
            + ("b" * 40)
            + "/compose.staging.yaml\nCOMPOSE_PROFILES=realtime\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "selector"
            with patch.object(host.Path, "is_file", return_value=True):
                p.write_text(good)
                self.assertEqual(host.read_selector(p)["COMPOSE_PROFILES"], "realtime")
                for bad in [
                    good + "echo oops\n",
                    good.replace("sha256:" + ("a" * 64), "latest"),
                    good.replace("realtime", "$(touch /tmp/unsafe)"),
                    good.replace("compass/secrets", "other/secrets"),
                ]:
                    p.write_text(bad)
                    with self.assertRaises(host.Refused):
                        host.read_selector(p)

    def test_baseline_manifest_matches_immutable_sources(self):
        hashes = json.loads((ROOT / "be/deploy/staging/baseline-sha256.json").read_text())
        self.assertEqual(len(hashes), 26)
        for filename, digest in hashes.items():
            self.assertEqual(
                hashlib.sha256((ROOT / "be" / filename).read_bytes()).hexdigest(), digest
            )


class FirewallTests(unittest.TestCase):
    def cloud(self):
        return (
            {"id": runner.FW, "droplet_ids": [runner.DROPLET], "tags": []},
            [
                {
                    "id": runner.DROPLET,
                    "name": "compass-staging-api-01",
                    "networks": {"v4": [{"type": "public", "ip_address": "157.245.60.65"}]},
                }
            ],
            [{"urn": f"do:droplet:{runner.DROPLET}"}],
        )

    def test_cloud_identity_is_not_container_name_guessing(self):
        f, d, r = self.cloud()
        runner.validate_cloud(f, d, r)
        for bad in [
            (dict(f, droplet_ids=[123]), d, r),
            (f, d, []),
            (f, [], r),
            (dict(f, tags=["foreign"]), d, r),
        ]:
            with self.assertRaises(RuntimeError):
                runner.validate_cloud(*bad)

    def test_preexisting_ssh_rule_is_never_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "lease"
            p.write_text(
                json.dumps({"firewall": runner.FW, "cidr": "8.8.8.8/32", "created": False})
            )
            with patch.object(runner, "api") as api, patch.object(runner, "run") as run:
                runner.close_firewall(p)
                api.assert_not_called()
                run.assert_not_called()

    def test_owned_rule_cleanup_is_idempotent_and_exact(self):
        present = {
            "inbound_rules": [
                {"protocol": "tcp", "ports": "22", "sources": {"addresses": ["8.8.8.8/32"]}}
            ]
        }
        absent = {"inbound_rules": []}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "lease"
            p.write_text(json.dumps({"firewall": runner.FW, "cidr": "8.8.8.8/32", "created": True}))
            with (
                patch.object(runner, "api", side_effect=[[present], [absent]]),
                patch.object(runner, "run") as run,
            ):
                runner.close_firewall(p)
                self.assertEqual(run.call_args.args[-1], "protocol:tcp,ports:22,address:8.8.8.8/32")
                runner.close_firewall(p)
                self.assertEqual(run.call_count, 1)

    def test_cleanup_rejects_broad_or_foreign_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "lease"
            for cidr, fw in [("0.0.0.0/0", runner.FW), ("8.8.8.8/32", "foreign")]:
                p.write_text(json.dumps({"firewall": fw, "cidr": cidr, "created": True}))
                with patch.object(runner, "run") as run, self.assertRaises(RuntimeError):
                    runner.close_firewall(p)
                run.assert_not_called()


class OrderingTests(unittest.TestCase):
    def test_rollout_fences_consumers_before_schema_and_never_starts_storage(self):
        script = "\n".join(
            line
            for line in (ROOT / "be/deploy/staging/deploy.sh").read_text().splitlines()
            if not line.lstrip().startswith("#")
        )
        self.assertLess(
            script.index("host_preflight.py .candidate-config.json >"), script.index("docker pull")
        )
        self.assertLess(
            script.index("python deploy/staging/database_preflight.py"),
            script.index("phase=quiescing"),
        )
        self.assertLess(
            script.index("python - worker-idle"),
            script.index("docker stop --timeout -1 compass-worker-1"),
        )
        self.assertLess(
            script.index("docker stop --timeout -1 compass-worker-1"),
            script.index("phase=migrating"),
        )
        self.assertLess(
            script.index("phase=migrating"), script.index("python manage.py migrate --noinput")
        )
        self.assertIn("up -d --no-deps --pull never", script)
        for forbidden in [
            "down -v",
            "volume rm",
            "--fake",
            "seed_staging_dataset",
            "--remove-orphans",
            "up -d postgres",
        ]:
            self.assertNotIn(forbidden, script)
        self.assertLess(
            script.index("meta['built_at']"), script.index("mv /opt/compass/.deploy.env.next")
        )
