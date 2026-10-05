# Record retrieval and historical filtering

Branch: `codex/record-retrieval-history`.
Base: `staging` at `6a6bb887284f18f284586e0d56b404e05f8f7bb4`.
The audited base in the request had moved by the command palette change; this slice
uses the current staging contracts and portal composition. Merge requires review
and a subsequent explicit instruction.

## Backend contracts

All paths below are GET operations under `/api/v1`.

| Operation | Path | Change |
| --- | --- | --- |
| `appointmentsListMy` | `/appointments/me` | Optional `search` string; self collection and existing filters retained. |
| `availabilityListProviders` | `/availability/providers` | Existing search now handles tokens across first, middle, last name, and email. |
| `availabilityGetProvider` | `/availability/providers/{provider_id}` | New UUID lookup returning the existing `AvailabilityProviderSummary`; typed 401/403/404/422 responses. |
| `routineInterviewsListAssigned` | `/routine-interviews` | Existing search also matches the linked Appointment reference and tokenized Student identity. |
| `counselingListMyEncounters` | `/counseling/me/encounters` | Optional `search`; list Student projection adds nullable `institutional_id`. |
| `goodMoralListRequests` | `/good-moral/requests` | Optional UUID `form_revision_id`; search includes Official Receipt; operational summary adds `official_receipt_number`; revision metadata. |
| `referralsList` | `/referrals` | Optional UUID `form_revision_id` and revision metadata. |
| `callSlipsList` | `/call-slips` | Optional UUID `form_revision_id` and revision metadata on the operational collection. |
| `inventoryListStudents` | `/inventory/students` | Optional UUID `form_revision_id` and revision metadata for the authorized roster and selected Academic Year. |
| `feedbackListCustomerFeedbackResponses` | `/feedback/customer-feedback/responses` | Optional UUID `form_revision_id` and revision metadata. |

The five revision-enabled responses expose
`filter_options.form_revisions: FormRevisionFilterOption[]`. Each option contains
only `id`, nullable `official_code`, and nullable `official_revision`.
`EncounterCollectionStudent` and `CounselingEncounterCollectionItem` keep the
Institutional ID addition confined to the encounter collection. The shared identity
schema and encounter detail response retain their existing fields. Student Good
Moral and My Call Slips responses are not expanded with operational metadata.

The canonical `contracts/openapi.json` was exported with `manage.py export_openapi`;
Orval bindings were regenerated using `pnpm api:generate`. Generated client files
were not edited manually.

## Search semantics

| Collection | Matching behavior |
| --- | --- |
| My Appointments | Trimmed, case-insensitive substring of `reference_code` only, after self scope and before pagination. No Student/provider identity search. |
| Provider directory | Every whitespace-separated token must match at least one of first/middle/last name or email. Existing 254-character normalization is retained. |
| Assigned Routine Interviews | Every token must match Student first/middle/last name, Institutional ID, or linked Appointment reference. Assignment scope and existing filters still apply. |
| My Counseling encounters | Same identity/reference token semantics, restricted to the current Counselor's encounters. Direct encounters remain searchable by Student identity. |
| Operational Good Moral | The complete trimmed string matches the Official Receipt number, OR every identity token matches Student names, Institutional ID, or applicant name snapshot. Blank receipts do not match a nonempty receipt search. |
| Referrals, Call Slips, Inventory, Customer Feedback | Existing domain search semantics are retained and compose with the exact revision filter. Customer Feedback still searches respondent name only. |

New Appointments and encounter search and the existing Routine Interview/Good Moral
search reject input longer than 160 characters. No confidential intake, evaluations,
Counseling notes, Referral reasons, feedback text, or encrypted content is searched.

## Revision options and authorization

Collection metadata (Option A in the request) avoids a separate configuration API
and uses the same successful, authorized response as the records. The small shared
helper in `compass/institutional_forms/filter_options.py` projects safe revision
identity; each domain supplies its already-authorized record queryset and permitted
form families.

Options are computed before search, pagination, lifecycle, and other narrowing
filters, so an empty search result does not remove meaningful historical choices.
Only revisions represented by authorized records are included; status and active
renderer compatibility are not conditions for historical retrieval. Good Moral
uses both Current Student and Graduate families and preserves separate UUIDs even
when labels coincide. Variant selection does not narrow these choices.

Inventory options additionally use the selected Academic Year and the same scoped
Student population as its current roster or historical records. Its current roster
uses a correlated existence check on both Student and Academic Year, preventing a
revision on another year's Inventory from matching. Exact revision filters exclude
MISSING rows and Good Moral requests whose stored revision is null. There are no
"No revision" or "Pending revision" pseudo-options.

Existing capabilities, role restrictions, inherited organization scope, Counselor
assignment, and Student self scope remain authoritative. Options never require
`institutional_forms.view`. Unauthorized records contribute neither rows nor
revision choices. The provider summary requires `availability.manage` and uses the
same eligibility queryset as the directory: Counselors (including inactive accounts)
and legacy Guidance Services Staff with existing Availability configuration. Other
accounts return 404 after authorization; existing mutation rules remain authoritative.

## Frontend routes and components

Paths in this table are relative to `fe/src`; generated hooks are used throughout.

| Route | Changed component or route source |
| --- | --- |
| `/portal/appointments/my` | `features/appointments/appointments-my-page.tsx` |
| `/portal/availability/providers` | `features/availability/availability-pages.tsx` |
| `/portal/availability/providers/[providerId]` | New `app/(portal)/portal/availability/providers/[providerId]/page.tsx`; `ProviderAvailabilityDetailPage` and existing workspace in `availability-pages.tsx`. |
| `/portal/routine-interviews` | `features/routine-interviews/routine-counselor-workspace.tsx` |
| `/portal/counseling` | `features/counseling/counselor-encounters.tsx` |
| `/portal/good-moral` | `features/good-moral/good-moral-operational-list.tsx`; `app/(portal)/portal/good-moral/page.tsx` |
| `/portal/referrals` | `features/referrals/referrals-page.tsx`; `app/(portal)/portal/referrals/page.tsx` |
| `/portal/call-slips` | `features/call-slips/call-slips-page.tsx`; `app/(portal)/portal/call-slips/page.tsx` |
| `/portal/inventory` | `features/inventory/counselor/inventory-roster.tsx` |
| `/portal/feedback/customer-feedback/responses` | Customer Feedback portion of `features/feedback/feedback-response-lists.tsx` |

The actual Counseling collection route is `/portal/counseling`, with backend
`/counseling/me/encounters`; the existing encounter detail routes remain unchanged.
The request's guessed collection filename/path was adapted to the current code.

`features/institutional-forms/form-revision-filter.tsx` is the shared presentation
control. It submits exact UUIDs, labels safe code/revision combinations, handles null
metadata, and retains an unresolved selected value as "Selected revision" while
metadata is pending or fails. Metadata arriving later cannot reset the user's
selection. It does not display UUIDs as labels or invent historical descriptions.

Search and revision state are URL-backed, compose with existing filters, reset the
page on apply, survive refresh/history, and participate in Clear filters. Search
collections with structured filters use explicit apply. The provider directory keeps
its existing debounced search, cancels pending search navigation when opening a
provider, and links to a real route. The provider route resolves its summary directly
and presents loading/error/recovery states; an unconfirmed summary cannot enable
configuration mutations. Weekly schedule, exception, preview, cleanup, and form
safety behavior are reused.

## Validation

- Focused backend collection, search, provider discovery, queue, and roster tests:
  **30 passed, 225 deselected**. The nine new integration tests cover identity/reference
  matching, mixed tokens, exact/historical revisions, scope, filter composition,
  malformed UUIDs, narrow projections, null revisions, Inventory year/MISSING behavior,
  authorization without configuration access, and excluded collection schemas.
- Relevant OpenAPI contract tests: **29 passed, 2 deselected**. Full contract-module
  inspection found two existing failures, reproduced against unchanged staging:
  `test_organization_person_projection_schema_is_dedicated_and_complete` expects a
  projection without the existing `responsibility_scope` field;
  `test_core_schemas_and_realistic_error_responses_are_typed` assumes a direct
  `DistributionRow.percentage.type` despite its existing nullable `anyOf` schema.
  Neither unrelated expectation nor product behavior was changed.
- Backend Ruff lint and formatting check passed; Django system check reported zero
  issues; migration dry-run reported no changes; OpenAPI `--check` passed.
- Frontend `pnpm lint`, `pnpm typecheck`, **215 tests**, and `pnpm build` passed.
  Five new rendered-control tests cover retained unresolved UUIDs, resolved metadata,
  distinct UUIDs with identical labels, null metadata, and the All revisions option.
- Browser review used the actual local frontend with synthetic read-only API fixtures,
  without institutional form configuration capability. Reviewed all five revision
  controls, receipt/Institutional ID display, composed search URLs, refresh/history,
  metadata failure recovery, provider navigation/refresh/not-found states, and a
  375-pixel mobile viewport. A pending directory-search navigation race discovered
  during review was fixed and rechecked. Browser fixtures do not substitute for the
  database-backed matching and authorization tests.

The entire Django suite was not run. Local validation is distinct from repository
CI. This slice introduces no models, migrations, dependencies, deployment, or merge.

## Intentional exclusions

- Routine Interview Form Revision filtering — not implemented.
- Exit Interview Form Revision filtering — not implemented.
- CSM Form Revision filtering — not implemented.
- Graduate Tracer Form Revision filtering — not implemented.
- Global record search — not implemented.
