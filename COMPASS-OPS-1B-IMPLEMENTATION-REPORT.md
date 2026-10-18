# COMPASS-OPS-1B Implementation Report

**Date:** 2026-10-18
**Base:** `staging` at `4d87a839` (UX-P2A, UX-P2B, and merged UX-P3 included)
**Branch:** `codex/ops-1b-floating-filter-refinement`
**Pull request:** [#279](https://github.com/ils12058/COMPASS/pull/279)
**Merge or deployment:** none; this work is limited to a frontend PR.

## Audit matrix

| Collection or pattern | Audit finding | Decision |
| --- | --- | --- |
| Follow-Ups | Status was the immediate workflow choice, while Due Date, Assignee, and Sort by shared an undifferentiated dialog grid. The Filters count omitted non-default Status, and sorting was not visually separated. | Keep Status as a compact quick filter. Group Due Date under Progress & timing, Assignee under Responsibility, and ordering under Display order. Count non-default Status, Due Date, and Assignee; exclude default Pending and sorting. |
| Assessment Records | Order shared the record-filter grid, counted as an active filter, and sort-only state offered a Clear filters action that reset the ordering. | Separate Display order, count only record filters, and preserve ordering when clearing filters. |
| Managed Appointments | Search and advanced filters use one explicit-apply flow; status has a defined default and ordering is handled separately. | No change; controls already match their workflow and sorting is distinct. |
| Referrals | Search and record filters are applied together; date range validation stays with the filter dialog and sort state is independently retained. | No change; no grouping or clear-state defect warranted a broader redesign. |
| Call Slips and Service Catalog | Collection-specific search/filter and ordering controls are already placed with their respective workflows. | No change. |
| Good Moral operational lists and My Work | These are purpose-built operational or ranked queues; changing them would overlap adjacent work or alter queue presentation without an identified defect. | Inspected and deferred. Good Moral issuance and printing remain out of scope. |
| Shared `FloatingListTools` consumers | A keyboard pass found Tab could leave the native modal after its final control in the tested browser. The existing component already handles modal semantics, Escape, and focus restoration. | Add a bounded Tab/Shift+Tab loop. Keep the existing toolbar, dialog state, and consumer APIs. |
| Availability and UX-P3-owned pages | These files are owned by concurrent work. | Inspected only; not modified. |

## Implementation

- Follow-Ups keeps Status in the floating bar because it is the primary queue workflow. `ListToolField` gives it compact sizing and alignment with Filters; its accessible description explains the default and active state.
- The dialog uses fieldsets for Progress & timing, Responsibility, and Display order. The Due Date hint explains that the backend applies it only to Pending follow-ups.
- The Filters count includes any non-default Status, Due Date, and Assignee. Clear filters restores Pending and clears Due Date and Assignee while preserving the user's sort order and resetting pagination.
- The current Status-change behavior that clears Due Date is preserved. The backend service query applies `due_window` only to Pending records, and browser coverage verifies both the query parameter behavior and independent Assignee/sort preservation.
- Assessment Records now separates sorting from record filtering. Sort-only state has no Clear filters action, and clearing an actual filter retains the selected ordering.
- The shared toolbar gains a Tab/Shift+Tab boundary check for its native dialog. Escape and focus restoration remain part of the existing behavior.

No backend, generated API, query parameter, authorization, lifecycle, or collection access changes were made. `FloatingListTools` remains the shared component.

## Validation

| Check | Result |
| --- | --- |
| Focused Follow-Ups and shared toolbar unit tests | 8 passed |
| Full frontend unit suite | 816 passed, 0 failed |
| Frontend lint | passed (`pnpm lint`) |
| Frontend typecheck | passed (`pnpm typecheck`) |
| Production build | not run at the user's direction to stop the remaining broad checks |
| Follow-Ups browser regression, Chromium | 10/10 passed in the earlier run; final test-only screenshot cleanup and expanded-dock assertion were added afterward and not rerun |
| Assessment Records sort/filter browser regression, Chromium | targeted check passed earlier; final screenshot-only test update was not rerun |
| WebKit browser regressions | not run at the user's direction to stop the remaining checks |

The passing Chromium checks cover default Pending, active filter count, Status/Due Date dependency, Assignee, sort, pagination reset, Clear filters, keyboard focus loop, Escape and focus restoration. The earlier responsive run covered 320, 375, 768, 1024, and 1440 CSS-pixel viewports, toolbar/dialog bounds, touch-target height, no horizontal overflow, and modal focus. A final assertion that the expanded navigation dock narrows the 1024px workspace was added afterward and not rerun. The production build and WebKit browser checks remain unverified.

## Visual evidence

Before evidence uses the base `staging` implementation and synthetic data. After evidence uses the implementation branch and the same synthetic follow-up/assessment fixtures.

| State | Before | After |
| --- | --- | --- |
| Follow-Ups default desktop | [1440px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/followups-default-1440.png) | [1440px](fe/docs/evidence/ops-1b/after/chromium/guidance-followups/followups-default-1440.png) |
| Follow-Ups filters applied | [1440px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/followups-applied-1440.png) | [1440px](fe/docs/evidence/ops-1b/after/chromium/guidance-followups/followups-applied-1440.png) |
| Follow-Ups dialog | [1440px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/followups-applied-dialog-1440.png) | [1440px](fe/docs/evidence/ops-1b/after/chromium/guidance-followups/followups-filter-dialog-1440.png) |
| Follow-Ups mobile toolbar | [375px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/followups-default-375.png) | [375px](fe/docs/evidence/ops-1b/after/chromium/guidance-followups/followups-default-375.png) |
| Follow-Ups narrowed workspace | [1024px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/followups-default-1024.png) | [1024px](fe/docs/evidence/ops-1b/after/chromium/guidance-followups/followups-default-1024.png) |
| Assessment Records filters | [1440px](fe/docs/evidence/ops-1b/before/chromium/ops-1b-baseline/assessment-filters-1440.png) | [Dialog](fe/docs/evidence/ops-1b/after/chromium/assessment-records/assessment-filter-dialog-1440.png), [sort-only state](fe/docs/evidence/ops-1b/after/chromium/assessment-records/assessment-sort-only-1440.png) |

The Follow-Ups browser run also captured the 320px toolbar/dialog and wrote structured results under `fe/docs/evidence/ops-1b/after/`. Captures were taken from the development server, so the development-only Next.js indicator is visible in the images.

## Deferred scope and integration

Other audited collection pages were left intact because their controls already follow their workflow or because a wider change would overlap concurrent work. No Availability, Good Moral issuance/printing, document-rendering, or backend files were changed. The branch is based on `staging` and does not depend on OPS-1A or UX-P3 unmerged changes.

**Pull request:** [#279](https://github.com/ils12058/COMPASS/pull/279)
**Implementation commit SHA:** `bd727f6d0af2de02a50d677104930566b0cc98bc`
