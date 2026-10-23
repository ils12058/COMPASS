# Rename verification and history disposition

The mandatory [127-file CONT-0 inventory](../cont-0/rename-inventory.csv) was reconciled against starting SHA `0ba5024a8468b3e27b2b1b3723cf431bf0390f61` before editing. [Disposition CSV](rename-disposition.csv): 61 transformed files, 10 renamed files, 3 Context surfaces already removed/preserved by CONT-1A, 32 preserved historical files, and 21 historical ADR/frontend reports annotated with supersession links. Files added since CONT-0, especially CONT-1A regression tests, were included in the final source scan as well.

Canonical resource mapping:

| Contract | Current canonical value |
| --- | --- |
| Model / table / reverse | `StudentSessionSummary` / `counseling_studentsessionsummary` / `student_session_summary` |
| Services / content | `student_session_summaries.py` / `student_session_summary_content.py` |
| Ciphertext constraint | `student_session_summary_ciphertext_present` |
| Schemas and operations | StudentSessionSummary / StudentSessionSummaries identifiers in exported OpenAPI |
| Safe errors | `student_session_summary_not_found`, `_already_published`, `_empty`, `_content_unavailable` |
| Capabilities | `student_session_summaries.view_self`, `.view_assigned`, `.manage_assigned` |
| Publication event | `STUDENT_SESSION_SUMMARY_PUBLISHED` / `counseling.student_session_summary.published` |
| Notification source / target | `student_session_summary` / `STUDENT_SESSION_SUMMARY` |
| Future Audit target | `counseling.studentsessionsummary` |
| Templates | `student_session_summary_published.html` and `.txt` |
| Setting / file convention | `STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS[_FILE]` |
| Secret source | `student_session_summary_encryption_keys` |
| Authenticated identities | `student_session_summary_id` + `encounter_id` |
| Rotation | `rotate_student_session_summary_encryption` |
| Frontend | `student-session-summary-section.tsx`, `student-session-summaries.tsx`, `/portal/counseling/student-session-summaries/[summaryId]` |
| Backend tests | `test_student_session_summaries.py`, `test_student_session_summary_encryption.py`; new contract/cutover suites |

The broad end-of-change scan includes case-insensitive model/CamelCase, snake case, hyphenated resource strings, display terminology and old frontend paths, including hidden CI/configuration files. Every remaining matched file is listed with line numbers and a reason in [historical-reference-allowlist.csv](historical-reference-allowlist.csv). This is a source snapshot; line numbers may move in later changes.

Permitted references do not create aliases: immutable baseline schema; frozen old-format oracle; historical ADR/audit/validation/UAT evidence; explicit negative tests and stale fixtures; the offline historical-schema preflight tool; one-time migration guards; and the policy synchronizer's refusal of unconverted database rows. The cutover documents necessarily identify retired names. The old ordinary modules, API operations/routes, frontend detail route, runtime capability checks, producer identifiers, settings fallback and dual-binding reader are absent. No unrelated use of the word shared was renamed.

CI counseling selection now includes the two renamed suites and new contract/cutover suites. Existing duration keys follow renamed filenames; new measured timing values are recorded only after actual final test execution. Generated Orval clients are regenerated from the exported backend contract and remain excluded from Git.
