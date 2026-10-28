# Source adapters and frozen field inventories

Each Grant selects exact IDs. The owning domain loads and checks one source; ordinary detail projections are not called and trimmed afterward.

## Encounter

`counseling/continuity_encounters.py` implements `read_selected_encounter_for_continuity`. `_lock_encounter` checks the exact Student/UUID, historical Counselor if recorded in the Grant, recognized entry/delivery modes, ordered completed times and canonical Counseling Service. If Appointment-backed, the locked parent must be actionable and match Student, provider, service and delivery mode; cancelled/no-show or malformed links deny. Historical Service inactivity is not a new-work prerequisite for reading an otherwise valid completed record.

`ENCOUNTER_METADATA_V1` releases exactly:

| Field | Meaning |
| --- | --- |
| id | Selected Encounter UUID |
| started_at / ended_at | Original actual timestamps |
| entry_mode / delivery_mode | Recorded structural modes |
| counselor_id | Historical author/provider UUID |

Service identification, Student display/contact data, Appointment IDs/details, Intake, Evaluation, Summary, media, messages and credentials are omitted. There is no Encounter list. The response wraps this fixed object with Grant UUID/version, operational/disclosure policy versions and the fixed projection identifier. No source or ownership field is updated.

## Finalized Routine Evaluation

`routine_interviews/continuity.py` implements `read_selected_evaluation_for_continuity`. `_lock_evaluation` selects structural columns only, verifies submitted Intake, finalized Evaluation at/before backend time, valid chronology, required Encounter link and matching Student/Counselor, canonical service, entry/delivery mode and Appointment relationship. It reuses the source-owned `routine_interview_encounter_match_issue_for_facts` semantics. Linked Encounter completion must precede finalization. Parent Appointment and Service are locked as part of source validation; no parent content or meeting credential is disclosed.

After all grant/policy/source checks, `_evaluation_projection` calls the existing `content.read_evaluation()` exactly once. Existing authenticated ciphertext binding, section identity, keyring, schema and value validation are unchanged. Deferred ORM retrieval loads only Counselor Evaluation ciphertext; Student Intake remains deferred even when its stored ciphertext is deliberately unreadable. No second ciphertext store or Handoff key is introduced.

The independent, pinned `FINALIZED_EVALUATION_V1` inventory contains:

- academic_adjustment_rating, physical_adjustment_rating, social_adjustment_rating;
- spiritual_adjustment_rating, financial_adjustment_rating, emotional_adjustment_rating;
- other_adjustment, special_concern, recommendations.

**None is approved by default.** Valid disclosure evidence must select a nonempty exact subset, bound into the Grant policy digest. The adapter constructs a new dictionary from only those approved keys. It never serializes the complete decrypted section. The typed response inventories all possible V1 fields as optional; `exclude_unset` omits unapproved fields entirely while preserving an approved rating whose source value is null. No caller-selected fields query exists. An ordinary Evaluation schema addition does not enter this pinned inventory or expand old policy digests. Tests inject a future ordinary field and prove omission; a policy naming that unknown field denies before decryption.

Evaluation response fields are `grant_id`, `grant_version`, `policy_version`, `disclosure_policy_version`, fixed `projection`, selected `routine_interview_id`, and the approved `evaluation` field object. It includes no Intake, Inventory, unselected source, general Routine detail or extra professional narrative.

## Revision and historical integrity

CONT-2A's marker algorithms remain unchanged and are shared through source-owned helpers: Encounter `updated_at` ISO marker; Routine SHA-256 over Routine and linked Encounter `updated_at` markers. Request/approval structural selectors still do not load ciphertext. At every read, locked source-owned structural revisions must equal the sealed approved scope. Changes deny with 409 or lifecycle/identity 404; scopes are never silently rebound or refreshed. Ordinary source services preserve immutable historical author identity and update revisions on material changes. This is not tamper resistance against a privileged database owner rewriting records, timestamps and provenance together.

Source reads perform no ownership, timestamp, Appointment, Routine link, College responsibility or Grant state writes. Only the authorized-read Audit event is appended. Ordinary source reads/writes keep their existing capabilities and author predicates, even for a receiver who can read this selected projection.

Referrals, Follow-Ups, Student Intake, Inventory/Support detail, Student Session Summary, assessments, recordings/transcripts, messages, credentials and bulk exports have no continuity adapter, allowed kind or route here. Any later category/field/version requires its own institutional evidence, source-owned adapter and tests; it cannot inherit authority from these two projections.
