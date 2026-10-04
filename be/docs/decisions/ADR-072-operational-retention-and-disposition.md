# ADR-072: Operational retention and disposition governance

- Status: Proposed
- Date: 2026-10-04
- Refines/supersedes: ADR-069's live retention boundary for the explicitly supported operational treatments below
- Preserves: ADR-045 confidential-content boundary, ADR-011 append-only Audit Trail, ADR-026 consent guarantees

## Context and authority

ADR-069 correctly removed a descriptive `RetentionPolicy` registry that had no adopted schedule or
operational disposition. That historical decision is unchanged. This decision introduces a new
`OperationalRetentionRule`, review cases, holds, verified executors, and accountable authorization.
It does not resurrect the removed table, old UI, or old live audit actions. This is post-Phase-12
governance work, without a new numbered phase or a claim of legal/ISO compliance.

Human governance supplies the approved policy reference, duration and effective date. COMPASS never
seeds or infers an institutional period, basis, rule activation or disposition approval. No active,
effective rule means no destructive treatment. Rules do not constitute legal advice or certification.

Three canonical capabilities are added: `privacy_governance.retention.view`, `.manage`, and
`.approve`. Management and approval each require the view capability; dependencies constrain grants
without manufacturing authority. The DPO designation is the sole baseline holder of all three.
Plain Institutional Officers, IT Admin, Head Guidance, Counselors, Guidance Services Staff and
Students gain none. Existing overrides can deliberately grant exceptional authority. Every route
checks effective capabilities, without checking role/designation names.

Retention authority grants no Inventory, Counseling, Graduate Tracer, E-Counseling or other domain
content access. The DPO sees opaque case references, category, rule/revision, count, eligibility,
hold, approval and outcome metadata. Source row IDs, provider identifiers and original answers are
not projected into the governance API or copied into its audit metadata.

## Rules and exact date semantics

Rules begin DRAFT and remain normally editable without MFA. Every draft save increments its revision.
Activation and retirement require the existing backend recent-MFA mechanism: an account without a
confirmed active authenticator receives `mfa_setup_required`; an enrolled account without recent
verification receives `recent_mfa_required`. No consequential request is automatically replayed.

Activated/retired terms are immutable. Amendments require a new draft after retiring the old rule;
one ACTIVE rule per category is enforced in PostgreSQL. Future effective dates are allowed, but
discovery and execution do not use them early. Activation itself does not approve any disposition.

`duration_days` is a positive integer, bounded to 365000 as a technical validation limit, with no
default. Each elapsed day means exactly 86400 seconds from the UTC anchor. No calendar-month/year,
leap-year anniversary, month-end rounding or prose interpretation exists. `effective_on` is an
institutional calendar date using the configured COMPASS timezone. Existing rows are not treated
during schema migration.

## Supported executor contracts

| Category | Source and eligible lifecycle | Code-owned trigger | Treatment | Blockers and verification |
| --- | --- | --- | --- | --- |
| `GRADUATE_TRACER` | Identifiable schema-v1 `GraduateTracerResponse`, SUBMITTED | `SUBMITTED_AT`: `submitted_at` plus elapsed days | `ANONYMIZE` | Active/effective immutable rule, unchanged source/version, reached boundary, no hold; verify the entire allowlisted aggregate replacement, deleted identifying source and children |
| `ECOUNSELING_RECORDING` | `ECounselingMediaCapture` RECORDING, READY, room expiry reached | `MEDIA_READY_AT`: `ready_at` plus elapsed days | `DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE` | READY lifecycle, artifact ID present, expired room, unchanged source, rule and hold checks; verify documented Daily response for that exact recording ID |
| `ECOUNSELING_TRANSCRIPT` | `ECounselingMediaCapture` TRANSCRIPTION, READY stored artifact, room expiry reached | `MEDIA_READY_AT`: `ready_at` plus elapsed days | `DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE` | Same media checks; verify exact transcript ID and documented `t_deleted` result |

Recording and stored-transcript rules remain separate. Live transcription without a stored artifact
does not become an executable stored-transcript case. Consent approval, withdrawal, media capture,
retention eligibility, disposition approval and artifact deletion remain separate truths.

## Frozen cases, holds and execution

V1 uses a **single-member case** instead of a bulk batch. Unique `(category, source_id)` prevents
duplicate candidates. The source ID is internal, with source version, eligibility timestamp,
immutable rule and exact rule revision. Each reviewed approval has exactly one frozen member; later
eligible records get separate unapproved cases. There is no membership-edit API or generic model/
object deletion API. Discovery refreshes unapproved cases in bounded pages; it never approves them.

Holds store only a bounded safe administrative reason and placement/release provenance. Management
authority is required. Placement cancels any queued approval; releasing a hold leaves a reviewable
case requiring a new approval. Holds and retirement cannot interrupt a provider operation already
PROCESSING; those requests return a conflict rather than falsely promising to prevent an in-flight
irreversible operation. All governance paths lock rule then case, and tracer paths additionally lock
Student then source consistently with self-service creation.

Approval requires `.approve`, recent MFA, an exact expected case revision, effective immutable rule,
current source version, reached retention boundary, no hold and no blocker. Stale state is rejected;
the UI closes confirmation, reloads and requires a fresh review. The committed transition is
APPROVED → QUEUED. Celery dispatch occurs only after transaction commit. There is no second execution
button, automatic approval or age-driven deletion job.

Beat discovers eligibility every five minutes and recovers approved dispatch every minute. A durable
QUEUED row is the outbox when broker dispatch fails. Claims use row locks, a unique claim token and
PROCESSING state; duplicate delivery cannot reclaim a live case. Tracer anonymization, verification,
completion and audit append are one database transaction. Provider calls occur outside database
transactions; local minimization happens only after the verified provider result and a matching
claim/source check. This is at-least-once dispatch with idempotent treatment, not exactly-once
execution across PostgreSQL and Daily.

Transient Daily failures have three total automatic attempts, with 60 then 120 second backoff.
Permanent errors become FAILED. Unverified outcomes/custom storage become RECONCILIATION_REQUIRED.
A claim older than 15 minutes requires deliberate reconciliation; it is not silently rerun. A
reviewed recent-MFA retry grants another bounded attempt budget, limited to three manual retries.
Custom-storage cases require deployment-owned reconciliation rather than the automatic retry path.

## Graduate Tracer field map and identity boundary

The current closed aggregate report justifies this exact retention map. It does not justify retaining
all structured survey values. The executor creates a new opaque UUID contribution, verifies it,
deletes the identifiable source and its three owned child collections transactionally, and stores no
old-to-new identifier mapping. The nullable Student FK allows only a submitted anonymized contribution
to have no Student; the identity-shape constraint and normal nullable uniqueness semantics are explicit.

| Before | After |
| --- | --- |
| `student` | NULL; no pseudonymous Student code or reversible replacement relationship |
| original `id` | Original row removed; independent new UUID, never returned by retention API or logged as a mapping |
| `name_snapshot`, `permanent_address_snapshot`, `email_snapshot`, `telephone_contact_numbers_snapshot`, `mobile_number_snapshot`, `province` | Empty strings |
| `birth_date` | NULL |
| `degree_other_reason`, `advanced_study_other_reason`, `unemployment_other_reason`, `self_employed_college_skills`, `present_occupation`, `reasons_for_staying_other`, `reasons_for_accepting_other`, `reasons_for_changing_other`, `first_job_duration_other`, `first_job_source_other`, `time_to_first_job_other`, `useful_competencies_other`, `curriculum_improvement_suggestions` | Empty strings |
| `undergraduate_degree_reasons`, `graduate_study_reasons`, `advanced_study_reasons`, `reasons_for_accepting_first_job`, `reasons_for_changing_job` | Empty arrays; not used by current aggregate reports |
| `education_rows` (degree/specialization, institution, graduation year, honors); `professional_exam_rows` (exam, exact date, rating); `training_rows` (title, duration/credits, institution) | All child rows deleted |
| `sex`, `civil_status`, `region_of_origin`, `residence_location` | Retained bounded analytical values used by current distributions |
| `current_employment_state`, `unemployment_reasons`, `present_employment_status`, `employer_business_line`, `place_of_work` | Retained bounded analytical values used by current distributions |
| `first_job_after_college`, `reasons_for_staying_on_job`, `first_job_related_to_course`, `first_job_duration`, `first_job_source`, `time_to_first_job`, `first_job_level`, `current_job_level`, `initial_gross_monthly_earning`, `curriculum_relevant_to_first_job`, `useful_competencies` | Retained bounded analytical values used by current distributions; descriptive OTHER text removed |
| `instrument_schema_version`, `status` | Retain schema-v1 and SUBMITTED for aggregate membership |
| `submitted_at` | Institutional submission calendar date at midnight; exact clock time removed while preserving date-filter semantics |
| `created_at` / `updated_at` | Submission day / disposition day at midnight; original exact timestamps removed |
| `anonymized_at` | Disposition calendar day at midnight |

Verification checks NULL Student, anonymization marker, every removed field against its empty/null
default, child absence, valid retained choices and original-source absence. Re-running verification/
anonymization of an anonymous contribution is safe. The report locks its frozen population until
all distributions finish, preventing replacement during its separate aggregate queries.

Anonymous contributions are excluded from all identifiable Head Guidance and self-service queries;
only aggregate reporting reads them through product APIs. The original Student receives controlled
`graduate_tracer_disposed` (409), with no cached personal content displayed by the client. A minimal
`GraduateTracerDisposedParticipation` stores Student, schema version and disposed calendar date,
with **no response/case/anonymous-row ID**, to prevent repeat participation in the same instrument.
The prior report contribution therefore cannot be linked back through that marker.

There are no Graduate Tracer notifications, reopen tables or release-log relationships to a response
in the current graph. Three child tables are its only model FK dependents. Historical append-only
AuditEvents can still identify the original actor and now-removed response UUID. Aggregate report
release events carry only date-filter/scope information. Disposition cases retain the removed source
UUID for restore reconciliation, never the anonymous UUID. No historical audit evidence is rewritten.
These restricted system facts prove an action on the former identifiable row; ordinary product APIs
cannot use them as a reverse identity map to the anonymous contribution. Privileged database access,
prior exports, rare analytical combinations and outside knowledge remain governance considerations;
existing aggregate disclosure warnings remain, without claiming zero statistical re-identification risk.

## Daily provider verification and limitations

Official Daily documentation was checked on 2026-10-04:

- [Delete Recording](https://docs.daily.co/reference/rest-api/recordings/delete-recording): `DELETE /recordings/{recording_id}`, confirmed by `deleted: true` and matching `id`.
- [Get Recording Info](https://docs.daily.co/reference/rest-api/recordings/get-recording): metadata-only preflight, exact ID and finished lifecycle.
- [Delete Transcript](https://docs.daily.co/reference/rest-api/transcripts/delete-transcript): `DELETE /transcript/{transcriptId}`, confirmed by matching `transcriptId` and `status: t_deleted`.
- [Get Transcript Info](https://docs.daily.co/reference/rest-api/transcripts/get-transcript): metadata-only preflight and documented `t_deleted` reconciliation after a lost response.

No invented endpoint, artifact URL, download, playback or media copy exists. Daily-owned cloud
artifacts can be disposed using these verified contracts. Customer-managed storage markers
(`storage_provider` for recordings or nonempty transcript `outParams`) trigger truthful external
reconciliation. This slice cannot prove deletion from deployment-owned S3/OCI copies and never marks
such a case completed automatically. A missing/unavailable recording after a lost delete response
also remains unresolved rather than treating any 404 as verified erasure.

The capture row remains as lifecycle evidence; only its provider artifact reference is cleared after
confirmed disposition, with a separate `artifact_disposed_at`. Consent decisions and withdrawal
survive, as do minimal instance/session and lifecycle facts. Late media webhooks cannot resurrect a
disposed reference. Student/Counselor workspaces show disposition independently of consent/capture.
Temporary URLs, provider credentials, tokens, object keys and media/transcript content are discarded.

## Audit, deployment and future scope

New stable actions are `privacy.retention.rule.created`, `.updated`, `.activated`, `.retired`;
`privacy.retention.hold.placed`, `.released`; and `privacy.disposition.approved`, `.started`,
`.completed`, `.failed`, `.retry.authorized`. The shared append-only Audit Trail records rule/case ID,
category, action, revision, one-record count, state and safe blocker. No source content/identity or
provider access material is audited. Safe Privacy & Security Activity presentations retain historical
removed-registry actions unchanged. AuditEvents themselves are never disposed by this feature.

Deployment must migrate, synchronize identity policy and restart web/worker/one Beat scheduler using
the same image. The normal canonical OpenAPI export and Orval client generation are required;
generated frontend files remain ignored/uncommitted. No ACTIVE rule is seeded in demo/live staging.

Live-data/provider disposition is not physical erasure from historical backups or prior exports.
Database/object backup retention remains infrastructure-owned. Before treating a historical restore
as authoritative, operators must reconcile/reapply completed decisions using the protected original
source identifiers, without reconnecting anonymous contributions. See the dedicated runbook.

Customer Feedback/CSM remains future work pending a tested free-text and analytical minimization
contract. Individual Inventory, Routine Interview, Exit Interview, Counseling/Shared Summary,
Referral, Call Slip, Appointment, Good Moral and Audit Trail are unsupported. Their PROTECT/provenance
graphs are unchanged, and they cannot be selected as executable rules. New categories require an ADR,
closed category/trigger/action contract, an owned executor, verification, dependency checks and tests;
no generic delete-anything executor is authorized.

UCN/DPO must still supply approved durations, policy references/effective dates, authorized exceptional
holders, real hold decisions and any future reporting/minimization changes. Infrastructure owners must
confirm Daily storage configuration and backup restoration procedures. The application supplies none
of these institutional policy decisions by default.
