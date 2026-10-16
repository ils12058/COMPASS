# CANON-1C — COMPASS Staging Dataset v1 design

Operator documentation: [`be/docs/staging-dataset-v1.md`](../../be/docs/staging-dataset-v1.md).
Decision: [ADR-116](../../be/docs/decisions/ADR-116-canonical-baseline-and-staging-dataset-v1.md).
Generated UAT documents: [`uat/`](uat/).

## Identity and lineage

| Component | Retired | Canonical |
| --- | --- | --- |
| Dataset | Demo Dataset v1/v2 | **COMPASS Staging Dataset v1** |
| Package | `compass.demo_seed` | `compass.staging_seed` |
| Command | `seed_demo_staging` | `seed_staging_dataset` (`seed`, `verify`, `report`, `issue-credentials`) |
| Documentation | `docs/staging-demo-seeding.md` | `docs/staging-dataset-v1.md` (old doc kept under `docs/historical/`) |
| Dataset version | 1 → 2 (upgrade path) | **1**, independent of the application/API version |
| Configuration | `DEMO_SEEDING_ENABLED`, `DEMO_ACCOUNT_PASSWORD`, `DEMO_EMAIL_DOMAIN`, `DEMO_ONBOARDING_EMAIL` | `STAGING_SEED_ENABLED`, `STAGING_SEED_EMAIL_DOMAIN`, `STAGING_SEED_ONBOARDING_EMAIL` (no password) |
| Identifiers | `DEMO-2026-…`, `demo-…@compass-demo.test` | `STG-S-…`/`STG-E-…`, `stg-…@compass-staging.test` (local) |
| Idempotency namespace | `demo-seed-v1` | `staging-dataset-v1` |
| Advisory lock | `2_026_092_801` | `2_026_101_601` |

Removed with the old package: the v1-to-v2 additive upgrade, partial-history repair rules for the
old cast, population-upgrade back-entry, `DEMO_DATASET_VERSION` detection, the shared-password
validator, count helpers used only by its report, and both old test modules. A database containing
`DEMO-2026-` accounts is refused, never adopted.

Reused (reviewed domain-service code, moved with history): the fail-closed guard, timeline and
business-day placement, availability-aware slot choice, the seed-only write allowlist and
email-intent settling, historical Academic Year back-entry, Inventory/Exit/Tracer/feedback content
builders, publication and Privacy Notice content, and the nine rich stories.

## Package layout

| Module | Responsibility |
| --- | --- |
| `config.py`, `guard.py`, `timeline.py` | Operator configuration, fail-closed environment boundary, deterministic Asia/Manila timeline |
| `identities.py`, `staff.py`, `students.py` | Account specifications: staff and negative-test accounts, 100 Students |
| `manifest.py` | Account registry, scenario catalog with verifiable predicates, static validation |
| `accounts.py`, `organization.py`, `history.py` | Provisioning (no password), routing and Availability, historical back-entry |
| `workflows.py` | Shared domain-service steps with timestamp alignment |
| `scenarios/rich.py`, `scenarios/action_ready.py`, `scenarios/background.py` | Story units, each atomic and marker-skipped |
| `publications.py`, `content/` | Announcements, Resources, Privacy Notices, feedback; data-only content |
| `encryption.py` | Secret-free keyring preflight (9 domains) |
| `credentials.py` | Explicit participant credential issuance |
| `verify.py`, `reports.py` | Read-only verification; generated documentation |
| `seed.py`, `management/commands/seed_staging_dataset.py` | Orchestration and operator entry point |

## Accounts

| Category | Count | Accounts |
| --- | ---: | --- |
| Staff — UAT-ready | 10 | `it_admin`, `it_admin_2`, `head_guidance`, `counselor_a`, `counselor_b`, `counselor_c`, `gss_a`, `gss_b`, `dpo`, `dpo_2` |
| Staff — restricted | 3 | `former_staff` (disabled), `unassigned_counselor` (no responsibility), `officer_no_designation` (no capabilities) |
| Students — rich scenario | 11 | `first_year` … `good_moral` (one onboarding, one former, two graduates) |
| Students — action-ready | 24 | `ar_01` … `ar_24` |
| Students — background | 64 | `bg_01` … `bg_64` |
| Students — restricted | 1 | `bg_65` (disabled) |
| **Total** | **113** | 100 Students, 13 staff |

Roles and designations are the canonical policy (IT_ADMIN, COUNSELOR, GUIDANCE_SERVICES_STAFF,
INSTITUTIONAL_OFFICER, STUDENT; HEAD_GUIDANCE_COUNSELOR, DPO). There is no UAT-only role.

Counselor caseloads drive real authorization scope and keep evaluators apart:

| Counselor | Colleges | Supervised staff |
| --- | --- | --- |
| `counselor_a` | Main CCMS, CAS, COENG | `gss_a` (and the disabled `former_staff`, until offboarded) |
| `counselor_b` | Main CBPA, Abaño COED | `gss_b` |
| `counselor_c` | Mercedes CFAST, Labo CANR, Jose Panganiban COTT, Entienza | — |
| `head_guidance` | Institution-wide supervision; consultation schedule | — |

The Graduate School has no responsibility and no seeded Students (graduate programs are outside
the dataset's undergraduate workflows). Good Moral preparation and issuance are office-wide by
design (`good_moral/work.py`), so every Counselor sees that work.

## Student design

| Group | Target | Design |
| --- | ---: | --- |
| Rich scenario | 11 | The reviewed multi-year stories (counseling with Routine evaluation and Shared Summary, referral to Call Slip to Encounter, walk-in and no-show, graduating with Exit draft and Head consultation, issued certificates, Tracer, alumna, former, onboarding, active referral) |
| Action-ready | 24 | Exactly one pending action each, for a Student or a staff evaluator, so that no two evaluators need the same Student |
| Background | 65 | Mostly submitted Inventories with varied household, commute, working, 4Ps, PWD, Indigenous and guardian profiles; drafts and missing records; graduates with Tracer submissions; former Students; a few Appointments and Routine stories; one disabled account |

Action-ready states (each its own atomic unit, marker = the record it creates, in any status):

| Key | Initial state | Scenario owner |
| --- | --- | --- |
| `ar_01`, `ar_02` | Submitted Inventory, no Appointment | Student books |
| `ar_03`, `ar_04` | Upcoming in-person Appointment | Student reschedules / cancels |
| `ar_05`, `ar_06` | Upcoming ONLINE Appointment, no consent | Counselor requests, Student decides |
| `ar_07` | Nearly complete Inventory draft | Student submits |
| `ar_08` | No current Inventory (booking still allowed: ADR-088) | Student starts |
| `ar_09` | Upcoming Appointment, Routine intake draft | Student completes intake |
| `ar_10`, `ar_11` | Exit Interview opportunity open, not started | Student completes |
| `ar_12` | Eligible, no Good Moral request | Student requests; also starts an Office conversation |
| `ar_13` | GRADUATED with Exit Interview, no Tracer | Student completes Tracer |
| `ar_14` | Counselor-started Appointment conversation, unread | Student replies |
| `ar_15` | Completed session, published Shared Summary, feedback invitation | Student reads and gives feedback |
| `ar_16` | Referral and LIVE Call Slip (counselor_c) | Student views |
| `ar_17` | Good Moral REQUESTED | counselor_b processes |
| `ar_18` | Good Moral READY_FOR_ISSUANCE | counselor_a issues and prints |
| `ar_19`, `ar_20` | Referral with no action | counselor_a / gss_b issue Call Slips |
| `ar_21` | Walk-in Encounter, submitted intake, no evaluation | counselor_a finalizes |
| `ar_22`, `ar_23` | Past Appointment still SCHEDULED | counselor_b completes / counselor_c marks no-show |
| `ar_24` | Submitted 2026-2027 Exit Interview | Head reopens; Student may request Good Moral |

Distribution (verified, see [summary](uat/STAGING-DATASET-v1-SUMMARY.md)): 86 CURRENT, 10
GRADUATED, 4 FORMER; six campuses and nine Colleges; 30 Programs, all from the canonical catalog;
current year levels 1–5. The population is a UAT design, not a statistical model of UCN
enrollment. A smaller approved cohort is made by marking or removing rows in `students.py`; no
selection is random and the manifest refuses dangling scenario references.

## Scenarios

91 scenarios: 88 executable and 3 `PENDING_IMPLEMENTATION` (Appointment Reminders, Service
Catalog Expansion, Shared Guidance Follow-Up). Each has an ID, feature, role, recommended account,
start route, initial state, preconditions, action, expected result, related accounts, mutating or
read-only, whether repeating needs fresh state, restrictions and readiness.

| Family | Scenarios |
| --- | --- |
| Student | Profile; Inventory (finish, start, history, draft with Call Slip); Appointments (book ×2, reschedule, cancel, FORMER refused, no-show view); Routine intake ×2; evaluation never shown; E-Counseling consent ×2; Exit Interview ×3; Good Moral ×6; Graduate Tracer ×2; Messages ×2; Shared Summary (published, draft hidden); Call Slips ×3; feedback; notifications; publications; history; onboarding |
| Guidance Counselor | Appointment list, completion, no-show; Shared Summary publication; Routine evaluation ×2; referral → Call Slip; new referral; Inventory roster and reopen; Good Moral process, issue, reprint, assisted start; E-Counseling consent request; Work Queue; Messages; My Activity; Student Profiling report; Availability |
| Guidance Services Staff | Call Slip from referral; new referral; assisted Good Moral; Exit opportunity; Work Queue; counseling content refused |
| Head Guidance Counselor | Guidance Operations; Appointment reassignment; Exit reopen and opportunity; reports and exports; feedback results; Academic Years (view only) |
| IT Administrator | Account create/disable/enable; capability override; organization routing (view only); Platform Operations; guidance records refused |
| DPO | Read-only retention oversight; Privacy Notice revision publish; privacy activity export; retired disposition links return Not Found; guidance records refused |
| Negative authorization | Disabled staff and Student cannot sign in; undesignated officer refused; unassigned Counselor sees no Students; cross-Student and cross-caseload access refused |

Every executable scenario lists `(account, predicate)` checks. Predicates are implemented in
`verify.py` against the database (for example `appointment:past_scheduled`,
`exit:opportunity_open`, `messages:unread`, `capabilities:no_counseling`), so the matrix's
initial states are proven, not asserted. Every UAT-ready account is the actor of at least one
scenario; background accounts are never actors; restricted accounts appear only in `NEG-…`.

## Credentials

Seeding never sets a password (Account Management semantics). `issue-credentials` is the explicit
operator step: distinct `secrets.token_urlsafe(18)` passwords validated by the normal policy, hash
only, one new `0600` handoff file outside the source tree, audited as `auth.password.initial_set`
(method only), skips accounts that already have a credential, reissue only for named accounts with
`--confirm-reissue` (revokes sessions, trusted browsers and pending email challenges; audited as
`auth.password.reset`). Restricted accounts only when named; disabled and onboarding never. MFA,
email verification and authorization policy are unchanged. No evaluator identity or assignment is
written by the system; the assignment template is blank.

## Timeline and reruns

Asia/Manila. Academic Years 2024-2025, 2025-2026 and current 2026-2027. Preparation date within
2026-09-21 … 2027-04-30, not after the institutional date and at most one day before it. Past
work lands on business days before it; upcoming work after it; no impossible chronology (services
receive explicit `now=` values and `align_timestamps` refuses future timestamps).

A rerun creates nothing that exists (whole-unit markers in any status), never modifies an account,
never restores a consumed state and refuses conflicting identities or routing before business
records. There is no reset option.

## Isolation

No email (never-attempted intents caused by seeding are dropped; in-app Notifications kept), no
push, no Daily room/token/recording/transcript, no object storage, no PSGC, no callback
registration. Guidance Messages emit only a content-free realtime hint. The test suite seeds with
Daily, outbound HTTP and object storage patched to fail and asserts that no mail was sent.
