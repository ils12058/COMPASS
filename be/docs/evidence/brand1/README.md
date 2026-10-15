# BRAND-1 static UCN document branding

BRAND-1 replaces the composed masthead and recognition artwork with the exact office-supplied PNGs. It extends the existing Chromium/pypdf report overlay to every registered document, so each physical PDF page receives one header and, when configured, one recognition strip. Body text remains selectable and dynamic.

Base: `staging` at `ea2e5b80bd9356ec343198f2725128b0ce4602d3` (fetched 15 October 2026).

## Artwork and A4 geometry

| Packaged original | Pixels | Width in PDF | Proportional height | SHA-256 |
|---|---|---|---|---|
| `header.png` | 6473 × 1083 RGBA | 210 mm | 35.13 mm | `daba7f6bc9cfd03814debe00cb180a642447a5f7209734deac2a223c9b0ffad2` |
| `footer-logos.png` | 6614 × 500 RGBA | 210 mm | 15.88 mm | `86ba43c33f19c3b9e478de28cce48851a093023b9adc103b14297bb0aab2e8b0` |

The attached files have higher resolution than the brief's nominal 2048-pixel dimensions. Their bytes, text, colors, and aspect ratios are unchanged. Header placement begins 5 mm below the top page edge, leaving blank paper above the complete supplied image. The recognition image ends 14 mm above the bottom edge; the bold form code and revision are stacked beneath it, with page numbering aligned separately at the right. Neither image adds a CSS separator.

A4 portrait is 210 × 297 mm. PDF body margins reserve 45 mm above and 34 mm below on every page. Standard body side margins are 25 mm; the report retains its previous 174 mm table width with 18 mm side margins. Inventory uses a 190 mm print box with 5 mm inner gutters around its existing 180 mm source body. This keeps its wider sibling-table rules inside the print box. Its three dedicated source sections remain bounded at 217 mm, within the 218 mm available body height. The existing value-fitting/truncation rules and three-page rejection check remain active.

Physical printers may trim page-edge artwork or apply scaling. Review at actual size with an A4-capable printer; institution approval is needed before changing the artwork for printer-specific safe areas. This change preserves the requested full-width PDF design.

## Registered template coverage

Every row uses the same repeated static PDF header. The optional `include_accreditation_footer: bool = False` mechanism remains in `DocumentTemplateSpec`; individual registered official templates opt in. The HTML partials also use the same packaged images. During PDF rendering, an internal shell flag suppresses in-flow artwork and HTML metadata to prevent duplicates; a single reusable overlay supplies artwork and Chromium supplies actual page counters.

| Template key (version 1) | Layout family | Recognition footer | Dynamic identity | Pagination | Kind |
|---|---|---|---|---|---|
| `individual_inventory` | Standard letterhead | Enabled | Bound historical Form Revision | Exactly 3; current/total on every page | Controlled official form |
| `exit_interview` | Standard letterhead; dedicated template | Enabled | No supported controlled binding; no code/revision invented | Natural flow; normal synthetic sample 3 pages | Official questionnaire |
| `referral_slip` | Compact form | Enabled | Saved controlled-form provenance | Natural flow; long reasons/remarks continue | Controlled official form |
| `call_slip` | Compact form | Enabled | Saved issuance provenance | Natural flow; normal/long-name samples 1 page | Controlled official form |
| `good_moral_current_student` | Certificate | Enabled | Saved issuance Form Revision | Natural flow; normal sample 1 page | Controlled official form |
| `good_moral_graduate` | Certificate | Enabled | Saved issuance Form Revision | Natural flow; normal sample 1 page | Controlled official form |
| `student_profiling_report` | Report | Enabled, as previously | Existing report scope/date label; no form code invented | Natural table flow and repeated table heads | Report |
| `foundation_test` | Report | Enabled, as previously | Caller fixture metadata when present | Multipage fixture | Internal test fixture |
| `foundation_test_no_footer` | Report | Disabled, as previously | Caller fixture metadata when present | Multipage fixture, no recognition image | Internal test fixture |

## Compatibility and security

`CanonicalDocumentBranding`, its singleton/getter, current `document_branding` injection, redundant office-heading partial, individual logos, and obsolete masthead/contact-icon CSS were removed. Local packaged resources, registry control, Django autoescaping, JavaScript/service-worker restrictions, remote HTTP(S) resource denial, render timeouts, PDF validation, permissions, confidential projections, audit events, and controlled-form consumers remain in place.

No migration was added, deleted, or rewritten. The historical branding-removal migration chain and `document_branding.updated` audit action remain intact. No form code, revision, saved record identity, questionnaire text, answer mapping, endpoint, retention rule, secret, or deployment configuration changed. Metadata remains derived from the consumer's supported current or historically bound revision. Caller-provided branding/asset overrides cannot replace the trusted assets. Footer identity and report labels are escaped independently of the HTML body.

## Reproduce synthetic visual evidence

Fixtures in `samples/` contain synthetic data from the existing domain PDF tests, plus explicit long-content variants. The large profiling-report fixture is a compact recipe referencing the existing pure synthetic scenario; its generated render context was checked for exact equality with the captured baseline context. They do not load records or require database/Redis services. Dates and times are restored from JSON before rendering, so certificate, Referral, and Call Slip date fields remain populated.

From `be/`, with the locked backend dependencies, installed Playwright Chromium and Poppler:

```sh
.venv/bin/python docs/evidence/brand1/render_samples.py --output /tmp/brand1-pdfs
```

This writes every sample PDF, a PNG for every page, and a page-count manifest. It checks A4 geometry, Inventory's exact three pages, one current/total page label per page, and the expected image count including footer opt-out. `--no-previews` omits Poppler conversion when only PDF generation is needed.

The committed previews show all three Inventory pages and before/after and continuation-page comparisons. Full-resolution synthetic PDFs and every-page PNGs are included in the owner handoff bundle. Automated PDF tests additionally measure image transforms (width, aspect ratio, edge position), body/metadata baselines, historical identifiers, and missing/unknown asset failures; filename-only HTML assertions are not used as layout proof.

## Source compatibility follow-ups

- The newly supplied UCN Exit Interview DOCX renders as three pages. Its self-assessment continues onto page 2, while COMPASS's existing normal sample fits self-assessment on page 1. The supplied specimen omits COMPASS's existing Program Chair group and contains inconsistent rating cells. BRAND-1 preserves the existing 15 self-assessment rows, 26 feedback rows, seven categories, and answer mappings. Its normal sample grows from two to three pages because branding space is now reserved on every page; matching the specimen's exact structure remains a separate compatibility decision.
- The supplied UCN Call Slip DOCX reports two pages and includes an explicit page break; COMPASS's existing saved Call Slip remains its supported workflow/template. Exact specimen reconstruction is outside BRAND-1.
- UCN F1 Parent Notification, F7 Routine Interview, and F8 Confidentiality Agreement do not receive new PDF endpoints or workflows here.
- The artwork spells the office name “Counselling”; existing UI terminology uses “Counseling.” The supplied artwork is preserved.
- Official UCN code/revision migration remains FORM-ID-1. Historical CNSC identities continue to print as saved.

The owner-supplied Referral PDF confirms stacked form identity and blank space before the institutional header. BRAND-1 follows that placement while preserving historical identity values; the newer UCN identity shown in the reference is not substituted for a stored CNSC revision.

## Validation record

Validation uses an isolated local PostgreSQL test database and Redis instance, with the repository's test settings and ephemeral encryption keys. No deployment services or secrets are used.

Commands run from `be/` (the test environment sets `POSTGRES_PORT=55432` and Redis URLs on local port `56379`):

```sh
uv lock --check
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m compileall -q compass tests
.venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings
.venv/bin/python manage.py check --settings=tests.settings
# Broader controls/provenance regression run:
.venv/bin/pytest tests/test_documents.py tests/test_documents_migrations.py tests/test_inventory_documents.py tests/test_exit_interview_documents.py tests/test_referrals.py tests/test_call_slips.py tests/test_good_moral.py tests/test_good_moral_preparation.py tests/test_call_slip_issuance_provenance.py tests/test_referral_call_slip_lifecycle.py tests/test_student_profiling_pdf.py --reuse-db -q
# Final affected recheck after display corrections, using a fresh seeded database:
.venv/bin/pytest tests/test_documents.py tests/test_inventory_documents.py tests/test_exit_interview_documents.py tests/test_good_moral.py::test_saved_render_provenance_drives_html_after_current_data_and_revision_change tests/test_good_moral.py::test_real_chromium_smoke_renders_issued_graduate_certificate tests/test_call_slips.py::test_call_slip_pdf_instruction_matches_saved_destination_and_release_policy tests/test_referrals.py::test_referral_pdf_keeps_source_identity_safe_filename_and_fail_closed_release --create-db -q
.venv/bin/python docs/evidence/brand1/render_samples.py --output /tmp/brand1-pdfs
```

The exact final results and sample counts are recorded in `validation.json`. Frontend checks are unnecessary because no frontend files change. The PR is for owner review; it does not merge or deploy.

Signature presentation follows the owner's review correction: a Good Moral signatory's printed name is placed above its signature rule, with the role beneath it. Printed signature names in both Good Moral variants, Referral Slips, and Call Slips use uppercase through Django's escaped presentation filter. Saved names and issuance/referrer provenance retain their original values and casing.

Both Good Moral variants retain short underlined receipt-number, date, and amount fields (30 mm minimum), including blank fields. Populated values print above the same rules.

## Visual preview index

- Inventory: [page 1 before/after](previews/individual_inventory-comparison-1.png), [page 2 before/after](previews/individual_inventory-comparison-2.png), [page 3 before/after](previews/individual_inventory-comparison-3.png).
- [Referral Slip](previews/referral_slip-comparison-1.png), [Call Slip](previews/call_slip-comparison-1.png), [Good Moral Current Student](previews/good_moral_current_student-comparison-1.png), [Good Moral Graduate](previews/good_moral_graduate-comparison-1.png).
- [Signature and receipt detail](previews/signature-and-receipt-detail.png): uppercase printed name above the rule, role below it, and three aligned fill-in rules. All rules start after the shared longest-label column (Official Receipt No.).
- [Exit Interview before/after](previews/exit_interview-comparison-1.png) and [all three current pages](previews/exit_interview-1.png).
- [Profiling report before/after](previews/student_profiling_report-comparison-1.png) and [first, middle, final pages](previews/report-continuations.png).
- [Footer-free fixture on all pages](previews/foundation_test_no_footer-1.png).
- Long Referral content: [pages 1–4](previews/referral-long-content-1.png), [page 5](previews/referral-long-content-2.png).

The synthetic stress report grows from 34 to 42 pages because its continuation pages now reserve the complete header as well as the footer. Its table width, content, and repeated table heads remain intact. The 90-row foundation sample grows from 3 to 4 pages. Neither has a fixed page-count contract. All 16 samples total 79 A4 pages; none is blank or footer-only.
