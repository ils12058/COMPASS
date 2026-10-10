# ADR-084 — Selective Graduate Tracer identifiable confidential content encryption

Status: Accepted for repository implementation; live cutover deferred.

## Decision and threat boundary

ADR-035 self-service/raw Head review, ADR-047 aggregate reporting and ADR-072 irreversible
retention have different data requirements. Encrypt 24 private root fields and 10 child fields
using the unchanged ADR-079 primitive. Keep metadata/search (E0) and the exact existing 20-field
analytical allowlist (E1) queryable. name_snapshot remains plaintext for historical Head search.
Database-only disclosure is the threat boundary; authorized application processes can decrypt.

GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS is one independent ordered keyring.
The first key writes; all keys read. Direct or _FILE configuration is required in every environment.
No fallback, derivation or reuse of any current/previous key from SECRET_KEY, TOTP, Web Push
storage, Routine Interview, Shared Summary, Referral, Exit Interview or Inventory.

## Exact storage split

E0: id, student, instrument_schema_version, status, name_snapshot, submitted_at, anonymized_at,
created_at, updated_at.

E1: sex, civil_status, region_of_origin, residence_location, current_employment_state,
unemployment_reasons, present_employment_status, employer_business_line, place_of_work,
first_job_after_college, reasons_for_staying_on_job, first_job_related_to_course,
first_job_duration, first_job_source, time_to_first_job, first_job_level, current_job_level,
initial_gross_monthly_earning, curriculum_relevant_to_first_job, useful_competencies.

Root E2: permanent_address_snapshot, email_snapshot, telephone_contact_numbers_snapshot,
mobile_number_snapshot, birth_date, province, undergraduate_degree_reasons,
graduate_study_reasons, degree_other_reason, advanced_study_reasons,
advanced_study_other_reason, unemployment_other_reason, self_employed_college_skills,
present_occupation, reasons_for_staying_other, reasons_for_accepting_first_job,
reasons_for_accepting_other, reasons_for_changing_job, reasons_for_changing_other,
first_job_duration_other, first_job_source_other, time_to_first_job_other,
useful_competencies_other, curriculum_improvement_suggestions.

Children retain id, response, position as plaintext. Education encrypts degree_and_specialization,
college_or_university, year_graduated, honors_or_awards. Professional Exam encrypts
examination_name, date_taken, rating. Training encrypts title, duration_and_credits, institution.
Dates use canonical ISO strings/null, years strict integers, choice arrays preserve order.
Typed frozen projections restore dates and choice tuples; models have no implicit decryption.

Each family has confidential_content_ciphertext. Each exact envelope has integer schema_version
1, payload with exactly its field set, and the following string UUID bindings:

| Family | Binding keys |
| --- | --- |
| Response | graduate_tracer_response_id |
| Education | graduate_tracer_response_id, education_row_id |
| Professional Exam | graduate_tracer_response_id, professional_exam_row_id |
| Training | graduate_tracer_response_id, training_row_id |

UUIDs are allocated before encrypt/save/bulk insertion. Student, status, timestamps, analytical
answers and child position are deliberately not bound. Cross-row/parent/family transplantation
fails. Runtime cryptography delegates to ADR-079; migrations freeze their historical v1 mechanics.

## Access, reports and disposition

An active graduated Student owner requires the existing self capability and owner selector before
any read. Head raw detail requires effective graduate_tracer.view and an identifiable SUBMITTED
selector. List/search/date/employment pagination and aggregate JSON/XLSX read E0/E1 only.
The workbook remains five visible aggregate sheets. No ordinary Counselor, GSS, IT Admin or DPO
raw access is introduced. Any unreadable selected root/child returns the stable generic 500
code graduate_tracer_confidential_content_unavailable. Replacement authenticates existing content
before writing and cannot repair corruption. No partial private answer is returned.

Identifiable roots require non-null/nonempty ciphertext. Anonymous roots require student NULL,
anonymized timestamp, SUBMITTED status and ciphertext NULL; they have no children.
ANALYTICAL_FIELDS stays exactly unchanged. Approved disposition copies E1 into a new UUID,
rounds timestamps to local calendar days, writes the existing Student/schema participation tombstone
and deletes source plus all children. It never decrypts or encrypts E2, even with corrupt tokens or
unavailable keys. No source-to-anonymous mapping is stored. All four disposed self operations
retain 409 handling. Anonymous metadata/defaults and child absence are explicitly verified.

## Migration, reverse and rotation

0003 adds four nullable envelopes and verifies identifiable backfill. It verifies existing anonymous
minimized rows and leaves their ciphertext NULL. 0004 first locks Response, Education, Exam and
Training in deterministic order using PostgreSQL EXCLUSIVE. Under this writer fence,
it authenticates every present identifiable token independently of current E1, compares against
latest validated plaintext, preserves identical tokens, reconciles valid stale or missing tokens,
and aborts atomically on corrupt present tokens or malformed anonymous rows. Late old-runtime
child replacements/new rows and submissions are included. A Phase-A source deleted by old
retention and replaced with an anonymous contribution is recognized as intentionally ciphertext-free.
No private content is fabricated for that contribution.

Only after verification does Phase B remove 34 private columns and install final constraints.
Controlled reverse acquires the same fence before DDL, restores temporary nullable fields,
authenticates/restores exact identifiable plaintext, restores anonymous empty/null historical
defaults without decrypt, verifies both and restores original field definitions. Corruption rolls
back the entire reverse. Phase-A reverse drops envelopes only after plaintext recovery. Writers
must remain drained until compatible activation; the table fence is not a rolling upgrade.

rotate_graduate_tracer_confidential_content supports dry-run and batch sizes 1–1000 (default 100).
Both modes refuse any legacy private column. Rotation verifies/counts all four families, locks
bounded real batches and changes ciphertext only using MultiFernet.rotate, preserving bytes and
token timestamp. Anonymous contributions are counted/skipped and remain NULL. Failures list
at most 20 bounded UUID/family/reason contexts, leave failed rows unchanged and return nonzero.
Committed batches survive interruption; reruns are idempotent/resumable.

## Deferred live cutover

The runtime inventory increases to 20; see [runtime-secrets.md](../runtime-secrets.md).
No live key, deployment or live migration is part of this change. Resolve actual deployed SHA and
migration graph and which ADR-080–084 keyrings are already provisioned. Independently provision
absent domains under separate live authorization. Escrow complete ordered keyrings off-host,
verify encrypted database/host rollback backups, and drain all old web/worker/beat, queued/in-flight
retention jobs and operator writers. Deploy an approved exact staging SHA, migrate under that
drain, activate compatible code, then validate authorized raw detail, lists, aggregate JSON/XLSX
and no-decrypt disposition. Rollback retains every required key and uses controlled reverse to the
exact prior graph before old code activation; anonymous content must remain minimized.
