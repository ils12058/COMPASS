# COMPASS Staging Dataset v1 (`seed_staging_dataset`)

`seed_staging_dataset` builds, verifies and documents **COMPASS Staging Dataset v1**: a
deterministic, synthetic, UAT-ready world for the reset-only release baseline (ADR-117). It
contains a fictional Guidance and Counseling Office, 19 Faculty, staff and negative-test accounts, and 103
Students designed for stakeholder testing. The decision record is
[ADR-116](decisions/ADR-116-canonical-baseline-and-staging-dataset-v1.md) for the dataset decision
and [ADR-117](decisions/ADR-117-release-baseline.md) for the current reset-only migration graph.

Dataset v1 is a **new lineage**. It is not the retired Demo Dataset v1/v2 (`seed_demo_staging`,
whose historical notes remain in git history) and never upgrades it: a database that
contains `DEMO-2026-…` accounts is refused. The dataset version (1) is independent of the COMPASS
application and API versions.

> **Synthetic data only.** Every name, `STG-S-…`/`STG-E-…`/`STG-F-…` identifier, address, receipt number
> (`STG-OR-…`), narrative and policy text is fictional. Never load institutional records into the
> dataset, and never use it as production data.

The command is operator tooling. There is no API, page, middleware or model flag for it, and no
production code path knows whether a record was seeded. It never runs at application startup.

## Independent 50-person allocation

Phase E E5 retains all 116 earlier identities and every earlier record/scenario definition.
It appends five Faculty (`STG-F-0001`…`STG-F-0005`) and one current COTT Student, `ar_27`
(`STG-S-0127`). The dataset now has **122 accounts and 113 scenarios (110 executable, three
pending)**. The earlier runbook's 102-scenario total was stale: the E5 base has 101 scenarios.
No model or migration changes are needed.

`UAT_50_ALLOCATION` in `compass/staging_seed/manifest.py` assigns 50 distinct participants:

| Category | Count | Keys |
| --- | ---: | --- |
| Head Guidance Counselor | 1 | `head_guidance` |
| Guidance Counselor | 3 | `counselor_a`, `counselor_b`, `counselor_c` |
| Guidance Office Assistant | 2 | `goa_a`, `goa_b` |
| Current Student | 30 | See the College allocation below |
| Faculty | 5 | `faculty_ccms`, `faculty_cas`, `faculty_cbpa`, `faculty_coed`, `faculty_coeng` |
| Alumni | 5 | `recent_graduate`, `alumni`, `ar_13`, `ar_25`, `ar_26` |
| ITSO Personnel | 3 | `it_admin`, `it_admin_2`, `it_admin_3` |
| Data Protection Officer | 1 | `dpo` |

The 30 current Students satisfy `UAT_50_STUDENT_QUOTA`:

| College / academic unit | Count | Keys |
| --- | ---: | --- |
| CCMS | 4 | `ar_01`, `ar_05`, `ar_14`, `ar_11` |
| CAS | 4 | `ar_03`, `ar_09`, `ar_12`, `ar_21` |
| CBPA | 4 | `ar_02`, `ar_10`, `ar_22`, `ar_06` |
| COENG | 3 | `ar_07`, `ar_19`, `bg_47` |
| COED | 3 | `ar_04`, `ar_15`, `ar_20` |
| CFAST | 3 | `ar_23`, `bg_54`, `bg_55` |
| CANR | 3 | `ar_08`, `ar_16`, `bg_56` |
| COTT | 3 | `bg_58`, `bg_59`, `ar_27` |
| Entienza | 3 | `ar_24`, `bg_60`, `bg_61` |

The three former reserves `ar_11`, `ar_21` and `ar_06` become allocated. `bg_61` is promoted
through `PROMOTED_BACKGROUND`, changing only label, summary, limitations and suitability.
The eight promoted background Students keep their identities, placement, enrollment, Inventory
and existing records. Reserves `first_year`, `second_year`, `ar_17`, `ar_18` and the other
UAT-ready accounts outside the allocation remain listed as reserves in the Selection Guide and
full Assignment Template. `COMPASS-UAT-50-ASSIGNMENTS.csv` contains exactly the 50 allocated
accounts; the Selection Guide prints exactly their 50 `--account` arguments.

### Faculty coverage and activation

Faculty accounts are active, email verified, canonical `FACULTY`, and `CREDENTIAL` planned;
seeding never sets passwords. Home Colleges are assigned through Account Management's
`validate_faculty_college` and `write_faculty_affiliation` with a synthetic assignment basis and
SYSTEM audit context, under the catalog gate and locked target account. Existing conflicting
Faculty affiliations fail preflight rather than being reassigned.

| Faculty key / institutional ID | College | Fresh-submit background Student | Received background Student | Scenarios |
| --- | --- | --- | --- | --- |
| `faculty_ccms` / `STG-F-0001` | CCMS | `bg_01` | `bg_05` | FAC-REF-01, FAC-REF-02 |
| `faculty_cas` / `STG-F-0002` | CAS | `bg_02` | `bg_06` | FAC-REF-03, FAC-REF-04 |
| `faculty_cbpa` / `STG-F-0003` | CBPA | `bg_03` | `bg_07` | FAC-REF-05, FAC-REF-06 |
| `faculty_coed` / `STG-F-0004` | COED | `bg_04` | `bg_08` | FAC-REF-07, FAC-REF-08 |
| `faculty_coeng` / `STG-F-0005` | COENG | `bg_48` | `bg_49` | FAC-REF-09, FAC-REF-10 |

Each pair uses different enrolled background Students of the Faculty's home College, never a
participant Student. Fresh submission has no preceding Guidance Office dependency. The even
scenario opens an unread receipt notice and an own submission already `RECEIVED_BY_GCO`.
No existing Guidance Office scenario depends on these new Referrals; their original Students
and initial states remain intact. `ar_27` owns STU-APT-11; `bg_61` owns STU-GM-10.

Digital Referrals, receipt/closure notices and tracking are **active** through the product's
code-owned provisional providers (`provisional_activation`), whose fixed audit decisions say
`PROVISIONAL`, never institutionally `APPROVED`. The seeder calls the real lookup/submission
and administrative policy services, `confirm_student`, `submit_referral`, and the GCO
`administration.transition` acknowledgment service. It acquires the exclusive catalog gate at
entry before account locks, avoiding a shared-to-exclusive gate upgrade during acknowledgment.
Bounded service sessions carry no MFA assertion and are revoked through the authentication
service immediately after the seed unit. No participant credentials are issued or exported.
The notification service creates the received notice; only its unsent email intent is removed.

This package proves a fresh local dataset for the separately authorized Phase E reset. It never
applies itself to live staging. Credential issuance and participant registers remain separate
owner operations; no real participant handoff is read or edited.

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
podman compose --profile local run --rm web python manage.py initialize_organization_catalog --seed
podman compose --profile local run --rm web python manage.py seed_staging_dataset seed
podman compose --profile local run --rm web python manage.py seed_staging_dataset verify
```

`seed` syncs only identity policy, Institutional Forms and the canonical Counseling Service.
Organization must first be explicitly initialized (`--seed` only on a fresh empty catalog) or,
for an already compatible release database, deliberately adopted (`--adopt`). Old migration
history is incompatible and requires the separately approved Phase E reset. Repeated checks
use `initialize_organization_catalog --check`. The seeder never reconciles catalog names, status or
Program policy; missing or retired fixture identities fail preflight rather than being repaired.
ORG-1 deployment/adoption remains separately approval-dependent; see
[deployment and recovery](../../docs/org-1/deployment-and-recovery.md).
The canonical baseline installs only into an empty database; a database with pre-canonical migration
history requires its separately reviewed clean-rebuild procedure, not an ORG-1 in-place conversion.

### Live staging (separate operator authorization only)

The first live seed onto the release baseline now runs **inside the separately authorized
[Phase E reset](staging-deployment.md#phase-e-reset)**, followed by strict verification. Its email
domain is chosen from the read-only preflight's existing synthetic domains; optional onboarding
email is a protected staging environment secret. The reset never issues credentials.

Routine deployment never seeds or verifies pristine UAT scenarios. Later incremental seeds remain
separate operator actions using the deployed release image and the same domain/onboarding settings.
They preserve completed UAT work and existing credentials; use `verify --allow-uat-changes` for an
active dataset. Record exact public `build_id`, compatible migration history and deployment checks
before using the following existing host command. Never run it on old-history staging:

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

Neither the Phase E reset nor seeding sets a password. After the Evaluation freeze and a separate
owner go-ahead, issue credentials **on the host only**, for exactly the allocated account keys in the
deployed manifest. Copy its Selection Guide's restricted command; never issue to the whole catalog.
Participant accounts are provisioned the way Account Management
provisions accounts: active, email verified (dataset mailboxes are operator-controlled), and **no
usable password**. They cannot sign in until the operator issues credentials:

```bash
# First source/export the verified selector as above; COMPOSE_FILE preserves both reset-era
# and routine-deployment resource selection. Mount a protected operator directory.
install -d -m 700 /root/uat-handoff
docker compose --project-name compass run --rm --no-deps --pull never -T \
  -v /root/uat-handoff:/handoff -e STAGING_SEED_ENABLED=true -e STAGING_SEED_EMAIL_DOMAIN="$DOMAIN" \
  web python manage.py seed_staging_dataset issue-credentials --account "$ACCOUNT_KEY" \
    --output /handoff/uat-credentials.csv
```

Repeat `--account` for every authorized allocated key using the deployed Selection Guide. The
example variable represents an explicitly selected key; there is no unrestricted automation or CI
handoff. Later incremental seeding and named credential reissuance stay separately authorized.

- Each selected credential account gets its own random password from `secrets`, validated by the
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

The seeded IT Administrators must enroll an authenticator at first sign-in and save their recovery
codes before returning to sign in. MFA is opt-in for every other role. The seeder does not provision
authenticator secrets or recovery codes; email verification and authorization still apply.
Evaluators should change their temporary password from Account > Security after first sign-in.

The onboarding Student (`onboarding`) demonstrates first-time Password Access instead: it has no
password and an unverified email, so it needs `STAGING_SEED_ONBOARDING_EMAIL` to reach a mailbox.

## Verification and UAT documentation

```sh
python manage.py seed_staging_dataset verify
python manage.py seed_staging_dataset report --output-dir /tmp/compass-staging-uat
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

`report` generates fresh documents in the selected output directory, from the manifest plus a
passing verification. The filenames below describe generated reports; historical copies are
available in git history:

| File | Contents |
| --- | --- |
| `STAGING-DATASET-v1-ACCOUNT-CATALOG.md` | Every account by role and category |
| `staging-accounts.csv` | The same, one row per account, for spreadsheet filtering |
| `UAT-ACCOUNT-SELECTION-GUIDE.md` | Recommended accounts per stakeholder role, conflicts and rules |
| `UAT-SCENARIO-MATRIX.md` | Every scenario with route, initial state, action, expected result and readiness |
| `UAT-ACCOUNT-ASSIGNMENT-TEMPLATE.csv` | Blank assignment worksheet for every UAT-ready account, reserves included (no evaluator identities) |
| `COMPASS-UAT-50-ASSIGNMENTS.csv` | The exact 50-person allocation: reference, stakeholder, College / unit, key, ID, login email, role and scenarios; evaluator columns blank |
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
| Action-ready Students (`ar_01`…`ar_27`) | 27 | One evaluator-owned pending action each |
| Background Students (`bg_01`…`bg_65`) | 65 | Quiet population across all six campuses for rosters, filters and reports; `bg_65` is disabled; eight are promoted to UAT-ready for the College distribution |
| Faculty (participants) | 5 | One each for CCMS, CAS, CBPA, COED and COENG; digital Referrals and received notices |
| Staff (participants) | 11 | IT Administrator ×3, Head Guidance Counselor, Counselors ×3 (separate caseloads), Guidance Office Assistant ×2, DPO ×2 |
| Staff (restricted) | 3 | Disabled former staff, a Counselor without responsibility, an undesignated Institutional Officer |

Counselor routing: `counselor_a` — Main CCMS, CAS, COENG; `counselor_b` — Main CBPA, Abaño COED;
`counselor_c` — Mercedes CFAST, Labo CANR, Jose Panganiban COTT, Entienza. The Graduate School has
no responsibility and no seeded Students. Good Moral preparation and issuance are office-wide by
design.

For a smaller evaluation session, schedule a subset of the allocated accounts and keep the
others as reserves. Preserve every dataset identity and record. Every scenario references a
valid account (the manifest validates this at import); no record is chosen at random.

## Seed-only writes and side effects

Everything goes through domain services, with these documented exceptions:

- **Accounts** use `User.objects.create_user` (no password) plus a SYSTEM `account.created` event,
  like `create_it_admin`, because Account Management services need an administrator session with
  recent MFA. Designations, lifecycle changes and disabling mirror Account Management invariants.
- **Faculty service sessions.** Bounded, non-MFA sessions use the authentication service and
  are revoked before the seed unit completes. They never enable participant sign-in. Faculty
  affiliation and policy activation follow the services described above.
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
`ACCOUNT_PROFILE_…`, `FEEDBACK_…`, `ROUTINE_INTERVIEW_…`, `STUDENT_SESSION_SUMMARY_…`,
`REFERRAL_…`, `EXIT_INTERVIEW_…`, `INVENTORY_…`, `GRADUATE_TRACER_…` and
`GUIDANCE_MESSAGE_ENCRYPTION_KEYS`.

## Domain coverage

| Class | Domains |
| --- | --- |
| SYNC | Identity policy; Institutional Forms; canonical Counseling Service |
| CHECK (no catalog writes) | Prior Organization initialization/adoption and active fixture identities |
| SEED (domain services) | Academic Years; accounts, designations, profiles; responsibility, supervision, affiliation; ONLINE Counseling delivery; office and provider Availability; Inventories; Appointments; Encounters; Student Session Summaries; Routine Interviews; Referrals; Call Slips; Good Moral; Exit Interviews and opportunities; Graduate Tracer; Guidance Messages; Customer Feedback; CSM; Announcements; Resources; Privacy Notices |
| DERIVED | Overview; Work Queue; Student Support; reports; My Activity; Notifications; documents |
| RUNTIME-ONLY | Sessions, MFA, challenges, email-change requests; Daily rooms, tokens, recordings, transcripts, webhooks; PSGC cache; Platform Operations state; email/push deliveries; worker state |
| INTENTIONALLY EMPTY | PSGC geography (answered "not specified"); Resource files; E-Counseling rooms and media; Inventory and Exit Interview reopen events |
| PENDING FEATURES | Appointment Reminders, Service Catalog Expansion, Shared Guidance Follow-Up Management: scenarios are `PENDING_IMPLEMENTATION` until those features merge |
