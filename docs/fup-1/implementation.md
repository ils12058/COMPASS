> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-1 implementation record

**Base:** `integration/ux15-modernization` at
`4614b228482336c100ec5363871c4303e013cedd`.
**Scope:** FUP-1A and FUP-1B only.
**Authority:** D-FUP-01 Option A and the D-FUP-07 copy are **Provisional — pending GCO**.

## 1. FUP-1A — characterization tests

File: `be/tests/test_guidance_followups.py`.

Six test functions were added after `test_referral_source_keeps_operational_scope`. They use the
existing `world`, `settings`, `client`, `context`, `create`, `create_for` and `setup_scope` fixtures
and helpers. No new factory, seed, test database or production change was introduced.

| Test (line) | Assertions |
|---|---|
| `test_referral_void_preserves_operational_task_across_workspaces` (278) | After a real `void_referral`: no Follow-Up event or `guidance_followup.*` audit is written; both linked operational tasks remain in the assignee's list, report count, My Work and `pending_followups`; HTTP detail returns `source: null`, `source_unavailable: true`, `status: PENDING`; `update`, `record_activity`, `reassign`, `complete` and `cancel` all succeed |
| `test_referral_void_makes_source_filter_and_context_unavailable` (380) | The source-filtered list and `guidanceFollowupsGetContext` both return 404 `followup_not_found`; the response body contains no Student name, Referral reference code, source reason, referrer name or Follow-Up UUID |
| `test_confidential_source_loss_orphans_task_without_recovery` (426) | After the Encounter's Counselor changes: detail and all five mutations raise `FollowUpNotFound`; list, report, My Work and pending projection omit the task; Counselor and Head Guidance recovery both exclude it; the row remains `PENDING` |
| `test_head_operational_list_remains_assignment_scoped` (507) | Head Guidance's ordinary list and report contain only the Head's own assigned task; a GSS task and another Counselor's confidential task do not appear; after the GSS owner is deactivated, Head recovery includes the operational GSS task and excludes the confidential task |
| `test_completion_does_not_change_referral_state` (543) | Completing a Referral-linked task leaves the Referral row, its actions and all `referrals.*` audit counts unchanged; the Follow-Up's COMPLETED event and `guidance_followup.completed` audit are the only changes |
| `test_source_loss_does_not_create_material_notification` (584) | A Referral void leaves material-event count, current-event count and the existing in-app notification count unchanged; `followup_notification_is_current` remains true |

Result: `39 passed` for the file. The six new functions account for six of the 39 collected cases; the
other 33 were already present. All passed without editing production code, so no audit divergence was
found.

## 2. FUP-1B — detail, context and help copy

### 2.1 Detail source panel

File: `fe/src/features/guidance-followups/followups-detail.tsx:108`.

The existing three branches are retained (readable source, `source_unavailable`, never linked). Only
the `source_unavailable` paragraph changed, to:

> The related record is no longer available to your account. This follow-up remains open and keeps its
> own status. Review whether the work is still needed. Completing or cancelling it records your reason
> but does not change the related record.

No button, checkbox, status change or new action was added. The existing edit, reschedule, reassign,
activity, complete and cancel actions remain the only actions.

### 2.2 Source-page context panel

File: `fe/src/features/guidance-followups/followups-context.tsx:21-22`.

Pending remains `null`. The error branch now renders one compact `PanelMessage`:

> Linked follow-ups are not available for this record.

The error branch renders no count, no task link, no source title and no create link. The list query was
already disabled unless the context read succeeds, so no second source-existence probe is made.

### 2.3 Help

File: `fe/src/features/guidance-followups/followups-help.tsx:11`.

New section heading:

> When a related record becomes unavailable

Section content:

> The follow-up keeps its own status and remains independently owned. Only the link to the related
> record becomes unavailable. Completing or cancelling the follow-up records your decision and does
> not change the related record.

### 2.4 Shared copy decision

No shared copy helper was added. The three strings serve different surfaces (detail sentence, compact
panel message, help paragraph), and list/report do not render source-unavailable copy. Adding a shared
constant would create an abstraction with one consumer per distinct string. `followups-shared.tsx` and
`fe/tests/guidance-followups.test.mjs` were not changed.

## 3. Browser regression extension

File: `fe/tests/guidance-followups.browser.mjs`.

The synthetic `world()` fixture now accepts `sourceUnavailable`:

- when true, the task has `source: null` and `source_unavailable: true`;
- the context endpoint replies 404 `followup_not_found`;
- the fixture answers the Counseling Encounter detail read used by the source page.

New checks:

1. **An unavailable related record is explained without a broken link and the task stays actionable**
   (`/portal/follow-ups/{id}`): the full detail copy is visible; no "Open related record" link exists;
   "Record activity" is enabled and opens its form; no write occurred.
2. **An unavailable linked source shows a generic context message without count, task link or create
   link** (`/portal/counseling/encounters/{id}`): the generic message is visible inside exactly one
   panel; that panel has no heading, link, button or standalone count; no "Linked follow-ups" heading
   or create link is rendered.

The existing Help check now also asserts the new heading and paragraph.

## 4. Explicit exclusions

Not implemented:

- FUP-1C list/report source indicator;
- FUP-1D review gate or review persistence;
- FUP-2 further action after completion;
- any FUP-3 slice;
- backend model, service, policy, API, migration, notification or recovery change;
- OpenAPI contract, generated client, Orval or seed change;
- authorization, capability, role, scope or copy approval change.

## 5. Rollback

The frontend change is copy-only and is reverted by reverting the three frontend files and the browser
test extension. The six backend tests are additive and can be removed without production impact. No
migration reversal, data rollback, cache invalidation or contract regeneration is required.
