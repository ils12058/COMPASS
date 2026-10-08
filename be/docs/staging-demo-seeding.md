# Staging demo dataset (`seed_demo_staging`)

`seed_demo_staging` turns a clean, migrated **local-staging** or **live-staging** database into a
deterministic Dataset v2 demonstration world: a fictional Guidance and Counseling Office, its
staff, the original eleven rich Student personas, and 46 lightweight population Students whose
accounts, cohorts, forms, sessions, referrals, certificates, and notifications fit together.
Dataset content is refined by [ADR-095](decisions/ADR-095-staging-demo-dataset-v2-and-pre-deployment-validation-baseline.md);
[ADR-068](decisions/ADR-068-staging-demo-dataset-seeder.md) remains the historical architecture.

> **The dataset is synthetic and intended only for local and live staging demonstrations. It must
> never be used as production institutional data.** Every name, identifier (`DEMO-2026-…`),
> address, narrative, receipt number (`DEMO-OR-…`), and policy text is fictional. Privacy Notice
> content is explicitly labelled as staging demonstration material.

The command is operator tooling. There is no API, page, button, middleware, or model flag for it,
and no production code path knows whether a record was seeded.

## Safety gates

Seeding runs only when **both** conditions hold:

| `APP_ENV` | `DEMO_SEEDING_ENABLED` | Result |
| --- | --- | --- |
| `local-staging` | `true` (default) | allowed |
| `live-staging` | `true` (explicit) | allowed |
| `live-staging` | unset / `false` (default) | refused |
| anything else (for example `production`, a future mode) | any value | refused |

The command keeps its own explicit allowlist (`local-staging`, `live-staging`). It never reasons
"not production, therefore allowed", so a future environment mode stays blocked until someone
deliberately adds it. The environment check runs before any secret is read or any database work
starts. A second concurrent run is refused through a PostgreSQL advisory lock.

## Configuration

These values are read only while the command runs; application startup never depends on them.
Each also accepts the repository's `NAME_FILE` convention (for example
`DEMO_ACCOUNT_PASSWORD_FILE=/run/secrets/demo_account_password`); do not set both forms.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DEMO_SEEDING_ENABLED` | live-staging | Operator opt-in. Defaults to `true` in local-staging and `false` in live-staging. |
| `DEMO_ACCOUNT_PASSWORD` | always | Shared password for ready demo accounts. Validated with the normal COMPASS password policy against every persona. Never printed, logged, or stored anywhere except Django's password hash. |
| `DEMO_EMAIL_DOMAIN` | live-staging | Domain for demo addresses such as `demo-head@<domain>`. Defaults to the reserved `compass-demo.test` in local-staging, which only Mailpit captures. |
| `DEMO_ONBOARDING_EMAIL` | optional | Full address for the onboarding persona, when its one-time code must reach a specific mailbox. |

Keep `DEMO_EMAIL_DOMAIN` and `DEMO_ONBOARDING_EMAIL` stable: accounts are matched by their
`DEMO-2026-…` institutional ID and email, and a mismatch fails closed instead of creating a second
cast.

### Demo email addresses

Use a domain whose mailboxes the operator controls (for example a catch-all mailbox on a staging
subdomain). Seeding itself sends no email, but later **live** demonstrations do: booking an
Appointment, issuing a Call Slip, publishing a Shared Summary, or requesting a password send
normal COMPASS email to the demo addresses. Addresses that cannot receive mail make those
deliveries fail and appear in Platform Operations.

The onboarding persona must be able to receive the real email one-time code if first-time
onboarding is demonstrated on live staging. Set `DEMO_ONBOARDING_EMAIL` to an operator-controlled
mailbox when the demo domain has no real mailboxes. The seeder never invents plus-address aliases;
use one only if you configure it explicitly and your provider supports it.

## Running it

Rebuild the backend image first so it contains the command.

Local staging (Mailpit captures all mail):

```sh
cd /Users/reynantlntno/Projects/COMPASS/be
read -rs DEMO_ACCOUNT_PASSWORD && export DEMO_ACCOUNT_PASSWORD
podman compose --profile local run --rm -e DEMO_ACCOUNT_PASSWORD web \
  python manage.py seed_demo_staging
```

Live staging uses Docker Compose on the Droplet. Run this only after the deployment workflow
succeeds and public `/api/v1/meta` reports the exact intended `staging` SHA as `build_id` with
`environment=live-staging`. As the deployment user on the Droplet, use the release image and
manifest selected by the workflow. The prompts keep the password out of shell history and the
long-running application `.env`.

The live manifest grants the host-managed runtime files from [runtime-secrets.md](runtime-secrets.md).
`DEMO_ACCOUNT_PASSWORD` is deliberately excluded from that inventory. Keep it one-off as below;
its `_FILE` form requires an explicit one-off mount and must not be added to web/worker/beat grants
or the long-running `.env`. Run the one-off command as follows:

```bash
seed_demo_live_staging() {
  local DEPLOY_PATH=/opt/compass DEPLOY_SHA COMPASS_IMAGE VERIFIED_BUILD_SHA
  local DEMO_ACCOUNT_PASSWORD DEMO_EMAIL_DOMAIN DEMO_ONBOARDING_EMAIL
  local -a demo_env

  # The deployment workflow writes only COMPASS_IMAGE to this state file.
  . "$DEPLOY_PATH/.deploy.env" || return
  export COMPASS_IMAGE
  DEPLOY_SHA="${COMPASS_IMAGE##*:}"
  [[ "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]] || return 1
  read -r -p 'Verified public /api/v1/meta build_id: ' VERIFIED_BUILD_SHA
  [[ "$DEPLOY_SHA" == "$VERIFIED_BUILD_SHA" ]] || return 1
  cd "$DEPLOY_PATH/releases/$DEPLOY_SHA" || return
  [[ -L .env ]] || return 1
  docker image inspect "$COMPASS_IMAGE" >/dev/null || return

  read -rs -p 'Demo account password: ' DEMO_ACCOUNT_PASSWORD
  printf '\n'
  [[ -n "$DEMO_ACCOUNT_PASSWORD" ]] || return 1
  read -r -p 'Demo email domain: ' DEMO_EMAIL_DOMAIN
  [[ -n "$DEMO_EMAIL_DOMAIN" ]] || return 1
  read -r -p 'Onboarding email (Enter to omit): ' DEMO_ONBOARDING_EMAIL
  export DEMO_ACCOUNT_PASSWORD DEMO_EMAIL_DOMAIN
  demo_env=(-e DEMO_SEEDING_ENABLED=true -e DEMO_ACCOUNT_PASSWORD -e DEMO_EMAIL_DOMAIN)
  if [[ -n "$DEMO_ONBOARDING_EMAIL" ]]; then
    export DEMO_ONBOARDING_EMAIL
    demo_env+=(-e DEMO_ONBOARDING_EMAIL)
  fi

  docker compose -f compose.staging.yaml run --rm --no-deps --pull never -T \
    "${demo_env[@]}" web python manage.py seed_demo_staging
}
seed_demo_live_staging
```

Enter an operator-controlled domain and, if onboarding will be demonstrated, an
operator-controlled mailbox. The deployed image is already cached on the Droplet; `--pull never`
keeps this one-off run tied to that image. `-e NAME` forwards each value from the operator shell
without putting it in the command line. The function's local variables disappear when it returns.

Before any writes, the run proves all eight encrypted domain keyrings can encrypt/decrypt.
Missing or invalid keys fail closed with the setting name only. It never generates keys.
The run then synchronizes canonical configuration by calling the same functions as
`sync_identity_policy`, `sync_organization_catalog`, `sync_institutional_forms`, and
`sync_canonical_services`, then verifies prerequisites before provisioning the cast: roles and
designations, the cast's Colleges and Programs, active supported form revisions, canonical
Counseling readiness, no conflicting demo identities, no
existing non-demo Counselor responsibility for the demo Colleges, and an Academic Year state the
dataset can extend.

The command prints the environment, dataset version, timeline anchor, a seed run ID, every demo
account with its role, designations, lifecycle, and authentication state, record counts, and how
much was created versus reused. It never prints the password or form content. Every audit event
caused by a run carries the run ID as its request ID.

## Reruns, idempotency, and what the command never does

An ordinary rerun is safe and reports mostly reused state:

- existing demo accounts are reused and never modified: passwords, email verification, completed
  onboarding, disabled state, and changes made during live demonstrations survive;
- each scenario is matched by a marker record and skipped as a whole when present;
- announcements, resources, feedback, and privacy records are matched by stable natural keys;
- existing Availability schedules and Organization relationships are reused, never replaced. If
  an existing office or Counselor schedule leaves no room for a demo Appointment, that scenario
  stops with a clear error instead of rewriting the schedule.

The command never truncates, flushes, deletes, or resets data, and it has no reset option.
Existing non-demo Counselor responsibilities, a foreign current Academic Year, a demo identity
used by a real account, or a partially present original v1 demo history stop the run with a clear error
before any business record is written.

Dataset version 2 is anchored to Academic Year 2026-2027 and runs when the institutional date is
between 2026-09-21 and 2027-04-30. Recent activity is placed on business days before and after the
run date, so seed close to the demonstration: upcoming Appointments and the active Call Slip fall
within roughly the following three weeks. Current-Student Good Moral requests state the semester of their
own request date (August to December is the first semester, January to May the second).

## Cast

Emails use `DEMO_EMAIL_DOMAIN`. All ready accounts share `DEMO_ACCOUNT_PASSWORD`.

| Persona | Local part | Role (designation) | Lifecycle | Account / authentication |
| --- | --- | --- | --- | --- |
| Ramon C. Bautista | `demo-admin` | IT_ADMIN | — | active, ready |
| Ma. Lourdes P. Villareal | `demo-head` | COUNSELOR (HEAD_GUIDANCE_COUNSELOR) | — | active, ready |
| Carlo D. Esguerra | `demo-counselor-a` | COUNSELOR — CCMS and CAS | — | active, ready |
| Kristine A. Manalo | `demo-counselor-b` | COUNSELOR — CBPA and COED | — | active, ready |
| Arnel S. Ocampo | `demo-staff` | GUIDANCE_SERVICES_STAFF (supervised by Esguerra) | — | active, ready |
| Grace F. Magbanua | `demo-dpo` | INSTITUTIONAL_OFFICER (DPO) | — | active, ready |
| Dennis R. Aragon | `demo-former-staff` | GUIDANCE_SERVICES_STAFF | — | **disabled** (former staff) |
| Bea Kristel L. Abad | `demo-student01` | STUDENT — BSIT 1 | CURRENT | active, ready |
| Mikaela Joy R. Serrano | `demo-student02` | STUDENT — BS Psychology 2 | CURRENT | active, ready |
| Jerome Andres S. Dela Paz | `demo-student03` | STUDENT — BSHM 3 | CURRENT | active, ready |
| Kevin Luis N. Pardo | `demo-student04` | STUDENT — BSIS 4 | CURRENT | active, ready |
| Rosalie Mae D. Obusan | `demo-student05` | STUDENT — BSBA 5 (graduating) | CURRENT | active, ready |
| Adrian Clyde G. Rosales | `demo-student06` | STUDENT — BS DevCom, graduated June 2026 | GRADUATED | active, ready |
| Ellaine Grace M. Cabrera | `demo-student07` | STUDENT — BSEd English, graduated June 2025 | GRADUATED | active, ready |
| Nathaniel Jose P. Samonte | `demo-student08` | STUDENT — BS Biology, transferred out | FORMER | active, ready |
| Trisha Anne V. Llamas | `demo-onboarding` | STUDENT — BSIT 1 | CURRENT | active, **onboarding** |
| Lance Emmanuel R. Bernardo | `demo-student10` | STUDENT — BA English Language Studies 2 | CURRENT | active, ready |
| Princess Joy E. Alcantara | `demo-student11` | STUDENT — BS Accountancy 3 | CURRENT | active, ready |

Graduated and former Students keep working accounts but no College affiliation. Operational
Guidance Student pickers require CURRENT lifecycle regardless of institutional or College scope;
the current Inventory roster uses its own current-year eligibility.

## Scenarios

| Scenario | Persona | Story across domains |
| --- | --- | --- |
| `SCENARIO_CURRENT_REGULAR` | Abad | Submitted Inventory (4Ps household); a cancelled booking; an upcoming ONLINE Counseling Appointment with a draft Routine Interview intake (the E-Counseling starting point). |
| `SCENARIO_ACADEMIC_ADJUSTMENT` | Serrano | Two annual Inventories; booked session → submitted intake → completed Appointment → Counseling Encounter → finalized evaluation → published Shared Summary → scheduled follow-up; an adviser Call Slip withdrawn (voided); read and unread notifications; Customer Feedback and CSM. |
| `SCENARIO_REFERRED_STUDENT` | Dela Paz | Program Chair Referral (and a voided duplicate) → Call Slip action → completed interview recorded as a REFERRED Encounter → direct Routine Interview awaiting evaluation → completed follow-up with published Shared Summary; Indigenous Peoples indicator. |
| `SCENARIO_COMPLETED_COUNSELING` | Pardo | Last year's Referral and Call Slip entered by the now-disabled staff member; a no-show; a walk-in Encounter with a finalized direct Routine Interview and an unpublished Shared Summary draft; a scheduled follow-up; PWD indicator. |
| `SCENARIO_GOOD_MORAL` | Alcantara | Issued current-Student Good Moral certificate (renderable) and a self-cancelled duplicate request; father-deceased indicator; feedback. |
| `SCENARIO_GRADUATING` | Obusan | Delayed final year: Exit Interview draft, pending Good Moral request, career consultation booked with Head Guidance. |
| `SCENARIO_ACTIVE_REFERRAL` | Bernardo | Inventory still in draft; a new adviser Referral and a Call Slip issued live for an interview later this week. |
| `SCENARIO_ALUMNI` | Cabrera | Historical Inventory and Exit Interview; submitted Graduate Tracer; pending graduate Good Moral request. |
| `SCENARIO_RECENT_GRADUATE` | Rosales | Historical Inventories and Exit Interview; issued graduate Good Moral certificate; Graduate Tracer draft. |
| Former / onboarding | Samonte, Llamas | One historical Inventory then FORMER; a provisioned account that has never signed in. |

Academic Years 2024-2025, 2025-2026, and 2026-2027 (current) are created through the Academic Year
service. On a clean database the historical years are entered first, each briefly current inside
one transaction, so Inventory and Exit Interview services run exactly as they do for real users and
the original history is entered as a year-by-year progression. Population back-entry uses
separate bounded Student transactions that restore the current year before commit. Audit events
record these actual operations at execution time. No other session observes a historical year
as current.

## Dataset v2 population and form coverage

| Composition | Count / states |
| --- | --- |
| Students | 57: 11 original rich personas + 46 population Students |
| Lifecycle | 46 CURRENT, 8 GRADUATED (recent graduates and an alumna), 3 FORMER |
| Enrollment-origin College | CCMS 15, CAS 16, CBPA 14, COED 12; graduates/former have no current affiliation |
| Current routing | Counselor A: 25 CCMS/CAS Students; Counselor B: 21 CBPA/COED Students |
| Population Programs | BSIT, BSIS, BSPSYCH, BSBIOL, BSBA, BSA, BSED, BEED, all canonical |
| Current year levels | 1–5 across available Inventory records; missing Inventories cannot supply Program/year to reports |
| Current Inventory | 34 submitted, 8 drafts (early/partial/nearly complete), 4 missing |
| Historical Inventory | 6 in 2024-2025; 19 in 2025-2026; 67 Inventories overall |
| Appointment | 8 scheduled, 3 completed, 3 cancelled, 2 no-show; 3 scheduled ONLINE |
| Counseling / Shared Summary | 7 Encounters; 2 published Summaries, 1 unpublished, others legitimately absent |
| Routine | 6: 1 draft Intake, 5 submitted, 3 finalized Evaluations, 2 pending |
| Exit Interview | 10 submitted, 3 drafts, remaining eligible examples not started |
| Graduate Tracer | 6 submitted, 1 draft, a graduate not started |
| Feedback / CSM | 6 each with different score patterns; 5 written responses and 1 without optional text |

Inventory answer fixtures include family income, parent/guardian circumstances, siblings (including
only-child and multi-sibling households), school history, organization memberships, daily transport
and fares, living circumstances, working-student context, and ordinary/support-indicator profiles.
Most submitted profiles have no special support indicator. Three population drafts are nearly
complete; two are early and two partial. Structured geography remains explicitly unspecified.

Population Students are mostly quiet. Eight carry one reservation each; two carry compact Routine
stories. `population_38` (Oliver Montes) has a submitted Intake and linked walk-in Encounter with
no Inventory, demonstrating ADR-088. `population_27` (Chloe Villanueva) has a finalized career/
entrepreneurship consultation with different evaluation ratings. Neither has a Shared Summary.
Tracer submissions cover course-related employment, unrelated employment, self-employment,
job-seeking, and further training/study. Exit matrices vary across 3/4/5 and draft depths.

### Additive upgrade and recovery

Run the same command on an existing v1 demo world. It adds population accounts and missing safe
v2 forms; original credentials, history, markers, and answers survive. The old `demo-seed-v1`
idempotency namespace remains intentional. Subsequent runs create no additional logical data.
An identity/name or academic provenance conflict stops with an operator-readable error.
An established graduate is never returned to CURRENT to fabricate missing historical forms.
Fix a failed later unit and rerun: completed units remain committed, each new population unit is
atomic, and the PostgreSQL advisory lock still prevents overlapping seed runs.

### Availability-aware placement

A desired date/time is story intent. Normal Appointment slot discovery evaluates current Service
settings and Counselor qualification, office/provider windows, exceptions, duration, prerequisites,
and reservations. Search is bounded to the desired day and four following calendar days, staying
on the same side of the anchor and avoiding demo non-working days. Within the first viable day,
the closest start to the desired local time wins, with earlier start as tie-breaker.

Clean databases receive demo weekly schedules. Existing compatible institutional schedules are
reused unchanged. If there is no compatible slot, the scenario/provider/mode/window is reported
and the schedule is preserved. Completion/no-show and Appointment-backed Encounter timestamps
follow the selected slot. No external provider readiness is required for canonical seed state.

### Encryption keyrings

All are operator-supplied; none are generated by this command:

- `ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`
- `FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`
- `ROUTINE_INTERVIEW_ENCRYPTION_KEYS`
- `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS`
- `REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`
- `EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`
- `INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`
- `GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`

The pre-deployment baseline requires the entire backend suite to have zero failures/errors,
plus static, migration, and canonical OpenAPI checks. This slice does not authorize or perform
live deployment, key provisioning/rotation, encryption cutover, Daily provisioning, or Spaces
mutation. Retention periods and destructive governance approvals remain unseeded.

## Domain coverage

| Class | Domains |
| --- | --- |
| SYNC (reused synchronizers) | Identity policy; Organization catalog; Institutional Forms; canonical Counseling Service |
| SEED (through domain services) | Academic Years; accounts, designations, profiles; Counselor responsibility, Staff supervision, Student affiliation; ONLINE Counseling delivery; office and provider Availability with two exceptions; Individual Inventory (with Student Support facts); Appointments; Counseling Encounters; Shared Summaries; Routine Interviews; Referrals and actions; Call Slips; Good Moral; Exit Interviews; Graduate Tracer; Customer Feedback; CSM; Announcements; Resources; Privacy Notices, a draft revision, and one acknowledgment |
| DERIVED (never written directly) | Portal Overview; Student Support context; Student Profiling and Graduate Tracer reports; My Activity, Security Activity, Privacy & Security Activity; Notifications; controlled-form metadata; Good Moral, Referral, and Call Slip documents |
| RUNTIME-ONLY (never seeded) | Authentication sessions, trusted sessions, login challenges, email OTP challenges, recent MFA, TOTP factors and recovery codes, email-change requests; Daily rooms, tokens, recordings, webhooks, transcriptions; PSGC cache; Platform Health, Environment, Maintenance; email deliveries; worker state |
| INTENTIONALLY EMPTY | Structured PSGC geography in Inventories (would need live PSA validation; answered as "not specified"); Resource files (would need object-storage uploads); E-Counseling rooms and media (lazy provider provisioning); Inventory and Exit Interview reopen events (each emails the Student) |

## Seed-only writes and side effects

Everything goes through domain services, with these documented exceptions:

- **Accounts** use `User.objects.create_user` plus a SYSTEM `account.created` event, like
  `create_it_admin`, because Account Management services require an administrator session with
  recent MFA. Designations, Student lifecycle changes, and the one disable mirror the Account
  Management invariants and audit actions. Provisioned accounts get no "access changed" security
  notification: nothing about their access changed.
- **Historical timestamps.** Services stamp wall-clock time. Back-entered records have their
  business timestamps (created, submitted, published, read, …) moved onto the demo timeline
  through an allowlist of timestamp columns; status, relationships, and content are never touched.
  Audit events are never rewritten and keep the real seed-run time.
- **Email intents.** Services that notify create an in-app Notification and an email delivery.
  Seeding keeps the Notification and removes only the not-yet-committed, never-attempted email
  delivery it caused, so a bulk seed never emails anyone. Queued delivery tasks find nothing and
  do nothing. Live actions after seeding send email normally.
- Back-entered Call Slips use the existing quiet HISTORICAL issuance mode; the single slip issued
  during the run uses LIVE issuance and creates the Student's in-app notification.

Seeding never calls Daily, PSGC, Turnstile, object storage, or the PDF renderer. Good Moral,
Referral, and Call Slip documents render on demand from the seeded records.

## Onboarding demonstration

The onboarding persona is active, has no usable password, no verified email, and no sessions,
challenges, or MFA state. Starting normal Password Access from the sign-in page resolves the
account to email verification: COMPASS emails a one-time code, the user sets a first password,
the email becomes verified, and ordinary sign-in follows. Reruns never undo a completed
onboarding. MFA follows the deployment's normal policy; the seeder creates no TOTP secrets,
recovery codes, or bypasses.
