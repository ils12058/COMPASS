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
        self.assertIn('read_doctl_tag_digest.py "$tags" "$DEPLOY_SHA"', workflow)
        self.assertIn(
            'image="registry.digitalocean.com/$DO_REGISTRY_NAME/$DO_REGISTRY_REPOSITORY:$DEPLOY_SHA"',
            workflow,
        )
        self.assertIn(
            '[[ -z "$existing_digest" || "$existing_digest" == "$digest" ]]', workflow
        )
        self.assertIn('[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]', workflow)


def fixture():
    config = {
        "name": "compass",
        "volumes": {
            k: {"name": v[0], "external": True} for k, v in host.VOLUMES.items()
        },
        "networks": {"default": {"name": host.NETWORK, "external": True}},
    }
    volumes = {
        v[0]: {
            "Name": v[0],
            "CreatedAt": v[1],
            "Driver": "local",
            "Labels": {
                "com.docker.compose.project": "compass",
                "com.docker.compose.volume": k,
            },
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
                    {
                        "Type": "volume",
                        "Destination": dest,
                        "Name": host.VOLUMES[key][0],
                    }
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
                    volumes[host.VOLUMES["postgres_data"][0]]["CreatedAt"] = (
                        "new empty volume"
                    )
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
                    containers[0]["Config"]["Labels"]["com.docker.compose.oneoff"] = (
                        "True"
                    )
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
            "postgres": {
                "Config": {"Env": ["POSTGRES_DB=compass", "POSTGRES_USER=compass"]}
            }
        }
        candidate = {
            "services": {
                "postgres": {
                    "environment": {
                        "POSTGRES_DB": "compass",
                        "POSTGRES_USER": "compass",
                    }
                },
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
        self.assertEqual(
            host.normalize_infrastructure(a), host.normalize_infrastructure(b)
        )
        b["image"] = "postgres:18"
        self.assertNotEqual(
            host.normalize_infrastructure(a), host.normalize_infrastructure(b)
        )

    def test_selector_is_data_never_shell(self):
        good = (
            "COMPASS_IMAGE=sha256:"
            + ("a" * 64)
            + "\nCOMPASS_SECRETS_DIR=/opt/compass/secrets\nCOMPOSE_FILE=/opt/compass/releases/"
            + ("b" * 40)
            + "/compose.staging.yaml\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "selector"
            with patch.object(host.Path, "is_file", return_value=True):
                p.write_text(good)
                self.assertEqual(
                    host.read_selector(p)["COMPASS_SECRETS_DIR"], "/opt/compass/secrets"
                )
                for bad in [
                    good + "echo oops\n",
                    good + "COMPOSE_PROFILES=realtime\n",
                    good.replace("sha256:" + ("a" * 64), "latest"),
                    good.replace("compass/secrets", "$(touch /tmp/unsafe)"),
                    good.replace("compass/secrets", "other/secrets"),
                ]:
                    p.write_text(bad)
                    with self.assertRaises(host.Refused):
                        host.read_selector(p)

    def test_baseline_manifest_matches_immutable_sources(self):
        hashes = json.loads(
            (ROOT / "be/deploy/staging/baseline-sha256.json").read_text()
        )
        self.assertEqual(len(hashes), 36)
        for filename, digest in hashes.items():
            self.assertEqual(
                hashlib.sha256((ROOT / "be" / filename).read_bytes()).hexdigest(),
                digest,
            )

    def test_release_history_requires_every_guard_and_matching_catalog(self):
        baseline = json.loads(
            (ROOT / "be/deploy/staging/baseline-sha256.json").read_text()
        )
        applied = {(p.split("/")[1], Path(p).stem) for p in baseline}
        host.validate_release_history(baseline, applied, catalog_table=1)
        # No code-package registration file is available in the host's uploaded tooling bundle.
        cases = [
            (applied - {("good_moral", "0002_database_guards")}, 1),
            (applied - {("organization", "0001_release_baseline")}, 1),
            (applied | {("accounts", "0001_retired_baseline")}, 1),
            (applied, 0),
        ]
        for history, catalog_table in cases:
            with (
                self.subTest(history=history, catalog_table=catalog_table),
                self.assertRaises(host.Refused),
            ):
                host.validate_release_history(
                    baseline, history, catalog_table=catalog_table
                )


class FirewallTests(unittest.TestCase):
    def cloud(self):
        return (
            {"id": runner.FW, "droplet_ids": [runner.DROPLET], "tags": []},
            [
                {
                    "id": runner.DROPLET,
                    "name": "compass-staging-api-01",
                    "networks": {
                        "v4": [{"type": "public", "ip_address": "157.245.60.65"}]
                    },
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
                json.dumps(
                    {"firewall": runner.FW, "cidr": "8.8.8.8/32", "created": False}
                )
            )
            with patch.object(runner, "api") as api, patch.object(runner, "run") as run:
                runner.close_firewall(p)
                api.assert_not_called()
                run.assert_not_called()

    def test_owned_rule_cleanup_is_idempotent_and_exact(self):
        present = {
            "inbound_rules": [
                {
                    "protocol": "tcp",
                    "ports": "22",
                    "sources": {"addresses": ["8.8.8.8/32"]},
                }
            ]
        }
        absent = {"inbound_rules": []}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "lease"
            p.write_text(
                json.dumps(
                    {"firewall": runner.FW, "cidr": "8.8.8.8/32", "created": True}
                )
            )
            with (
                patch.object(runner, "api", side_effect=[[present], [absent]]),
                patch.object(runner, "run") as run,
            ):
                runner.close_firewall(p)
                self.assertEqual(
                    run.call_args.args[-1], "protocol:tcp,ports:22,address:8.8.8.8/32"
                )
                runner.close_firewall(p)
                self.assertEqual(run.call_count, 1)

    def test_cleanup_rejects_broad_or_foreign_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "lease"
            for cidr, fw in [("0.0.0.0/0", runner.FW), ("8.8.8.8/32", "foreign")]:
                p.write_text(
                    json.dumps({"firewall": fw, "cidr": cidr, "created": True})
                )
                with (
                    patch.object(runner, "run") as run,
                    self.assertRaises(RuntimeError),
                ):
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
            script.index("host_preflight.py .candidate-config.json >"),
            script.index("docker pull"),
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
            script.index("phase=migrating"),
            script.index("python manage.py migrate --noinput"),
        )
        self.assertIn("up -d --no-deps --pull never", script)
        self.assertIn("apps=(web worker beat realtime proxy)", script)
        common = (ROOT / "be/deploy/staging/deploy_common.sh").read_text()
        self.assertIn("for name in ['web','worker','beat','realtime']:", common)
        self.assertNotIn("--profile realtime", script)
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
            common.index("meta['built_at']"),
            common.index("mv /opt/compass/.deploy.env.next"),
        )


# Reset modules are host tooling, deliberately outside Django's test inventory.
sys.path.insert(0, str(ROOT / "be/deploy/staging"))
import os
import subprocess
import textwrap

import reset_preflight as reset_guard
import reset_redis
import reset_state


class ResetInputTests(unittest.TestCase):
    def validate(
        self,
        operation="reset",
        sha=None,
        phrase=None,
        domain="compass-staging.test",
        action="check",
    ):
        sha = sha or runner.BASELINE
        phrase = "RESET STAGING " + sha[:12] if phrase is None else phrase
        runner.validate_inputs(operation, sha, phrase, domain, action)

    def test_reset_phrase_domain_and_catalog_fail_closed(self):
        self.validate()
        for phrase in (
            "",
            "reset staging " + runner.BASELINE[:12],
            "RESET STAGING " + runner.BASELINE,
            "RESET STAGING " + "f" * 12,
        ):
            with self.subTest(phrase=phrase), self.assertRaises(RuntimeError):
                self.validate(phrase=phrase)
        for domain in (
            "",
            "https://example.test",
            "EXAMPLE.test",
            "example.test.",
            "*.test",
            "x.test:443",
            "x.test/path",
            "-x.test",
            "x-.test",
            "127.0.0.1",
            "localhost",
            "a" * 64 + ".test",
            "x.test\n",
        ):
            with self.subTest(domain=domain), self.assertRaises(RuntimeError):
                self.validate(domain=domain)
        for action in ("adopt", "seed", "other"):
            with self.subTest(action=action), self.assertRaises(RuntimeError):
                self.validate(action=action)

    def test_preflight_and_deploy_inputs(self):
        self.validate(operation="reset-preflight", phrase="", domain="")
        self.validate(operation="deploy", phrase="", domain="")
        for operation, phrase, domain, action in (
            ("deploy", "RESET STAGING " + runner.BASELINE[:12], "", "check"),
            ("deploy", "", "example.test", "check"),
            ("reset-preflight", "", "", "seed"),
            ("reset-preflight", "RESET STAGING " + runner.BASELINE[:12], "", "check"),
            ("unknown", "", "", "check"),
        ):
            with self.subTest(operation=operation), self.assertRaises(RuntimeError):
                self.validate(
                    operation=operation, phrase=phrase, domain=domain, action=action
                )

    def test_workflow_runs_same_validation_first_and_keeps_every_operation_gated(self):
        workflow = (ROOT / ".github/workflows/deploy-staging.yml").read_text()
        embedded = workflow.split("python3 - <<'PY'\n", 1)[1].split(
            "\n          PY", 1
        )[0]
        code = textwrap.dedent(embedded)
        # Execute the actual first workflow step locally, with no checkout, provider or shell.
        good = {
            "OPERATION": "reset",
            "EXPECTED_STAGING_SHA": runner.BASELINE,
            "CONFIRM_RESET": "RESET STAGING " + runner.BASELINE[:12],
            "DATASET_EMAIL_DOMAIN": "example.test",
            "ORG_CATALOG_ACTION": "check",
        }
        with patch.dict(os.environ, good, clear=True):
            exec(code, {})  # noqa: S102 - execute the checked-in validation step only
        for key, bad in [
            ("CONFIRM_RESET", "no"),
            ("DATASET_EMAIL_DOMAIN", "EXAMPLE.test"),
            ("ORG_CATALOG_ACTION", "seed"),
        ]:
            with (
                patch.dict(os.environ, {**good, key: bad}, clear=True),
                self.assertRaises(RuntimeError),
            ):
                exec(code, {})  # noqa: S102 - execute the checked-in validation step only
        self.assertLess(
            workflow.index("Validate operation inputs"),
            workflow.index("uses: actions/checkout"),
        )
        self.assertNotIn("Refuse the reset-only release baseline", workflow)
        self.assertIn("require_full_regression.py", workflow)
        self.assertIn("if: inputs.operation != 'reset-preflight'", workflow)
        self.assertIn(
            "STAGING_SEED_ONBOARDING_EMAIL: ${{ secrets.STAGING_SEED_ONBOARDING_EMAIL }}",
            workflow,
        )

    def test_old_runtime_fails_new_lineage_independently_of_database(self):
        # Real Git ancestry in a throwaway repository, so the check does not depend on how
        # much history the CI checkout fetched: old -> baseline -> new.
        self.assertRegex(runner.BASELINE, "^[0-9a-f]{40}$")
        self.assertEqual(host.BASELINE, runner.BASELINE)
        with tempfile.TemporaryDirectory() as directory:
            git_env = {
                "GIT_DIR": f"{directory}/.git",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "lineage",
                "GIT_AUTHOR_EMAIL": "lineage@example.invalid",
                "GIT_COMMITTER_NAME": "lineage",
                "GIT_COMMITTER_EMAIL": "lineage@example.invalid",
            }
            with patch.dict(os.environ, git_env):
                subprocess.run(["git", "init", "-q", directory], check=True)
                commits = []
                for name in ("old", "baseline", "new"):
                    subprocess.run(
                        ["git", "commit", "-q", "--allow-empty", "-m", name], check=True
                    )
                    commits.append(
                        subprocess.run(
                            ["git", "rev-parse", "HEAD"],
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.strip()
                    )
                old, baseline, new = commits
                with patch.object(runner, "BASELINE", baseline):
                    with self.assertRaises(subprocess.CalledProcessError):
                        runner.validate_runtime_lineage(old, new)
                    runner.validate_runtime_lineage(baseline, new)
                    runner.validate_runtime_lineage(new, new)


class ResetPreflightTests(unittest.TestCase):
    def baseline(self):
        return json.loads((ROOT / "be/deploy/staging/baseline-sha256.json").read_text())

    def database(self, migrations=None, table=True):
        return {
            "migrations_table": table,
            "migrations": list(
                migrations
                if migrations is not None
                else reset_guard.expected_history(self.baseline())
            ),
            "catalog_table": 1,
        }

    def test_classification_and_old_history_independent_of_lineage(self):
        baseline = self.baseline()
        self.assertEqual(
            reset_guard.classify_database(baseline, self.database()), "release"
        )
        self.assertEqual(
            reset_guard.classify_database(baseline, self.database([], False)), "empty"
        )
        canonical = {(p.split("/")[1], "0001_canonical_baseline") for p in baseline}
        self.assertEqual(
            reset_guard.classify_database(baseline, self.database(canonical)),
            "canonical",
        )
        with self.assertRaises(host.Refused):
            host.validate_release_history(baseline, canonical, catalog_table=1)
        for rows in (
            [],
            [("accounts", "0001_initial")],
            [("accounts", "0001_release_baseline")],
            canonical | {("accounts", "0001_release_baseline")},
            reset_guard.expected_history(baseline) | {("accounts", "0002_unknown")},
        ):
            with self.subTest(rows=rows), self.assertRaises(reset_guard.host.Refused):
                reset_guard.classify_database(baseline, self.database(rows))

    def test_resources_allow_removed_apps_but_never_wrong_storage(self):
        v, n, c, config = fixture()
        storage = [
            x for x in c if x["Name"] in ("/compass-postgres-1", "/compass-redis-1")
        ]
        reset_guard.host.validate_resources(v, n, storage, config, reset=True)
        for change in (
            "mount",
            "created",
            "foreign",
            "network",
            "missing_storage",
            "stopped_storage",
        ):
            a, b, services, candidate = copy.deepcopy((v, n, storage, config))
            if change == "mount":
                services[0]["Mounts"][0]["Name"] = "compass_postgres_data"
            elif change == "created":
                a[host.VOLUMES["postgres_data"][0]]["CreatedAt"] = "new"
            elif change == "foreign":
                services[0]["Config"]["Labels"]["com.docker.compose.project"] = "other"
            elif change == "network":
                b["Labels"]["com.docker.compose.project"] = "other"
            elif change == "missing_storage":
                services.pop()
            else:
                services[0]["State"]["Running"] = False
            with (
                self.subTest(change=change),
                self.assertRaises(reset_guard.host.Refused),
            ):
                reset_guard.host.validate_resources(
                    a, b, services, candidate, reset=True
                )

    def test_checkpoint_is_same_sha_image_domain_and_regular_protected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "in-progress.json"
            value = {
                "sha": runner.BASELINE,
                "image": "immutable",
                "domain": "example.test",
            }
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            with patch.object(reset_guard, "checkpoint_path", return_value=path):
                self.assertEqual(
                    reset_guard.read_checkpoint(
                        runner.BASELINE, "immutable", "example.test"
                    ),
                    value,
                )
                for sha, image, domain in [
                    ("a" * 40, "immutable", "example.test"),
                    (runner.BASELINE, "other", "example.test"),
                    (runner.BASELINE, "immutable", "other.test"),
                ]:
                    with self.assertRaises(reset_guard.host.Refused):
                        reset_guard.read_checkpoint(sha, image, domain)
                path.chmod(0o644)
                with self.assertRaises(reset_guard.host.Refused):
                    reset_guard.read_checkpoint(
                        runner.BASELINE, "immutable", "example.test"
                    )

    def test_lock_free_busy_and_inherited_lock(self):
        import fcntl

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(reset_guard, "ROOT", Path(directory)),
        ):
            path = Path(directory) / ".live-reset.lock"
            path.touch()
            reset_guard.check_lock(False)
            with path.open("rb") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(reset_guard.host.Refused):
                    reset_guard.check_lock(False)
            path.unlink()
            reset_guard.check_lock(False)
            with self.assertRaises(reset_guard.host.Refused):
                reset_guard.check_lock(True)

    def test_missing_configuration_fails_without_printing_values(self):
        with (
            patch.object(
                reset_state.Path,
                "read_text",
                return_value=json.dumps(
                    {"services": {"web": {"environment": {"APP_ENV": "live-staging"}}}}
                ),
            ),
            patch.object(reset_state, "quiet") as quiet,
        ):
            with self.assertRaisesRegex(
                reset_state.host.Refused, "COMPASS_PORTAL_ORIGIN"
            ):
                reset_state.settings_check()
            quiet.assert_not_called()

    def test_reset_redis_reuses_normalization_and_no_secret_argument(self):
        source = (ROOT / "be/deploy/runtime-secrets/redis-start.sh").read_text()
        program = reset_redis.reset_program()
        self.assertIn(
            source[source.index("read_password() {") : source.index("\ncase ")], program
        )
        self.assertIn("redis-cli --no-auth-warning FLUSHALL", program)
        self.assertNotIn("redis-cli -a", program)


class ResetOrderingExecutionTests(unittest.TestCase):
    """Execute the real reset shell and helpers against stateful fake Docker/psql, never a daemon."""

    def rehearsal(self, failure="", *, partial=False, drift=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        deploy_root = base / "compass"
        release = deploy_root / "releases" / runner.BASELINE
        staging = release / "deploy/staging"
        staging.mkdir(parents=True)
        (release / "deploy/runtime-secrets").mkdir()
        secrets = deploy_root / "secrets"
        secrets.mkdir()
        (secrets / "counselor_handoff_summary_encryption_keys").write_text("synthetic")
        (secrets / "guidance_followup_encryption_keys").write_text("synthetic")
        (release / "compose.staging.yaml").touch()
        (release / ".registry").mkdir()
        # Only path relocation in the test copy; commands, ordering and failure traps are production.
        for filename in ("reset.sh", "deploy_common.sh", "reset_database.sql"):
            content = (
                (ROOT / "be/deploy/staging" / filename)
                .read_text()
                .replace("/opt/compass", str(deploy_root))
            )
            (staging / filename).write_text(content)
        v, n, containers, config = fixture()
        baseline = json.loads(
            (ROOT / "be/deploy/staging/baseline-sha256.json").read_text()
        )
        image = (
            "registry.digitalocean.com/compass/compass-backend:"
            + runner.BASELINE
            + "@sha256:"
            + "b" * 64
        )
        for c in containers:
            c["Id"] = c["Name"].lstrip("/")
            c["Image"] = "sha256:fake-image"
            c["State"]["Health"] = {"Status": "healthy"}
        if partial:
            containers = [c for c in containers if c["Id"] == "compass-postgres-1"]
            containers[0]["State"]["Running"] = False
        config["services"] = {
            "postgres": {
                "environment": {"POSTGRES_DB": "compass", "POSTGRES_USER": "compass"},
                "image": "postgres:pinned",
            },
            "redis": {"image": "redis:pinned"},
            "proxy": {"image": "caddy:pinned"},
            "realtime": {
                "environment": {"REALTIME_ALLOWED_ORIGINS": "https://example.test"}
            },
            **{
                k: {
                    "environment": {
                        "APP_ENV": "live-staging",
                        "COMPASS_PORTAL_ORIGIN": "https://example.test",
                    }
                }
                for k in ("web", "worker", "beat")
            },
        }
        snapshot = {
            "database_class": "canonical" if not partial else "interrupted-unavailable",
            "counts": {
                "migration_count": len(baseline),
                "account_count": len(config["services"]),
            },
            "volumes": v,
            "network": n,
            "recovery": partial,
        }
        (release / ".reset-preflight.json").write_text(
            json.dumps(snapshot, sort_keys=True) + "\n"
        )
        state_file = base / "state.json"
        state_file.write_text(json.dumps(containers))
        data_file = base / "data.json"
        data_file.write_text(
            json.dumps(
                {
                    "candidate": config,
                    "snapshot": snapshot,
                    "image": image,
                    "migration_count": len(baseline),
                    "account_count": len(config["services"]),
                }
            )
        )
        bindir = base / "bin"
        bindir.mkdir()
        log = base / "calls.jsonl"
        fake = """
import io, json, os, runpy, subprocess, sys, urllib.request
from pathlib import Path
args=sys.argv[1:]; name=Path(sys.argv[0]).name
log=Path(os.environ['E3_CALLS']); data=json.loads(Path(os.environ['E3_DATA']).read_text())
statepath=Path(os.environ['E3_STATE']); state=json.loads(statepath.read_text())
with log.open('a') as f: f.write(json.dumps([name,*args])+'\\n')
if os.environ.get('E3_FAILURE') and os.environ['E3_FAILURE'] in ' '.join(args): sys.exit(9)
if name=='flock':
    import fcntl
    fcntl.flock(int(args[-1]),fcntl.LOCK_EX|fcntl.LOCK_NB); sys.exit(0)
if name=='psql':
    with log.open('a') as f: f.write(json.dumps(['sql',sys.stdin.read()])+'\\n')
    sys.exit(0)
if name=='docker':
    if args[:2]==['ps','-aq']: print(' '.join(c['Id'] for c in state))
    elif args[:2]==['image','inspect']:
        print(json.dumps([{'Id':'sha256:fake-image','Config':{'Labels':{'org.opencontainers.image.revision':os.environ['DEPLOY_SHA'],'org.opencontainers.image.version':os.environ['APP_VERSION'],'org.opencontainers.image.created':os.environ['BUILD_TIME']}}}]))
    elif args[0]=='inspect': print(json.dumps([c for c in state if c['Id'] in args[1:] or c['Image'] in args[1:]]))
    elif args[0]=='rm': state=[c for c in state if c['Id'] not in args[1:]]
    elif args[0]=='stop':
        for c in state:
            if c['Id'] in args: c['State']['Running']=False
    elif args[0]=='exec' and '-i' in args:
        content=sys.stdin.read()
        if 'psql' in ' '.join(args): subprocess.run(['psql'],input=content,text=True,check=True)
        else:
            with log.open('a') as f: f.write(json.dumps(['redis-program',content])+'\\n')
    elif args[0]=='compose':
        args=args[args.index('-f')+2:]
        if args[0]=='config': print(json.dumps(data['candidate']))
        elif args[0]=='rm': state=[c for c in state if c['Config']['Labels']['com.docker.compose.service'] not in args[1:]]
        elif args[0]=='up':
            for service in ('web','worker','beat','realtime','proxy','postgres','redis'):
                if service not in args: continue
                state=[c for c in state if c['Config']['Labels']['com.docker.compose.service']!=service]
                state.append({'Id':'compass-'+service+'-1','Name':'/compass-'+service+'-1','Image':'sha256:fake-image','Config':{'Labels':{'com.docker.compose.service':service,'com.docker.compose.oneoff':'False'}},'State':{'Running':True,'Health':{'Status':'healthy'}}})
        elif args[0]=='run' and args[-1]=='verify': print('Verification PASSED.\\n  Schema readiness               '+str(data['migration_count'])+' passed,   0 failed,   0 warnings')
    statepath.write_text(json.dumps(state)); sys.exit(0)
if name=='python3':
    if args[0].endswith('check-runtime-secrets.py'): sys.exit(0)
    if args[0].endswith('reset_preflight.py'):
        snapshot=data['snapshot']
        if os.environ.get('E3_DRIFT'): snapshot['database_class']='empty'
        print(json.dumps(snapshot,sort_keys=True)); sys.exit(0)
    if args[0].endswith('host_preflight.py'):
        print(json.dumps({'accounts':data['account_count'],'migration_count':data['migration_count']})); sys.exit(0)
    sys.path.insert(0,os.environ['E3_SOURCE'])
    import reset_preflight
    reset_preflight.ROOT=Path(os.environ['E3_ROOT'])
    if args[0]=='-':
        urllib.request.urlopen=lambda *a,**kw: io.StringIO(json.dumps({'application':'COMPASS','environment':'live-staging','build_id':os.environ['DEPLOY_SHA'],'version':os.environ['APP_VERSION'],'built_at':os.environ['BUILD_TIME']}))
        sys.argv=['-',*args[1:]]; exec(sys.stdin.read()); sys.exit(0)
    sys.argv=args; runpy.run_path(str(Path(os.environ['E3_SOURCE'])/Path(args[0]).name),run_name='__main__')
"""
        for name in ("docker", "psql", "python3", "flock"):
            file = bindir / name
            file.write_text("#!" + sys.executable + "\n" + textwrap.dedent(fake))
            file.chmod(0o755)
        env = {
            **os.environ,
            "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
            "DEPLOY_SHA": runner.BASELINE,
            "IMAGE": image,
            "APP_VERSION": "test",
            "BUILD_TIME": "2026-11-09T00:00:00Z",
            "DATASET_EMAIL_DOMAIN": "example.test",
            "E3_CALLS": str(log),
            "E3_DATA": str(data_file),
            "E3_STATE": str(state_file),
            "E3_SOURCE": str(ROOT / "be/deploy/staging"),
            "E3_ROOT": str(deploy_root),
            "E3_FAILURE": failure,
            "E3_DRIFT": "true" if drift else "",
        }
        if partial:
            directory = deploy_root / "operator/resets"
            directory.mkdir(parents=True, mode=0o700)
            directory.parent.chmod(0o700)
            marker = directory / "in-progress.json"
            marker.write_text(
                json.dumps(
                    {
                        "sha": runner.BASELINE,
                        "image": image,
                        "domain": "example.test",
                        "before": snapshot,
                        "started_at": "fixture",
                    }
                )
            )
            marker.chmod(0o600)
        result = subprocess.run(
            ["bash", str(staging / "reset.sh"), "reset"],
            env=env,
            input="private-onboarding@example.test\n",
            capture_output=True,
            text=True,
            check=False,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls, json.loads(state_file.read_text()), deploy_root

    def test_real_reset_order_receipt_selector_and_no_credential_leak(self):
        result, calls, state, deploy_root = self.rehearsal()
        self.assertEqual(result.returncode, 0, result.stderr)
        serialized = [" ".join(c) for c in calls]

        def position(text):
            return next(i for i, call in enumerate(serialized) if text in call)

        steps = [
            "reset_state.py fence",
            "rm -f proxy web worker beat realtime",
            "reset_state.py empty-database",
            "psql",
            "reset_state.py empty-redis",
            "up -d --no-deps --force-recreate --pull never postgres redis",
            "manage.py migrate --noinput",
            "manage.py sync_identity_policy",
            "manage.py sync_canonical_services",
            "manage.py sync_institutional_forms",
            "initialize_organization_catalog --seed --reference reset:",
            "initialize_organization_catalog --check",
            "manage.py migrate --check",
            "manage.py check --deploy --database default",
            "seed_staging_dataset seed",
            "seed_staging_dataset verify",
            "up -d --no-deps --pull never --wait",
            "compass_doctor --worker-smoke",
            "host_preflight.py",
            "reset_state.py receipt",
        ]
        order = [position(x) for x in steps]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("issue-credentials", "\n".join(serialized))
        self.assertNotIn(
            "private-onboarding", result.stdout + result.stderr + "\n".join(serialized)
        )
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt["seed_verify"]["passed"])
        self.assertFalse((deploy_root / "operator/resets/in-progress.json").exists())
        written = deploy_root / ".deploy.env"
        # Relocate only the path in the fixture, then feed the production parser.
        with patch.object(host.Path, "is_file", return_value=True):
            written.write_text(
                written.read_text().replace(str(deploy_root), "/opt/compass")
            )
            parsed = host.read_selector(written)
        self.assertNotIn(":", parsed["COMPOSE_FILE"])
        self.assertNotIn("STAGING_SEED_ENABLED", written.read_text())
        for c in state:
            self.assertTrue(c["State"]["Running"])
        files = list((deploy_root / "operator/resets").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_pre_boundary_failures_leave_old_runtime_and_sql_untouched(self):
        for failure in ("settings-check", "reset_state.py image", "reset_preflight.py"):
            with self.subTest(failure=failure):
                result, calls, state, root = self.rehearsal(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(all(c["State"]["Running"] for c in state))
                self.assertFalse(
                    any(c[0] == "psql" or "stop" in c or "rm" in c for c in calls)
                )
                self.assertFalse((root / ".deploy.env").exists())
        result, calls, state, root = self.rehearsal(drift=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(c["State"]["Running"] for c in state))

    def test_after_boundary_failures_fence_started_or_partial_apps(self):
        for failure in (
            "empty-database",
            "empty-redis",
            "force-recreate",
            "migrate --noinput",
            "sync_canonical_services",
            "seed_staging_dataset verify",
            "compass_doctor",
            "host_preflight.py",
            "reset_state.py receipt",
            "stop --timeout 30",
        ):
            with self.subTest(failure=failure):
                result, calls, state, root = self.rehearsal(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(
                    all(
                        not c["State"]["Running"]
                        for c in state
                        if c["Config"]["Labels"]["com.docker.compose.service"]
                        in reset_guard.APPS
                    )
                )
                self.assertIn("App services remain stopped", result.stderr)
                self.assertTrue((root / "operator/resets/in-progress.json").is_file())
                self.assertFalse(
                    any(c[0] == "docker" and c[1] == "start" for c in calls)
                )

    def test_same_sha_partial_storage_retry_recreates_storage_before_emptying(self):
        result, calls, _state, _root = self.rehearsal(partial=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        serialized = [" ".join(c) for c in calls]
        recovery = next(
            i
            for i, x in enumerate(serialized)
            if "force-recreate --pull never postgres redis" in x
        )
        empty = next(i for i, x in enumerate(serialized) if "empty-database" in x)
        self.assertLess(recovery, empty)


class ResetInspectionExecutionTests(unittest.TestCase):
    def inspect_fixture(self, *, recovery=False, broken=""):
        import contextlib

        v, n, c, candidate = fixture()
        n.update(Id="synthetic-network-id", Created="2026-10-16T21:31:13Z")
        for container in c:
            container["Id"] = container["Name"].lstrip("/")
            if container["Id"] == "compass-postgres-1":
                container["Config"]["Env"] = [
                    "POSTGRES_DB=compass",
                    "POSTGRES_USER=compass",
                ]
        candidate["services"] = {
            "postgres": {
                "environment": {"POSTGRES_DB": "compass", "POSTGRES_USER": "compass"}
            },
            "realtime": {
                "environment": {"REALTIME_ALLOWED_ORIGINS": "https://example.test"}
            },
            **{name: {"environment": {}} for name in ("web", "worker", "beat")},
        }
        baseline = json.loads(
            (ROOT / "be/deploy/staging/baseline-sha256.json").read_text()
        )
        rows = sorted(reset_guard.expected_history(baseline))
        database = {
            "migrations_table": True,
            "migrations": rows,
            "migration_count": len(rows),
            "account_count": len(candidate["services"]),
            "catalog_table": 1,
            "email_domains": ["example.test"],
        }
        checkpoint = None
        if recovery:
            checkpoint = {
                "before": {"network": {"id": n["Id"], "created": n["Created"]}}
            }
            database["migrations"] = rows[
                :1
            ]  # Interrupted first release migration, with durable fence.
            c = [
                container
                for container in c
                if container["Id"] in ("compass-postgres-1", "compass-redis-1")
            ]
        if broken in {"oneoff", "foreign_oneoff"}:
            oneoff = copy.deepcopy(fixture()[2][0])
            oneoff.update(
                Id="compass-web-run-scratch",
                Name="/compass-web-run-scratch",
                Image="candidate-image" if broken == "oneoff" else "foreign-image",
            )
            oneoff["Config"]["Labels"]["com.docker.compose.oneoff"] = "True"
            c.append(oneoff)
        if broken == "unknown":
            database["migrations"] = [*rows, ("unknown_app", "0001_initial")]
        if broken == "origins":
            candidate["services"]["realtime"]["environment"][
                "REALTIME_ALLOWED_ORIGINS"
            ] = ""
        if broken == "mount":
            c[-3]["Mounts"][0]["Name"] = "compass_postgres_data"
        if broken == "network_replaced":
            n["Id"] = "different"
        if broken == "missing_checkpoint":
            checkpoint = None
        if broken == "unavailable":
            database = None
        ids = [container["Id"] for container in c]

        def docker(*args):
            if args[0] == "image":
                return [{"Id": "candidate-image"}]
            if args[0] == "volume":
                return [v[args[2]]]
            if args[0] == "network":
                return [n]
            return c

        def run(*args, **kwargs):
            return (
                " ".join(ids)
                if args[1] == "ps"
                else "\n".join(v)
                + ("\ncompass_postgres_data" if broken == "old_volume" else "")
            )

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        "DEPLOY_SHA": runner.BASELINE,
                        "IMAGE": "immutable",
                        "DATASET_EMAIL_DOMAIN": "example.test",
                    },
                )
            )
            stack.enter_context(patch.object(reset_guard.host, "validate_host"))
            stack.enter_context(patch.object(reset_guard, "check_lock"))
            stack.enter_context(
                patch.object(reset_guard, "read_checkpoint", return_value=checkpoint)
            )
            stack.enter_context(
                patch.object(reset_guard.host, "docker_json", side_effect=docker)
            )
            stack.enter_context(patch.object(reset_guard.host, "run", side_effect=run))
            stack.enter_context(
                patch.object(
                    reset_guard.host, "read_selector", side_effect=FileNotFoundError
                )
            )
            stack.enter_context(
                patch.object(reset_guard, "database_snapshot", return_value=database)
            )
            return reset_guard.inspect(candidate, recovery=recovery)

    def test_complete_read_only_inspection_passes_and_reports_names_counts(self):
        result = self.inspect_fixture()
        self.assertEqual(result["database_class"], "release")
        self.assertEqual(result["email_domains"], ["example.test"])
        self.assertIsNone(result["current_revision"])
        self.assertTrue(result["realtime_running"])
        self.assertIn("created", result["network"])
        host.validate_resources(*fixture())
        baseline = json.loads(
            (ROOT / "be/deploy/staging/baseline-sha256.json").read_text()
        )
        host.validate_release_history(
            baseline, reset_guard.expected_history(baseline), catalog_table=1
        )

    def test_unknown_history_config_resource_and_old_volume_fail_closed(self):
        for broken in ("unknown", "origins", "mount", "old_volume", "unavailable"):
            with (
                self.subTest(broken=broken),
                self.assertRaises(reset_guard.host.Refused),
            ):
                self.inspect_fixture(broken=broken)

    def test_partial_history_or_unavailable_requires_same_candidate_checkpoint(self):
        self.assertEqual(
            self.inspect_fixture(recovery=True)["database_class"], "interrupted-release"
        )
        self.assertEqual(
            self.inspect_fixture(recovery=True, broken="unavailable")["database_class"],
            "interrupted-unavailable",
        )
        self.assertEqual(
            self.inspect_fixture(recovery=True, broken="oneoff")["reset_oneoffs"],
            [{"id": "compass-web-run-scratch", "running": True}],
        )
        for broken in (
            "unknown",
            "missing_checkpoint",
            "network_replaced",
            "foreign_oneoff",
        ):
            with (
                self.subTest(broken=broken),
                self.assertRaises(reset_guard.host.Refused),
            ):
                self.inspect_fixture(recovery=True, broken=broken)

    def test_host_identity_and_freeze_are_checked_before_docker(self):
        import io

        with (
            patch.object(
                reset_guard.host.urllib.request,
                "urlopen",
                return_value=io.BytesIO(b"wrong"),
            ),
            self.assertRaisesRegex(reset_guard.host.Refused, "Droplet"),
        ):
            reset_guard.host.validate_host()
        with (
            patch.object(
                reset_guard.host.urllib.request,
                "urlopen",
                return_value=io.BytesIO(b"602091909"),
            ),
            patch.object(reset_guard.host.Path, "exists", return_value=True),
            self.assertRaisesRegex(reset_guard.host.Refused, "freeze"),
        ):
            reset_guard.host.validate_host()


class ResetRunnerRoutingTests(unittest.TestCase):
    def test_reset_does_not_check_old_runtime_lineage_and_email_is_stdin_only(self):
        from types import SimpleNamespace

        sha = runner.BASELINE
        image = (
            f"registry.digitalocean.com/compass/compass-backend:{sha}@sha256:"
            + "b" * 64
        )
        environment = {
            "OPERATION": "reset",
            "CONFIRM_RESET": "RESET STAGING " + sha[:12],
            "DATASET_EMAIL_DOMAIN": "example.test",
            "DEPLOY_SHA": sha,
            "IMAGE": image,
            "ORG_CATALOG_ACTION": "check",
            "DEPLOY_PATH": "/opt/compass",
            "STAGING_DEPLOY_USER": "compass",
            "STAGING_DEPLOY_PORT": "22",
            "STAGING_DEPLOY_HOST": "157.245.60.65",
            "STAGING_FIREWALL_ID": runner.FW,
            "APP_VERSION": "test",
            "BUILD_TIME": "2026-11-09T00:00:00Z",
            "STAGING_REGISTRY_PULL_CONFIG": "/synthetic/config",
            "STAGING_SEED_ONBOARDING_EMAIL": "private@example.test",
        }

        def run(*args, **kwargs):
            if args[0] == "git" and args[1] == "ls-remote":
                return SimpleNamespace(stdout=sha + "\trefs/heads/staging\n", stderr="")
            if args[0] == "ssh" and "echo new" in args[-1]:
                return SimpleNamespace(stdout="new\n", stderr="")
            if args[0] == "ssh" and "reset_preflight.py" in args[-1]:
                return SimpleNamespace(
                    stdout=json.dumps(
                        {"database_class": "canonical", "current_revision": "0a843dae"}
                    ),
                    stderr="",
                )
            return SimpleNamespace(stdout="{}", stderr="")

        with (
            patch.dict(os.environ, environment),
            patch.object(runner, "ssh_options", return_value=[]),
            patch.object(runner, "run", side_effect=run) as commands,
            patch.object(runner, "validate_runtime_lineage") as lineage,
            patch("builtins.print"),
        ):
            runner.deploy()
        lineage.assert_not_called()
        reset = [
            call
            for call in commands.call_args_list
            if call.args[0] == "ssh" and call.args[-1].endswith("reset.sh reset")
        ]
        self.assertEqual(len(reset), 1)
        self.assertEqual(reset[0].kwargs["input"], "private@example.test\n")
        self.assertNotIn(
            "private@example.test",
            " ".join(str(call.args) for call in commands.call_args_list),
        )
        self.assertIn(".registry", commands.call_args_list[-1].args[-1])
