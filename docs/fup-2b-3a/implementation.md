> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-2B + FUP-3A implementation record

**Authority:** every behavior and string below is **Provisional — pending GCO/FAC**. This is an
engineering record, not institutional approval. The code-owned provisional providers are not an
approved adapter and do not represent any GCO, UCN, FAC, privacy or records decision.

## 1. Part A — FUP-2B create next follow-up

### 1.1 URL helper

`fe/src/features/guidance-followups/followups-shared.tsx` adds:

```ts
export function nextFollowupHref(item: Pick<FollowUpDetail, "source" | "student_id" | "student_name">) {
  const reference = item.source
    ? `source_kind=${encodeURIComponent(item.source.kind)}&source_id=${encodeURIComponent(item.source.id)}`
    : `student_id=${encodeURIComponent(item.student_id)}&student_name=${encodeURIComponent(item.student_name)}`;
  return `/portal/follow-ups/new?${reference}`;
}
```

The helper is pure and has exactly two outputs:

| Detail state | Link |
|---|---|
| `item.source` is present (the related record is readable to this actor) | `/portal/follow-ups/new?source_kind=<encoded kind>&source_id=<encoded id>` |
| `item.source` is `null` (no source or an unavailable source) | `/portal/follow-ups/new?student_id=<encoded id>&student_name=<encoded name>` |

The query contains no category, visibility, assignee, due date, description, outcome, status,
version, predecessor/successor or confidential value. The source path is omitted entirely when the
source is not readable, so an unavailable related record cannot be inferred from the next-task link.

### 1.2 Completed detail panel

`fe/src/features/guidance-followups/followups-detail.tsx` renders one additional panel after the
main detail panel when, and only when:

```tsx
access.manage && item.status === "COMPLETED"
```

Panel copy:

- Title: `What happens next`
- Body: `Create a new task when more work is needed. It gets its own responsible staff member and due date. It does not reopen this follow-up or change the related record.`
- Action: a secondary navigation link labelled exactly `Create next follow-up`

The link is a `Link`, not a mutation. It creates nothing, writes nothing and does not change the
completed task. The panel is not rendered for view-only accounts, Pending tasks or cancelled tasks.

### 1.3 Existing create page behavior

The target is the existing `/portal/follow-ups/new` page. It already reads `source_kind`,
`source_id`, `student_id` and `student_name`; FUP-2B adds no new parameter or endpoint.

- With a readable source, the create page resolves the source through the existing context query,
  derives the category and visibility from that live record, and locks the category. If the record
  is no longer writable, the existing failure state is shown; no stale classification is copied.
- Without a source, the create page accepts the Student identity, leaves the category selectable
  and starts as an operational task. It never copies `COUNSELOR_CONFIDENTIAL` from the completed
  task.
- The assignee is always chosen by the user. The link does not preselect, hide or lock an assignee.
- The helper carries `student_name` only to label the selected Student; it carries no admission,
  clinical or other confidential data.

### 1.4 Help

`fe/src/features/guidance-followups/followups-help.tsx` adds:

**Heading:** `Creating the next follow-up`

**Content:**

> The next follow-up is a separate task with its own responsible staff member and due date. When
> the related record is still available, the new task is linked to it and takes its classification
> from that record. When the related record is unavailable, the new task is created without a link
> and does not inherit the earlier task's confidential classification.

The rendered apostrophe is the plain ASCII apostrophe; the JSX uses `&apos;` only to satisfy
`react/no-unescaped-entities`.

### 1.5 Tests

`fe/tests/guidance-followups.test.mjs` — `Create next follow-up links only the readable source or
the standalone Student identity`:

- exact source href and exact query-key list for a readable Referral source;
- exact Student href for a `source: null` task and for an unavailable source;
- round-trip encoding of `&`, `/`, `?`, `#` and `..`;
- forbidden keys are absent from every generated URL.

`fe/tests/guidance-followups.browser.mjs` — six checks:

- `A completed follow-up offers one explicit next-task link to its readable source` — panel copy,
  one link, exact href, only `source_kind` and `source_id`, forbidden keys absent;
- `An unavailable related record starts the next task as a standalone follow-up` — exact Student
  href, only `student_id` and `student_name`, no source key;
- `No next-task action is offered for a view-only account`;
- `No next-task action is offered for a Pending follow-up`;
- `No next-task action is offered for a cancelled follow-up`;
- the Help check asserts the new heading and content.

## 2. Part B — FUP-3A provisional Faculty Referral journey

### 2.1 Default-on provider wiring

The existing provider functions remain the only integration point. No setting, environment
variable, database grant, feature-flag package or `*_ENABLED` gate is read.

| Provider | Default return |
|---|---|
| `faculty_policy.get_approved_lookup_policy()` | `provisional_lookup_policy()` |
| `faculty_policy.get_approved_submission_policy()` | `provisional_submission_policy()` |
| `administrative_policy.get_approved_acknowledgment_policy()` | `provisional_acknowledgment_policy()` |
| `administrative_policy.get_approved_closure_policy()` | `provisional_closure_policy()` |
| `administrative_policy.get_approved_tracking_disclosure_policy()` | `provisional_tracking_disclosure_policy()` |
| `administrative_policy.get_approved_faculty_notice_policy()` | **`None` — FAC-D8 remains inactive** |

The notice provider stays `None` because Faculty Referral notices require separate event,
recipient, channel and disclosure approval. No Faculty or Student Referral notice is produced.

### 2.2 Truthful provisional evidence

`be/compass/referrals/provisional_activation.py` defines five fixed, unmistakably synthetic Audit
events:

| Kind | Fixed event ID | Event action |
|---|---|---|
| `STUDENT_CONFIRMATION` | `f3a00001-0000-4000-8000-000000000001` | `REFERRAL_FACULTY_POLICY_RECORDED` |
| `DIGITAL_SUBMISSION` | `f3a00002-0000-4000-8000-000000000002` | `REFERRAL_FACULTY_POLICY_RECORDED` |
| `ACKNOWLEDGMENT` | `f3a00003-0000-4000-8000-000000000003` | administrative `POLICY_RECORDED` |
| `CLOSURE` | `f3a00004-0000-4000-8000-000000000004` | administrative `POLICY_RECORDED` |
| `FACULTY_TRACKING` | `f3a00005-0000-4000-8000-000000000005` | administrative `POLICY_RECORDED` |

Each event is created with `get_or_create(pk=...)` on the first resolution whose live scopes are
all non-empty, using the existing `AuditEvent` action for its family, `actor_type=SYSTEM`,
`outcome=SUCCESS`, and metadata:

```text
decision = PROVISIONAL
provisional = true
authority = CODE_OWNED_PENDING_INSTITUTIONAL_APPROVAL
policy_kind = <kind>
policy_digest = <fixed digest for kind>
policy_version = code_owned_provisional_v1
evidence_reference = CODE_OWNED_PROVISIONAL_NOT_INSTITUTIONAL
contract_evidence_reference = CODE_OWNED_PROVISIONAL_CONTRACT   (administrative kinds only)
```

The code never writes `decision=APPROVED`, never rewrites an existing Audit row, and never claims
an institutional reference. Audit rows are append-only; a later version must use new fixed IDs and
digests rather than editing these rows.

### 2.3 Fixed digests and live scope separation

Each kind has one fixed SHA-256 digest computed over:

- the provisional decision, authority, version and evidence reference;
- the policy kind and its fixed constraints;
- the contract evidence reference for administrative kinds.

The digest deliberately does **not** bind the live Faculty/College/staff sets or the rolling
validity window. Adding or retiring an eligible Faculty account, College or staff member therefore
does not invent a new policy version. The digest test proves five distinct, stable digests and
proves that a live catalog change leaves the digest unchanged and the event row singular.

The live scopes are recomputed on every provider call:

- Faculty policies: all active `FACULTY` users and all active Colleges with an active Campus.
- Administrative policies: all active `COUNSELOR` and `GUIDANCE_SERVICES_STAFF` users and all active
  Colleges with an active Campus.
- Faculty tracking: the Faculty scope, with the `FACULTY` role.

The validity window is rolling: `valid_from = now - 1 day`, `valid_until = now + 1 day`.

If any required live set is empty, no event is created and structural validation fails closed. A
prior success does not make a later empty scope pass: the event row remains (append-only), but the
next resolution is still denied. The focused tests cover both a first-resolution empty scope and an
empty scope after a prior resolution.

### 2.4 Validation split and separation from approved policies

`FacultyPolicyEvidence` and `ApprovedAdministrativePolicy` now expose:

- `_validate_structure(...)` — existing shape, date, scope, role and contract checks;
- `_validate_activation(...)` — event lookup and metadata checks;
- `validate/validate_evidence(...)` — structure followed by activation.

The approved classes keep the original approved activation rule: the event must be
`decision=APPROVED`, carry the approved digest/version/evidence, and have
`occurred_at <= now`. The approved path behavior is unchanged.

The provisional classes override only `digest` and `_validate_activation`:

- the digest returns the fixed provisional digest;
- activation requires the fixed event action, `SUCCESS`, and exact provisional metadata;
- activation does not check event `occurred_at <= now`, because currentness is already enforced by
  the rolling validity window and the event may be created during the first resolution.

Separation is enforced in both directions:

- an `APPROVED` event carrying a provisional digest cannot validate a provisional policy;
- a `PROVISIONAL` event carrying an approved digest cannot validate an approved policy;
- the same two-way check is exercised for an administrative acknowledgment policy.

### 2.5 Engineering defaults

| Kind | Provisional constraints |
|---|---|
| Student confirmation | 300-second ticket age; 10 actor attempts and 30 IP attempts per 300 seconds; exact normalized institutional identifier; display name only; active Faculty and active Student College scope |
| Digital submission | Canonical `UCN-OP-GCO-01F3` revision `1` schema `1`; `UCN_F3_DIGITAL_CAPTURE_V1`; active Faculty with an active managed home; reference/time/Student-name own projection; lookup-policy digest |
| Acknowledgment | `EXPLICIT_RECEIPT_UCN_F3_V1`; eligible Counselor or Guidance Services Staff; current Student College scope |
| Closure | `ADMINISTRATIVE_REVIEW_RETAIN_LINKS_V1`; eligible Counselor or Guidance Services Staff; `obligations_reviewed=true` required by the existing administration service |
| Faculty tracking | `THREE_STAGE_TIMES_V1`; acknowledged submissions only; eligible Faculty and current Student College scope |

These are the existing domain defaults expressed as fixed provisional constraints. The table is a
description of code behavior, not an approved institutional rule.

### 2.6 Canonical journey proof

`be/tests/test_fup3a_faculty_referral_journey.py` uses the real default providers; the only
monkeypatch replaces the Redis-backed confirmation limiter with an in-memory synthetic limiter. No
approved policy is substituted.

The main test proves:

1. Availability reports confirmation, submission and own tracking as available by default.
2. Exact Student confirmation returns only a display name and a confirmation ticket.
3. Faculty submission succeeds as `SUBMITTED`, records the fixed provisional submission event, and
   creates no `ReferralAction` and no `GuidanceFollowUp`.
4. Faculty list and detail responses contain exactly the existing Faculty keys and no Follow-Up,
   assignee, due date, activity, outcome or Counseling field.
5. GCO acknowledgment succeeds as `RECEIVED_BY_GCO`, records the fixed provisional acknowledgment
   event, and updates the Faculty projection.
6. A Counselor creates two operational `REFERRAL_ACTION` Follow-Ups through the existing create
   path, explicitly assigned to a Guidance Services Staff member; the assigned user can read them
   and sees both in the list.
7. Faculty responses remain clean after Follow-Up creation.
8. Administrative closure with `obligations_reviewed=true` succeeds as
   `ADMINISTRATIVELY_CLOSED`; both linked Follow-Ups remain `PENDING`; completing one Follow-Up
   leaves the Referral state, timestamps, administrative fields and Referral-targeted Audit events
   untouched.
9. Voiding the Referral leaves the second Follow-Up `PENDING`, keeps its assignee and version, and
   leaves the row count unchanged. The assigned user still reads it; detail returns `source: null`,
   `source_unavailable: true`; it remains in the assigned user's list; no cancel, complete or
   relink occurs.
10. Faculty can no longer read the voided Referral; no `ReferralAction` exists; submission,
    acknowledgment, closure, completion and voiding produce no Referral notification and no email.
    The only notifications are the existing Follow-Up assignment notices described in §2.8.

### 2.7 No new surface

No model, migration, service authorization, endpoint, OpenAPI operation, generated model, seed,
package dependency or notification producer was added. The journey uses the existing Faculty and
administrative services. The Referral-linked Follow-Up is created through the existing Follow-Up
create path. No source-driven action runs in either direction.

### 2.8 Notification nuance

The journey test observes two `Notification` rows after the two Follow-Ups are created. They are
the existing in-app `FOLLOWUP_ASSIGNED` notices produced by the Follow-Up domain for the assigned
staff member (`event_committed_intent` in `guidance_followups/integration.py`). They are not
Referral notices and are not created by FUP-3A.

The test therefore asserts the truthful scoped property:

- submission, acknowledgment, closure, completion and voiding add no notification;
- no notification has `target_type="REFERRAL"`;
- no notification has a Referral-related `source_type`;
- every notification goes to the existing Follow-Up assignee, never to Faculty;
- `EmailDelivery` remains at zero.

This is a deviation from the brief's literal "no Notification from any step" expectation: the
existing Follow-Up assignment behavior is not suppressed, because doing so would change unrelated
domain behavior. It is disclosed in [`validation.md`](validation.md) §4.3.

## 3. Explicit exclusions

No change was made to `contracts/openapi.json`, `fe/src/lib/api/generated/**`, Follow-Up or Referral
models, migrations, seeds, package files, notification policy/catalog/delivery, Faculty notice
policy, source-driven automation, capability grants or role definitions. FUP-1D, FUP-2C, FUP-3B,
FUP-3C and FUP-4 were not implemented.
