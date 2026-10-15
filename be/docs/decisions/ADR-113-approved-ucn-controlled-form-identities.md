# ADR-113: Approved UCN controlled-form identities

- Status: Accepted
- Date: 2026-10-15
- Scope: FORM-ID-1; supersedes the active identities in ADR-063 and the unconfirmed F7/F9 identity decisions in ADR-023/ADR-031. Those documents remain historical records.

## Authority and identity mapping

The project owner confirmed that the nine supplied UCN DOCX specimens are institutionally approved. Those specimens govern official identity and wording. Existing CNSC code and templates are compatibility baselines. Branding alone does not establish document identity.

| Family | Active official identity | Internal answer schema | Rendering version |
|---|---|---:|---:|
| call_slip | UCN-OP-GCO-01F2, Revision 2 | 1 | 2 |
| referral_slip | UCN-OP-GCO-01F3, Revision 1 | 1 | 2 |
| good_moral_current_student | UCN-OP-GCO-01F4, Revision 1 | 1 | 2 |
| individual_inventory | UCN-OP-GCO-01F5, Revision 1 | 1 | 1 |
| good_moral_graduate | UCN-OP-GCO-01F6, Revision 1 | 1 | 1 |
| routine_interview | UCN-OP-GCO-01F7, Revision 1 | 1 | No PDF workflow |
| exit_interview | UCN-OP-GCO-01F9, Revision 1 | 2 | 2 |
| customer_feedback | CNSC-OP-GTA-01F14, Revision 0 | 1 | Unchanged |

F2's filename says Revision 1 but its printed footer says Revision 2. The printed Revision 2 is authoritative. Official revision, internal answer schema, and rendering version are independent numbers. F2 does **not** acquire answer schema 2 because its official revision is 2.

F1 Parent Notification Letter and F8 Staff Confidentiality and Data Privacy Agreement remain source-only documents. Neither creates a workflow. No approved UCN F14 was supplied; Customer Feedback retains CNSC F14 Revision 0, including optional respondent identity.

## Activation and history

The canonical registry retains the five superseded CNSC identities as supported, inactive definitions. Explicit `sync_institutional_forms` creates missing legacy and UCN rows, retires obsolete active rows, and activates exactly one canonical identity for each family. Fresh databases do not depend on a preexisting CNSC row. Unknown rows remain retained and inactive after synchronization.

Read/render compatibility requires the exact family, official code, official revision, and internal schema. New-record resolution additionally requires a canonical definition marked active. A retired CNSC row manually left active is rejected for new creation and shown as an invalid active configuration. Reconciliation must not rewrite a persisted schema version under the same official identity; a conflict requires operator investigation. It is not safe to change saved identity through metadata repair.

Existing records keep their saved revision FK. Reprints resolve that saved identity and supported presentation, not today's active revision. Good Moral additionally retains its saved renderer key/version. Unknown identities fail closed in official PDF consumers. No global replacement, historical migration rewrite, or institutional-record backfill is performed.

## F7 and F9 ownership

New scheduled and direct Routine Interviews require the active supported F7 revision. Existing null revision records remain null and readable under their existing behavior. The approved Questions 1–7, concern options, six 1–10 ratings, other-adjustment text, recommendations, assigned Counselor and Student boundaries fit answer schema 1. No Routine PDF is introduced.

Exit Interview gains a nullable protected `FormRevision` FK through additive migration `0005_saved_form_revision`. There is no default and no data backfill. The existing-record return path precedes active-revision lookup, preserving historical drafts and correction access when current configuration changes.

The approved F9 omits the legacy Program Chair category (three ratings and its comment). New UCN F9 therefore uses internal schema 2: 15 self-assessment ratings and 23 College feedback ratings across six categories. Unlabelled legacy records retain all 26 feedback ratings across seven categories. Both use the unchanged Section III 0–5 numeric range; zero receives no invented semantic label. Legacy model choices and encrypted fields remain available.

Validation, PDF projection, and frontend category/completion/submission behavior follow the saved contract. The API returns its saved revision and applicable feedback item codes; clients cannot select or mutate revision ownership. UCN records reject legacy-only answers rather than silently discarding them. Reopening and resubmission retain identity. Student/Counselor authorization and confidential content encryption are unchanged.

## Source presentation

UCN F2 has its own presentation retaining the source instruction, reference-number line, interview start/end, Student signature, purpose checkboxes, receipt/attendance remarks table, and status line. Fields that the digital schema does not capture stay blank for paper completion; they are never inferred from report time, referral content, lifecycle state, or account identifiers. The existing destination and recorded interview end remain projected. This does not add a purpose/receipt capture workflow.

UCN F3 retains source signature wording and date/time/action fields. UCN F4 removes the extra course insertion between College and major, which is not present in the approved specimen. Legacy templates remain available for CNSC reprints. F5 and F6 reuse compatible answer projections and layouts. UCN F5 restores the source headings “UNIQUE FEATURES” and “PERCEPTIONS” while legacy headings remain unchanged. F5 keeps its approved “MODE OF TRANSPORTATION TO AND FROM CNSC” wording, and F9 keeps its approved CNSC self-assessment wording.

Repeated institutional artwork is drawn above Chromium page backgrounds in reserved margins; opaque continuation-page backgrounds must not mask the masthead/footer. This is a rendering correction, not a layout redesign.

Exact Word typography and duplicate-copy imposition remain DOC-TPL-1 concerns. F2's source contains two duplicate copies whose footers each say Page 1 of 1; COMPASS emits one record copy per PDF. The F2 source masthead spells “COUNCELLING”; shared institutional artwork uses “COUNSELLING”. This spelling discrepancy is recorded, not treated as a change to the approved body wording. The source Word pagination also varies under LibreOffice (F7 2 pages and F9 3 pages despite Page 1 of 1 footers). Generated PDFs use their actual page counts. These presentation differences do not remove questions, ratings, receipts, signatures, or identity. Any further source-layout changes require DOC-TPL-1 coordination.

## Bootstrap and release

Deployment order remains: migrate, sync identity policy, sync canonical services, sync institutional forms, sync organization catalog where required, check. Deploy backend and frontend contracts together for F9. Validate fresh initialization, demo seeding, creation and official rendering before owner-authorized reset/deployment. No reset, deployment, merge, key provisioning, or production operation is authorized by this decision.

The initial base `40492b1aacca7b608c1cf8bc0a4aef618d9d78f1` and updated audited staging base `d6ce342dab9b5721b38d508984c7785152453078` have inherited CI formatting/shard-coverage failures and a fresh demo-seeder Graduate Tracer classification failure. These require the owning GTS/CI workstream before release. See the implementation evidence and reset checklist in `outputs/FORM-ID-1-Implementation-Report.md`.
