# COMPASS-DOC-1 Implementation Report

## Release details

- Base branch: `staging`
- Evidence baseline SHA: `ccf2122b3ad248ce3b9a4f833da4d3a2024320d8`
- Rebased staging SHA: `00cdbddb84c97e91a0e6c4fe622b1baa148de2da`
- Implementation branch: `codex/doc-1-reports-email-refinement`
- Implementation code commit SHA: `54b7a47371dbcf801b41a359eb0d6393e7e52a2c`
- Pull request: [#280](https://github.com/ils12058/COMPASS/pull/280)
- Merge and deployment: not performed

## Architecture audit

| Area | Current contract | DOC-1 boundary |
| --- | --- | --- |
| Student Profiling | `build_student_profiling_report` owns population, scope, coverage, reconciliation, denominators, percentages, and advisory disclosure warnings. PDF and XLSX renderers consume this aggregate; the PDF validates reconciliation before printing. | Presentation-only changes in `reports/pdf.py`, the Student Profiling report templates, and `reports/xlsx.py`. No aggregate builder or policy changes. |
| Graduate Tracer | The builder selects submitted schema-v1 responses and produces aggregate sections. XLSX output is aggregate-only and retains academic filters, denominator labels, multi-selection meaning, and disclosure restrictions. | Workbook layout and presentation only. No raw response data, aggregate-builder changes, or PDF generator. |
| Email rendering | `render_email` renders HTML and text alternatives from paired Django templates and shared shells. Notification templates receive a code-owned subject and no notification or source-record context. | Shared shell and paired message-template changes only. SMTP, recipient selection, event catalog, retries, and delivery code stay unchanged. |
| Privacy and security | Student Profiling prints exact aggregate counts with advisory warnings. Counseling notifications avoid case details. Authentication messages retain OTP purpose, expiry, and account-security instructions. | Preserve warnings and sparse sensitive-event content; add no personal data, private links, or contact addresses. |
| Sender and replies | Live `DEFAULT_FROM_EMAIL` is deployment-configured. The mail adapter has no reply-to override; the monitored status of the deployed sender cannot be confirmed from this checkout. | Add no unverified “do not reply” claim or invented contact information. |

## Student Profiling

- PDF: added a compact executive summary using the canonical submitted Inventory and coverage counts, moved methodology notes after the distribution tables, and retained detailed population, reconciliation, filter, disclosure, and appendix content.
- XLSX: moved profile population and coverage figures to a visible Key Figures section, added canonical recorded College and Program counts, kept reconciliation and privacy notices, placed methodology notes after the Program legend, and added wrapped row heights, wrapped long Program headers, repeated identifiers, and explicit print settings.
- Category worksheets retain numeric count and percentage cells, existing sheet names, freeze panes, filters, data ordering, and denominator rows. Printed wide tables paginate horizontally at 100% scale with identifier columns repeated.

## Graduate Tracer

- XLSX: brought the respondent count to the top of Summary, labeled methodology notes, highlighted disclosure warnings, wrapped long category labels, and added A4 landscape print setup.
- The existing five-sheet structure, aggregate-only output, schema version, submission period, classification filters, denominator labels, multi-selection flag, exact counts, percentages, and empty-report handling are retained.

## Transactional emails

- Replaced the large maroon banner, framed card, and cream background with a white, text-led institutional shell using modest COMPASS branding, office identification, subtle dividers, and mobile spacing.
- Plain-text messages now show the same institutional identity before the message and a concise automated-message footer.
- Added clearer event-specific review steps and official-channel help guidance for appointment, Call Slip, Good Moral, Guidance Follow-Up, E-Counseling consent, and Group Session messages. HTML and text wording remain paired.
- Authentication workflows, event subjects, event catalog, recipient context, sender settings, and delivery behavior are unchanged. Existing OTP and security warnings are preserved.

## Statistical, privacy, and security contracts

- No aggregate calculation, denominator, percentage, filter, report access, schema, release audit, or disclosure policy was changed.
- No Student identity, Graduate Tracer response, counseling detail, internal record ID, token, or privileged link was added to email or report output.
- Small-population warnings remain visible, and report values remain exact and unsuppressed.
- No changes were made to shared `documents/static/documents/css/print.css`, `.generated-value`, Good Moral printing, E-Counseling components, availability, filters, or portal navigation.

## Files modified

- Report presentation: `be/compass/reports/pdf.py`, `be/compass/reports/xlsx.py`, `be/compass/reports/graduate_tracer_xlsx.py`, and `be/compass/documents/templates/documents/reports/student_profile.html`.
- Shared email presentation: `be/compass/common/templates/compass/email/base.html` and `base.txt`.
- Paired transactional message templates under `be/compass/notifications/templates/notifications/email/`: `appointment_cancelled`, `appointment_reassigned`, `appointment_reminder`, `appointment_rescheduled`, `appointment_scheduled`, `call_slip_issued`, `call_slip_voided`, `ecounseling_consent_requested`, `good_moral_issued`, `good_moral_request_initiated`, `group_session_update`, and `guidance_followup` (`.html` and `.txt` for each).
- Regression coverage: `be/tests/test_student_profiling_pdf.py`, `be/tests/test_student_profiling_xlsx.py`, `be/tests/test_graduate_tracer_xlsx.py`, `be/tests/test_transactional_email.py`, and `be/tests/test_notification_delivery.py`.
- Review record and synthetic visual evidence: this report and files under `docs/evidence/doc-1/`.

## Evidence and validation

All evidence uses synthetic records and values. Student Profiling “before” output was generated from the evidence baseline revision above; “refined” output was generated from this branch, rebased on the listed staging SHA. Workbook print views were rendered through LibreOffice. Email HTML previews were rendered locally in Chromium; plain text is shown separately. No real accounts, responses, credentials, or communications were used.

- Student Profiling PDF: [overview comparison](docs/evidence/doc-1/pdf/student-profiling-overview-comparison.png), [distribution comparison](docs/evidence/doc-1/pdf/student-profiling-distribution-comparison.png), [long-table comparison](docs/evidence/doc-1/pdf/student-profiling-long-table-comparison.png), [baseline PDF](docs/evidence/doc-1/pdf/student-profiling-before.pdf), [refined PDF](docs/evidence/doc-1/pdf/student-profiling-after.pdf).
- Student Profiling XLSX: [Summary comparison](docs/evidence/doc-1/student-xlsx/student-profiling-summary-comparison.png), [category comparison](docs/evidence/doc-1/student-xlsx/student-profiling-category-comparison.png), [long-table comparison](docs/evidence/doc-1/student-xlsx/student-profiling-long-table-comparison.png), with [baseline workbook](docs/evidence/doc-1/student-xlsx/student-profiling-before-synthetic.xlsx) and [refined workbook](docs/evidence/doc-1/student-xlsx/student-profiling-after-synthetic.xlsx).
- Graduate Tracer XLSX: [Summary print view](docs/evidence/doc-1/graduate-tracer/graduate-tracer-summary.png), [long-label distribution view](docs/evidence/doc-1/graduate-tracer/graduate-tracer-long-label-distribution.png), and [synthetic workbook](docs/evidence/doc-1/graduate-tracer/graduate-tracer-synthetic.xlsx).
- Transactional emails: [appointment reminder](docs/evidence/doc-1/email/appointment-reminder-comparison.png), [Good Moral issued](docs/evidence/doc-1/email/good-moral-issued-comparison.png), [E-Counseling consent](docs/evidence/doc-1/email/ecounseling-consent-comparison.png), [security password change](docs/evidence/doc-1/email/security-password-changed-comparison.png), and the [plain-text alternative](docs/evidence/doc-1/email/appointment-reminder-plain-text.png) ([text file](docs/evidence/doc-1/email/appointment-reminder-after.txt)).

Validation:

- `uv run ruff check` on the changed Python source and test files — passed.
- `uv run ruff format --check` on the changed Python source and test files — passed.
- `git diff --check` — passed.
- After rebasing on staging, `tests/test_student_profiling_xlsx.py tests/test_graduate_tracer_xlsx.py tests/test_transactional_email.py tests/test_notification_delivery.py tests/test_notifications.py` — 208 passed.
- After rebasing on staging, `tests/test_student_profiling_pdf.py::test_real_chromium_pdf_pagination_footer_and_structure[two_programs]` — 1 passed.
- A combined PDF/report regression run processed 92 tests without failures before the Graduate Tracer XLSX test exposed a test-only numeric-versus-string page-size assertion. The long process was stopped during the later OTP tests to reduce load while concurrent browser and TypeScript work was running. The assertion was corrected, the Student Profiling and Graduate Tracer workbook files were rerun, and the email and delivery files were rerun independently; all focused reruns above passed. No report-generation, aggregate, or privacy test failure was reported in the interrupted run.
- Synthetic PDF and XLSX print outputs were rendered and visually inspected. Email templates were rendered in local Chromium previews.

## Known limitations and deferred work

- Gmail, Outlook, and Apple Mail were not available as live rendering clients; compatibility claims will be limited to deterministic template checks and local previews.
- Deployment-specific sender address and reply monitoring could not be verified from repository configuration. The templates do not claim replies are unmonitored.
- Cell suppression policy remains outside this presentation change and still requires institutional review.
- A Graduate Tracer PDF, public portal deep links, and richer email event context remain out of scope.

## Concurrent-worktree assessment

The changes are limited to report presentation, report tests, shared email shells, and paired transactional email templates. No files owned by the concurrent E-Counseling/Good Moral print, availability, or floating-filter work were changed. The shared print stylesheet was not edited.
