# Validation, evidence and limits

Audit date: 2026-10-23, Asia/Manila. Source baseline: integration `5fddafec9e72ec987f6605533825e65795818b81`. Commands below were run locally against that source with documentation additions only. No database connection or migration was needed.

## Baseline and source inspection

Executed `git remote -v`, `git fetch origin --prune`, `git rev-parse origin/integration/ux15-modernization origin/staging origin/main`, primary checkout status and worktree listing. Exact remote/references are in [README](README.md). Managed worktree created at the recorded integration ref; `git switch -c audit/cont-0-case-continuity`; verified HEAD matched integration and the new worktree started clean. Primary untracked files were neither staged nor edited.

Inspected current models/services/routes/capabilities/encryption/tests across all requested domains, Call Slips, Overview/Guidance Operations, frontend Counseling/Routine/Student/Notification flows and current cache/expiry helpers. Read relevant ADRs including current refinements and Proposal #6. Do not infer old ADR descriptions or proposal intentions are implemented. No deployment log/database/secret inspection was required.

Proposal source actually used: `/Users/reynantlntno/Downloads/COMPASS Development Proposal Notes - Fifteen Proposals.md`, Proposal #6 lines 3837–4680. The earlier `.txt` location was absent; the Markdown source was located and used. The newer request overrides Proposal #6's rolling-compatibility/legacy-alias recommendation and permits separately authorized disposable-data cutover. Proposal source is local background, not an approved policy. The full source is not copied into this PR.

## Executed focused tests

Used the existing local Python environment (Python 3.13.12, Django 6.1.1, pytest 9.1.1) without installing/updating dependencies. Process environment was restricted to PATH, `DJANGO_SETTINGS_MODULE=tests.settings`, `PYTHONDONTWRITEBYTECODE=1`; the test module provisions synthetic ephemeral content keyrings. No live key/env file was read or printed. Selected tests have no database fixture. Pytest-django denies unrequested database access.

Reproduce from the audit checkout (adjust the interpreter location if needed):

```python
# Run with the project Python; this launches a clean test-settings subprocess.
import os
import subprocess

audit_backend = "/Users/reynantlntno/.codex/worktrees/cont-0-case-continuity/COMPASS/be"
audit_python = "/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python"
audit_env = {
    "PATH": os.environ["PATH"],
    "DJANGO_SETTINGS_MODULE": "tests.settings",
    "PYTHONDONTWRITEBYTECODE": "1",
}
audit_tests = [
    "test_exact_text_round_trip_and_frozen_compatibility",
    "test_invalid_text_rejected_without_exposing_input",
    "test_token_cannot_be_transplanted",
    "test_damaged_tokens_fail_closed",
    "test_exact_envelope_and_payload_schema",
    "test_unbounded_failure_reason_rejected",
    "test_required_keyring_startup_fails_safely",
    "test_reuse_of_any_other_key_rejected",
    "test_settings_preserve_order_and_file_keyring",
]
subprocess.run(
    [audit_python, "-m", "pytest", "-q",
     *["tests/test_counseling_shared_summary_encryption.py::" + name
       for name in audit_tests],
     "tests/test_routine_crypto_compatibility.py",
     "tests/test_canonical_baseline.py::"
     "test_registered_migrations_preserve_immutable_schema_only_baselines"],
    cwd=audit_backend, env=audit_env, check=True,
)
```

Result: **55 passed in 0.78s**, exit 0. This verifies current Summary codec roundtrip/frozen-format compatibility, invalid input/schema/binding rejection, safe errors, startup required/independent/ordered/file keyrings, Routine codec compatibility and immutable canonical migration registry. It does **not** execute author/Student/Context database authorization or a future binding conversion.

## Executed database-free graph and OpenAPI checks

Run the following in the same restricted `tests.settings` subprocess above. Database connection attempts are deliberately forbidden, including accidental management-command access:

```python
import django
from django.db.backends.base.base import BaseDatabaseWrapper

def refuse(*args, **kwargs):
    raise RuntimeError("CONT-0 forbids database connections")

BaseDatabaseWrapper.ensure_connection = refuse
django.setup()

from django.apps import apps
from django.core.management import call_command
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState

loader = MigrationLoader(None, ignore_no_migrations=True)
labels = {c.label for c in apps.get_app_configs()
          if c.name.startswith("compass.")}
leaves = [n for n in loader.graph.leaf_nodes() if n[0] in labels]
assert len(leaves) == len({n[0] for n in leaves})
changes = MigrationAutodetector(
    loader.project_state(), ProjectState.from_apps(apps),
    NonInteractiveMigrationQuestioner(),
).changes(graph=loader.graph)
assert not changes
call_command("export_openapi", check=True)
```

Result: **28 COMPASS leaves**, one per model-owning app; model state matches graph; **OpenAPI contract current**, exit 0. No `migrate`, database creation, schema application or model/contract rewrite ran. Future rename migrations do not exist yet, so their PostgreSQL/fresh-install/upgrade/test-database behavior is explicitly unverified.

## Documentation and naming checks

The inventory was generated from **tracked files at the exact baseline**, including hidden `.github` and `be/.env.example`, not ignored/untracked/generated content. Search used case-insensitive `shared[_-]?summar`, compact class names, spaced terminology, Student route `/portal/counseling/summaries` and the existing ciphertext constraint. Only matched identifiers and line numbers were extracted, not adjacent values or confidential text.

Result: [rename-inventory.csv](rename-inventory.csv) covers **127 files / 490 distinct file-token pairs**: 76 transform, 2 remove Context Summary surface, 1 preserve immutable migration, 18 annotate superseded decisions, 29 preserve historical artifacts, 1 preserve frozen oracle. Generated Orval output is not tracked; its generation/consumer changes are a required derived surface, not falsely inventoried baseline files. The CSV is a review inventory and canonical-name proposal, **not a replacement script**. Special cases (Context removal, immutable Audit, common UI helper `counseling-shared.tsx`) need semantic handling.

Final checks performed:

- All relative Markdown file targets in the package exist.
- Every inventoried token/line matches its baseline file; all matched baseline files have a disposition.
- AST checks establish Context Summary selection has exactly Student + publication filter and explicit decryption, without an author predicate.
- AST checks verify all three actual Context defaults (24/24/7); committed OpenAPI contains the inspected author/self/Context Summary operations.
- Initial staged whitespace check flagged CSV CRLF line endings. Normalized the inventory to LF; final documentation-only changed-path guard and staged `git diff --check` pass. No tracked runtime/config/migration/test/contract file changed.
- Git local/remote head, PR target/state and final cleanliness verified at publication; final commit SHA is reported by the PR/agent, not embedded recursively in the same commit.

## Inspected tests, not executed database evidence

| Existing file / representative tests | Material claim supported by source expectations |
| --- | --- |
| `test_counseling_context.py`: exact-provider/cancellation, Head exact provider, cross-College `world`, contextual Inventory/Support generic denial, own Encounter after expiry, direct-mode matching, minimized history, published-only summaries | Current window, relationship and cross-domain projections; specifically B reads A's published summary |
| `test_shared_summaries.py`: author/Student relationship, publication idempotence/immutability, drafts, private Routine exclusion | Ordinary summary audience and publication contract |
| `test_counseling_shared_summary_encryption.py`: denied-before-decrypt, Context filtering/corruption, storage/rotation cases using `world` | Existing database-backed storage/authorization expectations; excluded from the executed 55 |
| `test_routine_interviews.py`, `test_routine_encounter_linking.py` | Student Intake privacy, Evaluation author/finalization, matching and historical ownership |
| `test_appointment_management_scope.py`, `test_appointment_action_projection.py`, `test_appointments.py` | Counseling exact-provider, current Head provider-only, GSS non-Counseling scope and reassignment constraints |
| `test_guidance_followups.py` | Source Student/identity match, confidential GSS denial, currentness, version/reassignment/recovery boundaries |
| `test_assessment_records.py`, configuration/HTTP tests | Active Counselor/effective capabilities + record scope, independent encrypted result domain |
| `test_referrals.py`, `test_call_slips.py`, `test_inventory_counselor_review.py`, `test_student_support.py`, E-Counseling/media tests | Other source-domain controls referenced in access matrix |

No full backend/frontend suite, browser session, PostgreSQL-backed auth/concurrency suite, fresh database migration, synthetic reset, provider/media access, live environment probe, CI completion or UAT was executed for CONT-0. Relevant filenames and implementation predicates were checked; inspection is not a test pass. Broader testing is unnecessary for the documentation changes but remains mandatory for future security implementation.

## Confidence and open evidence needs

High confidence: baseline identity, current code/route/predicate/defaults, existing cross-author Summary query and test expectation, cryptographic envelope/rotation mechanics, immutable baseline integrity and current disk-state graph/OpenAPI agreement. Moderate confidence: absence of other disclosure paths in the inspected surfaces; this is bounded static review, not exhaustive penetration testing or proof about deployment/proxy caches. Proposed grant/state/concurrency/cutover/UI architecture requires actual implementation and synthetic PostgreSQL/browser validation before security confidence can be claimed.

Institutional policy/basis/retention/Acting delegation/disposability: **unverified**, not inferred. Live records/keyrings/current DB state: deliberately not inspected. No secrets/confidential Student content were reproduced in documentation. No runtime change, deployment, SSH, database connection/reset/migration, real-data access, outbound message or merge occurred.
