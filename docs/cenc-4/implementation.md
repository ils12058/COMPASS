# CENC-4 implementation

Everything below is engineering-provisional. No GCO, institutional, privacy, security, clinical or UAT
approval is claimed. Copy is final for this slice and is the first thing CENC-5 UAT may revise.

## 1. One identity rule, two readers

`be/compass/counseling/services.py` previously expressed the identity rule twice in spirit: once in
`appointment_encounter_matches` (Detail + Counseling Workspace) and once inside the worklist design.
There is now exactly one definition:

```python
def _encounter_identity_q(
    *,
    appointment_id: UUID | OuterRef,
    student_id: UUID | OuterRef,
    counselor_id: UUID | OuterRef,
    service_id: UUID | OuterRef,
    delivery_mode: str | OuterRef,
) -> Q:
    return Q(
        appointment_id=appointment_id,
        student_id=student_id,
        counselor_id=counselor_id,
        service_id=service_id,
        delivery_mode=delivery_mode,
        entry_mode=CounselingEntryMode.APPOINTMENT,
    )
```

`appointment_encounter_matches` keeps its signature, docstring and behavior (`services.py:239`), now
built on the helper. The worklist passes `OuterRef(...)` values into the same helper, so
the projection and the list can never drift apart. Times are still **not** compared (D-CENC-25).

The strict write-side check in `be/compass/counseling/finish_service.py:75-93` is unchanged. It stays
a literal, field-by-field comparison inside the transaction; the shared `Q` is a read-side tool.

The exposure rule was extracted the same way — `_encounter_fact_exposed(actor=, appointment=, at=)`
holds the previous conditions verbatim (canonical COUNSELING service code, active actor,
`role.code == "COUNSELOR"`, `appointment.provider_id == actor.pk`, and `counseling.view_assigned` at
`at or timezone.now()`), and both readers call it:

| Reader | Question | `None` when |
|---|---|---|
| `appointment_encounter_recorded` | does a **matching** Encounter exist? (unchanged) | the fact is not exposed to this actor |
| `appointment_encounter_linked` (new) | does **any** Encounter link to this Appointment (`appointment_id=appointment.pk`), matching or not? | the fact is not exposed to this actor |

`be/compass/appointments/api.py` adds `counseling_encounter_linked: bool | None` to
`AppointmentDetailResponse` immediately after `counseling_encounter_recorded` and serializes it in
`appointments_get` with the same actor and Appointment. It is **not** added to `AppointmentResponse`,
so no list payload grows, and `counseling_encounter_recorded` is byte-for-byte unchanged.

## 2. The worklist

`list_documentation_review(*, counselor, page=1, page_size=DEFAULT_PAGE_SIZE, now=None)` →
`CounselingDocumentationReviewPage` of `CounselingDocumentationReviewItem(appointment, reason,
encounter_id)`.

Scope, in order:

1. `_validate_active_counselor(counselor)` then `_validate_page(page, page_size)` (`page_size ≤ 50`).
2. `service = get_counseling_service(require_active=False)` — the canonical row, resolved without
   requiring it to be active, because historical Appointments must stay reviewable after
   deactivation.
3. `Appointment.objects.select_related("student", "student__role", "service").filter(provider_id=
   counselor.pk, student__is_active=True, student__role__code="STUDENT", service_id=service.pk,
   status__in=(SCHEDULED, COMPLETED))`.

Two `Exists` annotations answer the same question the readers answer:

- `_has_linked` — `CounselingEncounter.objects.filter(appointment_id=OuterRef("pk"))`
- `_has_matching` — the same `_encounter_identity_q` with `OuterRef("student_id")`,
  `OuterRef("provider_id")`, `OuterRef("service_id")`, `OuterRef("delivery_mode")`

### 2.1 The three reasons and their precedence

`_documentation_review_reason(row)` decides per row, and the arms are mutually exclusive by
construction:

| Order | Condition | Reason | Plain meaning |
|---|---|---|---|
| 1 | `_has_linked and not _has_matching` | `LINKED_CONFLICT` | a link exists but fails the identity rule; needs administrative review |
| 2 | otherwise `status == SCHEDULED` | `UNCOMPLETED_APPOINTMENT` | a matching Encounter is already recorded; the Appointment still needs **Complete** |
| 3 | otherwise | `MISSING_ENCOUNTER` | COMPLETED with no link at all; a record may be missing |

The filter mirrors that precedence with exactly one arm per row:

```python
.filter(
    Q(status=AppointmentStatus.COMPLETED, _has_linked=False)                    # MISSING_ENCOUNTER
    | (Q(status=AppointmentStatus.SCHEDULED, _has_matching=True) & ended)       # UNCOMPLETED_APPOINTMENT
    | Q(_has_linked=True, _has_matching=False, starts_at__lte=current)          # LINKED_CONFLICT
)
```

Excluded, and why: CANCELLED / NO_SHOW (D-CENC-09 legacy correction is out of scope), non-COUNSELING
services, other providers' Appointments (D-CENC-14), inactive Students (consistent with
`list_appointment_candidates`), SCHEDULED with no matching Encounter (nothing is documented yet and
the session may not have happened), COMPLETED **with** a matching Encounter (already reconciled),
COMPLETED with a link that matches nothing but has not started (`starts_at__lte` guard on the
conflict arm), and time-only differences (D-CENC-25).

`encounter_id` comes from a correlated `Subquery` filtered on `appointment_id=OuterRef("pk")` **and**
`counselor_id=counselor.pk`, limited to one row, because Encounter reads are assigned-only
(`get_encounter_for_actor`). A conflict whose Encounter belongs to another Counselor is still
reported; its identifier is not.

### 2.2 The online boundary

`ended` gates only the `UNCOMPLETED_APPOINTMENT` arm:

```python
ended = Q(delivery_mode=DeliveryMode.ONLINE, ends_at__lt=current - grace) | (
    ~Q(delivery_mode=DeliveryMode.ONLINE) & Q(ends_at__lte=current)
)
```

with `grace = timedelta(seconds=settings.ECOUNSELING_REJOIN_GRACE_SECONDS)` (default `900`).
`be/compass/ecounseling/services.py:198-228` computes
`available_until = ends_at + grace` and reports the window OPEN while `current <= available_until`,
and CENC-1 refuses to finish while it is OPEN. A row that says "complete this" must not appear during
that window, so ONLINE requires the strict `ends_at__lt=current - grace`; the prompt's
`ends_at__lte=current - grace` would surface exactly one instant (`current == ends_at + grace`) in
which the access period is still OPEN and Complete is still refused. Both required data points still
hold: at `grace − 1s` the row is absent, at `grace + 1s` it is present. IN_PERSON and other modes are
gated only by their own end, inclusive of the exact ending instant. `be/tests/test_counseling_documentation_review.py::test_worklist_waits_for_the_online_access_window_to_close`
pins both.

### 2.3 Ordering and paging

`.order_by("ends_at", "id")` — oldest session first, deterministic tie-break — and the canonical
offset slice used everywhere else in this module: `rows = list(queryset[offset:offset + page_size +
1])`, `has_next = len(rows) > page_size`, `items = tuple(rows[:page_size])`. The page cursor is
`("ends_at", "id")`, which is stable for a derived list because both columns are immutable here.

Nothing is persisted, no lock is taken, and no `select_for_update` appears: the read-only proof test
snapshots `CounselingEncounter`, `RoutineInterview`, `FeedbackOpportunity`, `Notification` and
`AuditEvent` around a complete page read and asserts equality.

## 3. Endpoint and schemas

```
GET /api/v1/counseling/documentation-review
operationId  counselingListDocumentationReview
auth         session_auth
gate         _require_counselor(request, "counseling.view_assigned")
params       page: int = 1, page_size: int = DEFAULT_PAGE_SIZE (20; max 50)
responses    200 CounselingDocumentationReviewPageResponse
             401, 403, 409 (CounselingError → _raise), 422 (invalid page / page_size)
```

`CounselingDocumentationReviewPageResponse` = `{items, page, page_size, has_next}`.
Each item is exactly nine keys: `appointment_id`, `reference_code`, `student`
(reusing `CounselingStudentResponse`: `id`, `display_name`, `institutional_id`, `profile_photo_url`,
`profile_photo_updated_at`), `delivery_mode`, `starts_at`, `ends_at`, `status`, `reason`,
`encounter_id` (`UUID | null`). `reason` is the three-value enum
`CounselingDocumentationReviewReason`.

`starts_at` / `ends_at` pass through `_institutional`, matching every other Appointment datetime that
crosses the boundary in `appointments/api.py` and `_appointment_candidate`.

The API-side `CounselingDocumentationReviewReason` mirrors the service enum in `StrEnum` form, the
same way `api.py` already mirrors `CounselingEntryMode`; the schemas stay `StrictSchema`, so no
unknown key can appear. There is no new error class, no new capability, and no write.

## 4. Frontend

### 4.1 `fe/src/features/counseling/documentation-review.ts` (pure)

`documentationReviewReasonCopy` (typed `Record<CounselingDocumentationReviewReason, {label,
message}>`, keyed off the **generated** enum), `counselingMismatchNotice`,
`counselingReconciliationNotice`, `completeConfirmationDescription({reconciliation})`,
`reviewPageFromParam` (non-positive, non-integer and unsafe values collapse to `1`), `reviewHref`
(sets `review_page` when `page > 1`, deletes it at page 1, preserves every other parameter),
`appointmentDetailHref`, `encounterDetailHref`. `LINKED_CONFLICT`'s message **is**
`counselingMismatchNotice` — one string, two surfaces.

### 4.2 `documentation-review-panel.tsx`

`"use client"`, props `{ access: CounselingAccess }`, returns `null` unless `access.canViewAssigned`.
Query: `useCounselingListDocumentationReview({ page, page_size: 5 }, { query: { enabled:
access.canViewAssigned, retry: false, staleTime: 0 } })` — `staleTime: 0` is deliberate so that
reconciling elsewhere changes what the Counselor sees when they return. Five rows keeps the list
beside the encounters it points at.

| State | Rendered |
|---|---|
| `isPending` | `Panel` + `PanelHeader` + `CounselingListSkeleton label="Loading appointments that need documentation…" framed={false}` |
| `isError` with no data | `PanelMessage role="alert" tone="danger"` with `counselingErrorMessage(error, "Needs documentation could not be loaded.")` + `Retry` |
| page 1 with zero items | `null` — an empty worklist is not news |
| `review_page > 1` with zero items | the stranded-page message + `Back to the first page` link (`reviewHref(..., 1)`) |
| data + `isError` | the rows, with `RefreshFailureNotice` above them |
| data | rows + `CanonicalPagination label="Needs documentation pages"`, `onPageChange → router.push(reviewHref(...), { scroll: false })` |

Each row: `PersonAvatar` + `display_name` + `institutional_id` when present, `reference_code · start –
end` via `formatCounselingDateTime`, the semibold reason label and its message, `Review appointment`
only when `getAppointmentAccess(user).canManage` (exactly the `appointments.manage` check), and
`View encounter` only when `encounter_id` is non-null. The header context is
`describeResultPage({count, page, hasNext, noun: {one: "appointment", other: "appointments"}})`.

**No authoring control appears in the panel** — no Finish, no Complete, no Record, no Follow-Up. It
points at the surfaces that own those writes.

### 4.3 Mount and URL state

`counselor-encounters.tsx` renders `{recordOpen ? null : <DocumentationReviewPanel access={access} />}`
immediately after the `RecordEncounterForm` line and above the encounters section, and keeps the
review page across filter submits with
`{reviewPage > 1 ? <input type="hidden" name="review_page" value={reviewPage} /> : null}` beside the
existing hidden `ordering`. `updateQuery` and `clearedHref` are unchanged: the encounters pager
already preserves unknown parameters, and clearing filters resets both lists' pages.

### 4.4 Finish suppression and Detail truthfulness

`finish-counseling-availability.ts` adds `"counseling_encounter_linked"` to its input `Pick` and,
after the recorded check, returns `UNAVAILABLE` when `appointment.counseling_encounter_linked ===
true`. Strict `=== true` matters: an unexposed (`null`) or absent (`undefined`) fact must never
suppress a legitimate offer.

`appointment-detail-page.tsx` derives two booleans — `encounterRecorded` (`recorded === true`) and
`encounterMismatch` (`linked === true && recorded === false`) — and uses them in four places:

1. the fact value: `Recorded` / `Linked, needs review` / `Not recorded`;
2. the existing COMPLETED "no Counseling Encounter is recorded" warning now additionally requires
   `!encounterMismatch`, so the two never contradict each other;
3. a `tone="warning"` mismatch notice for COMPLETED + `encounterMismatch`, and a `tone="info"`
   reconciliation notice for SCHEDULED + recorded + `canComplete`;
4. `ActionConfirmation` gained a required `reconciliation: boolean` prop (passed as
   `counseling && encounterRecorded`) so the Complete confirmation states that the already recorded
   Encounter will be kept and no second one created. Every other case keeps the existing description
   unchanged.

## 5. Copy inventory (verbatim)

Strings from the slice's inventory, all with typographic apostrophes:

| Where | String |
|---|---|
| Panel title | `Needs documentation` |
| Panel description | `Appointments of yours that may need a record or reconciliation. This list is derived from current records and doesn’t confirm that Counseling took place.` |
| Loading | `Loading appointments that need documentation…` |
| Error fallback | `Needs documentation could not be loaded.` (wrapped by `counselingErrorMessage`) |
| Empty page > 1 | `No appointments on this page need documentation.` + link `Back to the first page` |
| `MISSING_ENCOUNTER` label | `Completed without an Encounter` |
| `MISSING_ENCOUNTER` message | `This Appointment is marked completed, but no Counseling Encounter is recorded. Attendance isn’t assumed; record an Encounter only if Counseling took place.` |
| `UNCOMPLETED_APPOINTMENT` label | `Encounter recorded, Appointment not completed` |
| `UNCOMPLETED_APPOINTMENT` message | `The Counseling Encounter is already recorded. Completing the Appointment won’t create another Encounter.` |
| `LINKED_CONFLICT` label | `Encounter link needs review` |
| `LINKED_CONFLICT` message / `counselingMismatchNotice` | `A Counseling Encounter is linked to this Appointment but doesn’t match its Counseling details. This needs administrative review and can’t be corrected here.` |
| Row links | `Review appointment`, `View encounter` |
| Pagination label | `Needs documentation pages` |
| Detail fact value | `Linked, needs review` |
| Detail reconciliation notice | `This Counseling Encounter is already recorded. Complete the Appointment to reconcile it; this won’t create another Encounter.` |
| Complete confirmation (reconciliation) | `This Appointment will be marked completed. The Counseling Encounter already recorded for it will be kept; no second Encounter will be created.` |

One string is not in the slice inventory because it is the reused component's own wording, supplied by
the panel for the stale-refresh case: `The latest Needs documentation results could not be loaded.
Showing the last confirmed results.` (`RefreshFailureNotice`).

## 6. Plan-to-code reconciliations

1. **ONLINE `ended` uses `<`, not `<=`** — see §2.2. The two data points the prompt requires still
   pass; the strict form is what §2.5 ("the worklist must not surface a ready-to-complete row during
   the open window") actually means.
2. **`select_related` gained `student__role`** — the base filter reads `student__role__code`, so the
   join is prefetched instead of re-queried per row. Superset of the prompt's list; no behavior change.
3. **The reason enum is mirrored in `api.py`** as the module already mirrors `CounselingEntryMode`, so
   the schema is generated from a declared enum rather than a hand-written list.
4. **`Review appointment` gating uses `getAppointmentAccess(user).canManage`** rather than a literal
   `user.capabilities.includes("appointments.manage")`; that accessor *is* that check
   (`appointments-access.ts:20`), so the shared helper is used instead of duplicating it.
5. **The panel's `page_size` is 5** (prompt §4.7) while the endpoint default stays
   `DEFAULT_PAGE_SIZE = 20`; an API client that omits the parameter still gets the module's standard
   page size.
6. **`starts_at`/`ends_at` are institution-normalized** (§3), consistent with the existing Appointment
   projections; the prompt did not specify and an un-normalized value would have been the only odd one
   out.
