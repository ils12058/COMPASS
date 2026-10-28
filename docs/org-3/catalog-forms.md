# Focused Catalog forms

`catalog-model.ts` contains local draft/intent presentation state; payloads use generated request
interfaces. `catalog-query.ts` dispatches generated operations. `catalog-editor.tsx` owns one local
intent and review/recovery; `catalog-policy-fields.tsx` and `catalog-review.tsx` bound the field and
confirmation responsibilities. No generated output, backend schema, business logic or contract was
hand-edited.

Creation requires an explicit initial active/inactive choice, official code/name and bounded basis.
College/Program intent captures the actual parent UUID when opened. The parent is displayed and
re-read; no parent selector silently changes it. The review shows parent name/code/context. Campus
code is global, College/Program code is parent-qualified; inactive identities still reserve codes.
Code entry is independent from the name. Trim/uppercase normalization mirrors the backend; ordinary
editing has no code or parent inputs. Duplicate code has a field-associated error and retained input.

Name and basis have visible labels, required/max-length constraints and form-level validation for
blank/invalid plain text. Local code validation permits letters/digits/hyphen/underscore, up to 32
characters. Backend strict validation remains final, including concurrent parent and duplicate
conflicts. No caller permission, approval, MFA or impact flags enter requests.

| Intent | Payload and review |
|---|---|
| Create Campus | code/name/is_active/basis |
| Create College | Same plus fixed campus_id |
| Create Program | Same plus fixed college_id and complete classification/status/levels |
| Rename | Only name/basis/expected_resource_version; current name/code/parent/version displayed |
| Status | Only desired is_active/basis/version; deactivation requires fresh impact |
| Program policy | Entire classification/status/levels plus basis/version; current and proposed values displayed |

Rename compares stripped names and refuses a local no-op honestly. Policy and already-changed
status no-ops also produce review feedback rather than a fake saved event. Stale versions still
belong to backend concurrency enforcement. The dialog names the actual target/result and states
current-label versus saved-history semantics; finalized documents are not regenerated.

Program classification uses generated BACHELORS/MASTERS/DOCTORAL enums and an explicit null pending
option. Policy uses CONFIGURED/PENDING_POLICY. There is no Bachelor's or Years 1–4 default.
Configured policy requires known classification and at least one integer level 1–10; individual
labeled checkboxes preserve gaps. Payloads sort/deduplicate the selected set. Pending sends null
levels, never `[]`; temporarily switching status retains prior local choices but sends only the
current complete representation.

A pending/unclassified Program can be created inactive. New active Program creation requires complete
configured policy. Program activation remains server-validated. Existing migrated active unresolved
rows are not automatically deactivated. Changing an active Program to incomplete policy remains the
backend's refusal. A basis records accountability and never claims approval.

`catalog_pending_f4_policy_decision_required` explains that the certificate owner must resolve pending
F4 requests institutionally. There is no force, cancellation, re-preparation or fake approval control.
Existing Inventory, F4 1–4, F6 saved text, Tracer and issued output behavior is untouched.
