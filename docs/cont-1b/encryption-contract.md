# Encryption contract

`STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS` is required. The standard file-backed convention is `STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS_FILE`; source secret `student_session_summary_encryption_keys` is mounted through the repository inventory for applicable web/worker/Beat services. Configuration parsing preserves key order: first encrypts, all decrypt. Missing, malformed, repeated or empty entries fail safely. There is no old setting fallback. Fresh databases require no previous summary secret.

All later purpose-key declarations in `config/settings.py` now compare against the canonical ring. Separation covers Django/TOTP/Push, Routine, Referral, Exit, Inventory, Tracer, profile, feedback, messages, assessments and Follow-Ups. No real values were read or provisioned; tests use only synthetic rings.

The new resource format is version **1**, an exact authenticated JSON envelope:

```json
{"schema_version":1,"student_session_summary_id":"UUID","encounter_id":"UUID","payload":{"content":"text"}}
```

The resource identity and Encounter identity are inside authenticated plaintext. The new format requires the exact envelope and payload keys and types. Unicode/whitespace survive; NUL and invalid UTF-8 representations are rejected. Empty drafts are allowed; nonblank content is required to publish. Missing/corrupt/wrong-key/unsupported-version/wrong-identity tokens raise a generic `student_session_summary_content_unavailable` failure after authorization, never an empty-body substitute. No plaintext, ciphertext or key values belong in generic logs or Notification/email/Push/audit payloads.

The former `counseling_shared_summary_id` envelope is deliberately incompatible even if encrypted with a key supplied to the new ring. The frozen ADR-080 oracle is unchanged and is used only in tests to prove both directions are incompatible. Rotating an old token under a different primary key still leaves it incompatible.

`rotate_student_session_summary_encryption` verifies canonical identities/payload before rotating. It retains dry-run verification, UUID-ordered bounded batches (1–1000), row locks, safe bounded failures, interruption/resume and original Fernet timestamp. Rotation changes only ciphertext: no publication, business timestamp, Notification or Audit mutation. It is **not** an envelope converter. A retained-data converter is not supplied by this disposable-data slice and needs independent review/rehearsal using the original ring.

A code-only rollback cannot recover a changed table, binding or persisted capability identity. Preserve the recovery unit in the [cutover runbook](migration-and-cutover.md), including protected former keys required to interpret historical backups. Old secrets are never active runtime aliases.
