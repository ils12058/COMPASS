# COMPASS Staging Dataset v1 (`seed_staging_dataset`)

`seed_staging_dataset` builds, verifies and documents **COMPASS Staging Dataset v1**: a
deterministic, synthetic, UAT-ready world for the reset-only canonical baseline (CANON-1C). It
contains a fictional Guidance and Counseling Office, 14 staff and negative-test accounts, and 102
Students designed for stakeholder testing. The decision record is
[ADR-116](decisions/ADR-116-canonical-baseline-and-staging-dataset-v1.md).

Dataset v1 is a **new lineage**. It is not the retired Demo Dataset v1/v2 (`seed_demo_staging`,
[historical notes](historical/staging-demo-seeding.md)) and never upgrades it: a database that
contains `DEMO-2026-…` accounts is refused. The dataset version (1) is independent of the COMPASS
application and API versions.

> **Synthetic data only.** Every name, `STG-S-…`/`STG-E-…` identifier, address, receipt number
> (`STG-OR-…`), narrative and policy text is fictional. Never load institutional records into the
> dataset, and never use it as production data.

The command is operator tooling. There is no API, page, middleware or model flag for it, and no
production code path knows whether a record was seeded. It never runs at application startup.

## Independent 40-person allocation

The additive participant expansion appends `it_admin_3` (`STG-E-0014`, canonical `IT_ADMIN`),
`ar_25` and `ar_26` (`STG-S-0125`/`STG-S-0126`, canonical `STUDENT`, `GRADUATED`). The Alumni
fixtures use historical Inventory/Exit Interview records and draft/submitted Graduate Tracers;
their scenarios cover Tracer completion and a new graduate Good Moral request. Existing 113
identities, 91 scenario definitions and all 65 background Students are retained. There are now
116 accounts and 94 scenarios (91 executable, three pending); no migration is needed.

The allocation (`UAT_40_ALLOCATION` in `compass/staging_seed/manifest.py`) assigns distinct keys
to 1 Head, 3 Counselors, 2 GSS, 25 current Students, five graduated Alumni, 3 ITSO personnel and
1 DPO. The 25 current Students follow the finalized College distribution
(`UAT_40_STUDENT_QUOTA`): 3 each from CCMS, CAS, CBPA, COENG, COED, CFAST and CANR, and 2 each
from COTT and Entienza. The manifest refuses an allocation whose counts, College affiliations,
lifecycles or credential plans disagree with it.

To reach that distribution, seven background Students are promoted to UAT-ready
(`PROMOTED_BACKGROUND` in `students.py`): `bg_47` (COENG), `bg_54` and `bg_55` (CFAST), `bg_56`
(CANR), `bg_58` and `bg_59` (COTT) and `bg_60` (Entienza). Promotion changes only catalog text and
assignment suitability, which seeding never reads; each account keeps its identity, College
affiliation, enrollment, Inventory and existing records. Their eight scenarios (STU-APT-07..10,
STU-GM-08/09, STU-MSG-03, STU-FB-02) start from those existing records, so an already-seeded
database needs no write. Seven over-represented Main Campus Students (`first_year`, `second_year`,
`ar_06`, `ar_11`, `ar_17`, `ar_18`, `ar_21`) stay UAT-ready reserves outside the 40. There are 116
accounts and 102 scenarios (99 executable, three pending).

Shared catalog and staff/Student scenario dependencies still need scheduling. Reserve participant
accounts remain listed in the full Assignment Template; `COMPASS-UAT-40-ASSIGNMENTS.csv` lists
exactly the 40 allocated accounts.

This repository expansion does **not** apply itself to live staging. After a separate owner
authorization, an incremental seed on the deployed canonical revision creates only missing
accounts and fixtures; it preserves completed UAT work and existing credentials. Keep the same
email domain/onboarding settings. Use `verify --allow-uat-changes` and `report --allow-uat-changes`
for an active dataset. Obtain approval for exact participant keys before the separate
`issue-credentials --account KEY` step; never use an unrestricted issuance command for this cohort.
The Selection Guide prints the exact 40 `--account` arguments.

## Modes

| Mode | Writes? | Purpose |
| --- | --- | --- |
| `seed` (default) | Yes | Create what is missing, reuse what exists, refuse conflicts. Never sets a password. |
| `verify [--allow-uat-changes]` | No (read-only transaction) | Verify schema, configuration, accounts, routing, scenario initial states, workflow integrity, privacy and side effects. |
| `report --output-dir DIR [--allow-uat-changes]` | No (database) | Verify, then generate the seven UAT documents into `DIR`. Refuses to write if verification fails. |
| `issue-credentials --output FILE [--account KEY …] [--reissue --confirm-reissue]` | Yes | Give participant accounts distinct credentials and write one protected handoff file. |

## Safety gates

Every mode runs only when **both** hold, checked before any configuration is read or any query
runs:

| `APP_ENV` | `STAGING_SEED_ENABLED` | Result |
| --- | --- | --- |
| `local-staging` | `true` (default) | allowed |
| `live-staging` | `true` (explicit, one-off) | allowed |
| `live-staging` | unset / `false` (default) | refused |
| anything else (`production`, a future mode, empty) | any value | refused |

The allowlist is explicit; "not production" is never treated as permission. Write modes take a
PostgreSQL advisory lock, so a second concurrent `seed` or `issue-credentials` run is refused. The
long-running runtime must never set `STAGING_SEED_ENABLED`; the runtime-secret check rejects it.

The canonical schema itself is guarded: `migrate` and `manage.py check --database default` refuse a
database that records any pre-canonical COMPASS migration (`compass.E001`).

## Configuration

Read only while the command runs. Each accepts the repository's `NAME_FILE` convention.

| Variable | Required | Purpose |
| --- | --- | --- |
| `STAGING_SEED_ENABLED` | live-staging | One-off operator opt-in. Defaults to `true` in local-staging, `false` in live-staging. |
| `STAGING_SEED_EMAIL_DOMAIN` | live-staging | Domain for dataset addresses (`stg-<key>@<domain>`). Defaults to the reserved `compass-staging.test` in local-staging, captured only by Mailpit. |
| `STAGING_SEED_ONBOARDING_EMAIL` | optional | Full operator-controlled address for the onboarding Student's one-time code. |

There is no password variable. Keep the email settings stable: accounts are matched by `STG-…`
identifier and email, and a mismatch fails closed instead of creating a second population.

The retired `DEMO_SEEDING_ENABLED`, `DEMO_ACCOUNT_PASSWORD`, `DEMO_EMAIL_DOMAIN` and
`DEMO_ONBOARDING_EMAIL` variables are not read by anything.

## Running it

### Local staging (disposable database)

```sh
cd be
podman compose --profile local run --rm web python manage.py migrate --noinput
podman compose --profile local run --rm web python manage.py sync_identity_policy
podman compose --profile local run --rm web python manage.py sync_canonical_services
podman compose --profile local run --rm web python manage.py sync_institutional_forms
podman compose --profile local run --rm web python manage.py sync_organization_catalog
podman compose --profile local run --rm web python manage.py seed_staging_dataset seed
podman compose --profile local run --rm web python manage.py seed_staging_dataset verify
```

`seed` also calls the four synchronizers itself, so the explicit calls only make the order visible.
The canonical baseline installs only into an empty database; a local database created from the
old migration history must be rebuilt, not migrated.

### Live staging (separate operator authorization only)

The clean rebuild completed on 2026-10-17. Routine [staging deployment](staging-deployment.md)
never runs this command; do not reseed or reissue credentials during UAT without a separate owner
decision. For an authorized operator run, verify the canonical release
by its exact `build_id` and ensure the
cutover checks in `outputs/canon-1c/CANON-1C-Cutover-Dependencies.md` are recorded. Use the release
image already on the Droplet and a one-off container:

```bash
seed_staging_live() {
  local DEPLOY_PATH=/opt/compass DEPLOY_SHA COMPASS_IMAGE VERIFIED_BUILD_SHA DOMAIN
  . "$DEPLOY_PATH/.deploy.env" || return
  export COMPASS_IMAGE COMPASS_SECRETS_DIR COMPOSE_FILE COMPOSE_PROFILES
  DEPLOY_SHA="$(docker image inspect "$COMPASS_IMAGE" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
  [[ "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]] || return 1
  read -r -p 'Verified public /api/v1/meta build_id: ' VERIFIED_BUILD_SHA
  [[ "$DEPLOY_SHA" == "$VERIFIED_BUILD_SHA" ]] || return 1
  cd "$DEPLOY_PATH/releases/$DEPLOY_SHA" || return
  read -r -p 'Dataset email domain (operator-controlled): ' DOMAIN
  [[ -n "$DOMAIN" ]] || return 1
  docker compose --project-name compass run --rm --no-deps --pull never -T \
    -e STAGING_SEED_ENABLED=true -e STAGING_SEED_EMAIL_DOMAIN="$DOMAIN" \
    web python manage.py seed_staging_dataset "$@"
}
seed_staging_live seed
seed_staging_live verify
```

## Participant credentials

Seeding never sets a password. Participant accounts are provisioned the way Account Management
provisions accounts: active, email verified (dataset mailboxes are operator-controlled), and **no
usable password**. They cannot sign in until the operator issues credentials:

```bash
# First source/export the verified selector as above; COMPOSE_FILE preserves both reset-era
# and routine-deployment resource selection. Mount a protected operator directory.
install -d -m 700 /root/uat-handoff
docker compose --project-name compass run --rm --no-deps --pull never -T \
  -v /root/uat-handoff:/handoff -e STAGING_SEED_ENABLED=true -e STAGING_SEED_EMAIL_DOMAIN="$DOMAIN" \
  web python manage.py seed_staging_dataset issue-credentials --output /handoff/uat-credentials.csv
```

- Each UAT-ready credential account gets its own random password from `secrets`, validated by the
  normal COMPASS password policy (15+ characters). Only Django's hash is stored.
- The plaintext appears once, in a **new** file created with mode `0600`. The command refuses an
  existing file, a path inside the source tree, a disabled account, and the onboarding account.
  It never prints, logs or audits a password; the audit trail records only
  `auth.password.initial_set` with method `staging_operator_issuance`.
- Accounts that already have a usable password (issued earlier, or changed by the evaluator) are
  skipped. A normal `seed` rerun never touches credentials.
- Restricted negative-test accounts (`unassigned_counselor`, `officer_no_designation`) receive a
  credential only when named: `--account unassigned_counselor`.
- **Reissue** replaces a credential only for named accounts and needs both flags:
  `--account ar_01 --reissue --confirm-reissue`. It revokes the account's sessions, trusted
  browsers and pending email challenges, and is audited as `auth.password.reset`.
- Deliver each line privately to its assigned evaluator, then delete the handoff file. If the
  command fails, nothing was committed and any partial file is removed.

MFA, email verification and authorization policy are unchanged for UAT: staff roles listed in
`AUTH_MFA_REQUIRED_ROLE_CODES` set up an authenticator on first sign-in as usual. Evaluators should
change their temporary password from Account > Security after first sign-in.

The onboarding Student (`onboarding`) demonstrates first-time Password Access instead: it has no
password and an unverified email, so it needs `STAGING_SEED_ONBOARDING_EMAIL` to reach a mailbox.

## Verification and UAT documentation

```sh
python manage.py seed_staging_dataset verify
python manage.py seed_staging_dataset report --output-dir ../outputs/canon-1c/uat
```

`verify` runs in a PostgreSQL `READ ONLY` transaction. It fails visibly when the database and the
manifest disagree. Sections:

| Section | Proves |
| --- | --- |
| Schema readiness | All migrations applied, no model drift, no pre-canonical history, no retired ledger tables or tasks |
| Canonical configuration | Capabilities and grants, the full Organization catalog, active form revisions, the Counseling Service, current Academic Year |
| Account readiness | Every manifest account: identity, email, role, designations, lifecycle, College affiliation, active and authentication state; no stray `STG-` or `DEMO-` accounts |
| Organization routing | Counselor responsibility for nine Colleges and staff supervision exactly as declared |
| Scenario initial states | Every executable scenario's documented starting state (named predicates in the manifest) |
| Workflow integrity | Appointment providers follow routing, one Inventory per year, notifications for published summaries, LIVE Call Slips and issued certificates, Work Queue projections |
| Privacy and security | Every `*_ciphertext` column holds Fernet ciphertext only, Students hold only self capabilities, staff/IT/officer scopes, DPO scope equals the DPO designation, disabled accounts have no live session |
| External side effects | No email or push intents, no Daily-provisioned or local E-Counseling rooms for dataset accounts |

During active UAT, `--allow-uat-changes` reports states that evaluators changed (and the email
their actions legitimately send) as warnings; structural failures still fail.

`report` generates, from the manifest plus a passing verification:

| File | Contents |
| --- | --- |
| `STAGING-DATASET-v1-ACCOUNT-CATALOG.md` | Every account by role and category |
| `staging-accounts.csv` | The same, one row per account, for spreadsheet filtering |
| `UAT-ACCOUNT-SELECTION-GUIDE.md` | Recommended accounts per stakeholder role, conflicts and rules |
| `UAT-SCENARIO-MATRIX.md` | Every scenario with route, initial state, action, expected result and readiness |
| `UAT-ACCOUNT-ASSIGNMENT-TEMPLATE.csv` | Blank assignment worksheet for every UAT-ready account, reserves included (no evaluator identities) |
| `COMPASS-UAT-40-ASSIGNMENTS.csv` | The exact 40-person allocation: reference, stakeholder, College / unit, key, ID, login email, role and scenarios; evaluator columns blank |
| `STAGING-DATASET-v1-SUMMARY.md` | Counts and distributions read from the database |

Documents never contain passwords, MFA secrets, tokens, confidential answers or counseling
content; generation scans for credential material and refuses to write. Change the population or
a scenario in `compass/staging_seed/` and regenerate; never edit the generated files by hand.

## Reruns and what the command never does

A normal rerun reports reused state and changes nothing an evaluator did:

- existing accounts are never modified: credentials, verification, onboarding, disabled state;
- every scenario unit is matched by the record it creates (an Appointment, referral, request,
  opportunity, …) **in any status** and skipped as a whole, so a cancelled booking stays cancelled
  and a consumed pending task is not restored;
- publications, privacy records and feedback are matched by stable natural keys;
- existing Availability and Organization relationships are reused, never replaced; a conflicting
  relationship stops the run before business records are written.

The command never truncates, flushes, deletes or resets data and has no reset option. A pristine
dataset is a separately authorized database rebuild.

## Timeline

The dataset spans Academic Years 2024-2025, 2025-2026 and current 2026-2027 in Asia/Manila. The
**preparation date** anchors recent activity: past work on business days before it, upcoming work
after it. It defaults to the institutional date and may be set with
`seed --preparation-date YYYY-MM-DD` when it is within 2026-09-21 to 2027-04-30, not after the
institutional date, and at most one day before it (otherwise "upcoming" items would already be
over). Seed 1–3 business days before UAT: upcoming Appointments fall 2–10 business days later.

Historical years are entered through the normal current-year services: each historical Academic
Year is made current inside one transaction, its records are entered, and 2026-2027 is restored
before commit, so no other session observes a historical year as current.

## Population

| Group | Count | Purpose |
| --- | ---: | --- |
| Rich scenario Students | 11 | Multi-domain stories (counseling, referrals, Call Slips, certificates, Exit Interviews, Graduate Tracer, onboarding, a former Student) |
| Action-ready Students (`ar_01`…`ar_26`) | 26 | One evaluator-owned pending action each |
| Background Students (`bg_01`…`bg_65`) | 65 | Quiet population across all six campuses for rosters, filters and reports; `bg_65` is disabled; seven are promoted to UAT-ready for the College distribution |
| Staff (participants) | 11 | IT Administrator ×3, Head Guidance Counselor, Counselors ×3 (separate caseloads), Guidance Services Staff ×2, DPO ×2 |
| Staff (restricted) | 3 | Disabled former staff, a Counselor without responsibility, an undesignated Institutional Officer |

Counselor routing: `counselor_a` — Main CCMS, CAS, COENG; `counselor_b` — Main CBPA, Abaño COED;
`counselor_c` — Mercedes CFAST, Labo CANR, Jose Panganiban COTT, Entienza. The Graduate School has
no responsibility and no seeded Students. Good Moral preparation and issuance are office-wide by
design.

To use a smaller cohort, mark accounts as background or remove rows from `students.py` and
regenerate; every scenario still references a valid account (the manifest validates this at
import) and no record is chosen at random.

## Seed-only writes and side effects

Everything goes through domain services, with these documented exceptions:

- **Accounts** use `User.objects.create_user` (no password) plus a SYSTEM `account.created` event,
  like `create_it_admin`, because Account Management services need an administrator session with
  recent MFA. Designations, lifecycle changes and disabling mirror Account Management invariants.
- **Historical timestamps.** Back-entered records have allowlisted business timestamps moved onto
  the dataset timeline; status, relationships and content are never touched. Audit events are
  never rewritten and keep the real run time and one run ID.
- **Email intents.** Services that notify create an in-app Notification and an email delivery
  intent. Seeding keeps the Notification and deletes only the never-attempted intent it caused, so
  a bulk seed never emails anyone. Live UAT actions afterwards send normal staging email.
- Back-entered Call Slips use the quiet HISTORICAL issuance mode; Call Slips issued for upcoming
  interviews use LIVE issuance and create the Student's in-app notification.
- A Guidance Message thread is opened through the normal Counselor service; messages create only
  a content-free realtime hint.

Seeding never calls Daily, PSGC, Turnstile, object storage, push or the PDF renderer, creates no
E-Counseling room, recording or transcript, and registers no callback. Documents render on demand.

Actions that intentionally use real staging integrations during UAT (and need an operator-approved
plan): booking, cancelling or rescheduling Appointments, issuing Call Slips, publishing Shared
Summaries, reopening Inventories or Exit Interviews, issuing certificates and Password Access all
send email to the dataset addresses; starting or joining E-Counseling provisions a Daily room.

## Encryption keyrings

All are operator-supplied and probed before any write; none is generated:
`ACCOUNT_PROFILE_…`, `FEEDBACK_…`, `ROUTINE_INTERVIEW_…`, `COUNSELING_SHARED_SUMMARY_…`,
`REFERRAL_…`, `EXIT_INTERVIEW_…`, `INVENTORY_…`, `GRADUATE_TRACER_…` and
`GUIDANCE_MESSAGE_ENCRYPTION_KEYS`.

## Domain coverage

| Class | Domains |
| --- | --- |
| SYNC | Identity policy; Organization catalog; Institutional Forms; canonical Counseling Service |
| SEED (domain services) | Academic Years; accounts, designations, profiles; responsibility, supervision, affiliation; ONLINE Counseling delivery; office and provider Availability; Inventories; Appointments; Encounters; Shared Summaries; Routine Interviews; Referrals; Call Slips; Good Moral; Exit Interviews and opportunities; Graduate Tracer; Guidance Messages; Customer Feedback; CSM; Announcements; Resources; Privacy Notices |
| DERIVED | Overview; Work Queue; Student Support; reports; My Activity; Notifications; documents |
| RUNTIME-ONLY | Sessions, MFA, challenges, email-change requests; Daily rooms, tokens, recordings, transcripts, webhooks; PSGC cache; Platform Operations state; email/push deliveries; worker state |
| INTENTIONALLY EMPTY | PSGC geography (answered "not specified"); Resource files; E-Counseling rooms and media; Inventory and Exit Interview reopen events |
| PENDING FEATURES | Appointment Reminders, Service Catalog Expansion, Shared Guidance Follow-Up Management: scenarios are `PENDING_IMPLEMENTATION` until those features merge |
